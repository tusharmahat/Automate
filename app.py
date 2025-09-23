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
first_break_after = timedelta(hours=0)  # can adjust if needed
stagger_gap = timedelta(minutes=0)

# --- Inputs ---
st.subheader("👨‍💼 Break Giver(s)")
givers_input = st.text_input("Enter break giver names (comma-separated)", "Giver1, Giver2")
givers = [g.strip() for g in givers_input.split(",") if g.strip()]

st.subheader("👥 Employees (A/B Shift)")
st.markdown("Format per line: `A: Alice, Bob` or `B: Carol, Dave`")
employees_input = st.text_area("Enter employees per shift", "A: Alice, Bob\nB: Carol, Dave")

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

generate = st.button("Generate Schedule")

if generate:
    try:
        # --- Parse shift employees ---
        shift_employees = {}
        for line in employees_input.splitlines():
            if ":" in line:
                shift, emps = line.split(":")
                shift = shift.strip().upper()
                emp_list = [e.strip() for e in emps.split(",") if e.strip()]
                shift_employees[shift] = emp_list

        # --- Generate breaks per giver ---
        for giver in givers:
            table_key = f"table_{giver}"

            # Combine A then B
            emp_list = shift_employees.get("A", []) + shift_employees.get("B", [])

            if not emp_list:
                continue

            shift_start = datetime.combine(schedule_date, giver_shift_times[giver][0])
            shift_end = datetime.combine(schedule_date, giver_shift_times[giver][1])
            current_time = shift_start

            schedule = []

            # --- 15-min breaks for employees ---
            for emp in emp_list:
                start = current_time
                end = start + break15
                schedule.append([emp, "15 min", start.strftime("%H:%M"), end.strftime("%H:%M"), ""])
                current_time = end + stagger_gap

            # --- Breaker own 30-min break at midpoint ---
            mid_index = len(schedule) // 2
            breaker_start = datetime.strptime(schedule[mid_index][2], "%H:%M")
            breaker_end = breaker_start + break30
            schedule.insert(mid_index, [giver, "30 min (Giver)", breaker_start.strftime("%H:%M"), breaker_end.strftime("%H:%M"), ""])
            current_time = max(current_time, breaker_end + stagger_gap)

            # --- 30-min breaks for employees ---
            for emp in emp_list:
                start = current_time
                end = start + break30
                schedule.append([emp, "30 min", start.strftime("%H:%M"), end.strftime("%H:%M"), ""])
                current_time = end + stagger_gap

            # --- Total Time ---
            start_time_total = datetime.strptime(schedule[0][2], "%H:%M")
            end_time_total = datetime.strptime(schedule[-1][3], "%H:%M")
            total_time = end_time_total - start_time_total
            schedule.append(["", "Total Time", start_time_total.strftime("%H:%M"), end_time_total.strftime("%H:%M"), str(total_time)])

            df = pd.DataFrame(schedule, columns=["Employee", "Break Type", "Start", "End", "SA Initial"])
            st.session_state[table_key] = df

        st.success("✅ Schedule generated successfully!")

    except Exception as e:
        st.error(f"⚠️ {e}")

# --- Display editable tables ---
st.subheader("📅 Editable Schedule Per Break Giver")
for giver in givers:
    table_key = f"table_{giver}"
    df = st.session_state.get(table_key, pd.DataFrame())
    if df.empty:
        continue

    st.markdown(f"**Breaker: {giver} | Date: {schedule_date} | Start: {giver_shift_times[giver][0]} | End: {giver_shift_times[giver][1]}**")

    edited_df = st.data_editor(
        df,
        num_rows="dynamic",
        use_container_width=True,
        key=f"editor_{giver}"
    )

    st.session_state[table_key] = edited_df

# --- Excel export ---
st.subheader("⬇️ Download Schedule")
buffer = BytesIO()
wb = Workbook()
ws = wb.active
ws.title = "Schedule"

for giver in givers:
    df = st.session_state.get(f"table_{giver}", pd.DataFrame())
    if df.empty:
        continue

    # Table title
    ws.append([f"Breaker: {giver} | Date: {schedule_date} | Start: {giver_shift_times[giver][0]} | End: {giver_shift_times[giver][1]}"])
    title_row = ws.max_row
    ws.merge_cells(start_row=title_row, start_column=1, end_row=title_row, end_column=df.shape[1])
    cell = ws.cell(row=title_row, column=1)
    cell.font = Font(bold=True, color="FFFFFF")
    cell.fill = PatternFill("solid", fgColor="4F81BD")
    cell.alignment = Alignment(horizontal="center")

    # Header
    ws.append([c for c in df.columns if c != "Employee"])
    header_row = ws.max_row
    for col_num, _ in enumerate(df.columns, 1):
        c = ws.cell(row=header_row, column=col_num)
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor="D9E1F2")
        c.alignment = Alignment(horizontal="center")
        thin = Side(border_style="thin", color="000000")
        c.border = Border(top=thin, left=thin, right=thin, bottom=thin)

    # Data
    for r in dataframe_to_rows(df.drop(columns=["Employee"], errors="ignore"), index=False, header=False):
        ws.append(r)
    ws.append([])

# --- Adjust column widths ---
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
