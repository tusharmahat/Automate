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

    A_queue = shift_employees["A"].copy()
    B_queue = shift_employees["B"].copy()

    # --- Split employees per breaker ---
    breaker_assignments = {}
    for giver in givers:
        max_breaks = giver_max_breaks[giver]
        num_A = math.ceil(max_breaks / 2)
        num_B = max_breaks - num_A
        assigned_A = A_queue[:num_A]
        assigned_B = B_queue[:num_B]
        A_queue = A_queue[num_A:]
        B_queue = B_queue[num_B:]
        breaker_assignments[giver] = {"A": assigned_A, "B": assigned_B}

    for giver in givers:
        schedule = []
        current_time = datetime.combine(schedule_date, giver_shift_times[giver][0])
        assigned_A = breaker_assignments[giver]["A"]
        assigned_B = breaker_assignments[giver]["B"]

        # --- 15-min breaks for A ---
        for emp in assigned_A:
            start = current_time
            end = start + break15
            schedule.append([emp, "15 min", start.strftime("%H:%M"), end.strftime("%H:%M"), ""])
            current_time = end + stagger_gap

        # --- Insert Giver 30-min break in middle of A-shift ---
        if assigned_A:
            mid_index = len(schedule) // 2
            mid_start = datetime.strptime(schedule[mid_index][2], "%H:%M")
            mid_end = mid_start + break30
            schedule.insert(mid_index, [giver, "30 min (Giver)", mid_start.strftime("%H:%M"), mid_end.strftime("%H:%M"), ""])
            current_time = max(current_time, mid_end + stagger_gap)

        # --- 30-min breaks for A-shift employees ---
        for emp in assigned_A:
            start = current_time
            end = start + break30
            schedule.append([emp, "30 min", start.strftime("%H:%M"), end.strftime("%H:%M"), ""])
            current_time = end + stagger_gap

        # --- Wait for B shift start + 1 hour ---
        if assigned_B:
            b_min_start = datetime.combine(schedule_date, B_shift_start_time) + timedelta(hours=1)
            if current_time < b_min_start:
                current_time = b_min_start

        # --- 15-min breaks for B ---
        for emp in assigned_B:
            start = current_time
            end = start + break15
            schedule.append([emp, "15 min", start.strftime("%H:%M"), end.strftime("%H:%M"), ""])
            current_time = end + stagger_gap

        # --- 30-min breaks for B-shift employees ---
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
