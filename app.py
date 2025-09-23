import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.cell.cell import MergedCell

# --- Page setup ---
st.set_page_config(page_title="Break Scheduler", layout="wide")
st.title("☕ Break Scheduler with Checker")

# --- Settings ---
break15 = timedelta(minutes=15)
break30 = timedelta(minutes=30)
first_break_after = timedelta(hours=0)  # Start immediately
stagger_gap = timedelta(minutes=0)

# --- Inputs ---
st.subheader("👨‍💼 Break Giver(s)")
givers_input = st.text_input("Enter break giver names (comma-separated)", "Jamie, Ainura")
givers = [g.strip() for g in givers_input.split(",") if g.strip()]

st.subheader("👥 Employees (with shift, e.g., A: Alice, Bob)")
employees_input = st.text_area("Enter employees per shift", "A: Farshid, Caroll, Darin\nB: Lisseth, Sherry, Caroline, Gurleen, Julia")

# --- Schedule date ---
schedule_date = st.date_input("📅 Select Schedule Date", datetime.today())

# --- Shift input per giver ---
giver_shift_times = {}
giver_employee_count = {}
for giver in givers:
    st.subheader(f"{giver} info")
    col1, col2, col3 = st.columns(3)
    with col1:
        start_time = st.time_input(f"{giver} Shift Start", datetime.strptime("09:00", "%H:%M").time())
    with col2:
        end_time = st.time_input(f"{giver} Shift End", datetime.strptime("17:00", "%H:%M").time())
    with col3:
        count = st.number_input(f"Number of employees {giver} covers", min_value=1, value=5)
    giver_shift_times[giver] = (start_time, end_time)
    giver_employee_count[giver] = count

generate = st.button("Generate Schedule")

if generate:
    try:
        # --- Parse employees per shift ---
        shift_employees = {}
        for line in employees_input.splitlines():
            if ':' in line:
                shift, names = line.split(':', 1)
                shift_employees[shift.strip()] = [n.strip() for n in names.split(',') if n.strip()]

        # --- Flatten employees, prioritizing A then B ---
        ordered_employees = []
        for shift in sorted(shift_employees.keys()):
            ordered_employees.extend(shift_employees[shift])
        remaining_employees = ordered_employees.copy()

        st.session_state['tables'] = {}

        # --- Generate schedule per giver ---
        for giver in givers:
            emp_count = giver_employee_count[giver]
            shift_start = datetime.combine(schedule_date, giver_shift_times[giver][0])
            shift_end = datetime.combine(schedule_date, giver_shift_times[giver][1])

            emp_list = remaining_employees[:emp_count]
            remaining_employees = remaining_employees[emp_count:]

            if not emp_list:
                continue

            # Initialize break times
            schedule = []
            current_time = shift_start

            # --- 15-min break for each employee ---
            for emp in emp_list[:-1]:
                start = current_time
                end = start + break15
                schedule.append([emp, "15 min", start.strftime("%H:%M"), end.strftime("%H:%M"), ""])
                current_time = end + stagger_gap

            # --- Last employee 30-min ---
            last_emp = emp_list[-1]
            start = current_time
            end = start + break30
            schedule.append([last_emp, "30 min", start.strftime("%H:%M"), end.strftime("%H:%M"), ""])
            current_time = end + stagger_gap

            # --- Giver takes self-break in the middle ---
            mid_break_start = shift_start + (shift_end - shift_start)/2
            mid_break_end = mid_break_start + break30
            schedule.append([giver, "30 min (Giver)", mid_break_start.strftime("%H:%M"), mid_break_end.strftime("%H:%M"), ""])
            # After self-break, continue scheduling remaining 30-min breaks
            for emp in emp_list[:-1]:
                start = max(current_time, mid_break_end)
                end = start + break30
                schedule.append([emp, "30 min", start.strftime("%H:%M"), end.strftime("%H:%M"), ""])
                current_time = end + stagger_gap

            # --- Last employee 15-min ---
            start = max(current_time, mid_break_end)
            end = start + break15
            schedule.append([last_emp, "15 min", start.strftime("%H:%M"), end.strftime("%H:%M"), ""])

            # Compute total time
            total_start = shift_start.strftime("%H:%M")
            total_end = max([datetime.strptime(r[3], "%H:%M") for r in schedule]).strftime("%H:%M")
            total_duration = max([datetime.strptime(r[3], "%H:%M") for r in schedule]) - shift_start

            df = pd.DataFrame(schedule, columns=["Employee", "Break Type", "Start", "End", "SA Initial"])
            st.session_state['tables'][giver] = (df, total_start, total_end, total_duration)

        st.success("✅ Schedule generated!")

    except Exception as e:
        st.error(f"⚠️ {e}")

# --- Display editable tables ---
st.subheader("📅 Editable Schedule Per Break Giver")
if 'tables' in st.session_state:
    for giver, data in st.session_state['tables'].items():
        df, total_start, total_end, total_duration = data
        st.markdown(f"**Breaker: {giver} | Date: {schedule_date} | Start: {giver_shift_times[giver][0]} | End: {giver_shift_times[giver][1]} | Total: {total_duration}**")

        edited_df = st.data_editor(
            df,
            num_rows="dynamic",
            use_container_width=True,
            key=f"editor_{giver}"
        )
        st.session_state['tables'][giver] = (edited_df, total_start, total_end, total_duration)

# --- Excel export ---
st.subheader("⬇️ Download Schedule")
buffer = BytesIO()
wb = Workbook()
ws = wb.active
ws.title = "Schedule"

if 'tables' in st.session_state:
    for giver, data in st.session_state['tables'].items():
        df, total_start, total_end, total_duration = data
        ws.append([f"Breaker: {giver} | Date: {schedule_date} | Start: {giver_shift_times[giver][0]} | End: {giver_shift_times[giver][1]} | Total: {total_duration}"])
        title_row = ws.max_row
        ws.merge_cells(start_row=title_row, start_column=1, end_row=title_row, end_column=df.shape[1])
        cell = ws.cell(row=title_row, column=1)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="4F81BD")
        cell.alignment = Alignment(horizontal="center")

        ws.append(df.columns.tolist())
        header_row = ws.max_row
        for col_num, _ in enumerate(df.columns, 1):
            c = ws.cell(row=header_row, column=col_num)
            c.font = Font(bold=True)
            c.fill = PatternFill("solid", fgColor="D9E1F2")
            c.alignment = Alignment(horizontal="center")
            thin = Side(border_style="thin", color="000000")
            c.border = Border(top=thin, left=thin, right=thin, bottom=thin)

        for r in dataframe_to_rows(df, index=False, header=False):
            ws.append(r)
        ws.append([])

for ws in wb.worksheets:
    for col_cells in ws.columns:
        max_length = 0
        col_letter = None
        for cell in col_cells:
            if not isinstance(cell, MergedCell):
                col_letter = cell.column_letter
                break
        if not col_letter:
            continue
        for cell in col_cells:
            if cell.value and not isinstance(cell, MergedCell):
                max_length = max(max_length, len(str(cell.value)))
        ws.column_dimensions[col_letter].width = max_length + 2

wb.save(buffer)
st.download_button("Download Excel", buffer, "break_schedule.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
