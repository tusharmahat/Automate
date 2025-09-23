import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

st.set_page_config(page_title="Break Scheduler", layout="wide")
st.title("☕ Employee Break Scheduler")

# --- Parameters (editable in sidebar) ---
st.sidebar.header("⚙️ Settings")
break15 = timedelta(minutes=15)
break30 = timedelta(minutes=30)
min_gap = timedelta(hours=2)  # minimum time gap between 30 and 15
stagger_gap = timedelta(minutes=15)  # stagger each employee
first_break_after = timedelta(hours=2)  # no break before this

# --- Upload input file ---
st.subheader("📤 Upload Employee Shift File")
st.markdown("File must have columns: **Employee | Shift Start | Shift End** (time as HH:MM)")

uploaded_file = st.file_uploader("Upload Excel or CSV", type=["xlsx", "csv"])

if uploaded_file:
    # Read file
    if uploaded_file.name.endswith(".csv"):
        employees_df = pd.read_csv(uploaded_file)
    else:
        employees_df = pd.read_excel(uploaded_file)

    st.write("👥 Employee Shifts")
    st.dataframe(employees_df)

    # --- Break givers & assignment ---
    st.subheader("👨‍💼 Assign Employees to Break Givers")

    givers_input = st.text_input("Enter break giver names (comma-separated)", "Giver1, Giver2")
    givers = [g.strip() for g in givers_input.split(",") if g.strip()]

    giver_counts = {}
    if givers:
        total_emps = len(employees_df)
        st.markdown(f"Total employees: **{total_emps}**")
        for g in givers:
            giver_counts[g] = st.number_input(
                f"Number of employees for {g}", 
                min_value=0, 
                max_value=total_emps, 
                value=total_emps // len(givers)
            )

    if st.button("Generate Schedule"):
        schedule = []
        emp_index = 0

        for giver in givers:
            count = giver_counts[giver]
            assigned_emps = employees_df.iloc[emp_index:emp_index+count]
            emp_index += count

            for i, row in assigned_emps.iterrows():
                emp = row["Employee"]
                shift_start = datetime.strptime(str(row["Shift Start"]), "%H:%M")
                shift_end = datetime.strptime(str(row["Shift End"]), "%H:%M")

                # --- 30 min break ---
                start30 = shift_start + first_break_after + (i * stagger_gap)
                end30 = start30 + break30

                # --- 15 min break ---
                start15 = start30 + min_gap
                if start15 + break15 > shift_end:  # if not enough time left
                    start15 = shift_end - break15
                end15 = start15 + break15

                schedule.append([emp, giver, "30 min", start30.strftime("%H:%M"), end30.strftime("%H:%M")])
                schedule.append([emp, giver, "15 min", start15.strftime("%H:%M"), end15.strftime("%H:%M")])

        df = pd.DataFrame(schedule, columns=["Employee", "Break Giver", "Break Type", "Start", "End"])

        st.subheader("📅 Generated Break Schedule")
        st.dataframe(df, use_container_width=True)

        # --- Download buttons ---
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download as CSV", csv, "break_schedule.csv", "text/csv")

        xlsx_file = "break_schedule.xlsx"
        df.to_excel(xlsx_file, index=False)
        with open(xlsx_file, "rb") as f:
            st.download_button("⬇️ Download as Excel", f, "break_schedule.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
