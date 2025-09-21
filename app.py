import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from io import BytesIO

st.set_page_config(page_title="Break Scheduler", layout="wide")
st.title("☕ Editable Employee Break Scheduler")

# --- Sidebar settings ---
st.sidebar.header("⚙️ Break Settings")
break15 = timedelta(minutes=15)
break30 = timedelta(minutes=30)
min_gap = timedelta(hours=2)          # min gap between 30 + 15
stagger_gap = timedelta(minutes=15)   # stagger each employee
first_break_after = timedelta(hours=2)

# --- Inputs ---
st.subheader("👥 Enter Employees")
employees_input = st.text_area(
    "Type employee names separated by commas:",
    "Alice, Bob, Carol, Dave"
)
employees = [e.strip() for e in employees_input.split(",") if e.strip()]

col1, col2 = st.columns(2)
with col1:
    shift_start_str = st.text_input("Shift Start (HH:MM)", "09:00")
with col2:
    shift_end_str = st.text_input("Shift End (HH:MM)", "17:00")

generate = st.button("Generate Break Schedule")

if generate and employees:
    try:
        shift_start = datetime.strptime(shift_start_str, "%H:%M")
        shift_end = datetime.strptime(shift_end_str, "%H:%M")

        schedule = []
        for i, emp in enumerate(employees):
            # 30-min break
            start30 = shift_start + first_break_after + (i * stagger_gap)
            end30 = start30 + break30

            # 15-min break
            start15 = start30 + min_gap
            if start15 + break15 > shift_end:
                start15 = shift_end - break15
            end15 = start15 + break15

            schedule.append([emp, "30 min", start30.strftime("%H:%M"), end30.strftime("%H:%M")])
            schedule.append([emp, "15 min", start15.strftime("%H:%M"), end15.strftime("%H:%M")])

        df = pd.DataFrame(schedule, columns=["Employee", "Break Type", "Start", "End"])

        st.subheader("📅 Editable Break Schedule")
        edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)

        # --- Download buttons ---
        st.subheader("⬇️ Download Schedule")

        csv = edited_df.to_csv(index=False).encode("utf-8")
        st.download_button("Download as CSV", csv, "break_schedule.csv", "text/csv")

        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            edited_df.to_excel(writer, index=False, sheet_name="Schedule")
        st.download_button(
            "Download as Excel",
            data=buffer,
            file_name="break_schedule.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    except Exception as e:
        st.error(f"⚠️ Error: {e}")
