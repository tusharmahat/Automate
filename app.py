import streamlit as st
import warnings
import pandas as pd
from datetime import datetime, timedelta
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

# --- Hide warnings ---
warnings.filterwarnings("ignore")

# --- Hide console warnings ---
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

st_date = st.date_input("Schedule Date", datetime.today())
generate = st.button("Generate Schedule")

# --- Generate / persist schedule ---
if generate or "schedule" in st.session_state:
    try:
        shift_start = datetime.strptime(shift_start_str, "%H:%M")
        shift_end = datetime.strptime(shift_end_str, "%H:%M")
        giver_times = {g: shift_start for g in givers}

        if "schedule" not in st.session_state or generate:
            schedule = []

            for idx, emp in enumerate(employees):
                giver = givers[idx % len(givers)]
                start_time = giver_times[giver]

                if idx == len(employees) - 1:  # last employee
                    # 30-min first
                    start_30 = start_time + first_break_after
                    end_30 = start_30 + break30
                    if end_30 > shift_end:
                        end_30 = shift_end
                        start_30 = end_30 - break30
                    schedule.append([emp, giver, "30 min", start_30.strftime("%H:%M"), end_30.strftime("%H:%M"), ""])
                    giver_times[giver] = end_30 + stagger_gap

                    # 15-min last
                    start_15 = giver_times[giver]
                    end_15 = start_15 + break15
                    if end_15 > shift_end:
                        end_15 = shift_end
                        start_15 = end_15 - break15
                    schedule.append([emp, giver, "15 min", start_15.strftime("%H:%M"), end_15.strftime("%H:%M"), ""])
                    giver_times[giver] = end_15 + stagger_gap
                else:
                    # 15-min first
                    start_15 = start_time + first_break_after
                    end_15 = start_15 + break15
                    schedule.append([emp, giver, "15 min", start_15.strftime("%H:%M"), end_15.strftime("%H:%M"), ""])
                    giver_times[giver] = end_15 + stagger_gap

                    # 30-min second
                    start_30 = giver_times[giver]
                    end_30 = start_30 + break30
                    if end_30 > shift_end:
                        end_30 = shift_end
                        start_30 = end_30 - break30
                    schedule.append([emp, giver, "30 min", start_30.strftime("%H:%M"), end_30.strftime("%H:%M"), ""])
                    giver_times[giver] = end_30 + stagger_gap

            st.session_state.schedule = pd.DataFrame(
                schedule, columns=["Employee", "Break Giver", "Break Type", "Start", "End", "SA Initial"]
            )

        # --- Editable tables per giver ---
        st.subheader("📅 Editable Schedule Per Break Giver")
        edited_tables = {}
        for giver in givers:
            st.markdown(f"### Breaker: {giver} | Date: {st_date} | Start time: {shift_start_str}")
            giver_df = st.session_state.schedule[st.session_state.schedule["Break Giver"] == giver].reset_index(drop=True)
            edited_df = st.data_editor(giver_df, num_rows="dynamic", use_container_width=True, key=f"editor_{giver}")
            edited_tables[giver] = edited_df

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

        # --- Download Excel (Beautified) ---
        buffer = BytesIO()
        wb = Workbook()

        for giver, df in edited_tables.items():
            ws = wb.create_sheet(title=giver[:31])
            # Title row
            ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(df.columns))
            ws["A1"] = f"Breaker: {giver} | Date: {st_date} | Start time: {shift_start_str}"
            ws["A1"].font = Font(bold=True, size=12)
            ws["A1"].alignment = Alignment(horizontal="center")
            ws["A1"].fill = PatternFill("solid", fgColor="DDDDDD")

            # Header row
            for col_idx, col_name in enumerate(df.columns, 1):
                cell = ws.cell(row=2, column=col_idx, value=col_name)
                cell.font = Font(bold=True)
                cell.alignment = Alignment(horizontal="center")
                cell.fill = PatternFill("solid", fgColor="CCCCFF")
                cell.border = Border(left=Side(style="thin"), right=Side(style="thin"),
                                     top=Side(style="thin"), bottom=Side(style="thin"))

            # Data rows
            for r_idx, row in df.iterrows():
                for c_idx, value in enumerate(row, 1):
                    cell = ws.cell(row=r_idx + 3, column=c_idx, value=value)
                    cell.alignment = Alignment(horizontal="center")
                    cell.border = Border(left=Side(style="thin"), right=Side(style="thin"),
                                         top=Side(style="thin"), bottom=Side(style="thin"))

            # Adjust column widths
            for col_idx, col_name in enumerate(df.columns, 1):
                ws.column_dimensions[chr(64 + col_idx)].width = max(len(str(col_name)), 12)

        # Remove default sheet
        if "Sheet" in wb.sheetnames:
            wb.remove(wb["Sheet"])

        wb.save(buffer)
        st.download_button("Download Excel (per giver)", buffer, "break_schedule.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    except Exception as e:
        st.error(f"⚠️ {e}")
