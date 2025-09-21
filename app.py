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
    shift_date_str = st.text_input("Shift Date (YYYY-MM-DD)", datetime.today().strftime("%Y-%m-%d"))

generate = st.button("Generate Schedule")

# --- Initialize / persist schedule in session_state ---
if generate or "schedule" in st.session_state:
    try:
        shift_start = datetime.strptime(shift_start_str, "%H:%M")
        shift_end = datetime.strptime(shift_end_str, "%H:%M")
        shift_date = datetime.strptime(shift_date_str, "%Y-%m-%d")

        giver_count = len(givers)
        giver_time = {g: shift_start + first_break_after for g in givers}

        # Only generate new schedule if it doesn't exist
        if "schedule" not in st.session_state or generate:
            schedule = []

            # --- Step 1: Assign all 15-min breaks first ---
            for idx, emp in enumerate(employees):
                giver = givers[idx % giver_count]
                start = giver_time[giver]
                end = start + break15
                schedule.append([emp, giver, "15 min", start.strftime("%H:%M"), end.strftime("%H:%M"), ""])
                giver_time[giver] = end + stagger_gap

            # --- Step 2: Assign all 30-min breaks ---
            for idx, emp in enumerate(employees):
                giver = givers[idx % giver_count]
                start = giver_time[giver]
                end = start + break30
                if end > shift_end:
                    end = shift_end
                    start = end - break30
                schedule.append([emp, giver, "30 min", start.strftime("%H:%M"), end.strftime("%H:%M"), ""])
                giver_time[giver] = end + stagger_gap

            st.session_state.schedule = pd.DataFrame(schedule, columns=["Employee", "Break Giver", "Break Type", "Start", "End", "SA Initial"])

        # --- Editable tables per giver ---
        st.subheader("📅 Editable Schedule Per Break Giver")
        edited_tables = {}
        for giver in givers:
            st.markdown(f"### 🧑‍🤝‍🧑 Schedule for {giver}")
            giver_df = st.session_state.schedule[st.session_state.schedule["Break Giver"] == giver].reset_index(drop=True)
            edited_df = st.data_editor(giver_df, num_rows="dynamic", use_container_width=True, key=f"editor_{giver}")
            edited_tables[giver] = edited_df

        # Merge all giver tables back to session_state
        st.session_state.schedule = pd.concat(edited_tables.values(), ignore_index=True)

        # --- Checker: verify each employee has both breaks ---
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

        # --- Download Excel with styling ---
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            for giver, g_df in edited_tables.items():
                sheet_name = giver[:31]

                # Title row
                title = f"Breaker: {giver} | Date: {shift_date.strftime('%Y-%m-%d')} | Start time: {giver_time[giver].strftime('%H:%M')}"
                ws_title_df = pd.DataFrame([title.split("|")])
                ws_title_df.to_excel(writer, index=False, header=False, startrow=0, sheet_name=sheet_name)

                # Actual table
                g_df.to_excel(writer, index=False, startrow=2, sheet_name=sheet_name)

                ws = writer.sheets[sheet_name]

                # Merge title row across all table columns
                ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(g_df.columns))
                title_cell = ws.cell(row=1, column=1)
                title_cell.font = Font(bold=True, size=12)
                title_cell.alignment = Alignment(horizontal="center", vertical="center")
                title_cell.fill = PatternFill("solid", fgColor="BDD7EE")

                # Header style
                header_font = Font(bold=True, color="FFFFFF")
                header_fill = PatternFill("solid", fgColor="4F81BD")
                for col_num, col_name in enumerate(g_df.columns, 1):
                    cell = ws.cell(row=3, column=col_num)
                    cell.font = header_font
                    cell.fill = header_fill
                    cell.alignment = Alignment(horizontal="center", vertical="center")

                # Auto-adjust column widths
                for i, col in enumerate(g_df.columns, 1):
                    max_length = max(
                        g_df[col].astype(str).map(len).max(),
                        len(col)
                    ) + 2
                    ws.column_dimensions[get_column_letter(i)].width = max_length

                # Alternating row fill
                fill1 = PatternFill("solid", fgColor="DCE6F1")
                fill2 = PatternFill("solid", fgColor="FFFFFF")
                for row in range(4, 4 + len(g_df)):
                    fill = fill1 if (row % 2 == 0) else fill2
                    for col in range(1, len(g_df.columns) + 1):
                        ws.cell(row=row, column=col).fill = fill
                        ws.cell(row=row, column=col).alignment = Alignment(horizontal="center", vertical="center")

        st.download_button(
            "Download Excel (per giver, styled)", buffer, "break_schedule_styled.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error(f"⚠️ {e}")
