import streamlit as st
import warnings
import pandas as pd
from datetime import datetime, timedelta
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill

# --- Hide warnings ---
warnings.filterwarnings("ignore")
st.components.v1.html("<script>console.warn = () => {}; console.error = () => {};</script>")

# --- Page setup ---
st.set_page_config(page_title="Break Scheduler", layout="wide")
st.title("☕ Break Scheduler with Checker")

# --- Settings ---
st.sidebar.header("⚙️ Break Settings")
break15 = timedelta(minutes=15)
break30 = timedelta(minutes=30)
first_break_after = timedelta(hours=2)
stagger_gap = timedelta(minutes=0)

# --- Inputs ---
st.subheader("👨‍💼 Break Giver(s)")
givers_input = st.text_input("Enter break giver names (comma-separated)", "Giver1, Giver2")
givers = [g.strip() for g in givers_input.split(",") if g.strip()]

st.subheader("👥 Employees")
employees_input = st.text_area("Enter employee names (comma-separated)", "Alice, Bob, Carol, Dave")
employees = [e.strip() for e in employees_input.split(",") if e.strip()]

# Break giver start/end times input
giver_times = {}
st.subheader("⏰ Break Giver Schedule")
for giver in givers:
    col1, col2 = st.columns(2)
    with col1:
        start_str = st.text_input(f"{giver} Start (HH:MM)", "09:00", key=f"{giver}_start")
    with col2:
        end_str = st.text_input(f"{giver} End (HH:MM)", "17:00", key=f"{giver}_end")
    giver_times[giver] = [datetime.strptime(start_str, "%H:%M"), datetime.strptime(end_str, "%H:%M")]

generate = st.button("Generate Schedule")

# --- Generate / persist schedule ---
if generate or "schedule" in st.session_state:
    try:
        # Only regenerate if missing or button pressed
        if "schedule" not in st.session_state or generate:
            schedule = []

            # Assign breaks per employee sequentially
            for emp_idx, emp in enumerate(employees):
                for giver in givers:
                    start_time, shift_end = giver_times[giver]

                    # 15-min break
                    start_15 = start_time + first_break_after + timedelta(minutes=emp_idx * 15)
                    end_15 = start_15 + break15
                    if end_15 > shift_end:
                        end_15 = shift_end
                        start_15 = end_15 - break15
                    schedule.append([emp, giver, "15 min", start_15.strftime("%H:%M"), end_15.strftime("%H:%M"), ""])

                    # 30-min break (after 15-min)
                    start_30 = end_15 + timedelta(minutes=5)  # small gap
                    end_30 = start_30 + break30
                    if end_30 > shift_end:
                        end_30 = shift_end
                        start_30 = end_30 - break30
                    schedule.append([emp, giver, "30 min", start_30.strftime("%H:%M"), end_30.strftime("%H:%M"), ""])

            st.session_state.schedule = pd.DataFrame(
                schedule, columns=["Employee", "Break Giver", "Break Type", "Start", "End", "SA Initial"]
            )

        # --- Editable tables per giver ---
        st.subheader("📅 Editable Schedule Per Break Giver")
        edited_tables = {}
        today_str = datetime.today().strftime("%Y-%m-%d")

        for giver in givers:
            st.markdown(f"### Breaker: {giver} | Date: {today_str} | Start time: {giver_times[giver][0].strftime('%H:%M')}")
            giver_df = st.session_state.schedule[st.session_state.schedule["Break Giver"] == giver].reset_index(drop=True)
            edited_df = st.data_editor(giver_df, num_rows="dynamic", use_container_width=True, key=f"editor_{giver}")
            edited_tables[giver] = edited_df

        st.session_state.schedule = pd.concat(edited_tables.values(), ignore_index=True)

        # --- Checker ---
        warning_employees = []
        for emp in employees:
            emp_breaks = st.session_state.schedule[st.session_state.schedule["Employee"] == emp]["Break Type"].tolist()
            if "15 min" not in emp_breaks or "30 min" not in emp_breaks:
                warning_employees.append(emp)
        if warning_employees:
            st.warning(f"⚠️ The following employees are missing breaks: {', '.join(warning_employees)}")
        else:
            st.success("✅ All employees have both 15-min and 30-min breaks assigned.")

        # --- Download CSV ---
        st.subheader("⬇️ Download Schedule")
        csv = st.session_state.schedule.to_csv(index=False).encode("utf-8")
        st.download_button("Download CSV", csv, "break_schedule.csv", "text/csv")

        # --- Download Excel with beautification ---
        buffer = BytesIO()
        wb = Workbook()
        for giver, g_df in edited_tables.items():
            ws = wb.create_sheet(title=giver[:31])
            # Title row
            ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(g_df.columns))
            title_cell = ws.cell(row=1, column=1)
            title_cell.value = f"Breaker: {giver} | Date: {today_str} | Start time: {giver_times[giver][0].strftime('%H:%M')}"
            title_cell.font = Font(bold=True, size=12)
            title_cell.alignment = Alignment(horizontal="center")

            # Header row
            for col_idx, col_name in enumerate(g_df.columns, start=1):
                cell = ws.cell(row=2, column=col_idx)
                cell.value = col_name
                cell.font = Font(bold=True)
                cell.fill = PatternFill("solid", fgColor="DDDDDD")
                cell.alignment = Alignment(horizontal="center")
                thin = Side(border_style="thin", color="000000")
                cell.border = Border(top=thin, left=thin, right=thin, bottom=thin)

            # Data rows
            for r_idx, row in g_df.iterrows():
                for c_idx, value in enumerate(row, start=1):
                    cell = ws.cell(row=r_idx+3, column=c_idx)
                    cell.value = value
                    cell.alignment = Alignment(horizontal="center")
                    cell.border = Border(top=thin, left=thin, right=thin, bottom=thin)

            # Autofit columns
            for col_idx, col_cells in enumerate(ws.columns, start=1):
                max_length = max(len(str(cell.value)) if cell.value else 0 for cell in col_cells) + 2
                ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = max_length

        # Remove default sheet if empty
        if "Sheet" in wb.sheetnames and wb["Sheet"].max_row == 1:
            wb.remove(wb["Sheet"])

        wb.save(buffer)
        st.download_button("Download Excel (per giver, beautified)", buffer, "break_schedule.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    except Exception as e:
        st.error(f"⚠️ {e}")
