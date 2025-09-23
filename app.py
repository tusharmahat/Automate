if generate:
    st.session_state['tables'] = {}
    A_queue = shift_employees["A"].copy()
    B_queue = shift_employees["B"].copy()

    for giver in givers:
        max_breaks = giver_max_breaks[giver]
        num_A = math.ceil(max_breaks / 2)
        num_B = max_breaks - num_A

        # --- Assign employees from queues ---
        assigned_A = A_queue[:num_A]
        A_queue = A_queue[num_A:]  # remove assigned A employees

        assigned_B = []
        for _ in range(num_B):
            if B_queue:
                assigned_B.append(B_queue.pop(0))

        schedule = []
        current_time = datetime.combine(schedule_date, giver_shift_times[giver][0])

        # --- A-Shift 15-min breaks ---
        for emp in assigned_A:
            start = current_time
            end = start + break15
            schedule.append([emp, "15 min", start.strftime("%H:%M"), end.strftime("%H:%M"), ""])
            current_time = end + stagger_gap

        # --- Break giver self-break only if max_breaks >= 4 ---
        if max_breaks >= 4 and assigned_A:
            giver_break_start = current_time
            giver_break_end = giver_break_start + break30
            schedule.append([giver, "30 min (Giver)", giver_break_start.strftime("%H:%M"), giver_break_end.strftime("%H:%M"), ""])
            current_time = giver_break_end + stagger_gap

        # --- A-Shift 30-min breaks ---
        for emp in assigned_A:
            start = current_time
            end = start + break30
            schedule.append([emp, "30 min", start.strftime("%H:%M"), end.strftime("%H:%M"), ""])
            current_time = end + stagger_gap

        # --- Wait until B-shift +1 hour if necessary ---
        if assigned_B:
            B_shift_min_start = datetime.combine(schedule_date, B_shift_start_time) + timedelta(hours=1)
            if current_time < B_shift_min_start:
                current_time = B_shift_min_start

        # --- B-Shift 15-min breaks ---
        for emp in assigned_B:
            start = current_time
            end = start + break15
            schedule.append([emp, "15 min", start.strftime("%H:%M"), end.strftime("%H:%M"), ""])
            current_time = end + stagger_gap

        # --- B-Shift 30-min breaks ---
        for emp in assigned_B:
            start = current_time
            end = start + break30
            schedule.append([emp, "30 min", start.strftime("%H:%M"), end.strftime("%H:%M"), ""])
            current_time = end + stagger_gap

        # --- Total time ---
        if schedule:
            first_start = datetime.strptime(schedule[0][2], "%H:%M")
            last_end = datetime.strptime(schedule[-1][3], "%H:%M")
            total_time = last_end - first_start
            schedule.append(["", "Total Time", first_start.strftime("%H:%M"), last_end.strftime("%H:%M"), str(total_time)])

        df = pd.DataFrame(schedule, columns=["Employee", "Break Type", "Start", "End", "SA Initial"])
        st.session_state['tables'][giver] = df

    st.success("✅ Schedule generated successfully!")
