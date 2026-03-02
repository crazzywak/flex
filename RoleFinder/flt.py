import flet as ft
import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
xlsx_path = os.path.join(BASE_DIR, "data.xlsx")
logo_path = os.path.join(BASE_DIR, "logo.png")

print(xlsx_path)  # optional, to verify


def main(page: ft.Page):
    # עדכון שם המערכת בחלון
    page.title = "Role Finder"
    page.window.maximized = True
    page.rtl = True
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 40
    page.expand = True

    # טעינת נתונים מקובץ חיצוני
    try:
        if os.path.exists(xlsx_path):
            df_raw = pd.read_excel(xlsx_path, sheet_name=0)
            # סינון ערכים לא מספריים בעמודת שכר והמרה למספר
            df_raw = df_raw[pd.to_numeric(df_raw['שכר'], errors='coerce').notna()]
            df_raw['שכר'] = pd.to_numeric(df_raw['שכר'])
        else:
            page.add(ft.Text("שגיאה: קובץ data.xlsx לא נמצא בתיקיית ההרצה", color="red", size=20))
            return
    except Exception as e:
        page.add(ft.Text(f"שגיאה בטעינת הקובץ: {e}", color="red"))
        return

    # חישוב טווחים עבור הסליידרים
    min_s, max_s = float(df_raw['שכר'].min()), float(df_raw['שכר'].max())
    # חישוב גיל מתוך תאריך התחלה
    df_raw['גיל'] = pd.to_datetime(df_raw['תחילת עבודה']).apply(lambda x: 2025 - x.year)
    min_a, max_a = int(df_raw['גיל'].min()), int(df_raw['גיל'].max())

    salary_val_text = ft.Text(f"נבחר: {int(min_s)}", color=ft.Colors.BLUE_900, weight="bold")
    age_val_text = ft.Text(f"נבחר: {int(min_a)}", color=ft.Colors.BLUE_900, weight="bold")

    data_table = ft.DataTable(
        expand=True,
        column_spacing=50,
        heading_row_color=ft.Colors.GREY_200,
        columns=[
            ft.DataColumn(ft.Text("מחלקה", weight="bold")),
            ft.DataColumn(ft.Text("תפקיד", weight="bold")),
            ft.DataColumn(ft.Text("טווח שכר", weight="bold")),
        ]
    )

    def update_ui(e):
        salary_val_text.value = f"נבחר: {int(salary_slider.value)}"
        age_val_text.value = f"נבחר: {int(age_slider.value)}"

        filtered = df_raw.copy()
        filtered = filtered[filtered['גיל'] >= age_slider.value]
        filtered = filtered[filtered['שכר'] >= salary_slider.value]

        group_cols = ['אגף (מחלקה)', 'תפקיד']
        
        if not filtered.empty:
            summary = filtered.groupby(group_cols).agg(
                min_s=('שכר', 'min'), max_s=('שכר', 'max'),
                min_a=('גיל', 'min'), max_a=('גיל', 'max')
            ).reset_index()

            summary = summary[summary['max_s'] >= salary_slider.value]
        else:
            summary = pd.DataFrame()

        data_table.rows.clear()
        for _, row in summary.iterrows():
            data_table.rows.append(
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text(row['אגף (מחלקה)'], color=ft.Colors.BLUE_700, weight="bold")),
                    ft.DataCell(ft.Text(row['תפקיד'])),
                    ft.DataCell(ft.Text(f"{int(row['min_s'])} - {int(row['max_s'])}")),
                ])
            )
        page.update()

    # פקדי סינון
    gender_filter = ft.Dropdown(label="מין", value="לא משנה", on_select=update_ui, 
                               options=[ft.dropdown.Option("לא משנה"), ft.dropdown.Option("זכר"), ft.dropdown.Option("נקבה")])
    
    age_range_filter = ft.Dropdown(label="טווח גילאים", value="18-24", on_select=update_ui,
                                   options=[ft.dropdown.Option("18-24"), ft.dropdown.Option("25-34"), 
                                          ft.dropdown.Option("35-44"), ft.dropdown.Option("45-54"), 
                                          ft.dropdown.Option("55-64"), ft.dropdown.Option("65+")])
    
    work_hours_filter = ft.Dropdown(label="סוג שעות עבודה", value="בוקר בלי שעות נוספות", on_select=update_ui,
                                   options=[ft.dropdown.Option("בוקר בלי שעות נוספות"), 
                                          ft.dropdown.Option("שבוע בוקר+2-3 ש\"נ בשבוע"),
                                          ft.dropdown.Option("שבוע בוקר/לילה 12/12"),
                                          ft.dropdown.Option("שבוע בוקר+5 ש\"נ"),
                                          ft.dropdown.Option("חודש עם שבוע אחד של לילות")])
    
    work_duration_filter = ft.Dropdown(label="טווח זמן לעבודה", value="מועדפת", on_select=update_ui,
                                       options=[ft.dropdown.Option("מועדפת"), 
                                              ft.dropdown.Option("עד טווח זמן של שנה"),
                                              ft.dropdown.Option("לטווח זמן מעל שנה")])
    
    work_nature_filter = ft.Dropdown(label="אופי של עבודה", value="בישיבה", on_select=update_ui,
                                     options=[ft.dropdown.Option("בישיבה"), ft.dropdown.Option("בהליכה")])
    
    english_filter = ft.Dropdown(label="אנגלית", value="אין בכלל", on_select=update_ui,
                                options=[ft.dropdown.Option("אין בכלל"), ft.dropdown.Option("בסיסית"),
                                       ft.dropdown.Option("שליטה טובה"), ft.dropdown.Option("שפת אם")])
    
    russian_filter = ft.Dropdown(label="רוסית", value="אין בכלל", on_select=update_ui,
                                options=[ft.dropdown.Option("אין בכלל"), ft.dropdown.Option("בסיסית"),
                                       ft.dropdown.Option("שליטה טובה"), ft.dropdown.Option("שפת אם")])
    
    hebrew_filter = ft.Dropdown(label="עברית", value="אין בכלל", on_select=update_ui,
                               options=[ft.dropdown.Option("אין בכלל"), ft.dropdown.Option("בסיסית"),
                                      ft.dropdown.Option("שליטה טובה"), ft.dropdown.Option("שפת אם")])
    
    lift_weights_checkbox = ft.Checkbox(label="הרמת 15 ק\"ג", value=False, on_change=update_ui)
    
    read_drawings_checkbox = ft.Checkbox(label="שרטוטים", value=False, on_change=update_ui)
    
    electronics_technician_checkbox = ft.Checkbox(label="הנדסאי אלקטרוניקה", value=False, on_change=update_ui)
    
    assembly_experience_checkbox = ft.Checkbox(label="הרכבות", value=False, on_change=update_ui)
    
    welding_experience_checkbox = ft.Checkbox(label="הלחמות", value=False, on_change=update_ui)
    
    warehouse_experience_checkbox = ft.Checkbox(label="מחסן", value=False, on_change=update_ui)
    
    forklift_license_checkbox = ft.Checkbox(label="מלגזה", value=False, on_change=update_ui)
    
    machine_operator_checkbox = ft.Checkbox(label="מפעיל מכונה", value=False, on_change=update_ui)
    
    computer_software_filter = ft.Dropdown(label="ידע במחש ותוכנות", value="אין בכלל", on_select=update_ui,
                                         options=[ft.dropdown.Option("אין בכלל"), ft.dropdown.Option("בסיסית"),
                                                ft.dropdown.Option("שליטה טובה")])
    
    clear_handwriting_checkbox = ft.Checkbox(label="כתב יד", value=False, on_change=update_ui)
    
    integration_experience_checkbox = ft.Checkbox(label="אינטגרציה", value=False, on_change=update_ui)
    
    # Keep existing filters for now
    age_slider = ft.Slider(min=min_a, max=max_a, value=min_a, divisions=int(max_a-min_a) if max_a > min_a else 1, on_change=update_ui)
    exp_filter = ft.Dropdown(label="ניסיון קודם", value="הכל", on_select=update_ui, 
                            options=[ft.dropdown.Option("הכל"), ft.dropdown.Option("כן"), ft.dropdown.Option("לא")])
    salary_slider = ft.Slider(min=min_s, max=max_s, value=min_s, divisions=int(max_s-min_s) if max_s > min_a else 1, on_change=update_ui)

    # Filters section
    filters_section = ft.Container(
        content=ft.Column([
            ft.Text("מסנני מועמד", size=16, weight="bold", color=ft.Colors.BLUE_900),
            
            # First row: Basic info dropdowns
            ft.Row([
                gender_filter,
                ft.Container(width=15),
                age_range_filter,
                ft.Container(width=15),
                work_hours_filter,
                ft.Container(width=15),
                work_duration_filter,
            ], alignment=ft.MainAxisAlignment.CENTER, wrap=True),
            
            ft.Divider(height=1, color=ft.Colors.GREY_300),
            
            # Second row: More dropdowns
            ft.Row([
                work_nature_filter,
                ft.Container(width=15),
                english_filter,
                ft.Container(width=15),
                russian_filter,
                ft.Container(width=15),
                hebrew_filter,
            ], alignment=ft.MainAxisAlignment.CENTER, wrap=True),
            
            ft.Divider(height=1, color=ft.Colors.GREY_300),
            
            # Third row: Skills, salary and age
            ft.Row([
                computer_software_filter,
                ft.Container(width=15),
                exp_filter,
                ft.Container(width=15),
                ft.Column([ft.Text("ציפיות שכר:", weight="bold"), salary_slider, salary_val_text], spacing=2, width=180),
                ft.Container(width=15),
                ft.Column([ft.Text("גיל:", weight="bold"), age_slider, age_val_text], spacing=2, width=180),
            ], alignment=ft.MainAxisAlignment.CENTER, wrap=True),
            
            ft.Divider(height=1, color=ft.Colors.GREY_300),
            
            # Fourth row: ALL checkboxes in one line
            ft.Row([
                lift_weights_checkbox,
                read_drawings_checkbox,
                electronics_technician_checkbox,
                assembly_experience_checkbox,
                welding_experience_checkbox,
                warehouse_experience_checkbox,
                forklift_license_checkbox,
                machine_operator_checkbox,
                clear_handwriting_checkbox,
                ft.Container(width=5),
                integration_experience_checkbox,
            ], alignment=ft.MainAxisAlignment.CENTER, wrap=False),
            
            ft.Divider(height=1, color=ft.Colors.GREY_300),
            
        ], spacing=10),
        padding=15, bgcolor=ft.Colors.GREY_50, border_radius=20, border=ft.Border.all(1, ft.Colors.GREY_200)
    )
    # Table section at the bottom
    table_section = ft.Container(
        content=ft.Column([
            ft.ListView([data_table], expand=True, spacing=10)
        ], expand=True),
        expand=True
    )

    # Main layout with filters above and table below
    page.add(
        ft.Column([
            filters_section,
            table_section
        ], expand=True)
    )
    update_ui(None)

if __name__ == "__main__":
    ft.run(main)