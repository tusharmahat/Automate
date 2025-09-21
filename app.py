import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from io import BytesIO

st.set_page_config(page_title="Break Scheduler", layout="wide")
st.title("☕ Break Scheduler (Custom Order for Last Employee)")

# --- Sidebar settings ---
st.sidebar.header("⚙️ Break Settings")
break15 = timedelta(minutes=15)
break30 = timedelta(minutes=30)
stagger_gap = timedelta(minutes=15)          # stagger breaks
first_break_after = timedelta(hours=2)
min_gap_between_breaks = timedelta(hours=2)  # gap between first and second break

# --- Break givers input ---
st.subheader("👨‍💼 Break Giver(s)")
givers_input = st.text_input("Enter break giver names (comma-separated)", "Giver1, Giver2")
givers = [g.strip() for g in givers_input.split(",") if g.strip()]

# --- Employees input ---
st.subheader("👥 Employees")
employees_input = st.text_area("Enter employee names (comma-separated)", "Alice, Bob, Carol, Dave")
employees = [e.strip() for e in employees_input.split(",") if e.strip()]

# --- Shift times ---
col1, col2 = st.columns(2)
with col1:
    shift_start_str = st.text_input("Shift Start (HH:MM)", "09:00")
with col2:
    shift_end_str = st.text_input("Shift End (HH:MM)", "17:00")

# --- Generate button ---
generate = st.button("Generate Break Schedule")

if generate and employees and givers:
    try:
        shift_start = datetime.strptime(shift_start_str, "%H:%M")
        shift_end = datetime.strptime(shift_end_str, "%H:%M")

        giver_count = len(givers)
        schedule = []

        # --- Assign breaks for all employees ---
        for i, emp in enumerate(employees):
            giver = givers[i % giver_count]

            # Determine break order
            if i == len(employees) - 1:
                # Last employee: 30-min first
                first_type, second_type = "30 min", "15 min"
                first_duration, second_duration = break30, break15
            else:
                # All others: 15-min first
                first_type, second_type = "15 min", "30 min"
                first_duration, second_duration = break15, break30

            # First break
            start1 = shift_start + first_break_after + (i * stagger_gap)
            end1 = start1 + first_duration

            # Second break
            start2 = start1 + min_gap_between_breaks
            if start2 + second_duration > shift_end:
                start2 = shift_end - second_duration
            end2 = start2 + second_duration

            schedule.append([emp, giver, first_type, start1.strftime("%H:%M"), end1.strftime("%H:%M"), ""])
            schedule.append([emp, giver, second_type, start2.strftime("%H:%M"), end2.strftime("%H:%M"), ""])

        df = pd.DataFrame(schedule, columns=["Employee", "Break Giver", "Break Type", "Start", "End", "SA Initial"])

        st.subheader("📅 Editable Break Schedule (Per Giver)")

        # --- Separate tables per giver ---
        edited_tables = {}
        for giver in givers:
            st.markdown(f"### 🧑‍🤝‍🧑 Schedule for **{giver}**")
            giver_df = df[df["Break Giver"] == giver].reset_index(drop=True)
            edited_df = st.data_editor(giver_df, num_rows="dynamic", use_container_width=True)
            edited_tables[giver] = edited_df

        # --- Combine all for download ---
        final_df = pd.concat(edited_tables.values(), ignore_index=True)

        st.subheader("⬇️ Download Schedule")

        # CSV
        csv = final_df.to_csv(index=False).encode("utf-8")
        st.download_button("Download All (CSV)", csv, "break_schedule.csv", "text/csv")

        # Excel
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            for giver, giver_df in edited_tables.items():
                giver_df.to_excel(writer, index=False, sheet_name=giver[:31])
        st.download_button(
            "Download All (Excel, per giver)",
            data=buffer,
            file_name="break_schedule.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    except Exception as e:
        st.error(f"⚠️ Error: {e}")
