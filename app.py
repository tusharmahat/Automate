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
stagger_gap = timedelta(minutes=0)

# --- Inputs ---
st.subheader("👨‍💼 Break Giver(s)")
givers_input = st.text_input("Enter break giver names (comma-separated)", "Giver1, Giver2")
givers = [g.strip() for g in givers_input.split(",") if g.strip()]

st.subheader("👥 Employees")
employees_input = st.text_area("Enter all employees (comma-separated)", "Alice, Bob, Carol, Dave")
employees = [e.strip() for e in employees_input.split(",") if e.strip()]

# --- Schedule date ---
schedule_date = st.date_input("📅 Select Schedule Date", datetime.today())

# --- Shift input per giver ---
giver_shift_times = {}
for giver in givers:
    col1, col2 = st.columns(2)
    with col1:
        start_time = st.time_input(f"{giver} Shift Start", datetime.strptime("09:00", "%H:%M").time())
    with col2:
        end_time = st.time_input(f"{giver} Shift End", datetime.strptime("17:00", "%H:%M").time())
    giver_shift_times[giver] = (start_time, end_time)

# --- Employees per giver input ---
st.subheader("👥 Employees per Break Giver")
num_emp_per_giver = {}
remaining_employees = employees.copy()
for giver in givers:
    max_val = len(remaining_employees)
    num_emp = st.number_input(f"Number of employees {giver} gives break to", min_value=1, max_value=max_val, value=min(1, max_val))
    num_emp_per_giver[giver] = num_emp
    remaining_employees = remaining_employees[num_emp:]  # assign employees in order

generate = st.button("Generate Schedule")

if generate:
    try:
        # --- Assign employees per giver ---
        distributed = {}
        emp_index = 0
        for giver in givers:
            count = num_emp_per_giver[giver]
            distributed[giver] = employees[emp_index: emp_index + count]
            emp_index += count

        # --- Generate schedule ---
        st.session_state['schedules'] = {}
        for giver in givers:
            emp_list = distributed[giver]
            if not emp_list:
                continue

            table_key = f"table_{giver}"
            shift_start = datetime.combine(schedule_date, giver_shift_times[giver][0])
            shift_end = datetime.combine(schedule_date, giver_shift_times[giver][1])
            current_time = shift_start

            schedule = []

            # --- 15-min breaks for all except last employee ---
            for emp in emp_list[:-1]:
                start = current_time
                end = start + break15
                schedule.append([emp, "15 min", start.strftime("%H:%M"), end.strftime("%H:%M"), ""])
                current_time = end + stagger_gap

            # --- Last employee 30-min first ---
            last_emp = emp_list[-1]
            start = current_time
            end = start + break30
            schedule.append([last_emp, "30 min", start.strftime("%H:%M"), end.strftime("%H:%M"), ""])
            current_time = end + stagger_gap

            # --- Insert break giver's own 30-min break in the middle ---
            if len(schedule) > 1:
                middle_index = len(schedule) // 2
                giver_break_start_dt = datetime.strptime(schedule[middle_index][3], "%H:%M")
                giver_break_end_dt = giver_break_start_dt + break30
                schedule.insert(middle_index, [giver, "30 min (Giver)", 
                                               giver_break_start_dt.strftime("%H:%M"), 
                                               giver_break_end_dt.strftime("%H:%M"), ""])
                current_time = giver_break_end_dt + stagger_gap

            # --- 30-min breaks for others ---
            for emp in emp_list[:-1]:
                start = current_time
                end = start + break30
                schedule.append([emp, "30 min", start.strftime("%H:%M"), end.strftime("%H:%M"), ""])
                current_time = end + stagger_gap

            # --- Last employee 15-min break ---
            start = current_time
            end = start + break15
            schedule.append([last_emp, "15 min", start.strftime("%H:%M"), end.strftime("%H:%M"), ""])

            # --- Calculate total time ---
            total_start = datetime.strptime(schedule[0][2], "%H:%M")
            total_end = datetime.strptime(schedule[-1][3], "%H:%M")
            total_duration = total_end - total_start
            schedule.append(["", "Total Time", total_start.strftime("%H:%M"), total_end.strftime("%H:%M"), str(total_duration)])

            df = pd.DataFrame(schedule, columns=["Employee", "Break Type", "Start", "End", "SA Initial"])
            st.session_state['schedules'][giver] = df

        st.success("✅ Schedule generated successfully!")

    except Exception as e:
        st.error(f"⚠️ {e}")

# --- Display editable tables ---
st.subheader("📅 Editable Schedule Per Break Giver")
if 'schedules' in st.session_state:
    for giver, df in st.session_state['schedules'].items():
        st.markdown(f"**Breaker: {giver} | Date: {schedule_date} | Start: {giver_shift_times[giver][0]} | End: {giver_shift_times[giver][1]}**")
        edited_df = st.data_editor(
            df,
            num_rows="dynamic",
            use_container_width=True,
            key=f"editor_{giver}"
        )
        st.session_state['schedules'][giver] = edited_df

# --- Excel export ---
st.subheader("⬇️ Download Schedule")
if 'schedules' in st.session_state:
    buffer = BytesIO()
    wb = Workbook()
    ws = wb.active
    ws.title = "Schedule"

    for giver, df in st.session_state['schedules'].items():
        if df.empty:
            continue
        # Title row
        ws.append([f"Breaker: {giver} | Date: {schedule_date} | Start: {giver_shift_times[giver][0]} | End: {giver_shift_times[giver][1]}"])
        title_row = ws.max_row
        ws.merge_cells(start_row=title_row, start_column=1, end_row=title_row, end_column=df.shape[1])
        cell = ws.cell(row=title_row, column=1)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="4F81BD")
        cell.alignment = Alignment(horizontal="center")

        # Header
        ws.append(df.columns.tolist())
        header_row = ws.max_row
        for col_num, _ in enumerate(df.columns, 1):
            c = ws.cell(row=header_row, column=col_num)
            c.font = Font(bold=True)
            c.fill = PatternFill("solid", fgColor="D9E1F2")
            c.alignment = Alignment(horizontal="center")
            thin = Side(border_style="thin", color="000000")
            c.border = Border(top=thin, left=thin, right=thin, bottom=thin)

        # Data without break giver column
        export_df = df.copy()
        if "Employee" in export_df.columns:
            export_df = export_df.drop(columns=["Employee"])

        for r in dataframe_to_rows(export_df, index=False, header=False):
            ws.append(r)
        ws.append([])

    # Adjust column widths
    for ws_ in wb.worksheets:
        for col_cells in ws_.columns:
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
            ws_.column_dimensions[col_letter].width = max_length + 2

    wb.save(buffer)
    st.download_button("Download Excel", buffer, "break_schedule.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
