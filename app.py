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
givers_input = st.text_input("Enter break giver names (comma-separated)", "Jamie,Ainura,Gurleen,X")
givers = [g.strip() for g in givers_input.split(",") if g.strip()]

st.subheader("👥 Employees")
shift_A_input = st.text_area("Shift A Employees (comma-separated)", "Farshid,Caroll,Darin,Lisseth,Matthew,Muriel,Rogi,Zashmin")
shift_B_input = st.text_area("Shift B Employees (comma-separated)", "Sherry,Caroline,Julia,Kyle,Gurleen,Marie,Rabina,Rose")
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

    # --- Prepare queues ---
    A_queue = shift_employees["A"].copy()
    B_queue = shift_employees["B"].copy()

    # --- Initialize breaker counters ---
    breaker_counter = {giver: 0 for giver in givers}

    # --- Function to get next available breaker ---
    def get_next_breaker():
        for giver in givers:
            if breaker_counter[giver] < giver_max_breaks[giver]:
                return giver
        return None

    # --- Combine A then B queue with B-shift time adjustment ---
    combined_queue = []
    for emp in A_queue:
        combined_queue.append(("A", emp))
    for emp in B_queue:
        combined_queue.append(("B", emp))

    # --- Schedule generation ---
    schedules = {giver: [] for giver in givers}
    current_times = {giver: datetime.combine(schedule_date, giver_shift_times[giver][0]) for giver in givers}

    for shift_type, emp in combined_queue:
        giver = get_next_breaker()
        if giver is None:
            st.warning(f"No more available breaks to assign for {emp}.")
            continue

        # Adjust B shift start
        if shift_type == "B":
            b_min_start = datetime.combine(schedule_date, B_shift_start_time) + timedelta(hours=1)
            if current_times[giver] < b_min_start:
                current_times[giver] = b_min_start

        # Assign 15-min break
        start = current_times[giver]
        end = start + break15
        schedules[giver].append([emp, "15 min", start.strftime("%H:%M"), end.strftime("%H:%M"), ""])
        current_times[giver] = end + stagger_gap

        breaker_counter[giver] += 1

        # Insert self-break in middle of their assigned slots (once per giver)
        if not any(b[1].startswith(f"{giver}") and "Giver" in b[1] for b in schedules[giver]):
            mid_start = start
            mid_end = mid_start + break30
            schedules[giver].insert(len(schedules[giver])//2, [giver, "30 min (Giver)", mid_start.strftime("%H:%M"), mid_end.strftime("%H:%M"), ""])
            current_times[giver] = max(current_times[giver], mid_end + stagger_gap)

    # --- Convert to DataFrames ---
    for giver in givers:
        df = pd.DataFrame(schedules[giver], columns=["Employee", "Break Type", "Start", "End", "SA Initial"])
        if not df.empty:
            first_start = datetime.strptime(df.iloc[0]['Start'], "%H:%M")
            last_end = datetime.strptime(df.iloc[-1]['End'], "%H:%M")
            total_time = last_end - first_start
            df.loc[len(df)] = ["", "Total Time", first_start.strftime("%H:%M"), last_end.strftime("%H:%M"), str(total_time)]
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
