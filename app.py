import streamlit as st
import warnings
import pandas as pd
from datetime import datetime, timedelta
from io import BytesIO

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
stagger_gap = timedelta(minutes=0)

# --- Inputs ---
st.subheader("👨‍💼 Break Giver(s)")
givers_input = st.text_input("Enter break giver names (comma-separated)", "Giver1, Giver2")
givers = [g.strip() for g in givers_input.split(",") if g.strip()]

st.subheader("👥 Employees")
employees_input = st.text_area("Enter employee names (comma-separated)", "Alice, Bob, Carol, Dave")
employees = [e.strip() for e in employees_input.split(",") if e.strip()]

# --- Shift & per-giver times ---
shift_date_str = st.text_input("Date (YYYY-MM-DD)", datetime.today().strftime("%Y-%m-%d"))
shift_date = datetime.strptime(shift_date_str, "%Y-%m-%d")

giver_times = {}
for giver in givers:
    col1, col2 = st.columns(2)
    with col1:
        start_str = st.text_input(f"{giver} Start time (HH:MM)", "09:00")
    with col2:
        end_str = st.text_input(f"{giver} End time (HH:MM)", "17:00")
    giver_times[giver] = {
        "start": datetime.strptime(start_str, "%H:%M"),
        "end": datetime.strptime(end_str, "%H:%M")
    }

generate = st.button("Generate Schedule")

# --- Generate / persist schedule ---
if generate or "schedule" in st.session_state:
    try:
        if "schedule" not in st.session_state or generate:
            schedule = []

            # Assign 15-min breaks
            for idx, emp in enumerate(employees):
                giver = givers[idx % len(givers)]
                start = giver_times[giver]["start"]
                end = start + break15
                if end > giver_times[giver]["end"]:
                    end = giver_times[giver]["end"]
                    start = end - break15
                schedule.append([emp, giver, "15 min", start.strftime("%H:%M"), end.strftime("%H:%M"), ""])
                giver_times[giver]["start"] = end + stagger_gap

            # Assign 30-min breaks
            for idx, emp in enumerate(employees):
                giver = givers[idx % len(givers)]
                start = giver_times[giver]["start"]
                end = start + break30
                if end > giver_times[giver]["end"]:
                    end = giver_times[giver]["end"]
                    start = end - break30
                schedule.append([emp, giver, "30 min", start.strftime("%H:%M"), end.strftime("%H:%M"), ""])
                giver_times[giver]["start"] = end + stagger_gap

            st.session_state.schedule = pd.DataFrame(
                schedule, columns=["Employee", "Break Giver", "Break Type", "Start", "End", "SA Initial"]
            )

        # Editable tables per giver
        st.subheader("📅 Editable Schedule Per Break Giver")
        edited_tables = {}
        for giver in givers:
            st.markdown(f"### Breaker: {giver} | Date: {shift_date.strftime('%Y-%m-%d')} | Start time: {giver_times[giver]['start'].strftime('%H:%M')}")
            giver_df = st.session_state.schedule[st.session_state.schedule["Break Giver"] == giver].reset_index(drop=True)
            edited_df = st.data_editor(giver_df, num_rows="dynamic", use_container_width=True, key=f"editor_{giver}")
            edited_tables[giver] = edited_df

        # Merge all giver tables back
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

        # --- Download Excel with titles ---
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            for giver, g_df in edited_tables.items():
                sheet_name = giver[:31]
                # Title row
                title = f"Breaker: {giver} | Date: {shift_date.strftime('%Y-%m-%d')} | Start time: {giver_times[giver]['start'].strftime('%H:%M')}"
                title_df = pd.DataFrame([title.split("|")])
                title_df.to_excel(writer, index=False, header=False, startrow=0, sheet_name=sheet_name)
                # Actual table below
                g_df.to_excel(writer, index=False, startrow=2, sheet_name=sheet_name)

        st.download_button(
            "Download Excel (per giver)", buffer, "break_schedule.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error(f"⚠️ {e}")
