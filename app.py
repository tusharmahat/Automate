import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from io import BytesIO

st.set_page_config(page_title="Break Scheduler", layout="wide")
st.title("☕ Break Scheduler (15-min first, then 30-min)")

# --- Sidebar settings ---
st.sidebar.header("⚙️ Break Settings")
break15 = timedelta(minutes=15)
break30 = timedelta(minutes=30)
stagger_gap = timedelta(minutes=15)  # stagger breaks
first_break_after = timedelta(hours=2)
min_gap_between_breaks = timedelta(hours=2)  # gap between 15-min and 30-min

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

        # --- Step 1: assign all 15-min breaks first ---
        for i, emp in enumerate(employees):
            giver = givers[i % giver_count]
            start15 = shift_start + first_break_after + (i * stagger_gap)
            end15 = start15 + break15
            schedule.append([emp, giver, "15 min", start15.strftime("%H:%M"), end15.strftime("%H:%M"), ""])

        # --- Step 2: assign all 30-min breaks after 15-min are done ---
        for i, emp in enumerate(employees):
            giver = givers[i % giver_count]
            # Find the end of the 15-min break for this employee
            start15_dt = shift_start + first_break_after + (i * stagger_gap)
            start30 = start15_dt + min_gap_between_breaks
            end30 = start30 + break30
            if end30 > shift_end:
                start30 = shift_end - break30
                end30 = shift_end
            schedule.append([emp, giver, "30 min", start30.strftime("%H:%M"), end30.strftime("%H:%M"), ""])

        df = pd.DataFrame(schedule, columns=["Employee", "Break Giver", "Break Type", "Start", "End", "SA Initial"])

        st.subheader("📅 Editable Break Schedule (Per Giver)")

        # --- Show separate editable tables for each giver ---
        edited_tables = {}
        for giver in givers:
            st.markdown(f"### 🧑‍🤝‍🧑 Schedule for **{giver}**")
            giver_df = df[df["Break Giver"] == giver].reset_index(drop=True)
            edited_df = st.data_editor(giver_df, num_rows="dynamic", use_container_width=True)
            edited_tables[giver] = edited_df

        # --- Combine back for downloads ---
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
