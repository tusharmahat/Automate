import streamlit as st
import warnings
import pandas as pd
from datetime import datetime, timedelta
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

# --- Hide Python warnings ---
warnings.filterwarnings("ignore")

# --- Hide browser console warnings ---
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

generate = st.button("Generate Schedule")

if generate or "schedule" in st.session_state:
    try:
        shift_start = datetime.strptime(shift_start_str, "%H:%M")
        shift_end = datetime.strptime(shift_end_str, "%H:%M")

        giver_count = len(givers)
        giver_times = {g: shift_start + first_break_after for g in givers}

        # --- Generate schedule ---
        if "schedule" not in st.session_state or generate:
            schedule = []

            # Step 1: Assign 15-min breaks to everyone except last
            for idx, emp in enumerate(employees[:-1]):
                giver = givers[idx % giver_count]
                start = giver_times[giver]
                end = start + break15
                schedule.append([emp, giver, "15 min", start.strftime("%H:%M"), end.strftime("%H:%M"), ""])
                giver_times[giver] = end + stagger_gap

            # Step 2: Assign 30-min breaks to everyone except last
            for idx, emp in enumerate(employees[:-1]):
                giver = givers[idx % giver_count]
                start = giver_times[giver]
                end = start + break30
                if end > shift_end:
                    end = shift_end
                    start = end - break30
                schedule.append([emp, giver, "30 min", start.strftime("%H:%M"), end.strftime("%H:%M"), ""])
                giver_times[giver] = end + stagger_gap

            # Step 3 & 4: Last employee gets 30-min first, then 15-min
            last_emp = employees[-1]
            giver = givers[(len(employees)-1) % giver_count]
            start = giver_times[giver]
            end = start + break30
            if end > shift_end:
                end = shift_end
                start = end - break30
            schedule.append([last_emp, giver, "30 min", start.strftime("%H:%M"), end.strftime("%H:%M"), ""])
            giver_times[giver] = end + stagger_gap

            start = giver_times[giver]
            end = start + break15
            if end > shift_end:
                end = shift_end
                start = end - break15
            schedule.append([last_emp, giver, "15 min", start.strftime("%H:%M"), end.strftime("%H:%M"), ""])
            giver_times[giver] = end + stagger_gap

            st.session_state.schedule = pd.DataFrame(schedule, columns=["Employee", "Break Giver", "Break Type", "Start", "End", "SA Initial"])

        # --- Editable tables per giver ---
        st.subheader("📅 Editable Schedule Per Break Giver")
        edited_tables = {}
        today_str = datetime.today().strftime("%Y-%m-%d")
        for giver in givers:
            st.markdown(f"**Breaker: {giver} | Date: {today_str} | Start time: {shift_start_str}**")
            giver_df = st.session_state.schedule[st.session_state.schedule["Break Giver"] == giver].reset_index(drop=True)
            edited_df = st.data_editor(giver_df, num_rows="dynamic", use_container_width=True, key=f"editor_{giver}")
            edited_tables[giver] = edited_df

        # Merge back to session_state
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

        # --- Download Excel ---
        buffer = BytesIO()
        wb = Workbook()
        for giver, g_df in edited_tables.items():
            ws = wb.create_sheet(title=giver[:31])
            # Table title row
            ws.append([f"Breaker: {giver} | Date: {today_str} | Start time: {shift_start_str}"])
            ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=5)
            cell = ws.cell(row=1, column=1)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
            cell.alignment = Alignment(horizontal="center")

            # Column headers
            ws.append(list(g_df.columns))
            for col_cell in ws[2]:
                col_cell.font = Font(bold=True, color="FFFFFF")
                col_cell.fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
                col_cell.alignment = Alignment(horizontal="center")
                col_cell.border = Border(left=Side(style='thin'),
                                         right=Side(style='thin'),
                                         top=Side(style='thin'),
                                         bottom=Side(style='thin'))

            # Data rows
            for r in g_df.itertuples(index=False):
                ws.append(r)
            for row in ws.iter_rows(min_row=3, max_row=ws.max_row, min_col=1, max_col=5):
                for cell in row:
                    cell.border = Border(left=Side(style='thin'),
                                         right=Side(style='thin'),
                                         top=Side(style='thin'),
                                         bottom=Side(style='thin'))

        wb.remove(wb["Sheet"])
        wb.save(buffer)
        st.download_button("Download Excel (per giver)", buffer, "break_schedule.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    except Exception as e:
        st.error(f"⚠️ {e}")
