import flet as ft
import pandas as pd
import os
import re
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
data_path = os.path.join(BASE_DIR, "data.xlsx")
profiles_path = os.path.join(BASE_DIR, "job profiles.xlsx")
open_positions_path = os.path.join(BASE_DIR, "мисрот птухот.xlsx")

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

    # טעינת קובץ משרות פתוחות
    # מבנה: שורה 0 = תפקידים (col 1+), עמודה 0 = מחלקות (שורה 1+), col 1 = פרטי קשר
    # תא עם מספר >= 1 = יש משרות פתוחות, אחרת מסוננת
    open_positions_set = [None]  # list wrapper for mutability in nested functions
    df_open_ref = [None]

    def parse_open_positions(df_op):
        result = set()
        roles_row = df_op.iloc[0, 1:].tolist()
        for row_idx in range(1, len(df_op)):
            dept = str(df_op.iloc[row_idx, 0]).strip()
            if not dept or dept == 'nan':
                continue
            for col_offset, role in enumerate(roles_row):
                if pd.isna(role):
                    continue
                role_clean = str(role).strip()
                val = df_op.iloc[row_idx, col_offset + 1]
                try:
                    num = float(val)
                    if num >= 1:
                        result.add((dept, role_clean))
                except (ValueError, TypeError):
                    pass
        return result

    try:
        df_open_loaded = pd.read_excel(open_positions_path, header=None)
        df_open_ref[0] = df_open_loaded
        open_positions_set[0] = parse_open_positions(df_open_loaded)
    except Exception:
        pass

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
    filter_containers = {}  # col -> Container wrapping the control

    CHANGED_BORDER_COLOR = ft.Colors.ORANGE_600
    DEFAULT_BORDER_COLOR = ft.Colors.TRANSPARENT

    def update_filter_border(col):
        entry = filters_dict[col]
        ctrl = entry['control']
        container = filter_containers.get(col)
        if container is None:
            return
        if entry['type'] == 'checkbox':
            changed = ctrl.value  # default is False
        else:
            changed = ctrl.value != "הכל"
        container.border = ft.Border.all(2, CHANGED_BORDER_COLOR) if changed else ft.Border.all(1, DEFAULT_BORDER_COLOR)
        container.border_radius = 6
        page.update()

    def make_control(col):
        unique_vals = set(df_profiles[col].dropna().astype(str).str.strip())
        unique_vals = {v for v in unique_vals if v != ''}
        if unique_vals.issubset({'כן', 'לא'}):
            def on_cb_change(e, c=col):
                update_filter_border(c)
            cb = ft.Checkbox(label=col, value=False, on_change=on_cb_change)
            filters_dict[col] = {'type': 'checkbox', 'control': cb}
            container = ft.Container(content=cb, expand=True, border=ft.Border.all(1, DEFAULT_BORDER_COLOR), border_radius=6, padding=4)
            filter_containers[col] = container
            return container
        else:
            options = [ft.DropdownOption(key="הכל", text="הכל")] + [
                ft.DropdownOption(key=v, text=v) for v in sorted(list(unique_vals))
            ]
            def on_dd_change(e, c=col):
                update_filter_border(c)
            dd = ft.Dropdown(label=col, options=options, value="הכל", expand=True, on_select=on_dd_change)
            filters_dict[col] = {'type': 'dropdown', 'control': dd}
            container = ft.Container(content=dd, expand=True, border=ft.Border.all(1, DEFAULT_BORDER_COLOR), border_radius=6)
            filter_containers[col] = container
            return container
 
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
    PERSONAL_KEYWORDS   = ['גיל', 'מין', 'גר/ה רחוק']
    HOURS_KEYWORDS      = ['שעות', 'אופי', 'טווח', 'משקלים']
    EXPERIENCE_KEYWORDS = ['ניסיון']
    SKILLS_KEYWORDS     = ['עברית', 'אנגלית', 'רוסית', 'רישיון', 'הנדסאי', 'מחשב', 'שרטוטים' ]

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
            ft.DataColumn(ft.Text("משרות פתוחות", weight="bold")),
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

        # סינון לפי משרות פתוחות – אם הקובץ נטען, מציגים רק (מחלקה, תפקיד) שיש להם >= 1 משרה
        if open_positions_set[0] is not None:
            def has_open_position(row):
                dept = str(row['מחלקה']).strip()
                role = str(row['תפקיד']).strip()
                # בדיקה ישירה
                if (dept, role) in open_positions_set[0]:
                    return True
                # בדיקה חלקית – אם התפקיד בפרופיל מכיל חלק מהשם שבקובץ המשרות
                for (op_dept, op_role) in open_positions_set[0]:
                    if op_dept == dept and (op_role in role or role in op_role):
                        return True
                return False
            filtered_df = filtered_df[filtered_df.apply(has_open_position, axis=1)]

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

            # חישוב כמות משרות פתוחות
            open_count_str = "-"
            if open_positions_set[0] is not None and df_open_ref[0] is not None:
                dept = str(row['מחלקה']).strip()
                role = str(row['תפקיד']).strip()
                total = 0
                try:
                    df_open = df_open_ref[0]
                    roles_row_op = df_open.iloc[0, 1:].tolist()
                    for row_idx in range(1, len(df_open)):
                        op_dept = str(df_open.iloc[row_idx, 0]).strip()
                        if op_dept != dept:
                            continue
                        for col_offset, op_role in enumerate(roles_row_op):
                            if pd.isna(op_role):
                                continue
                            op_role_clean = str(op_role).strip()
                            if op_role_clean == role or op_role_clean in role or role in op_role_clean:
                                val = df_open.iloc[row_idx, col_offset + 1]
                                try:
                                    total += int(float(val))
                                except (ValueError, TypeError):
                                    pass
                except Exception:
                    pass
                if total > 0:
                    open_count_str = str(total)

            rows.append(
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text(str(row['מחלקה']))),
                    ft.DataCell(ft.Text(str(row['תפקיד']))),
                    ft.DataCell(ft.Text(salary_str)),
                    ft.DataCell(ft.Text(open_count_str)),
                ])
            )

        result_table.rows = rows
        page.update()

    # כפתור חיפוש
    search_button = ft.Button(
        content=ft.Row([ft.Icon(ft.Icons.SEARCH, color=ft.Colors.WHITE), ft.Text("חפש", color=ft.Colors.WHITE)], tight=True),
        on_click=update_table,
        style=ft.ButtonStyle(
            bgcolor={
                ft.ControlState.DEFAULT: ft.Colors.BLUE_700,
                ft.ControlState.HOVERED: ft.Colors.BLUE_900,
                ft.ControlState.PRESSED: ft.Colors.BLUE_300,
            },
            color=ft.Colors.WHITE,
            padding=ft.Padding(20, 14, 20, 14),
            elevation={"": 2, ft.ControlState.HOVERED: 6, ft.ControlState.PRESSED: 0},
            shadow_color=ft.Colors.BLUE_200,
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