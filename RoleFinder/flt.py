import flet as ft
import pandas as pd
import os
import re  # ייבוא ספריית ביטויים רגולריים

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

    # ניקוי ויישור שמות עמודות
    df_data.columns = df_data.columns.str.strip()
    df_profiles.columns = df_profiles.columns.str.strip()

    # שינוי שמות עמודות לחיבור
    df_data.rename(columns={'אגף (מחלקה)': 'מחלקה'}, inplace=True)
    
    col_names = list(df_profiles.columns)
    col_names[0] = 'מחלקה'
    col_names[1] = 'תפקיד'
    df_profiles.columns = col_names

    # מילוי תאים ממוזגים ריקים
    df_profiles['מחלקה'] = df_profiles['מחלקה'].ffill()

    # ניקוי רווחים מהתוכן עצמו
    df_data['מחלקה'] = df_data['מחלקה'].astype(str).str.strip()
    df_data['תפקיד'] = df_data['תפקיד'].astype(str).str.strip()
    df_profiles['מחלקה'] = df_profiles['מחלקה'].astype(str).str.strip()
    df_profiles['תפקיד'] = df_profiles['תפקיד'].astype(str).str.strip()

    # 2. חישוב טווחי שכר מתוך data.xlsx מבוסס Regex
    df_data['שכר'] = pd.to_numeric(df_data['שכר'], errors='coerce')
    
    min_salaries = []
    max_salaries = []

    # מעבר על כל פרופיל תפקיד וחיפוש בטבלת העובדים לפי Regex
    for idx, row in df_profiles.iterrows():
        dept = str(row['מחלקה'])
        role_pattern = str(row['תפקיד'])

        # חיתוך לפי מחלקה (בצורה מדויקת)
        dept_match = df_data['מחלקה'] == dept
        
        # חיתוך לפי תפקיד בעזרת Regex חכם
        try:
            role_match = df_data['תפקיד'].str.contains(role_pattern, regex=True, flags=re.IGNORECASE, na=False)
        except re.error:
            # אם הביטוי הרגולרי שבור (למשל עקב תו מיוחד באקסל), נופלים לחיפוש טקסט רגיל
            role_match = df_data['תפקיד'].str.contains(role_pattern, regex=False, na=False)

        matching_rows = df_data[dept_match & role_match]

        if not matching_rows.empty:
            min_salaries.append(matching_rows['שכר'].min())
            max_salaries.append(matching_rows['שכר'].max())
        else:
            min_salaries.append(float('nan'))
            max_salaries.append(float('nan'))

    # הרכבת טבלת הנתונים המאוחדת (df_merged)
    df_merged = df_profiles.copy()
    df_merged['שכר_מינימום'] = min_salaries
    df_merged['שכר_מקסימום'] = max_salaries

    # 3. יצירת מסננים דינמיים 
    filters_dict = {}
    filter_ui_elements = []

    # חישוב מינימום ומקסימום שכר (מותאם לשכר שעתי) מכלל הנתונים
    min_sal_val = df_data['שכר'].min()
    max_sal_val = df_data['שכר'].max()
    
    min_salary = float(min_sal_val) if pd.notna(min_sal_val) else 30.0
    max_salary = float(max_sal_val) if pd.notna(max_sal_val) else 100.0

    if max_salary <= min_salary:
        max_salary = min_salary + 10.0

    salary_label = ft.Text(f"{int(min_salary)} ₪ לשעה", weight="bold", size=16, color=ft.Colors.BLUE_700)
    age_label = ft.Text("25", weight="bold", size=16, color=ft.Colors.BLUE_700)

    sal_divisions = int(max_salary - min_salary) if max_salary > min_salary else 1

    salary_slider = ft.Slider(
        min=min_salary, max=max_salary, value=min_salary, expand=True,
        label="{value} ₪",
        divisions=sal_divisions
    )
    age_slider = ft.Slider(
        min=18.0, max=70.0, value=25.0, expand=True,
        label="{value}",
        divisions=52
    )

    def update_labels_on_release(e=None):
        salary_label.value = f"{int(salary_slider.value)} ₪ לשעה"
        age_label.value = str(int(age_slider.value))
        salary_label.update()
        age_label.update()

    salary_slider.on_change_end = update_labels_on_release
    age_slider.on_change_end = update_labels_on_release

    age_col = next((col for col in df_profiles.columns if 'גיל' in col), None)
    dynamic_cols = [c for c in df_profiles.columns[2:] if c != age_col and c not in ['שכר_מינימום', 'שכר_מקסימום']]

    FILTER_WIDTH = 180 

    for col in dynamic_cols:
        unique_vals = set(df_profiles[col].dropna().astype(str).str.strip())
        unique_vals = {v for v in unique_vals if v != ''}
        
        if unique_vals.issubset({'כן', 'לא'}):
            cb = ft.Checkbox(label=col, value=False)
            filters_dict[col] = {'type': 'checkbox', 'control': cb}
            
            filter_ui_elements.append(
                ft.Container(content=cb, width=FILTER_WIDTH, tooltip=col)
            )
        else:
            options = [ft.dropdown.Option("הכל")] + [ft.dropdown.Option(v) for v in sorted(list(unique_vals))]
            dd = ft.Dropdown(
                label=col, 
                options=options, 
                value="הכל", 
                width=FILTER_WIDTH, 
                text_size=13,
                content_padding=10,
                tooltip=col
            )
            filters_dict[col] = {'type': 'dropdown', 'control': dd}
            filter_ui_elements.append(dd)

    # 4. בניית טבלת התוצאות
    result_table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("מחלקה", weight="bold")),
            ft.DataColumn(ft.Text("תפקיד", weight="bold")),
            ft.DataColumn(ft.Text("טווח שכר בפועל", weight="bold")),
        ],
        rows=[]
    )

    results_title = ft.Text("תוצאות (תפקידים מתאימים):", weight="bold", size=18)

    def update_table(e=None):
        filtered_df = df_merged.copy()

        expected_salary = salary_slider.value
        filtered_df = filtered_df[
            (filtered_df['שכר_מקסימום'].isna()) | 
            (filtered_df['שכר_מקסימום'] >= expected_salary)
        ]

        if age_col:
            selected_age = int(age_slider.value)
            def is_age_in_range(age_str):
                if pd.isna(age_str): return True
                try:
                    parts = str(age_str).split('-')
                    if len(parts) == 2:
                        return int(parts[0]) <= selected_age <= int(parts[1])
                except:
                    pass
                return True
            filtered_df = filtered_df[filtered_df[age_col].apply(is_age_in_range)]

        for col, filter_data in filters_dict.items():
            ctrl = filter_data['control']
            if filter_data['type'] == 'checkbox':
                if ctrl.value:  
                    filtered_df = filtered_df[filtered_df[col].astype(str).str.strip() == 'כן']
            elif filter_data['type'] == 'dropdown':
                if ctrl.value != "הכל":
                    filtered_df = filtered_df[filtered_df[col].astype(str).str.strip() == ctrl.value]

        filtered_df = filtered_df.drop_duplicates(subset=['מחלקה', 'תפקיד'])

        # עדכון כותרת התוצאות עם הכמות שנמצאה
        results_title.value = f"תוצאות (תפקידים מתאימים): {len(filtered_df)}"

        rows = []
        for _, row in filtered_df.iterrows():
            min_s = f"{int(row['שכר_מינימום'])}" if not pd.isna(row['שכר_מינימום']) else "לא ידוע"
            max_s = f"{int(row['שכר_מקסימום'])}" if not pd.isna(row['שכר_מקסימום']) else "לא ידוע"
            
            salary_str = f"{min_s} ₪ - {max_s} ₪ לשעה" if min_s != max_s and min_s != "לא ידוע" else f"{min_s} ₪ לשעה" if min_s != "לא ידוע" else "לא ידוע"
            
            rows.append(
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text(str(row['מחלקה']))),
                    ft.DataCell(ft.Text(str(row['תפקיד']))),
                    ft.DataCell(ft.Text(salary_str)),
                ])
            )
        
        result_table.rows = rows
        page.update()

    search_button = ft.ElevatedButton(
        "סנן תוצאות", 
        on_click=update_table
    )

    # 5. עיצוב והוספה למסך
    page.add(        
        ft.Row([
            ft.Column([
                ft.Row([ft.Text("ציפיות שכר מועמד:", weight="bold"), salary_label], spacing=10),
                ft.Row([salary_slider])
            ], expand=1),
            ft.Column([
                ft.Row([ft.Text("גיל מועמד:", weight="bold"), age_label], spacing=10),
                ft.Row([age_slider])
            ], expand=1),
        ]),
        
        ft.Divider(),
        ft.Text("מסנני פרופיל תפקיד:", weight="bold", size=18),
        
        ft.Container(
            content=ft.Row(
                filter_ui_elements, 
                wrap=True,
                spacing=10,                  
                run_spacing=10,               
                alignment=ft.MainAxisAlignment.START 
            ),
            padding=15,
            bgcolor=ft.Colors.GREY_50,
            border_radius=10,
            border=ft.Border.all(1, ft.Colors.GREY_300)
        ),
        
        ft.Container(
            content=search_button,
            alignment=ft.alignment.Alignment.CENTER,
            padding=20
        ),
        
        ft.Divider(),
        results_title,
        ft.ListView([result_table], expand=True)
    )

    update_table()

ft.app(target=main)