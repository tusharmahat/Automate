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
first_break_after = timedelta(hours=2)
stagger_gap = timedelta(minutes=0)  # continuous for each giver

# --- Inputs ---
st.subheader("👨‍💼 Break Giver(s)")
givers_input = st.text_input("Enter break giver names (comma-separated)", "Giver1, Giver2")
givers = [g.strip() for g in givers_input.split(",") if g.strip()]

st.subheader("⏰ Break Giver Timings")
giver_times = {}
for giver in givers:
    col1, col2 = st.columns(2)
    with col1:
        start_str = st.text_input(f"{giver} Start Time (HH:MM)", "09:00", key=f"{giver}_start")
    with col2:
        end_str = st.text_input(f"{giver} End Time (HH:MM)", "17:00", key=f"{giver}_end")
    try:
        giver_times[giver] = {
            "start": datetime.strptime(start_str, "%H:%M"),
            "end": datetime.strptime(end_str, "%H:%M")
        }
    except:
        st.error(f"Invalid time format for {giver}. Use HH:MM")

st.subheader("👥 Employees")
employees_input = st.text_area("Enter employee names (comma-separated)", "Alice, Bob, Carol, Dave")
employees = [e.strip() for e in employees_input.split(",") if e.strip()]

generate = st.button("Generate Schedule")

# --- Initialize / persist schedule in session_state ---
if generate or "schedule" in st.session_state:
    try:
        # Only generate new schedule if it doesn't exist or if user clicks generate
        if "schedule" not in st.session_state or generate:
            schedule = []
            # Initialize giver times for scheduling
            current_times = {g: giver_times[g]["start"] + first_break_after for g in givers}

            # Step 1: Assign 15-min breaks
            for idx, emp in enumerate(employees):
                giver = givers[idx % len(givers)]
                start = current_times[giver]
                end = start + break15
                if end > giver_times[giver]["end"]:
                    end = giver_times[giver]["end"]
                    start = end - break15
                schedule.append([emp, giver, "15 min", start.strftime("%H:%M"), end.strftime("%H:%M"), ""])
                current_times[giver] = end + stagger_gap

            # Step 2: Assign 30-min breaks
            for idx, emp in enumerate(employees):
                giver = givers[idx % len(givers)]
                start = current_times[giver]
                end = start + break30
                if end > giver_times[giver]["end"]:
                    end = giver_times[giver]["end"]
                    start = end - break30
                schedule.append([emp, giver, "30 min", start.strftime("%H:%M"), end.strftime("%H:%M"), ""])
                current_times[giver] = end + stagger_gap

            # Store in session_state
            st.session_state.schedule = pd.DataFrame(
                schedule,
                columns=["Employee", "Break Giver", "Break Type", "Start", "End", "SA Initial"]
            )

        # --- Editable tables per giver ---
        st.subheader("📅 Editable Schedule Per Break Giver")
        edited_tables = {}
        for giver in givers:
            st.markdown(f"### 🧑‍🤝‍🧑 Schedule for {giver}")
            giver_df = st.session_state.schedule[st.session_state.schedule["Break Giver"] == giver].reset_index(drop=True)
            edited_df = st.data_editor(
                giver_df,
                num_rows="dynamic",
                use_container_width=True,
                key=f"editor_{giver}"
            )
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

        # --- Download ---
        st.subheader("⬇️ Download Schedule")
        csv = st.session_state.schedule.to_csv(index=False).encode("utf-8")
        st.download_button("Download CSV", csv, "break_schedule.csv", "text/csv")

        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            for giver, g_df in edited_tables.items():
                g_df.to_excel(writer, index=False, sheet_name=giver[:31])
        st.download_button("Download Excel (per giver)", buffer, "break_schedule.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    except Exception as e:
        st.error(f"⚠️ {e}")
