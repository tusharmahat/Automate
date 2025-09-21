import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from io import BytesIO

st.set_page_config(page_title="Continuous Break Scheduler", layout="wide")
st.title("☕ Continuous Break Scheduler per Break Giver")

# --- Settings ---
st.sidebar.header("⚙️ Break Settings")
break15 = timedelta(minutes=15)
break30 = timedelta(minutes=30)
first_break_after = timedelta(hours=2)
min_gap_between_breaks = timedelta(minutes=0)  # Continuous for each giver

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

generate = st.button("Generate Schedule")

if generate and employees and givers:
    try:
        shift_start = datetime.strptime(shift_start_str, "%H:%M")
        shift_end = datetime.strptime(shift_end_str, "%H:%M")

        giver_count = len(givers)
        # Initialize current time per giver
        giver_time = {g: shift_start + first_break_after for g in givers}

        schedule = []

        # Step 1: Assign all 15-min breaks first (except last employee if special rule)
        for idx, emp in enumerate(employees):
            # Determine break order for last employee
            if idx == len(employees) - 1:
                first_type, second_type = "30 min", "15 min"
                first_duration, second_duration = break30, break15
            else:
                first_type, second_type = "15 min", "30 min"
                first_duration, second_duration = break15, break30

            # Assign first break
            giver = givers[idx % giver_count]
            start1 = giver_time[giver]
            end1 = start1 + first_duration
            schedule.append([emp, giver, first_type, start1.strftime("%H:%M"), end1.strftime("%H:%M"), ""])
            # Update giver time
            giver_time[giver] = end1 + min_gap_between_breaks

        # Step 2: Assign second break for all employees
        for idx, emp in enumerate(employees):
            giver = givers[idx % giver_count]
            # For last employee, order reversed
            if idx == len(employees) - 1 and second_type == "15 min":
                start2 = giver_time[giver]
                end2 = start2 + break15
            else:
                start2 = giver_time[giver]
                end2 = start2 + break30
            if end2 > shift_end:
                end2 = shift_end
                start2 = end2 - (break30 if second_type=="30 min" else break15)
            schedule.append([emp, giver, second_type, start2.strftime("%H:%M"), end2.strftime("%H:%M"), ""])
            giver_time[giver] = end2 + min_gap_between_breaks

        df = pd.DataFrame(schedule, columns=["Employee", "Break Giver", "Break Type", "Start", "End", "SA Initial"])

        st.subheader("📅 Editable Schedule Per Break Giver")
        edited_tables = {}
        for giver in givers:
            st.markdown(f"### 🧑‍🤝‍🧑 Schedule for {giver}")
            giver_df = df[df["Break Giver"]==giver].reset_index(drop=True)
            edited_df = st.data_editor(giver_df, num_rows="dynamic", use_container_width=True)
            edited_tables[giver] = edited_df

        # --- Download ---
        final_df = pd.concat(edited_tables.values(), ignore_index=True)

        csv = final_df.to_csv(index=False).encode("utf-8")
        st.download_button("Download CSV", csv, "break_schedule.csv", "text/csv")

        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            for giver, g_df in edited_tables.items():
                g_df.to_excel(writer, index=False, sheet_name=giver[:31])
        st.download_button("Download Excel (per giver)", buffer, "break_schedule.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    except Exception as e:
        st.error(f"⚠️ {e}")
