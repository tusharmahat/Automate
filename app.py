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

st.subheader("👥 Employees")
employees_input = st.text_area("Enter employee names (comma-separated)", "Alice, Bob, Carol, Dave")
employees = [e.strip() for e in employees_input.split(",") if e.strip()]

col1, col2 = st.columns(2)
with col1:
    shift_start_str = st.text_input("Shift Start (HH:MM)", "09:00")
with col2:
    shift_end_str = st.text_input("Shift End (HH:MM)", "17:00")

generate = st.button("Generate Schedule")

generate = st.button("Generate Schedule")

if generate and employees and givers:
    try:
        shift_start = datetime.strptime(shift_start_str, "%H:%M")
        shift_end = datetime.strptime(shift_end_str, "%H:%M")

        giver_count = len(givers)
        giver_time = {g: shift_start + first_break_after for g in givers}

        # --- Step 1 & 2: Build initial schedule ---
        schedule = []
        for idx, emp in enumerate(employees):
            giver = givers[idx % giver_count]
            # 15-min break
            start15 = giver_time[giver]
            end15 = start15 + break15
            schedule.append([emp, giver, "15 min", start15.strftime("%H:%M"), end15.strftime("%H:%M"), ""])
            giver_time[giver] = end15 + stagger_gap

        for idx, emp in enumerate(employees):
            giver = givers[idx % giver_count]
            # 30-min break
            start30 = giver_time[giver]
            end30 = start30 + break30
            if end30 > shift_end:
                end30 = shift_end
                start30 = end30 - break30
            schedule.append([emp, giver, "30 min", start30.strftime("%H:%M"), end30.strftime("%H:%M"), ""])
            giver_time[giver] = end30 + stagger_gap

        df = pd.DataFrame(schedule, columns=["Employee", "Break Giver", "Break Type", "Start", "End", "SA Initial"])

        # --- Initialize session_state for persistence ---
        if "edited_tables" not in st.session_state:
            st.session_state.edited_tables = {giver: df[df["Break Giver"]==giver].reset_index(drop=True) for giver in givers}

        st.subheader("📅 Editable Schedule Per Break Giver")

        # --- Display editable tables ---
        for giver in givers:
            st.markdown(f"### 🧑‍🤝‍🧑 Schedule for {giver}")
            edited_df = st.data_editor(
                st.session_state.edited_tables[giver],
                num_rows="dynamic",
                use_container_width=True
            )
            st.session_state.edited_tables[giver] = edited_df

        # --- Combine tables for final processing ---
        final_df = pd.concat(st.session_state.edited_tables.values(), ignore_index=True)

        # --- Checker ---
        warning_employees = []
        for emp in employees:
            emp_breaks = final_df[final_df["Employee"]==emp]["Break Type"].tolist()
            if "15 min" not in emp_breaks or "30 min" not in emp_breaks:
                warning_employees.append(emp)

        if warning_employees:
            st.warning(f"⚠️ The following employees are missing breaks: {', '.join(warning_employees)}")
        else:
            st.success("✅ All employees have both 15-min and 30-min breaks assigned.")

        # --- Download buttons ---
        st.subheader("⬇️ Download Schedule")
        csv = final_df.to_csv(index=False).encode("utf-8")
        st.download_button("Download CSV", csv, "break_schedule.csv", "text/csv")

        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            for giver, g_df in st.session_state.edited_tables.items():
                g_df.to_excel(writer, index=False, sheet_name=giver[:31])
        st.download_button(
            "Download Excel (per giver)",
            buffer,
            "break_schedule.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error(f"⚠️ {e}")

