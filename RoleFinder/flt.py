import flet as ft
import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
csv_path = os.path.join(BASE_DIR, "data.csv")
logo_path = os.path.join(BASE_DIR, "logo.png")

print(csv_path)  # optional, to verify


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
        if os.path.exists(csv_path):
            df_raw = pd.read_csv(csv_path)
        else:
            page.add(ft.Text("שגיאה: קובץ data.csv לא נמצא בתיקיית ההרצה", color="red", size=20))
            return
    except Exception as e:
        page.add(ft.Text(f"שגיאה בטעינת הקובץ: {e}", color="red"))
        return

    # חישוב טווחים עבור הסליידרים
    min_s, max_s = float(df_raw['שכר'].min()), float(df_raw['שכר'].max())
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
            ft.DataColumn(ft.Text("טווח גילאים", weight="bold")),
            ft.DataColumn(ft.Text("מין", weight="bold")),
            ft.DataColumn(ft.Text("ניסיון", weight="bold")),
        ]
    )

    def update_ui(e):
        salary_val_text.value = f"נבחר: {int(salary_slider.value)}"
        age_val_text.value = f"נבחר: {int(age_slider.value)}"

        filtered = df_raw.copy()
        if gender_filter.value != "הכל":
            filtered = filtered[filtered['מין'] == gender_filter.value]
        if exp_filter.value != "הכל":
            filtered = filtered[filtered['ניסיון קודם'] == exp_filter.value]
        
        filtered = filtered[filtered['גיל'] >= age_slider.value]

        group_cols = ['מחלקה', 'תפקיד']
        
        if not filtered.empty:
            summary = filtered.groupby(group_cols).agg(
                min_s=('שכר', 'min'), max_s=('שכר', 'max'),
                min_a=('גיל', 'min'), max_a=('גיל', 'max'),
                gender_display=('מין', lambda x: ", ".join(set(x))),
                # לוגיקה מחמירה: אם יש "לא" אחד בתפקיד, כל השורה מסומנת כ-"לא"
                exp_final=('ניסיון קודם', lambda x: "לא" if "לא" in set(x) else "כן"),
                desc=('תיאור מחלקה', 'first')
            ).reset_index()

            summary = summary[summary['max_s'] >= salary_slider.value]
        else:
            summary = pd.DataFrame()

        data_table.rows.clear()
        for _, row in summary.iterrows():
            # תצוגה של X או V בלבד
            exp_icon = "✗" if row['exp_final'] == "לא" else "✓"
            icon_color = ft.Colors.RED if exp_icon == "✗" else ft.Colors.GREEN

            age_display = f"{int(row['min_a'])} - {int(row['max_a'])}" if int(row['min_a']) != int(row['max_a']) else f"{int(row['min_a'])}"

            data_table.rows.append(
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text(row['מחלקה'], tooltip=row['desc'], color=ft.Colors.BLUE_700, weight="bold")),
                    ft.DataCell(ft.Text(row['תפקיד'])),
                    ft.DataCell(ft.Text(f"{int(row['min_s'])} - {int(row['max_s'])}")),
                    ft.DataCell(ft.Text(age_display)),
                    ft.DataCell(ft.Text(row['gender_display'])),
                    ft.DataCell(ft.Text(exp_icon, size=20, color=icon_color, weight="bold")),
                ])
            )
        page.update()

    # פקדי סינון
    gender_filter = ft.Dropdown(label="מין", value="הכל", on_select=update_ui, 
                               options=[ft.dropdown.Option("הכל"), ft.dropdown.Option("זכר"), ft.dropdown.Option("נקבה")])
    age_slider = ft.Slider(min=min_a, max=max_a, value=min_a, divisions=int(max_a-min_a) if max_a > min_a else 1, on_change=update_ui)
    exp_filter = ft.Dropdown(label="ניסיון קודם", value="הכל", on_select=update_ui, 
                            options=[ft.dropdown.Option("הכל"), ft.dropdown.Option("כן"), ft.dropdown.Option("לא")])
    salary_slider = ft.Slider(min=min_s, max=max_s, value=min_s, divisions=int(max_s-min_s) if max_s > min_s else 1, on_change=update_ui)

    # Sidebar
    sidebar = ft.Container(
        content=ft.Column([
            ft.Text("מסנני מועמד", size=16, weight="bold", color=ft.Colors.BLUE_900),
            gender_filter,
            ft.Column([ft.Text("גיל:", weight="bold"), age_slider, age_val_text], spacing=2),
            ft.Divider(height=1, color=ft.Colors.GREY_300),
            exp_filter,
            ft.Column([ft.Text("ציפיות שכר:", weight="bold"), salary_slider, salary_val_text], spacing=2),
        ], scroll=ft.ScrollMode.AUTO, spacing=20),
        width=280, padding=15, bgcolor=ft.Colors.GREY_50, border_radius=20, border=ft.Border.all(1, ft.Colors.GREY_200)
    )

    # לוגו של המערכת
    logo_image = ft.Image(src=logo_path, width=300, height=60, fit="contain")
    
    # עדכון הכותרת ל-Role Finder
    header = ft.Row(
        controls=[logo_image],
        alignment=ft.MainAxisAlignment.CENTER
    )

    main_content = ft.Column([
        ft.Text("תפקידים מתאימים", size=26, weight="bold"),
        ft.Divider(height=10, color="transparent"),
        ft.ListView([data_table], expand=True, spacing=10)
    ], expand=True)

    page.add(header, ft.Container(height=20), ft.Row([sidebar, ft.VerticalDivider(width=30, color="transparent"), main_content], expand=True))
    update_ui(None)

if __name__ == "__main__":
    ft.run(main)