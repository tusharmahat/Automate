import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.cell.cell import MergedCell
import math
import os
import json

# --- JSON data file ---
DATA_FILE = "break_schedule_data.json"

# --- Page setup ---
st.set_page_config(page_title="Break Scheduler", layout="wide")
st.title("☕ Break Scheduler with Checker")

# --- Settings ---
break15 = timedelta(minutes=15)
break30 = timedelta(minutes=30)
stagger_gap = timedelta(minutes=0)

# --- Load existing data ---
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        saved_data = json.load(f)
    
    # Restore tables
    st.session_state['tables'] = {giver: pd.DataFrame(df) for giver, df in saved_data.get("tables", {}).items()}
    
    # Restore form data
    form_data = saved_data.get("form_data", {})
    givers_input_default = form_data.get("givers_input", "1,2,3,4")
    shift_A_input_default = form_data.get("shift_A_input", "1,2,3,4,5,6,7,8")
    shift_B_input_default = form_data.get("shift_B_input", "1b,2b,3b,4b,5b,6b,7b,8b")
    giver_max_breaks_default = form_data.get("giver_max_breaks", {})
    giver_shift_times_default = {}
    for g, times in form_data.get("giver_shift_times", {}).items():
        start = datetime.strptime(times[0], "%H:%M:%S").time()
        end = datetime.strptime(times[1], "%H:%M:%S").time()
        giver_shift_times_default[g] = (start, end)
    B_shift_start_time_default = datetime.strptime(form_data.get("B_shift_start_time", "13:00:00"), "%H:%M:%S").time()
    schedule_date_default = datetime.strptime(form_data.get("schedule_date", str(datetime.today().date())), "%Y-%m-%d").date()
else:
    st.session_state['tables'] = {}
    givers_input_default = "1,2,3,4"
    shift_A_input_default = "1,2,3,4,5,6,7,8"
    shift_B_input_default = "1b,2b,3b,4b,5b,6b,7b,8b"
    giver_max_breaks_default = {}
    giver_shift_times_default = {}
    B_shift_start_time_default = datetime.strptime("13:00", "%H:%M").time()
    schedule_date_default = datetime.today().date()

# --- Inputs ---
st.subheader("👨‍💼 Break Giver(s)")
givers_input = st.text_input("Enter break giver names (comma-separated)", givers_input_default)
givers = [g.strip() for g in givers_input.split(",") if g.strip()]

st.subheader("👥 Employees")
shift_A_input = st.text_area("Shift A Employees (comma-separated)", shift_A_input_default)
shift_B_input = st.text_area("Shift B Employees (comma-separated)", shift_B_input_default)
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
        default_val = giver_max_breaks_default.get(giver, 4)
        giver_max_breaks[giver] = st.number_input(f"Breaks for {giver}", min_value=1, max_value=20, value=default_val, step=1)

# --- Shift input per giver ---
st.subheader("Breaker Shift Times")
giver_shift_times = {}
for giver in givers:
    col1, col2 = st.columns(2)
    with col1:
        default_start = giver_shift_times_default.get(giver, (datetime.strptime("09:00","%H:%M").time(), None))[0]
        start_time = st.time_input(f"{giver} Shift Start", default_start)
    with col2:
        default_end = giver_shift_times_default.get(giver, (None, datetime.strptime("17:00","%H:%M").time()))[1]
        end_time = st.time_input(f"{giver} Shift End", default_end)
    giver_shift_times[giver] = (start_time, end_time)

# --- B-Shift start time ---
st.subheader("B-Shift Timing")
B_shift_start_time = st.time_input("B Shift Start Time (breaks start 1 hour after)", B_shift_start_time_default)

# --- Schedule date ---
schedule_date = st.date_input("📅 Select Schedule Date", schedule_date_default)

# --- Generate Schedule ---
generate = st.button("Generate Schedule")

if generate:
    st.session_state['tables'] = {}
    A_queue = shift_employees["A"].copy()
    B_queue_all = shift_employees["B"].copy()

    for giver in givers:
        max_breaks = giver_max_breaks[giver]

        num_A = min(math.ceil(max_breaks / 2), len(A_queue))
        assigned_A = A_queue[:num_A]
        A_queue = A_queue[num_A:]

        num_B = min(max_breaks - num_A, len(B_queue_all))
        assigned_B = B_queue_all[:num_B]
        B_queue_all = B_queue_all[num_B:]

        schedule = []
        current_time = datetime.combine(schedule_date, giver_shift_times.get(giver, (datetime.strptime("09:00","%H:%M").time(), datetime.strptime("17:00","%H:%M").time()))[0])

        # A-Shift 15-min breaks
        for emp in assigned_A:
            start = current_time
            end = start + break15
            schedule.append([emp, "15 min", start.strftime("%H:%M"), end.strftime("%H:%M"), ""])
            current_time = end + stagger_gap

        # Giver self-break
        if max_breaks >= 4 and assigned_A:
            giver_start = current_time
            giver_end = giver_start + break30
            schedule.append([giver, "30 min (Giver)", giver_start.strftime("%H:%M"), giver_end.strftime("%H:%M"), ""])
            current_time = giver_end + stagger_gap

        # A-Shift 30-min breaks
        for emp in assigned_A:
            start = current_time
            end = start + break30
            schedule.append([emp, "30 min", start.strftime("%H:%M"), end.strftime("%H:%M"), ""])
            current_time = end + stagger_gap

        # Wait until B-shift +1 hour
        if assigned_B:
            B_shift_min_start = datetime.combine(schedule_date, B_shift_start_time) + timedelta(hours=1)
            if current_time < B_shift_min_start:
                current_time = B_shift_min_start

        # B-Shift 15-min breaks
        for emp in assigned_B:
            start = current_time
            end = start + break15
            schedule.append([emp, "15 min", start.strftime("%H:%M"), end.strftime("%H:%M"), ""])
            current_time = end + stagger_gap

        # B-Shift 30-min breaks
        for emp in assigned_B:
            start = current_time
            end = start + break30
            schedule.append([emp, "30 min", start.strftime("%H:%M"), end.strftime("%H:%M"), ""])
            current_time = end + stagger_gap

        # Total time summary
        if schedule:
            first_start = datetime.strptime(schedule[0][2], "%H:%M")
            last_end = datetime.strptime(schedule[-1][3], "%H:%M")
            total_time = last_end - first_start
            schedule.append(["", "Total Time", first_start.strftime("%H:%M"), last_end.strftime("%H:%M"), str(total_time)])

        df = pd.DataFrame(schedule, columns=["Employee", "Break Type", "Start", "End", "SA Initial"])
        st.session_state['tables'][giver] = df

    # --- Save everything to JSON ---
    to_save = {
        "tables": {giver: df.to_dict(orient="records") for giver, df in st.session_state['tables'].items()},
        "form_data": {
            "givers_input": givers_input,
            "shift_A_input": shift_A_input,
            "shift_B_input": shift_B_input,
            "giver_max_breaks": giver_max_breaks,
            "giver_shift_times": {g: [str(t[0]), str(t[1])] for g, t in giver_shift_times.items()},
            "B_shift_start_time": str(B_shift_start_time),
            "schedule_date": str(schedule_date)
        }
    }

    with open(DATA_FILE, "w") as f:
        json.dump(to_save, f, indent=2)

    st.success("✅ Schedule generated and saved successfully!")

# --- Editable Tables ---
st.subheader("📅 Editable Schedule Per Break Giver")
if 'tables' in st.session_state:
    for giver, df in st.session_state['tables'].items():
        start_time, end_time = giver_shift_times.get(
            giver, 
            (datetime.strptime("09:00","%H:%M").time(), datetime.strptime("17:00","%H:%M").time())
        )
        st.markdown(f"**Breaker: {giver} | Date: {schedule_date} | Start: {start_time} | End: {end_time}**")
        edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True, key=f"editor_{giver}")
        st.session_state['tables'][giver] = edited_df

    # Save edits to JSON
    to_save = {
        "tables": {giver: df.to_dict(orient="records") for giver, df in st.session_state['tables'].items()},
        "form_data": {
            "givers_input": givers_input,
            "shift_A_input": shift_A_input,
            "shift_B_input": shift_B_input,
            "giver_max_breaks": giver_max_breaks,
            "giver_shift_times": {g: [str(t[0]), str(t[1])] for g, t in giver_shift_times.items()},
            "B_shift_start_time": str(B_shift_start_time),
            "schedule_date": str(schedule_date)
        }
    }
    with open(DATA_FILE, "w") as f:
        json.dump(to_save, f, indent=2)

# --- Excel Export ---
st.subheader("⬇️ Download Schedule")
buffer = BytesIO()
wb = Workbook()

if 'tables' in st.session_state:
    for giver, df in st.session_state['tables'].items():
        ws = wb.create_sheet(title=f"{giver}_Schedule")
        start_time, end_time = giver_shift_times.get(
            giver, 
            (datetime.strptime("09:00","%H:%M").time(), datetime.strptime("17:00","%H:%M").time())
        )
        ws.append([f"Breaker: {giver} | Date: {schedule_date} | Start: {start_time} | End: {end_time}"])
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

if "Sheet" in wb.sheetnames and wb["Sheet"].max_row == 1:
    wb.remove(wb["Sheet"])

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
st.download_button(
    label="Download Excel",
    data=buffer,
    file_name="break_schedule.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
