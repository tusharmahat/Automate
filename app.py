import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.cell.cell import MergedCell

# --- Page setup ---
st.set_page_config(page_title="Break Scheduler with Checker", layout="wide")
st.title("☕ Break Scheduler with Giver Self-Break Pause")

# --- Settings ---
break15 = timedelta(minutes=15)
break30 = timedelta(minutes=30)

# --- Inputs ---
st.subheader("👨‍💼 Break Giver(s)")
givers_input = st.text_input("Enter break giver names (comma-separated)", "Giver1, Giver2")
givers = [g.strip() for g in givers_input.split(",") if g.strip()]

st.subheader("👥 Employees")
employees_input = st.text_area("Enter all employees (comma-separated)", "Alice, Bob, Carol, Dave, Eve, Frank")
employees = [e.strip() for e in employees_input.split(",") if e.strip()]

# --- Schedule date ---
schedule_date = st.date_input("📅 Select Schedule Date", datetime.today())

# --- Shift input per giver ---
giver_shift_times = {}
giver_employee_count = {}
for giver in givers:
    col1, col2 = st.columns(2)
    with col1:
        start_time = st.time_input(f"{giver} Shift Start", datetime.strptime("09:00", "%H:%M").time())
    with col2:
        end_time = st.time_input(f"{giver} Shift End", datetime.strptime("17:00", "%H:%M").time())
    giver_shift_times[giver] = (start_time, end_time)

    # Input number of employees to assign
    count = st.number_input(f"How many employees {giver} will cover?", min_value=1, max_value=len(employees), value=2, step=1)
    giver_employee_count[giver] = count

generate = st.button("Generate Schedule")

if generate:
    try:
        remaining_employees = employees.copy()
        schedule_tables = {}

        for giver in givers:
            table_key = f"table_{giver}"
            if not remaining_employees:
                break

            num_to_assign = min(giver_employee_count[giver], len(remaining_employees))
            emp_list = remaining_employees[:num_to_assign]
            remaining_employees = remaining_employees[num_to_assign:]

            shift_start = datetime.combine(schedule_date, giver_shift_times[giver][0])
            shift_end = datetime.combine(schedule_date, giver_shift_times[giver][1])

            # Giver self-break in the middle of their shift
            giver_break_time = shift_start + (shift_end - shift_start) / 2

            schedule = []
            current_time = shift_start

            # Loop over employees and assign breaks sequentially
            i = 0
            while i < len(emp_list):
                emp = emp_list[i]

                # If giver break overlaps, pause employee breaks
                if current_time >= giver_break_time and current_time < (giver_break_time + break30):
                    schedule.append([giver, "30 min (Giver)", current_time.strftime("%H:%M"), (current_time + break30).strftime("%H:%M"), ""])
                    current_time += break30
                    # don't increment i; keep current employee next
                    continue

                # Assign 15-min break
                schedule.append([emp, "15 min", current_time.strftime("%H:%M"), (current_time + break15).strftime("%H:%M"), ""])
                current_time += break15
                i += 1

            # Assign 30-min breaks for all employees sequentially after 15-mins
            for emp in emp_list:
                # Pause if giver break overlaps
                if current_time >= giver_break_time and current_time < (giver_break_time + break30):
                    schedule.append([giver, "30 min (Giver)", current_time.strftime("%H:%M"), (current_time + break30).strftime("%H:%M"), ""])
                    current_time += break30
                schedule.append([emp, "30 min", current_time.strftime("%H:%M"), (current_time + break30).strftime("%H:%M"), ""])
                current_time += break30

            # Calculate total time
            total_start = shift_start
            total_end = current_time
            schedule.append(["", "Total Time", total_start.strftime("%H:%M"), total_end.strftime("%H:%M"), str(total_end - total_start)])

            df = pd.DataFrame(schedule, columns=["Employee", "Break Type", "Start", "End", "SA Initial"])
            st.session_state[table_key] = df
            schedule_tables[giver] = df

        # --- Display tables ---
        st.subheader("📅 Editable Schedule Per Break Giver")
        for giver in givers:
            df = st.session_state.get(f"table_{giver}", pd.DataFrame())
            if df.empty:
                continue

            st.markdown(f"**Breaker: {giver} | Date: {schedule_date} | Start: {giver_shift_times[giver][0]} | End: {giver_shift_times[giver][1]}**")
            edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True, key=f"editor_{giver}")
            st.session_state[f"table_{giver}"] = edited_df

        # --- Excel export ---
        st.subheader("⬇️ Download Schedule")
        buffer = BytesIO()
        wb = Workbook()
        ws = wb.active
        ws.title = "Schedule"

        for giver, df in schedule_tables.items():
            if df.empty:
                continue
            ws.append([f"Breaker: {giver} | Date: {schedule_date} | Start: {giver_shift_times[giver][0]} | End: {giver_shift_times[giver][1]}"])
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

    except Exception as e:
        st.error(f"⚠️ {e}")
