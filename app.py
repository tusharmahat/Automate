import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.cell.cell import MergedCell
import math

# --- Page setup ---
st.set_page_config(page_title="Break Scheduler", layout="wide")
st.title("☕ Break Scheduler with Checker")

# --- Settings ---
break15 = timedelta(minutes=15)
break30 = timedelta(minutes=30)
stagger_gap = timedelta(minutes=0)

# --- Inputs ---
st.subheader("👨‍💼 Break Giver(s)")
givers_input = st.text_input("Enter break giver names (comma-separated)", "1,2,3,4")
givers = [g.strip() for g in givers_input.split(",") if g.strip()]

st.subheader("👥 Employees")
shift_A_input = st.text_area("Shift A Employees (comma-separated)", "1,2,3,4,5,6,7,8")
shift_B_input = st.text_area("Shift B Employees (comma-separated)", "1b,2b,3b,4b,5b,6b,7b,8b")
shift_employees = {
    "A": [e.strip() for e in shift_A_input.split(",") if e.strip()],
    "B": [e.strip() for e in shift_B_input.split(",") if e.strip()]
}

# --- Breaker max breaks ---
st.subheader("Assign number of breaks per Breaker")
giver_max_breaks = {}
cols = st.columns(len(givers))
for i, giver in enumerate(givers):
    with cols[i]:
        giver_max_breaks[giver] = st.number_input(f"Breaks for {giver}", min_value=1, max_value=20, value=4, step=1)

# --- Shift input per giver ---
st.subheader("Breaker Shift Times")
giver_shift_times = {}
for giver in givers:
    col1, col2 = st.columns(2)
    with col1:
        start_time = st.time_input(f"{giver} Shift Start", datetime.strptime("09:00", "%H:%M").time())
    with col2:
        end_time = st.time_input(f"{giver} Shift End", datetime.strptime("17:00", "%H:%M").time())
    giver_shift_times[giver] = (start_time, end_time)

# --- B-Shift start time for 1-hour delay ---
st.subheader("B-Shift Timing")
B_shift_start_time = st.time_input("B Shift Start Time (breaks start 1 hour after)", datetime.strptime("13:00", "%H:%M").time())

# --- Schedule date ---
schedule_date = st.date_input("📅 Select Schedule Date", datetime.today())

# --- Generate Schedule ---
generate = st.button("Generate Schedule")

if generate:
    st.session_state['tables'] = {}
    A_queue = shift_employees["A"].copy()
    B_queue = shift_employees["B"].copy()

    for giver in givers:
        max_breaks = giver_max_breaks[giver]
        num_A = math.ceil(max_breaks / 2)
        num_B = max_breaks - num_A

        # --- Assign employees from queues ---
        assigned_A = A_queue[:num_A]
        A_queue = A_queue[num_A:]  # remove assigned A employees

        assigned_B = []
        for _ in range(num_B):
            if B_queue:
                assigned_B.append(B_queue.pop(0))

        schedule = []
        current_time = datetime.combine(schedule_date, giver_shift_times[giver][0])

        # --- A-Shift 15-min breaks ---
        for emp in assigned_A:
            start = current_time
            end = start + break15
            schedule.append([emp, "15 min", start.strftime("%H:%M"), end.strftime("%H:%M"), ""])
            current_time = end + stagger_gap

        # --- Break giver self-break only if max_breaks >= 4 ---
        if max_breaks >= 4 and assigned_A:
            giver_break_start = current_time
            giver_break_end = giver_break_start + break30
            schedule.append([giver, "30 min (Giver)", giver_break_start.strftime("%H:%M"), giver_break_end.strftime("%H:%M"), ""])
            current_time = giver_break_end + stagger_gap

        # --- A-Shift 30-min breaks ---
        for emp in assigned_A:
            start = current_time
            end = start + break30
            schedule.append([emp, "30 min", start.strftime("%H:%M"), end.strftime("%H:%M"), ""])
            current_time = end + stagger_gap

        # --- Wait until B-shift +1 hour if necessary ---
        if assigned_B:
            B_shift_min_start = datetime.combine(schedule_date, B_shift_start_time) + timedelta(hours=1)
            if current_time < B_shift_min_start:
                current_time = B_shift_min_start

        # --- B-Shift 15-min breaks ---
        for emp in assigned_B:
            start = current_time
            end = start + break15
            schedule.append([emp, "15 min", start.strftime("%H:%M"), end.strftime("%H:%M"), ""])
            current_time = end + stagger_gap

        # --- B-Shift 30-min breaks ---
        for emp in assigned_B:
            start = current_time
            end = start + break30
            schedule.append([emp, "30 min", start.strftime("%H:%M"), end.strftime("%H:%M"), ""])
            current_time = end + stagger_gap

        # --- Total time ---
        if schedule:
            first_start = datetime.strptime(schedule[0][2], "%H:%M")
            last_end = datetime.strptime(schedule[-1][3], "%H:%M")
            total_time = last_end - first_start
            schedule.append(["", "Total Time", first_start.strftime("%H:%M"), last_end.strftime("%H:%M"), str(total_time)])

        df = pd.DataFrame(schedule, columns=["Employee", "Break Type", "Start", "End", "SA Initial"])
        st.session_state['tables'][giver] = df

    st.success("✅ Schedule generated successfully!")

# --- Display Editable Tables ---
st.subheader("📅 Editable Schedule Per Break Giver")
if 'tables' in st.session_state:
    for giver, df in st.session_state['tables'].items():
        st.markdown(f"**Breaker: {giver} | Date: {schedule_date} | Start: {giver_shift_times[giver][0]} | End: {giver_shift_times[giver][1]}**")
        edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True, key=f"editor_{giver}")
        st.session_state['tables'][giver] = edited_df

# --- Excel Export ---
st.subheader("⬇️ Download Schedule")
buffer = BytesIO()
wb = Workbook()
ws = wb.active
ws.title = "Schedule"

if 'tables' in st.session_state:
    for giver, df in st.session_state['tables'].items():
        # Table title
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

        # Data
        for r in dataframe_to_rows(df, index=False, header=False):
            ws.append(r)
        ws.append([])

# Adjust column widths
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
