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
first_break_after = timedelta(hours=2)
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

# Shift input per giver
giver_shift_times = {}
for giver in givers:
    col1, col2 = st.columns(2)
    with col1:
        start_str = st.time_input(f"{giver} Shift Start", datetime.strptime("09:00", "%H:%M").time())
    with col2:
        end_str = st.time_input(f"{giver} Shift End", datetime.strptime("17:00", "%H:%M").time())
    giver_shift_times[giver] = (start_str, end_str)

generate = st.button("Generate Schedule")

if generate:
    try:
        today_str = schedule_date.strftime("%Y-%m-%d")
        schedule_tables = {}

        # --- Distribute employees evenly to givers ---
        distributed = {g: [] for g in givers}
        for i, emp in enumerate(employees):
            giver = givers[i % len(givers)]
            distributed[giver].append(emp)

        # --- Generate breaks for each giver ---
        for giver in givers:
            emp_list = distributed[giver]
            if not emp_list:
                continue

            shift_start = datetime.combine(schedule_date, giver_shift_times[giver][0])
            shift_end = datetime.combine(schedule_date, giver_shift_times[giver][1])
            giver_time = {emp: shift_start + first_break_after for emp in emp_list}

            schedule = []

            # --- 15-min breaks for all except last ---
            for emp in emp_list[:-1]:
                start = giver_time[emp]
                end = start + break15
                schedule.append([emp, "15 min", start.strftime("%H:%M"), end.strftime("%H:%M"), ""])
                giver_time[emp] = end + stagger_gap

            # --- Last employee 30-min first ---
            last_emp = emp_list[-1]
            start = giver_time[last_emp]
            end = start + break30
            schedule.append([last_emp, "30 min", start.strftime("%H:%M"), end.strftime("%H:%M"), ""])
            giver_time[last_emp] = end + stagger_gap

            # --- 30-min breaks for others ---
            for emp in emp_list[:-1]:
                start = giver_time[emp]
                end = start + break30
                schedule.append([emp, "30 min", start.strftime("%H:%M"), end.strftime("%H:%M"), ""])
                giver_time[emp] = end + stagger_gap

            # --- Last employee 15-min ---
            start = giver_time[last_emp]
            end = start + break15
            schedule.append([last_emp, "15 min", start.strftime("%H:%M"), end.strftime("%H:%M"), ""])

            df = pd.DataFrame(schedule, columns=["Employee", "Break Type", "Start", "End", "SA Initial"])
            schedule_tables[giver] = df
            st.session_state[f"table_{giver}"] = df  # persist table

        # --- Editable tables ---
        st.subheader("📅 Editable Schedule Per Break Giver")
        for giver in givers:
            df = st.session_state.get(f"table_{giver}", pd.DataFrame())
            if df.empty:
                continue

            st.markdown(f"**Breaker: {giver} | Date: {today_str} | Start: {giver_shift_times[giver][0]} | End: {giver_shift_times[giver][1]}**")

            edited_df = st.data_editor(
                df,
                num_rows="dynamic",
                use_container_width=True,
                key=f"editor_{giver}"
            )

            # save edits back
            st.session_state[f"table_{giver}"] = edited_df

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
            ws.append([f"Breaker: {giver} | Date: {today_str} | Start: {giver_shift_times[giver][0]} | End: {giver_shift_times[giver][1]}"])
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

            # Data with alternating row colors
            fill_colors = ["FFFFFF", "F2F2F2"]
            for i, r in enumerate(dataframe_to_rows(df, index=False, header=False)):
                ws.append(r)
                for j in range(1, len(r)+1):
                    cell = ws.cell(row=ws.max_row, column=j)
                    cell.alignment = Alignment(horizontal="center")
                    cell.fill = PatternFill("solid", fgColor=fill_colors[i % 2])

            ws.append([])  # blank row between tables

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

    except Exception as e:
        st.error(f"⚠️ {e}")
