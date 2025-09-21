import streamlit as st
import warnings
import pandas as pd
from datetime import datetime, timedelta
from io import BytesIO
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

# --- Hide Python warnings ---
warnings.filterwarnings("ignore")

# --- Hide browser console warnings ---
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
stagger_gap = timedelta(minutes=0)  # continuous for each giver

# --- Inputs ---
st.subheader("👨‍💼 Break Giver(s)")
givers_input = st.text_input("Enter break giver names (comma-separated)", "Giver1, Giver2")
givers = [g.strip() for g in givers_input.split(",") if g.strip()]

st.subheader("👥 Employees")
employees_input = st.text_area("Enter employee names (comma-separated)", "Alice, Bob, Carol, Dave")
employees = [e.strip() for e in employees_input.split(",") if e.strip()]

col1, col2, col3 = st.columns(3)
with col1:
    shift_start_str = st.text_input("Shift Start (HH:MM)", "09:00")
with col2:
    shift_end_str = st.text_input("Shift End (HH:MM)", "17:00")
with col3:
    schedule_date = st.date_input("Date", datetime.today())

generate = st.button("Generate Schedule")

if generate or "schedule" in st.session_state:
    try:
        shift_start = datetime.strptime(shift_start_str, "%H:%M")
        shift_end = datetime.strptime(shift_end_str, "%H:%M")
        schedule_date_str = schedule_date.strftime("%Y-%m-%d")

        giver_count = len(givers)
        giver_time = {g: shift_start + first_break_after for g in givers}

        # --- Generate schedule only if not exists ---
        if "schedule" not in st.session_state or generate:
            schedule = []
            # 15-min breaks
            for idx, emp in enumerate(employees):
                giver = givers[idx % giver_count]
                start = giver_time[giver]
                end = start + break15
                schedule.append([emp, giver, "15 min", start.strftime("%H:%M"), end.strftime("%H:%M"), ""])
                giver_time[giver] = end + stagger_gap
            # 30-min breaks
            for idx, emp in enumerate(employees):
                giver = givers[idx % giver_count]
                start = giver_time[giver]
                end = start + break30
                if end > shift_end:
                    end = shift_end
                    start = end - break30
                schedule.append([emp, giver, "30 min", start.strftime("%H:%M"), end.strftime("%H:%M"), ""])
                giver_time[giver] = end + stagger_gap

            st.session_state.schedule = pd.DataFrame(
                schedule, columns=["Employee", "Break Giver", "Break Type", "Start", "End", "SA Initial"]
            )

        # --- Editable tables per giver ---
        st.subheader("📅 Editable Schedule Per Break Giver")
        edited_tables = {}
        for giver in givers:
            st.markdown(f"### Breaker: {giver} | Date: {schedule_date_str} | Start time: {shift_start_str}")
            giver_df = st.session_state.schedule[st.session_state.schedule["Break Giver"] == giver].reset_index(drop=True)
            edited_df = st.data_editor(giver_df, num_rows="dynamic", use_container_width=True, key=f"editor_{giver}")
            edited_tables[giver] = edited_df

        # Merge back
        st.session_state.schedule = pd.concat(edited_tables.values(), ignore_index=True)

        # --- Checker ---
        warning_employees = []
        for emp in employees:
            emp_breaks = st.session_state.schedule[st.session_state.schedule["Employee"] == emp]["Break Type"].tolist()
            if "15 min" not in emp_breaks or "30 min" not in emp_breaks:
                warning_employees.append(emp)
        if warning_employees:
            st.warning(f"⚠️ Missing breaks: {', '.join(warning_employees)}")
        else:
            st.success("✅ All employees have both breaks assigned.")

        # --- Download ---
        st.subheader("⬇️ Download Schedule")
        csv = st.session_state.schedule.to_csv(index=False).encode("utf-8")
        st.download_button("Download CSV", csv, "break_schedule.csv", "text/csv")

        # --- Excel with beautification ---
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            for giver, g_df in edited_tables.items():
                ws_name = giver[:31]
                g_df_copy = g_df[["Employee", "Break Type", "Start", "End", "SA Initial"]].copy()

                ws = writer.book.create_sheet(title=ws_name)
                # Title row
                title = f"Breaker: {giver} | Date: {schedule_date_str} | Start time: {shift_start_str}"
                ws.append([title])
                ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(g_df_copy.columns))
                ws["A1"].font = Font(bold=True, color="FFFFFF", size=12)
                ws["A1"].fill = PatternFill("solid", fgColor="4F81BD")
                ws["A1"].alignment = Alignment(horizontal="center")

                # Header row
                ws.append(list(g_df_copy.columns))
                for cell in ws[2]:
                    cell.font = Font(bold=True, color="FFFFFF")
                    cell.fill = PatternFill("solid", fgColor="4F81BD")

                # Table rows with alternating colors
                fill1 = PatternFill("solid", fgColor="DCE6F1")
                fill2 = PatternFill("solid", fgColor="FFFFFF")
                for idx, row in enumerate(ws.iter_rows(min_row=3, max_row=ws.max_row)):
                    fill = fill1 if idx % 2 == 0 else fill2
                    for cell in row:
                        cell.fill = fill

                # Auto column width
                for col in ws.columns:
                    max_length = max(len(str(cell.value)) if cell.value else 0 for cell in col)
                    ws.column_dimensions[get_column_letter(col[0].column)].width = max_length + 2

        st.download_button(
            "Download Excel (per giver)", buffer, "break_schedule.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error(f"⚠️ {e}")
