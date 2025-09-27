import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import json
import os

# --- Constants ---
DATA_FILE = "schedule_data.json"
break15 = timedelta(minutes=15)
break30 = timedelta(minutes=30)

# --- Load previous data ---
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        saved_data = json.load(f)
else:
    saved_data = {}

# --- Inputs ---
st.title("☕ Break Scheduler with Checker")

# Breakers
st.subheader("👨‍💼 Break Giver(s)")
default_breakers = saved_data.get("breakers_input", "Gurleen,Caroll,Caroline,Yashreet,SherryX")
breakers_input = st.text_input("Enter breaker names (comma-separated)", default_breakers)
breaker_names = [b.strip() for b in breakers_input.split(",") if b.strip()]

# Employees
st.subheader("👥 Employees")
default_shiftA = saved_data.get("shift_A_input", "Jamie,Rabina,Lisseth,Sherry,Hadeel,Ishwori,Jeff,Julia,Marie,Muhammad,Pati")
default_shiftB = saved_data.get("shift_B_input", "Andrew,Caroline,Jasmeet,Rose,Warrick,Yashreet")
shift_A_input = st.text_area("Shift A Employees (comma-separated)", default_shiftA)
shift_B_input = st.text_area("Shift B Employees (comma-separated)", default_shiftB)

A_shift = [e.strip() for e in shift_A_input.split(",") if e.strip()]
B_shift = [e.strip() for e in shift_B_input.split(",") if e.strip()]

# Breaker settings
st.subheader("Breaker Shift Times and Break Type")
breakers = []
for b_name in breaker_names:
    prev = saved_data.get("breaker_settings", {}).get(b_name, {})
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        start_time = st.time_input(f"{b_name} Shift Start", prev.get("start", datetime.strptime("10:00","%H:%M").time()))
    with col2:
        end_time = st.time_input(f"{b_name} Shift End", prev.get("end", datetime.strptime("17:00","%H:%M").time()))
    with col3:
        break_type = st.selectbox(f"{b_name} Break Type", ["15 min only", "30 min only", "Both"], index=["15 min only","30 min only","Both"].index(prev.get("type","Both")))
    with col4:
        max_breaks = st.number_input(f"Max breaks for {b_name}", min_value=1, max_value=20, value=prev.get("breaks",4))
    breakers.append({
        "name": b_name,
        "start": start_time,
        "end": end_time,
        "type": break_type,
        "breaks": max_breaks
    })

# --- Save input data ---
saved_data["breakers_input"] = breakers_input
saved_data["shift_A_input"] = shift_A_input
saved_data["shift_B_input"] = shift_B_input
saved_data["breaker_settings"] = {b["name"]: b for b in breakers}

with open(DATA_FILE, "w") as f:
    json.dump(saved_data, f, default=str)

# --- Button to generate schedule ---
if st.button("Generate Schedule"):
    
    # --- Create break pools ---
    A_breaks = [{"emp": emp, "type": "15"} for emp in A_shift] + [{"emp": emp, "type": "30"} for emp in A_shift]
    B_breaks = [{"emp": emp, "type": "15"} for emp in B_shift] + [{"emp": emp, "type": "30"} for emp in B_shift]
    break_pool = A_breaks + B_breaks
    
    schedule_tables = {b["name"]: [] for b in breakers}
    
    # --- Assign breaks ---
    for b in breakers:
        b_name = b["name"]
        start_time = datetime.combine(datetime.today(), b["start"])
        end_time = datetime.combine(datetime.today(), b["end"])
        allowed_types = []
        if b["type"] in ["15 min only", "Both"]:
            allowed_types.append("15")
        if b["type"] in ["30 min only", "Both"]:
            allowed_types.append("30")
        
        current_time = start_time
        i = 0
        while i < len(break_pool):
            brk = break_pool[i]
            emp, b_type = brk["emp"], brk["type"]
            
            if b_type not in allowed_types:
                i += 1
                continue
            
            duration = break15 if b_type == "15" else break30
            
            if current_time + duration > end_time:
                i += 1
                continue
            
            # Assign break
            schedule_tables[b_name].append({
                "Employee": emp,
                "Break Type": f"{b_type} min",
                "Start": current_time.strftime("%H:%M"),
                "End": (current_time + duration).strftime("%H:%M"),
                "SA Initial": ""
            })
            current_time += duration
            
            # Remove from pool
            break_pool.pop(i)
            i = 0
    
    # --- Display schedule ---
    st.subheader("📅 Schedule per Breaker")
    for b_name, df_list in schedule_tables.items():
        if df_list:
            df = pd.DataFrame(df_list)
            st.markdown(f"**Breaker: {b_name}**")
            st.dataframe(df)
    
    # --- Show unassigned breaks if any ---
    if break_pool:
        st.warning("⚠️ Some breaks could not be scheduled within breaker shifts!")
        st.dataframe(pd.DataFrame(break_pool))
