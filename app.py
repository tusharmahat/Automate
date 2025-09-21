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

# Shift start/end per giver
st.subheader("⏰ Break Giver Shift Times")
giver_times = {}
for giver in givers:
    col1, col2 = st.columns(2)
    with col1:
        start_str = st.text_input(f"{giver} Start Time (HH:MM)", "09:00", key=f"{giver}_start")
    with col2:
        end_str = st.text_input(f"{giver} End Time (HH:MM)", "17:00", key=f"{giver}_end")
    giver_times[giver] = (datetime.strptime(start_str, "%H:%M"), datetime.strptime(end_str, "%H:%M"))

generate = st.button("Generate Schedule")

# --- Initialize / persist schedule in session_state ---
if generate or "schedule" in st.session_state:
    try:
        if "schedule" not in st.session_state or generate:
            schedule = []

            # --- Step 1: Assign all 15-min breaks first ---
            for idx, emp in enumerate(employees):
                giver = givers[idx % len(givers)]
                start, shift_end = giver_times[giver]
                start = start + first_break_after + timedelta(minutes=idx*15)  # stagger per employee
                end = start + break15
                if end > shift_end:
                    end = shift_end
                    start = end - break15
                schedule.append([emp, giver, "15 min", start.strftime("%H:%M"), end.strftime("%H:%M"), ""])

            # --- Step 2: Assign all 30-min breaks ---
            for idx, emp in enumerate(employees):
                giver = givers[idx % len(givers)]
                start, shift_end = giver_times[giver]
                start = start + first_break_after + timedelta(minutes=15*len(employees) + idx*30)
                end = start + break30
                if end > shift_end:
                    end = shift_end
                    start = end - break30
                schedule.append([emp, giver, "30 min", start.strftime("%H:%M"), end.strftime("%H:%M"), ""])

            st.session_state.schedule = pd.DataFrame(schedule, columns=["Employee", "Break Giver", "Break Type", "Start", "End", "SA Initial"])

        # --- Editable tables per giver ---
        st.subheader("📅 Editable Schedule Per Break Giver")
        edited_tables = {}
        today_str = datetime.now().strftime("%Y-%m-%d")
        for giver in givers:
            st.markdown(f"**Breaker: {giver} | Date: {today_str} | Start time: {giver_times[giver][0].strftime('%H:%M')}**")
            giver_df = st.session_state.schedule[st.session_state.schedule["Break Giver"] == giver].reset_index(drop=True)
            edited_df = st.data_editor(giver_df, num_rows="dynamic", use_container_width=True, key=f"editor_{giver}")
            edited_tables[giver] = edited_df

        # Merge all giver tables back to session_state
        st.session_state.schedule = pd.concat(edited_tables.values(), ignore_index=True)

        # --- Checker ---
        warning_employees = []
        for emp in employees:
            emp_breaks = st.session_state.schedule[st.session_state.schedule["Employee"] == emp]["Break Type"].tolist()
            if "15 min" not in emp_breaks or "30 min" not in emp_breaks:
                warning_employees.append(emp)
        if warning_employees:
            st.warning(f"⚠️ Employees missing breaks: {', '.join(warning_employees)}")
        else:
            st.success("✅ All employees have both 15-min and 30-min breaks assigned.")

        # --- Download CSV ---
        st.subheader("⬇️ Download Schedule")
        csv = st.session_state.schedule.to_csv(index=False).encode("utf-8")
        st.download_button("Download CSV", csv, "break_schedule.csv", "text/csv")

        # --- Download Excel with beautification ---
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            for giver, g_df in edited_tables.items():
                ws_name = giver[:31]
                g_df_copy = g_df[["Employee", "Break Type", "Start", "End", "SA Initial"]].copy()

                ws = writer.book.create_sheet(title=ws_name)
                # Title row
                title = f"Breaker: {giver} | Date: {today_str} | Start time: {giver_times[giver][0].strftime('%H:%M')}"
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

                # Append DataFrame rows
                for idx, row in g_df_copy.iterrows():
                    ws.append(list(row))

                # Alternating row colors starting from row 3 (after header)
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

        st.download_button("Download Excel (per giver)", buffer, "break_schedule.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    except Exception as e:
        st.error(f"⚠️ {e}")
