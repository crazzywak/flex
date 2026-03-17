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

def clean_text(text):
    return re.sub(r'\s*X\d+$', '', text, flags=re.IGNORECASE).strip()

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
    multiselect_cols_ref = [set()] # <-- ADD THIS LINE

    # ---- הודעת סטטוס ואנימציה ----
    cat_container = ft.Container(
        content=ft.Image(src="/cat.gif", width=50, height=50), # FIXED: Web-relative path
        alignment=ft.Alignment.CENTER_RIGHT, 
        animate=ft.Animation(2000, ft.AnimationCurve.LINEAR), 
        visible=False,
        height=50,
    )

    status_bar = ft.Container(
        content=ft.Text("", color=ft.Colors.WHITE, weight="bold", size=14, text_align=ft.TextAlign.CENTER),
        bgcolor=ft.Colors.GREEN_600,
        border_radius=8,
        padding=ft.Padding(16, 10, 16, 10),
        visible=False,
    )

    def show_loading():
        # 1. Snap the cat back to the right side instantly
        cat_container.alignment = ft.Alignment.CENTER_RIGHT
        cat_container.visible = True
        status_bar.visible = False
        page.update()

        # 2. Trigger the walk safely in the background
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

        multiselect_cols_ref[0] = set()
        clean_col_names = []

        for c in col_names:
            c_str = str(c).strip()
            if c_str.endswith(' M'):
                clean_name = c_str[:-2].strip() # Remove the ' M'
                print(f"Found multiselect column: {clean_name}")
                multiselect_cols_ref[0].add(clean_name)
                clean_col_names.append(clean_name)
            else:
                clean_col_names.append(c_str)
                
        df_profiles.columns = clean_col_names # Apply the clean names
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

    dynamic_cols = [
        c for c in df_profiles.columns[2:]
        if c not in ['טווח גילאים']
    ]

    print ("Dynamic columns:", dynamic_cols)

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
        keyboard_type=ft.KeyboardType.NUMBER,
        text_align=ft.TextAlign.RIGHT,
        expand=True
    )
    age_field = ft.TextField(
        label="גיל מועמד",
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
        container = filter_containers.get(col)
        if container is None:
            return
            
        if entry['type'] == 'checkbox':
            changed = entry['control'].value
        elif entry['type'] == 'dropdown':
            changed = entry['control'].value != ALL_OPTION
        elif entry['type'] == 'multiselect':
            # Changed if ANY of the checkboxes are checked
            changed = any(cb.value for cb in entry['controls'].values())
            
        container.border = ft.Border.all(2, CHANGED_BORDER_COLOR) if changed else ft.Border.all(1, DEFAULT_BORDER_COLOR)
        page.update()

    def make_control(col):
        df_profiles = df_profiles_ref[0]
        unique_vals = set(df_profiles[col].dropna().astype(str).str.strip())
        unique_vals = {v for v in unique_vals if v != '' and v != 'לא משנה'}

        print ("Making control for:", col)
        
        # 1. NEW: MULTI-SELECT HANDLER (ExpansionTile with wrapped text)
        if col in multiselect_cols_ref[0]:
            checkboxes = {}
            row_controls = []
            
            def on_multi_change(e, c=col):
                update_filter_border(c)
                entry = filters_dict[c]
                selected = [val for val, cb in entry['controls'].items() if cb.value]
                # Update subtitle to show selected items
                entry['tile'].subtitle = ft.Text(", ".join(selected), size=12, color=ft.Colors.BLUE_700) if selected else None
                page.update()
                
            for v in sorted(list(unique_vals)):
                # Checkbox without a label
                cb = ft.Checkbox(value=False, on_change=on_multi_change)
                checkboxes[v] = cb
                
                # Closure to capture the correct checkbox and column for the click event
                def make_row_click(current_cb, current_col):
                    def row_click(e):
                        current_cb.value = not current_cb.value
                        current_cb.update()
                        on_multi_change(e, c=current_col)
                    return row_click

                # Wrap the checkbox and text in a clickable container
                row = ft.Container(
                    content=ft.Row(
                        controls=[
                            cb,
                            ft.Text(v, expand=True)  # expand=True forces long text to wrap
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER
                    ),
                    on_click=make_row_click(cb, col),
                    padding=ft.Padding(0, 2, 0, 2),
                    ink=True,  # Adds a nice ripple effect when the text is clicked
                    border_radius=4
                )
                row_controls.append(row)
                
            tile = ft.ExpansionTile(
                title=ft.Text(col, size=14),
                controls=row_controls,
                affinity=ft.TileAffinity.LEADING,
            )
            filters_dict[col] = {'type': 'multiselect', 'controls': checkboxes, 'tile': tile}
            container = ft.Container(content=tile, expand=True, border=ft.Border.all(1, DEFAULT_BORDER_COLOR), border_radius=6)
            filter_containers[col] = container
            return container

        # 2. YES/NO CHECKBOX HANDLER
        elif unique_vals.issubset({'כן', 'לא'}):
            def on_cb_change(e, c=col): update_filter_border(c)
            cb = ft.Checkbox(label=col, value=False, on_change=on_cb_change)
            filters_dict[col] = {'type': 'checkbox', 'control': cb}
            container = ft.Container(content=cb, expand=True, border=ft.Border.all(1, DEFAULT_BORDER_COLOR), border_radius=6, padding=4)
            filter_containers[col] = container
            return container
            
        # 3. STANDARD SINGLE DROPDOWN HANDLER
        else:
            options = [ft.DropdownOption(key=ALL_OPTION, text=ALL_OPTION)] + [
                ft.DropdownOption(key=v, text=clean_text(v)) for v in sorted(list(unique_vals))
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
    PERSONAL_KEYWORDS   = ['מין', 'גר קרוב']
    HOURS_KEYWORDS      = ['שעות', 'אופי', 'משקלים']
    EXPERIENCE_KEYWORDS = ['הרכבות', 'אינטגרציה', 'הלחמות', 'בקרת איכות', 'מפעיל/ת מכונה', 'חיווט', 'מחסן', 'X-ray']
    SKILLS_KEYWORDS     = ['עברית', 'אנגלית', 'רוסית', 'רישיון', 'הנדסאי', 'מחשב', 'שרטוטים']

    def categorize(col):
        for kw in PERSONAL_KEYWORDS:
            if kw in col: return 'פרטים אישיים'
        for kw in HOURS_KEYWORDS:
            if kw in col: return 'שעות/אופי עבודה'
        for kw in EXPERIENCE_KEYWORDS:
            if kw in col: return 'ניסיון'
        for kw in SKILLS_KEYWORDS:
            if kw in col: return 'כישורים'
        return 'טוב לדעת'

    categories = {'פרטים אישיים': [], 'שעות/אופי עבודה': [], 'ניסיון': [], 'כישורים': [], 'טוב לדעת': []}

    for col in dynamic_cols:
        categories[categorize(col)].append(make_control(col))

    def build_category_section(title, controls):
        if not controls:
            return None
            
        # Determine the width based on the category title
        col_width = 200 # Default width
        if title == 'פרטים אישיים':
            col_width = 170 # Lowered by 30
        elif title == 'שעות/אופי עבודה':
            col_width = 230 # Increased by 30
            
        return ft.Container(
            content=ft.Column([
                ft.Text(title, font_family='assistant', weight="bold", size=16, color=ft.Colors.BLUE_800),
                ft.Column(controls, width=col_width, spacing=10),
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

    # ---- פופאפ פרטי תפקיד ----
    def show_profile_popup(profile_row):
        """Show a dialog with all job_profiles details for the clicked row."""
        skip_cols = {'שכר_מינימום', 'שכר_מקסימום'}

        detail_rows = []
        for col in profile_row.index:
            if col in skip_cols:
                continue
            val = profile_row[col]
            val_str = str(val).strip() if pd.notna(val) else "—"
            if val_str in ('', 'nan', 'None'):
                val_str = "—"
            detail_rows.append(
                ft.Container(
                    content=ft.Row(
                        [                            
                            ft.Text(clean_text(val_str), size=13, expand=True, text_align=ft.TextAlign.RIGHT),
                            ft.Text(f"{col}", weight="bold", size=13, color=ft.Colors.BLUE_800, width=160, text_align=ft.TextAlign.RIGHT),
                        ],
                        spacing=12,
                    ),
                    padding=ft.Padding(6, 4, 6, 4),
                    bgcolor=ft.Colors.BLUE_50 if len(detail_rows) % 2 == 0 else ft.Colors.WHITE,
                    border_radius=4,
                )
            )

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text(
                f"{profile_row.get('תפקיד', '')} — {profile_row.get('מחלקה', '')}",
                weight="bold",
                size=16,
                text_align=ft.TextAlign.RIGHT,
            ),
            content=ft.Container(
                content=ft.Column(
                    detail_rows,
                    spacing=2,
                    scroll=ft.ScrollMode.AUTO,
                ),
                width=520,
                height=460,
            ),
            actions=[
                ft.TextButton("סגור", on_click=lambda e: close_dlg(dlg)),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        def close_dlg(d):
            d.open = False
            page.update()

        page.overlay.append(dlg)
        dlg.open = True
        page.update()

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
        show_loading()
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

            for col, filter_data in filters_dict.items():
                if filter_data['type'] == 'checkbox':
                    ctrl = filter_data['control']  # Safe to extract here
                    # If UNCHECKED, show only jobs that do not require it ('לא')
                    if not ctrl.value:
                        filtered_df = filtered_df[filtered_df[col].astype(str).str.strip() == 'לא']
                        
                elif filter_data['type'] == 'dropdown':
                    ctrl = filter_data['control']  # Safe to extract here
                    if ctrl.value != ALL_OPTION:
                        df_profiles = df_profiles_ref[0]
                        all_raw = sorted(
                            {str(v).strip() for v in df_profiles[col].dropna()
                             if str(v).strip() not in ('', ALL_OPTION)}
                        )

                        def base_label(v):
                            return clean_text(v)

                        def included_indices(v):
                            own_idx = all_raw.index(v)
                            m = re.search(r'X(\d+)$', v, flags=re.IGNORECASE)
                            extra = []
                            if m:
                                extra = [int(d) - 1 for d in m.group(1)]
                            return set([own_idx] + extra)

                        selected_raw = ctrl.value
                        try:
                            accepted_indices = included_indices(selected_raw)
                            accepted_bases = {base_label(all_raw[i]) for i in accepted_indices if 0 <= i < len(all_raw)}
                        except ValueError:
                            accepted_bases = {base_label(selected_raw)}

                        filtered_df = filtered_df[
                            filtered_df[col].astype(str).str.strip().apply(base_label).isin(accepted_bases)
                        ]
                        
                elif filter_data['type'] == 'multiselect':
                    # Multiselect logic (uses 'controls' instead of 'control')
                    selected_raw_list = [v for v, cb in filter_data['controls'].items() if cb.value]
                    
                    if selected_raw_list:
                        df_profiles = df_profiles_ref[0]
                        all_raw = sorted(
                            {str(v).strip() for v in df_profiles[col].dropna()
                             if str(v).strip() not in ('', ALL_OPTION)}
                        )

                        def base_label(v):
                            return clean_text(v)

                        def included_indices(v):
                            own_idx = all_raw.index(v)
                            m = re.search(r'X(\d+)$', v, flags=re.IGNORECASE)
                            extra = []
                            if m:
                                extra = [int(d) - 1 for d in m.group(1)]
                            return set([own_idx] + extra)

                        accepted_bases = set()
                        for selected_raw in selected_raw_list:
                            try:
                                accepted_indices = included_indices(selected_raw)
                                for i in accepted_indices:
                                    if 0 <= i < len(all_raw):
                                        accepted_bases.add(base_label(all_raw[i]))
                            except ValueError:
                                accepted_bases.add(base_label(selected_raw))

                        # Filter: Keeps the row if it matches ANY of the checked options
                        filtered_df = filtered_df[
                            filtered_df[col].astype(str).str.strip().apply(base_label).isin(accepted_bases)
                        ]

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
                                        break
                    except Exception:
                        pass
                    if total > 0:
                        open_count_str = str(total)

                def make_row_handler(captured_row):
                    def on_row_select(e):
                        show_profile_popup(captured_row)
                    return on_row_select

                rows.append(
                    ft.DataRow(
                        cells=[
                            ft.DataCell(ft.Text(str(row['מחלקה']))),
                            ft.DataCell(ft.Text(str(row['תפקיד']))),
                            ft.DataCell(ft.Text(salary_str)),
                            ft.DataCell(ft.Text(open_count_str)),
                        ],
                        on_select_change=make_row_handler(row),
                    )
                )

            result_table.rows = rows
            search_button.disabled = False
            refresh_btn.disabled = False
            page.update()

            show_status(f"✔ החיפוש הושלם בהצלחה — נמצאו {count} תפקידים מתאימים")

        page.run_task(do_search)

    # ---- פונקציית רענון ----
    def refresh_data(e=None):
        show_loading()
        search_button.disabled = True
        refresh_btn.disabled = True

        async def do_refresh():
            await asyncio.sleep(0.1)
            ok, err = await asyncio.to_thread(load_data)            

            if not ok:
                show_status(f"✘ שגיאה בטעינת הנתונים: {err}", success=False)
            else:
                now = datetime.now().strftime("%H:%M:%S")
                show_status(f"✔ הנתונים עודכנו בהצלחה מקבצי האקסל ({now})")

            search_button.disabled = False
            refresh_btn.disabled = False
            page.update()

        page.run_task(do_refresh)

    def reset_filters(e):
        """Reset all filters to their default values"""
        for col, filter_data in filters_dict.items():
            if filter_data['type'] == 'checkbox':
                filter_data['control'].value = False
            elif filter_data['type'] == 'dropdown':
                filter_data['control'].value = ALL_OPTION
            elif filter_data['type'] == 'multiselect':
                for cb in filter_data['controls'].values():
                    cb.value = False
                filter_data['tile'].subtitle = None # Clear the subtitle
                
            update_filter_border(col)
        
        salary_field.value = ""
        age_field.value = ""
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
        src="/logo.png", # FIXED: Web-relative path
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
        cat_container, 
        status_bar,
        ft.Divider(),
        ft.Row([reset_button], alignment=ft.MainAxisAlignment.START),
        filters_panel,
        ft.Divider(),
        results_title,
        start_work_dd,
        ft.ListView([result_table], expand=True)
    )

# FIXED: Replaced ft.run() with ft.app() and defined assets directory
assets_path = os.path.join(BASE_DIR, "assets")
ft.run(main, assets_dir=assets_path)