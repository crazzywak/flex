import flet as ft
import pandas as pd
import os
import re
import asyncio
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
data_path = os.path.join(BASE_DIR, "data.xlsx")
profiles_path = os.path.join(BASE_DIR, "job profiles.xlsx")
open_positions_path = os.path.join(BASE_DIR, "мисрот птухот.xlsx")

# Constants
ALL_OPTION = "לא משנה"

def main(page: ft.Page):
    page.title = "Role Finder - מערכת איתור תפקידים"
    page.rtl = True
    page.padding = 30
    page.scroll = ft.ScrollMode.ADAPTIVE
    page.window.maximized = True
    
    # 1. רקע לבן
    page.bgcolor = ft.Colors.WHITE

    # ---- מצב גלובלי ----
    df_data_ref = [None]
    df_profiles_ref = [None]
    open_positions_set = [None]
    df_open_ref = [None]

    # ---- הודעת סטטוס ואנימציה ----
    cat_container = ft.Container(
        content=ft.Image(src=os.path.join(BASE_DIR, "cat.gif"), width=50, height=50),
        alignment=ft.Alignment.CENTER_RIGHT, 
        animate=ft.Animation(2000, ft.AnimationCurve.LINEAR), # 8-second slow walk
        visible=False,
        height=50,
    )

    status_bar = ft.Container(
        content=ft.Text("", color=ft.Colors.WHITE, weight="bold", size=14, text_align=ft.TextAlign.CENTER),
        bgcolor=ft.Colors.GREEN_600,
        border_radius=8,
        padding=ft.Padding(16, 10, 16, 10),
        visible=False,
        # animate_opacity=300,
    )

    def show_loading():
        # 1. Snap the cat back to the right side instantly
        cat_container.alignment = ft.Alignment.CENTER_RIGHT
        cat_container.visible = True
        status_bar.visible = False
        page.update()

        # # 2. Trigger the walk safely in the background
        async def trigger_walk():
            await asyncio.sleep(0.1)
            cat_container.animate = ft.Animation(10000, ft.AnimationCurve.LINEAR)
            cat_container.alignment = ft.Alignment.CENTER_LEFT
            page.update()

        page.run_task(trigger_walk)

    def show_status(message: str, success: bool = True):
        # 1. Hide the cat and show the message
    
        cat_container.visible = False
        status_bar.content.value = message
        status_bar.bgcolor = ft.Colors.GREEN_700 if success else ft.Colors.RED_700
        status_bar.visible = True
        page.update()

    # ---- טעינת נתונים ----
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

    def load_data():
        """טוען את כל קבצי האקסל מחדש"""
        try:
            df_data = pd.read_excel(data_path)
            df_profiles = pd.read_excel(profiles_path)
        except Exception as e:
            return False, f"שגיאה בטעינת הקבצים: {e}"

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

        df_data_ref[0] = df_data
        df_profiles_ref[0] = df_profiles

        try:
            df_open_loaded = pd.read_excel(open_positions_path, header=None)
            df_open_ref[0] = df_open_loaded
            open_positions_set[0] = parse_open_positions(df_open_loaded)
        except Exception:
            df_open_ref[0] = None
            open_positions_set[0] = None

        return True, ""

    # טעינה ראשונית
    success, err_msg = load_data()
    if not success:
        page.add(ft.Text(err_msg, color="red", size=20))
        return

    df_data = df_data_ref[0]
    df_profiles = df_profiles_ref[0]

    # ---- זיהוי עמודות ----
    start_work_col = next((col for col in df_data.columns if 'תחילת' in col), None)
    age_col = next((col for col in df_profiles.columns if 'גיל' in col), None)

    dynamic_cols = [
        c for c in df_profiles.columns[2:]
        if c != age_col and c not in ['שכר_מינימום', 'שכר_מקסימום']
    ]

    # ---- טווחי שכר ----
    async def compute_salary_ranges(df_source):
        await asyncio.sleep(0.1)
        df_profiles = df_profiles_ref[0]
        min_salaries = []
        max_salaries = []
        for _, row in df_profiles.iterrows():
            dept = str(row['מחלקה']).strip()
            role_raw = str(row['תפקיד']).strip()
            dept_match = df_source['מחלקה'] == dept
            role_parts = [p.strip() for p in role_raw.split(',') if p.strip()]
            combined_role_match = pd.Series([False] * len(df_source), index=df_source.index)
            for part in role_parts:
                part_match = df_source['תפקיד'] == part
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

    # ---- שדות קלט ----
    min_sal_val = df_data['שכר'].min()
    min_salary = float(min_sal_val) if pd.notna(min_sal_val) else 30.0

    salary_field = ft.TextField(
        label="ציפיות שכר (₪ לשעה)",
        value=str(int(min_salary)),
        keyboard_type=ft.KeyboardType.NUMBER,
        text_align=ft.TextAlign.RIGHT,
        expand=True
    )
    age_field = ft.TextField(
        label="גיל מועמד",
        value="25",
        keyboard_type=ft.KeyboardType.NUMBER,
        text_align=ft.TextAlign.RIGHT,
        expand=True
    )

    CHANGED_BORDER_COLOR = ft.Colors.ORANGE_600
    DEFAULT_BORDER_COLOR = ft.Colors.TRANSPARENT

    filters_dict = {}
    filter_containers = {}

    def update_filter_border(col):
        entry = filters_dict[col]
        ctrl = entry['control']
        container = filter_containers.get(col)
        if container is None:
            return
        changed = ctrl.value if entry['type'] == 'checkbox' else ctrl.value != ALL_OPTION
        container.border = ft.Border.all(2, CHANGED_BORDER_COLOR) if changed else ft.Border.all(1, DEFAULT_BORDER_COLOR)
        page.update()

    def make_control(col):
        df_profiles = df_profiles_ref[0]
        unique_vals = set(df_profiles[col].dropna().astype(str).str.strip())
        unique_vals = {v for v in unique_vals if v != '' and v != 'לא משנה'}
        if unique_vals.issubset({'כן', 'לא'}):
            def on_cb_change(e, c=col): update_filter_border(c)
            cb = ft.Checkbox(label=col, value=False, on_change=on_cb_change)
            filters_dict[col] = {'type': 'checkbox', 'control': cb}
            container = ft.Container(content=cb, expand=True, border=ft.Border.all(1, DEFAULT_BORDER_COLOR), border_radius=6, padding=4)
            filter_containers[col] = container
            return container
        else:
            options = [ft.DropdownOption(key=ALL_OPTION, text=ALL_OPTION)] + [
                ft.DropdownOption(key=v, text=v) for v in sorted(list(unique_vals))
            ]
            def on_dd_change(e, c=col): update_filter_border(c)
            dd = ft.Dropdown(label=col, options=options, value=ALL_OPTION, expand=True, on_select=on_dd_change)
            filters_dict[col] = {'type': 'dropdown', 'control': dd}
            container = ft.Container(content=dd, expand=True, border=ft.Border.all(1, DEFAULT_BORDER_COLOR))
            filter_containers[col] = container
            return container

    # ---- פילטר תקופת טווח שכר ----
    start_work_dd = ft.Dropdown(
        label="תקופת טווח שכר",
        options=[
            ft.DropdownOption(key=ALL_OPTION, text=ALL_OPTION),
            ft.DropdownOption(key="חצי שנה", text="חצי שנה"),
        ],
        value=ALL_OPTION
    )

    # ---- קטגוריות ----
    PERSONAL_KEYWORDS   = ['גיל', 'מין', 'גר/ה רחוק']
    HOURS_KEYWORDS      = ['שעות', 'אופי', 'טווח', 'משקלים']
    EXPERIENCE_KEYWORDS = ['הרכבות', 'אינטגרציה', 'הלחמות', 'בקרת איכות', 'מפעיל/ת מכונה', 'חיווט', 'מחסן']
    SKILLS_KEYWORDS     = ['עברית', 'אנגלית', 'רוסית', 'רישיון', 'הנדסאי', 'מחשב', 'שרטוטים']

    def categorize(col):
        for kw in PERSONAL_KEYWORDS:
            if kw in col: return 'פרטים אישיים'
        for kw in HOURS_KEYWORDS:
            if kw in col: return 'שעות/אופי עבודה'
        for kw in EXPERIENCE_KEYWORDS:
            if kw in col: return 'ניסיון'
        for kw in SKILLS_KEYWORDS:
            if kw in col or kw in col.lower(): return 'כישורים'
        return 'טוב לדעת'

    categories = {'פרטים אישיים': [], 'שעות/אופי עבודה': [], 'ניסיון': [], 'כישורים': [], 'טוב לדעת': []}

    if age_col:
        categories['פרטים אישיים'].append(make_control(age_col))
    for col in dynamic_cols:
        categories[categorize(col)].append(make_control(col))

    def build_category_section(title, controls):
        if not controls:
            return None
        return ft.Container(
            content=ft.Column([
                ft.Text(title, font_family='assistant', weight="bold", size=16, color=ft.Colors.BLUE_800),
                ft.Column(controls, width=200, spacing=10),
            ], spacing=8),
            padding=ft.Padding(12, 10, 12, 10),
            bgcolor=ft.Colors.WHITE,
            border=ft.Border.all(1, ft.Colors.BLUE_100),
        )

    category_sections = [
        build_category_section(title, controls)
        for title, controls in categories.items() if controls
    ]

    filters_panel = ft.Container(
        content=ft.Row(
            [s for s in category_sections if s],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.START,
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

    # ---- פונקציית חיפוש ----
    def update_table(e=None):
        show_loading() # מציג את החתול טוען
        search_button.disabled = True
        refresh_btn.disabled = True
        
        async def do_search():
            await asyncio.sleep(0.1)
            try:
                expected_salary = float(salary_field.value.strip())
            except (ValueError, AttributeError):
                expected_salary = min_salary

            try:
                selected_age = int(age_field.value.strip())
            except (ValueError, AttributeError):
                selected_age = 25

            df_source = df_data_ref[0].copy()

            if start_work_dd.value == "חצי שנה" and start_work_col:
                cutoff_date = datetime.today() - timedelta(days=183)
                def is_within_half_year(val):
                    if pd.isna(val): return True
                    try:
                        if isinstance(val, datetime):
                            return val >= cutoff_date
                        parsed = pd.to_datetime(str(val).strip(), dayfirst=True, errors='coerce')
                        return True if pd.isna(parsed) else parsed >= cutoff_date
                    except Exception:
                        return True
                df_source = df_source[df_source[start_work_col].apply(is_within_half_year)]

            df_merged = await compute_salary_ranges(df_source)

            filtered_df = df_merged[
                (df_merged['שכר_מקסימום'].isna()) |
                (df_merged['שכר_מקסימום'] >= expected_salary)
            ]

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

            for col, filter_data in filters_dict.items():
                ctrl = filter_data['control']
                if filter_data['type'] == 'checkbox':
                    if ctrl.value:
                        filtered_df = filtered_df[filtered_df[col].astype(str).str.strip() == 'כן']
                elif filter_data['type'] == 'dropdown':
                    if ctrl.value != ALL_OPTION:
                        filtered_df = filtered_df[filtered_df[col].astype(str).str.strip() == ctrl.value]

            filtered_df = filtered_df.drop_duplicates(subset=['מחלקה', 'תפקיד'])

            if open_positions_set[0] is not None:
                def has_open_position(row):
                    dept = str(row['מחלקה']).strip()
                    role_aliases = [p.strip() for p in str(row['תפקיד']).split(',') if p.strip()]
                    for role in role_aliases:
                        if (dept, role) in open_positions_set[0]:
                            return True
                        for (op_dept, op_role) in open_positions_set[0]:
                            if op_dept == dept and (op_role in role or role in op_role):
                                return True
                    return False
                filtered_df = filtered_df[filtered_df.apply(has_open_position, axis=1)]

            count = len(filtered_df)
            results_title.value = f"תוצאות (תפקידים מתאימים): {count}"

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

                open_count_str = "-"
                if open_positions_set[0] is not None and df_open_ref[0] is not None:
                    dept = str(row['מחלקה']).strip()
                    role_aliases = [p.strip() for p in str(row['תפקיד']).split(',') if p.strip()]
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
                                for role in role_aliases:
                                    if op_role_clean == role:
                                        val = df_open.iloc[row_idx, col_offset + 1]
                                        try:
                                            total += int(float(val))
                                        except (ValueError, TypeError):
                                            pass
                                        break  # avoid double-counting same cell for multiple aliases
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
            search_button.disabled = False
            refresh_btn.disabled = False
            page.update()

            # הודעת הצלחה ומעלים את החתול
            show_status(f"✔ החיפוש הושלם בהצלחה — נמצאו {count} תפקידים מתאימים")

        page.run_task(do_search)

    # ---- פונקציית רענון ----
    def refresh_data(e=None):
        # 1. Show the cat and disable the button IMMEDIATELY on the main thread
        show_loading()
        search_button.disabled = True
        refresh_btn.disabled = True

        # 2. Define the heavy work
        async def do_refresh():
            await asyncio.sleep(0.1)
            # Run the heavy Excel loading
            ok, err = await asyncio.to_thread(load_data)            

            # When finished, update the UI
            if not ok:
                show_status(f"✘ שגיאה בטעינת הנתונים: {err}", success=False)
            else:
                now = datetime.now().strftime("%H:%M:%S")
                show_status(f"✔ הנתונים עודכנו בהצלחה מקבצי האקסל ({now})")

            search_button.disabled = False
            refresh_btn.disabled = False
            page.update()

        # 3. Launch the heavy work in the background!
        page.run_task(do_refresh)

    def reset_filters(e):
        """Reset all filters to their default values"""
        for col, filter_data in filters_dict.items():
            ctrl = filter_data['control']
            if filter_data['type'] == 'checkbox':
                ctrl.value = False
            elif filter_data['type'] == 'dropdown':
                ctrl.value = ALL_OPTION
            update_filter_border(col)
        
        # Reset salary and age fields to defaults
        salary_field.value = str(int(min_salary))
        age_field.value = "25"
        
        # Reset start work dropdown
        start_work_dd.value = ALL_OPTION
        
        page.update()

    # ---- כפתורים ----
    reset_button = ft.Button(
        content=ft.Row(
            [ft.Icon(ft.Icons.FILTER_NONE, color=ft.Colors.WHITE), ft.Text("אפס מסננים", color=ft.Colors.WHITE)],
            tight=True
        ),
        on_click=reset_filters,
        style=ft.ButtonStyle(
            bgcolor={
                ft.ControlState.DEFAULT: ft.Colors.BLUE_700,
                ft.ControlState.HOVERED: ft.Colors.BLUE_900,
                ft.ControlState.PRESSED: ft.Colors.BLUE_300,
            },
            color=ft.Colors.WHITE,
            padding=ft.Padding(20, 14, 20, 14),
            elevation={"": 2, ft.ControlState.HOVERED: 6, ft.ControlState.PRESSED: 0},
            shadow_color=ft.Colors.ORANGE_200,
        ),
    )

    search_button = ft.Button(
        content=ft.Row(
            [ft.Icon(ft.Icons.SEARCH, color=ft.Colors.WHITE), ft.Text("חפש", color=ft.Colors.WHITE)],
            tight=True
        ),
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

    refresh_btn = ft.Button(
        content=ft.Row(
            [ft.Icon(ft.Icons.REFRESH, color=ft.Colors.WHITE), ft.Text("רענן", color=ft.Colors.WHITE)],
            tight=True
        ),
        on_click=refresh_data,
        style=ft.ButtonStyle(
            bgcolor={
                ft.ControlState.DEFAULT: ft.Colors.BLUE_700,
                ft.ControlState.HOVERED: ft.Colors.BLUE_900,
                ft.ControlState.PRESSED: ft.Colors.BLUE_300,
            },
            color=ft.Colors.WHITE,
            padding=ft.Padding(20, 14, 20, 14),
            elevation={"": 2, ft.ControlState.HOVERED: 6, ft.ControlState.PRESSED: 0},
            shadow_color=ft.Colors.TEAL_200,
        ),
    )

    logo_img = ft.Image(
        src="logo.png",
    )

    # ---- בניית הממשק ----
    page.add(
        ft.Row(height=60, controls=[
            salary_field,
            age_field,
            search_button,
            refresh_btn,
            logo_img,
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=16),
        cat_container, # הוספת קונטיינר החתול
        status_bar,
        ft.Divider(),
        ft.Row([reset_button], alignment=ft.MainAxisAlignment.START),
        filters_panel,
        ft.Divider(),
        results_title,
        start_work_dd,
        ft.ListView([result_table], expand=True)
    )

ft.run(main)