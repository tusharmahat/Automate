import streamlit as st
import warnings
import pandas as pd
from datetime import datetime, timedelta
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

# --- Hide warnings ---
warnings.filterwarnings("ignore")

hide_console_warning = """
<script>
console.warn = () => {};
console.error = () => {};
</script>
"""
st.components.v1.html(hide_console_warning)

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

col1, col2 = st.columns(2)
with col1:
    shift_start_str = st.text_input("Shift Start (HH:MM)", "09:00")
with col2:
    shift_end_str = st.text_input("Shift End (HH:MM)", "17:00")

date_str = st.date_input("Date")
generate = st.button("Generate Schedule")

# --- Generate / persist schedule ---
if generate or "schedule" in st.session_state:
    try:
        shift_start = datetime.strptime(shift_start_str, "%H:%M")
        shift_end = datetime.strptime(shift_end_str, "%H:%M")

        # Only regenerate if button pressed
        if "schedule" not in st.session_state or generate:
            schedule = []

            for giver in givers:
                giver_time = shift_start + first_break_after

                # 15-min for all except last employee
                for emp in employees[:-1]:
                    start = giver_time
                    end = start + break15
                    schedule.append([emp, giver, "15 min", start.strftime("%H:%M"), end.strftime("%H:%M"), ""])
                    giver_time = end + stagger_gap

                # Last employee 30-min first
                last_emp = employees[-1]
                start = giver_time
                end = start + break30
                schedule.append([last_emp, giver, "30 min", start.strftime("%H:%M"), end.strftime("%H:%M"), ""])
                giver_time = end + stagger_gap

                # 30-min for all except last
                for emp in employees[:-1]:
                    start = giver_time
                    end = start + break30
                    schedule.append([emp, giver, "30 min", start.strftime("%H:%M"), end.strftime("%H:%M"), ""])
                    giver_time = end + stagger_gap

                # Last employee 15-min last
                start = giver_time
                end = start + break15
                schedule.append([last_emp, giver, "15 min", start.strftime("%H:%M"), end.strftime("%H:%M"), ""])

            st.session_state.schedule = pd.DataFrame(
                schedule, columns=["Employee", "Break Giver", "Break Type", "Start", "End", "SA Initial"]
            )

        # --- Editable tables per giver ---
        st.subheader("📅 Editable Schedule Per Break Giver")
        edited_tables = {}
        for giver in givers:
            st.markdown(f"### Breaker: {giver} | Date: {date_str} | Start time: {shift_start_str}")
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
        for giver, df in edited_tables.items():
            ws = wb.create_sheet(title=giver[:31])
            # Title row
            title = f"Breaker: {giver} | Date: {date_str} | Start time: {shift_start_str}"
            ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(df.columns))
            cell = ws.cell(row=1, column=1, value=title)
            cell.font = Font(bold=True, size=12, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="4F81BD")
            cell.alignment = Alignment(horizontal="center")

            # Header row
            for col_idx, col in enumerate(df.columns, 1):
                c = ws.cell(row=2, column=col_idx, value=col)
                c.font = Font(bold=True)
                c.fill = PatternFill("solid", fgColor="BDD7EE")
                c.alignment = Alignment(horizontal="center")
                c.border = Border(left=Side(style='thin'), right=Side(style='thin'),
                                  top=Side(style='thin'), bottom=Side(style='thin'))

            # Data rows
            for r_idx, row in enumerate(df.itertuples(index=False), 3):
                for c_idx, value in enumerate(row, 1):
                    c = ws.cell(row=r_idx, column=c_idx, value=value)
                    c.alignment = Alignment(horizontal="center")
                    c.border = Border(left=Side(style='thin'), right=Side(style='thin'),
                                      top=Side(style='thin'), bottom=Side(style='thin'))

            # Adjust column widths
            for col_idx, col in enumerate(df.columns, 1):
                ws.column_dimensions[chr(64+col_idx)].width = max(12, len(col)+2)

        # Remove default sheet
        if "Sheet" in wb.sheetnames:
            wb.remove(wb["Sheet"])
        wb.save(buffer)
        st.download_button("Download Excel (per giver)", buffer, "break_schedule.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    except Exception as e:
        st.error(f"⚠️ {e}")
