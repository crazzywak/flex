import flet as ft
import pandas as pd
import os
import re
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
data_path = os.path.join(BASE_DIR, "data.xlsx")
profiles_path = os.path.join(BASE_DIR, "job profiles.xlsx")

def main(page: ft.Page):
    page.title = "Role Finder - מערכת איתור תפקידים"
    page.rtl = True
    page.padding = 30
    page.scroll = ft.ScrollMode.ADAPTIVE
    page.window.maximized = True

    # 1. טעינת נתונים
    try:
        df_data = pd.read_excel(data_path)
        df_profiles = pd.read_excel(profiles_path)
    except Exception as e:
        page.add(ft.Text(f"שגיאה בטעינת הקבצים: {e}", color="red", size=20))
        return

    df_data.columns = df_data.columns.str.strip()
    df_profiles.columns = df_profiles.columns.str.strip()
    df_data.rename(columns={'אגף (מחלקה)': 'מחלקה'}, inplace=True)

    col_names = list(df_profiles.columns)
    col_names[0] = 'מחלקה'
    col_names[1] = 'תפקיד'
    df_profiles.columns = col_names
    df_profiles['מחלקה'] = df_profiles['מחלקה'].ffill()

    df_data['מחלקה'] = df_data['מחלקה'].astype(str).str.strip()
    df_data['תפקיד'] = df_data['תפקיד'].astype(str).str.strip()
    df_profiles['מחלקה'] = df_profiles['מחלקה'].astype(str).str.strip()
    df_profiles['תפקיד'] = df_profiles['תפקיד'].astype(str).str.strip()

    df_data['שכר'] = pd.to_numeric(df_data['שכר'], errors='coerce')

    # זיהוי עמודת תחילת עבודה ב-df_data
    start_work_col = next((col for col in df_data.columns if 'תחילת' in col), None)

    # פונקציה לחישוב טווחי שכר על סמך df_data מסונן
    def compute_salary_ranges(df_source):
        min_salaries = []
        max_salaries = []
        for _, row in df_profiles.iterrows():
            dept = str(row['מחלקה']).strip()
            role_raw = str(row['תפקיד']).strip()
            dept_match = df_source['מחלקה'] == dept

            role_parts = [p.strip() for p in role_raw.split(',') if p.strip()]
            combined_role_match = pd.Series([False] * len(df_source), index=df_source.index)
            for part in role_parts:
                try:
                    part_match = df_source['תפקיד'].str.contains(part, regex=True, flags=re.IGNORECASE, na=False)
                except re.error:
                    part_match = df_source['תפקיד'].str.contains(part, regex=False, na=False)
                combined_role_match = combined_role_match | part_match

            matching_rows = df_source[dept_match & combined_role_match]
            if not matching_rows.empty:
                min_salaries.append(matching_rows['שכר'].min())
                max_salaries.append(matching_rows['שכר'].max())
            else:
                min_salaries.append(float('nan'))
                max_salaries.append(float('nan'))

        result = df_profiles.copy()
        result['שכר_מינימום'] = min_salaries
        result['שכר_מקסימום'] = max_salaries
        return result

    # 2. יצירת מסננים
    min_sal_val = df_data['שכר'].min()
    max_sal_val = df_data['שכר'].max()
    min_salary = float(min_sal_val) if pd.notna(min_sal_val) else 30.0
    max_salary = float(max_sal_val) if pd.notna(max_sal_val) else 100.0
    if max_salary <= min_salary:
        max_salary = min_salary + 10.0

    salary_field = ft.TextField(
        label="ציפיות שכר (₪ לשעה)",
        value=str(int(min_salary)),
        keyboard_type=ft.KeyboardType.NUMBER,
        text_align=ft.TextAlign.RIGHT,
    )
    age_field = ft.TextField(
        label="גיל מועמד",
        value="25",
        keyboard_type=ft.KeyboardType.NUMBER,
        text_align=ft.TextAlign.RIGHT,
    )

    age_col = next((col for col in df_profiles.columns if 'גיל' in col), None)

    dynamic_cols = [
        c for c in df_profiles.columns[2:]
        if c != age_col
        and c not in ['שכר_מינימום', 'שכר_מקסימום']
    ]

    filters_dict = {}

    def make_control(col):
        unique_vals = set(df_profiles[col].dropna().astype(str).str.strip())
        unique_vals = {v for v in unique_vals if v != ''}
        if unique_vals.issubset({'כן', 'לא'}):
            cb = ft.Checkbox(label=col, value=False)
            filters_dict[col] = {'type': 'checkbox', 'control': cb}
            return ft.Container(content=cb, expand=True)
        else:
            options = [ft.DropdownOption(key="הכל", text="הכל")] + [
                ft.DropdownOption(key=v, text=v) for v in sorted(list(unique_vals))
            ]
            dd = ft.Dropdown(label=col, options=options, value="הכל", expand=True)
            filters_dict[col] = {'type': 'dropdown', 'control': dd}
            return dd
 
    # פילטר תחילת עבודה
    start_work_options = [
        ft.DropdownOption(key="הכל", text="הכל"),
        ft.DropdownOption(key="חצי שנה", text="חצי שנה"),
    ]
    start_work_dd = ft.Dropdown(
        label="תחילת עבודה",
        options=start_work_options,
        value="הכל"
    )

    # שיוך עמודות לקטגוריות לפי מילות מפתח בשם
    PERSONAL_KEYWORDS   = ['גיל', 'מין', 'רישיון', 'גר/ה רחוק']
    HOURS_KEYWORDS      = ['שעות', 'משמרת', 'משרה', 'היקף', 'אופי', 'נסיעות', 'נסיעה', 'שטח', 'עבודה מהבית', 'היברידי', 'גמיש']
    EXPERIENCE_KEYWORDS = ['ניסיון']
    SKILLS_KEYWORDS     = ['עברית', 'אנגלית', 'רוסית', 'מחשב', 'תוכנה', 'הסמכה', 'תעודה', 'השכלה', 'לימודים', 'מקצוע', 'כלי', 'טכנולוג']

    def categorize(col):
        for kw in PERSONAL_KEYWORDS:
            if kw in col:
                return 'פרטים אישיים'
        for kw in HOURS_KEYWORDS:
            if kw in col:
                return 'שעות/אופי עבודה'
        for kw in EXPERIENCE_KEYWORDS:
            if kw in col:
                return 'ניסיון'
        for kw in SKILLS_KEYWORDS:
            if kw in col or kw in col.lower():
                return 'כישורים'

        return 'טוב לדעת'

    categories = {
        'פרטים אישיים': [],
        'שעות/אופי עבודה': [],
        'ניסיון': [],
        'כישורים': [],
        'טוב לדעת': [],
    }

    # גיל שייך לפרטים אישיים
    if age_col:
        categories['פרטים אישיים'].append(make_control(age_col))

    for col in dynamic_cols:
        categories[categorize(col)].append(make_control(col))

    def build_category_section(title, controls):
        if not controls:
            return None
        return ft.Container(
            content=ft.Column([
                ft.Text(title, weight="bold", size=14, color=ft.Colors.BLUE_800),
                ft.Column(controls, width=200, spacing=10),
            ], spacing=8),
            padding=ft.Padding(12, 10, 12, 10),
            bgcolor=ft.Colors.WHITE,
            border_radius=8,
            border=ft.Border.all(1, ft.Colors.BLUE_100),
        )

    category_sections = [
        build_category_section(title, controls)
        for title, controls in categories.items()
        if controls
    ]

    filters_panel = ft.Container(
        content=ft.Row(
            [s for s in category_sections if s],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.START,
            wrap=True,
            run_spacing=12,
        ),
        padding=15,
        bgcolor=ft.Colors.GREY_50,
        border_radius=10,
        border=ft.Border.all(1, ft.Colors.GREY_300),
    )

    result_table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("מחלקה", weight="bold")),
            ft.DataColumn(ft.Text("תפקיד", weight="bold")),
            ft.DataColumn(ft.Text("טווח שכר", weight="bold")),
        ],
        rows=[]
    )
    results_title = ft.Text("תוצאות (תפקידים מתאימים):", weight="bold", size=18)

    # 3. פונקציית חיפוש – רק בלחיצת כפתור
    def update_table(e=None):
        try:
            expected_salary = float(salary_field.value.strip())
        except (ValueError, AttributeError):
            expected_salary = min_salary

        try:
            selected_age = int(age_field.value.strip())
        except (ValueError, AttributeError):
            selected_age = 25

        # סינון df_data לפי תחילת עבודה לפני חישוב טווחי שכר
        df_source = df_data.copy()

        if start_work_dd.value == "חצי שנה":
            if start_work_col:
                cutoff_date = datetime.today() - timedelta(days=183)

                def is_within_half_year(val):
                    if pd.isna(val):
                        return True
                    try:
                        if isinstance(val, datetime):
                            result = val >= cutoff_date
                            return result
                        parsed = pd.to_datetime(str(val).strip(), dayfirst=True, errors='coerce')
                        if pd.isna(parsed):
                            return True
                        result = parsed >= cutoff_date
                        return result
                    except Exception as ex:
                        return True

                before = len(df_source)
                df_source = df_source[df_source[start_work_col].apply(is_within_half_year)]

        # חישוב טווחי שכר על בסיס df_data המסונן
        df_merged = compute_salary_ranges(df_source)

        # סינון לפי שכר
        filtered_df = df_merged[
            (df_merged['שכר_מקסימום'].isna()) |
            (df_merged['שכר_מקסימום'] >= expected_salary)
        ]

        # סינון לפי גיל
        if age_col:
            def is_age_in_range(age_str):
                if pd.isna(age_str): return True
                try:
                    parts = str(age_str).split('-')
                    if len(parts) == 2:
                        return int(parts[0].strip()) <= selected_age <= int(parts[1].strip())
                except:
                    pass
                return True
            filtered_df = filtered_df[filtered_df[age_col].apply(is_age_in_range)]

        # סינון פילטרים דינמיים
        for col, filter_data in filters_dict.items():
            ctrl = filter_data['control']
            if filter_data['type'] == 'checkbox':
                if ctrl.value:
                    filtered_df = filtered_df[filtered_df[col].astype(str).str.strip() == 'כן']
            elif filter_data['type'] == 'dropdown':
                if ctrl.value != "הכל":
                    filtered_df = filtered_df[filtered_df[col].astype(str).str.strip() == ctrl.value]

        filtered_df = filtered_df.drop_duplicates(subset=['מחלקה', 'תפקיד'])
        results_title.value = f"תוצאות (תפקידים מתאימים): {len(filtered_df)}"

        rows = []
        for _, row in filtered_df.iterrows():
            min_s = f"{int(row['שכר_מינימום'])}" if not pd.isna(row['שכר_מינימום']) else "לא ידוע"
            max_s = f"{int(row['שכר_מקסימום'])}" if not pd.isna(row['שכר_מקסימום']) else "לא ידוע"
            if min_s == "לא ידוע":
                salary_str = "לא ידוע"
            elif min_s != max_s:
                salary_str = f"{min_s} ₪ - {max_s} ₪ לשעה"
            else:
                salary_str = f"{min_s} ₪ לשעה"

            rows.append(
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text(str(row['מחלקה']))),
                    ft.DataCell(ft.Text(str(row['תפקיד']))),
                    ft.DataCell(ft.Text(salary_str)),
                ])
            )

        result_table.rows = rows
        page.update()

    # כפתור חיפוש
    search_button = ft.Button(
        content=ft.Row([ft.Icon(ft.Icons.SEARCH, color=ft.Colors.WHITE), ft.Text("חפש", color=ft.Colors.WHITE)], tight=True),
        on_click=update_table,
        style=ft.ButtonStyle(
            bgcolor=ft.Colors.BLUE_700,
            color=ft.Colors.WHITE,
            padding=ft.Padding(20, 14, 20, 14),
        ),
    )

    # 4. בניית הממשק
    page.add(
        ft.Row(height=60, controls=[
            start_work_dd,
            salary_field,
            age_field,
            search_button
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=16),
        ft.Divider(),
        filters_panel,
        ft.Divider(),
        results_title,
        ft.ListView([result_table], expand=True)
    )

ft.run(main)