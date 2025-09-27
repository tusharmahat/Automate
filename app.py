import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.cell.cell import MergedCell
import json
import os

DATA_FILE = "break_schedule_data.json"
break15 = timedelta(minutes=15)
break30 = timedelta(minutes=30)

st.set_page_config(page_title="☕ Break Scheduler", layout="wide")
st.title("☕ Break Scheduler with Checker (Finish by 16:15)")

# --- Load previous data ---
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        saved = json.load(f)
    st.session_state['tables'] = {k: pd.DataFrame(v) for k,v in saved.get("tables", {}).items()}
    form_data = saved.get("form_data", {})
else:
    st.session_state['tables'] = {}
    form_data = {}

# --- Inputs ---
st.subheader("👨‍💼 Break Giver(s)")
givers_input = st.text_input("Enter break giver names (comma-separated)", form_data.get("givers_input","Gurleen,Caroll,Caroline,Yashreet,SherryX"))
givers = [g.strip() for g in givers_input.split(",") if g.strip()]

st.subheader("👥 Employees")
shift_A_input = st.text_area("Shift A Employees (comma-separated)", form_data.get("shift_A_input","Jamie,Rabina,Lisseth,Sherry,Hadeel,Ishwori,Jeff,Julia,Marie,Muhammad,Pati"))
shift_B_input = st.text_area("Shift B Employees (comma-separated)", form_data.get("shift_B_input","Andrew,Caroline,Jasmeet,Rose,Warrick,Yashreet"))
shift_employees = {
    "A": [e.strip() for e in shift_A_input.split(",") if e.strip()],
    "B": [e.strip() for e in shift_B_input.split(",") if e.strip()]
}

st.subheader("Assign number of breaks per Breaker and Break Type")
giver_max_breaks = {}
giver_break_type = {}
cols = st.columns(len(givers))
for i, giver in enumerate(givers):
    with cols[i]:
        giver_max_breaks[giver] = st.number_input(f"Breaks for {giver}", min_value=1, max_value=20, value=form_data.get("giver_max_breaks",{}).get(giver,4))
        giver_break_type[giver] = st.selectbox(f"Break Type for {giver}", ["15 min only","30 min only","Both"], index=["15 min only","30 min only","Both"].index(form_data.get("giver_break_type",{}).get(giver,"Both")))

st.subheader("Breaker Shift Times")
giver_shift_times = {}
for giver in givers:
    col1,col2 = st.columns(2)
    with col1:
        start_time = st.time_input(f"{giver} Shift Start", datetime.strptime(form_data.get("giver_shift_times",{}).get(giver,[str(datetime.strptime('09:00','%H:%M').time())])[0],"%H:%M:%S").time() if giver in form_data.get("giver_shift_times",{}) else datetime.strptime("09:00","%H:%M").time())
    with col2:
        end_time = st.time_input(f"{giver} Shift End", datetime.strptime(form_data.get("giver_shift_times",{}).get(giver,[None,str(datetime.strptime('17:00','%H:%M').time())])[1],"%H:%M:%S").time() if giver in form_data.get("giver_shift_times",{}) else datetime.strptime("17:00","%H:%M").time())
    giver_shift_times[giver]=(start_time,end_time)

schedule_date = st.date_input("📅 Select Schedule Date", datetime.strptime(form_data.get("schedule_date",str(datetime.today().date())),"%Y-%m-%d").date())

# --- Scheduling logic ---
def schedule_until_deadline(breakers, shift_A, shift_B, schedule_date):
    A_15 = [(e,"15 min") for e in shift_A]
    A_30 = [(e,"30 min") for e in shift_A]
    B_15 = [(e,"15 min") for e in shift_B]
    B_30 = [(e,"30 min") for e in shift_B]
    
    tables = {}
    
    for br in breakers:
        current_time = datetime.combine(schedule_date, br['shift_start'])
        shift_end_time = datetime.combine(schedule_date, br['shift_end'])
        max_end_time = datetime.combine(schedule_date, datetime.strptime("16:15","%H:%M").time())
        table = []
        assigned = 0
        
        pools = []
        if br['break_type'] in ["15 min only","Both"]:
            pools.extend([A_15,B_15])
        if br['break_type'] in ["30 min only","Both"]:
            pools.extend([A_30,B_30])
        
        A_done=False
        while assigned < br['max_breaks'] and any(pools):
            for i,pool in enumerate(pools):
                if not pool: continue
                emp,b_type = pool.pop(0)
                dur = break15 if b_type=="15 min" else break30
                if current_time + dur > min(shift_end_time, max_end_time): continue
                if not A_done and i>=1:
                    table.append(["","","","",""])  # gap row
                    A_done=True
                table.append([emp,b_type,current_time.strftime("%H:%M"),(current_time+dur).strftime("%H:%M"),""])
                current_time += dur
                assigned += 1
                if assigned >= br['max_breaks']: break
        tables[br['name']] = pd.DataFrame(table,columns=["SA","Break Type","Start","End","SA Initial"])
    
    return tables

# --- Generate ---
generate = st.button("Generate Schedule (Finish by 16:15)")
if generate:
    breakers=[]
    for g in givers:
        breakers.append({
            "name":g,
            "shift_start":giver_shift_times[g][0],
            "shift_end":giver_shift_times[g][1],
            "max_breaks":giver_max_breaks[g],
            "break_type":giver_break_type[g]
        })
    st.session_state['tables'] = schedule_until_deadline(breakers, shift_employees["A"], shift_employees["B"], schedule_date)

    # Save JSON
    to_save = {
        "tables": {g: df.to_dict(orient="records") for g,df in st.session_state['tables'].items()},
        "form_data":{
            "givers_input": givers_input,
            "shift_A_input": shift_A_input,
            "shift_B_input": shift_B_input,
            "giver_max_breaks":giver_max_breaks,
            "giver_break_type":giver_break_type,
            "giver_shift_times":{g:[str(t[0]),str(t[1])] for g,t in giver_shift_times.items()},
            "schedule_date":str(schedule_date)
        }
    }
    with open(DATA_FILE,"w") as f:
        json.dump(to_save,f,indent=2)
    st.success("✅ Schedule generated and saved!")

# --- Display tables ---
st.subheader("📅 Editable Schedule Per Breaker")
for g,df in st.session_state.get('tables',{}).items():
    st.markdown(f"**Breaker: {g} | Date: {schedule_date}**")
    edited = st.data_editor(df,num_rows="dynamic",use_container_width=True,key=f"editor_{g}")
    st.session_state['tables'][g]=edited

# --- Break counter ---
st.subheader("📝 Break Count Per Employee")
all_rows = pd.concat(st.session_state['tables'].values(),ignore_index=True)
counter_df = pd.DataFrame([[emp,len(all_rows[all_rows["SA"]==emp])] for emp in shift_employees["A"]+shift_employees["B"]],
                          columns=["Employee","Total Breaks"])
st.dataframe(counter_df)

# --- Excel export ---
st.subheader("⬇️ Download Schedule")
buffer=BytesIO()
wb=Workbook()
ws=wb.active
ws.title="Schedule"

for g,df in st.session_state.get('tables',{}).items():
    ws.append([f"Breaker: {g} | Date: {schedule_date}"])
    title_row=ws.max_row
    ws.merge_cells(start_row=title_row,start_column=1,end_row=title_row,end_column=df.shape[1])
    c=ws.cell(row=title_row,column=1)
    c.font=Font(bold=True,color="FFFFFF")
    c.fill=PatternFill("solid",fgColor="4F81BD")
    c.alignment=Alignment(horizontal="center")
    ws.append(df.columns.tolist())
    for r in dataframe_to_rows(df,index=False,header=False):
        ws.append(r)
    ws.append([])

# Adjust column widths
for col_cells in ws.columns:
    max_length=0
    col_letter=None
    for cell in col_cells:
        if not isinstance(cell,MergedCell):
            col_letter=cell.column_letter
            break
    if not col_letter: continue
    for cell in col_cells:
        if cell.value and not isinstance(cell,MergedCell):
            max_length=max(max_length,len(str(cell.value)))
    ws.column_dimensions[col_letter].width=max_length+2

wb.save(buffer)
st.download_button("Download Excel",buffer,"break_schedule.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
