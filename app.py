"""
TPCT - Streamlit UI
--------------------
The actual input form: pick a competency, date range, daily start
time, allowed days of week, and available instructors. Generates
a plan (or infeasibility report), lets you view/override it, and
download a PDF.

Usage:
    streamlit run app.py
"""

import sqlite3
import os
from datetime import date, timedelta, time, datetime

import streamlit as st
import pandas as pd
from streamlit_calendar import calendar as st_calendar

import scheduler
import pdfexport
import overrides
import dataadmin
import blackout
import dashboard

DB_PATH = "tpct.db"

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DAY_NAME_TO_INT = {name: i for i, name in enumerate(DAY_NAMES)}


def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_competencies(conn):
    cur = conn.cursor()
    cur.execute("SELECT competency_id, name FROM competencies ORDER BY name")
    return cur.fetchall()  # [(id, name), ...]


def get_instructors(conn):
    cur = conn.cursor()
    cur.execute("SELECT instructor_id, name FROM instructors ORDER BY name")
    return cur.fetchall()  # [(id, name), ...]


def get_tasks_for_request(conn, request_id):
    """Distinct task names currently in a generated plan, for the override dropdown."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT DISTINCT t.task_id, t.name
        FROM plan_segments ps
        JOIN tasks t ON ps.task_id = t.task_id
        WHERE ps.request_id = ?
        ORDER BY t.sequence_order
        """,
        (request_id,)
    )
    return cur.fetchall()


# ------------------------------------------------------------
# PAGE SETUP
# ------------------------------------------------------------

st.set_page_config(page_title="Training Plan Creation Tool", layout="wide")
st.title("Training Plan Creation Tool (TPCT)")

conn = get_connection()

if "result" not in st.session_state:
    st.session_state.result = None
if "request_id" not in st.session_state:
    st.session_state.request_id = None

tab_generate, tab_concurrent, tab_manage, tab_blackout, tab_dashboard = st.tabs(
    ["Generate Plan", "Concurrent Plans", "Manage Data", "Blackout Dates", "Instructor Dashboard"]
)

with tab_generate:
    # ------------------------------------------------------------
    # INPUT FORM
    # ------------------------------------------------------------

    st.header("1. Build a Training Plan")

    competencies = get_competencies(conn)
    instructors = get_instructors(conn)

    if not competencies:
        st.error("No competencies found in the database. Run seed.py first.")
        st.stop()

    if not instructors:
        st.error("No instructors found in the database. Run seed.py first.")
        st.stop()

    competency_names = [name for _, name in competencies]
    competency_name_to_id = {name: cid for cid, name in competencies}

    instructor_names = [name for _, name in instructors]
    instructor_name_to_id = {name: iid for iid, name in instructors}

    col1, col2 = st.columns(2)

    with col1:
        selected_competency_name = st.selectbox("Competency", competency_names)
        start_date = st.date_input("Start date", value=date.today() + timedelta(days=7))
        end_date = st.date_input("End date", value=date.today() + timedelta(days=28))
        daily_start_time = st.time_input("Daily start time", value=time(8, 0))
        daily_end_time = st.time_input("Daily end time (hard stop)", value=time(16, 0))

    with col2:
        allowed_day_names = st.multiselect(
            "Allowed training days",
            DAY_NAMES,
            default=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        )
        selected_instructor_names = st.multiselect(
            "Available instructors (for the entire plan duration)",
            instructor_names,
            default=instructor_names
        )

    generate_clicked = st.button("Generate Training Plan", type="primary")

    if generate_clicked:
        if end_date < start_date:
            st.error("End date cannot be before start date.")
        elif daily_end_time <= daily_start_time:
            st.error("Daily end time must be after daily start time.")
        elif not allowed_day_names:
            st.error("Select at least one allowed training day.")
        elif not selected_instructor_names:
            st.error("Select at least one available instructor.")
        else:
            competency_id = competency_name_to_id[selected_competency_name]
            allowed_days_of_week = [DAY_NAME_TO_INT[d] for d in allowed_day_names]
            available_instructor_ids = [instructor_name_to_id[n] for n in selected_instructor_names]

            result = scheduler.create_training_plan(
                conn,
                competency_id=competency_id,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                daily_start_time=daily_start_time.strftime("%H:%M"),
                daily_end_time=daily_end_time.strftime("%H:%M"),
                allowed_days_of_week=allowed_days_of_week,
                available_instructor_ids=available_instructor_ids,
            )
            st.session_state.result = result
            st.session_state.request_id = result["request_id"]


    # ------------------------------------------------------------
    # RESULTS
    # ------------------------------------------------------------

    result = st.session_state.result

    if result is not None:
        st.header("2. Result")

        if result["feasible"]:
            st.success(f"Plan generated successfully (Plan #{result['request_id']}).")

            segments = overrides.get_plan_segments(conn, st.session_state.request_id)

            table_rows = []
            for seg in segments:
                (segment_id, task_id, task_name, instructor_id, instructor_name,
                 segment_date, start_time, end_time, hours) = seg
                table_rows.append({
                    "Date": segment_date,
                    "Time": f"{start_time}-{end_time}",
                    "Task": task_name,
                    "Instructor": instructor_name,
                    "Hours": hours,
                })

            st.dataframe(table_rows, width='stretch', hide_index=True)

            # --- Interactive month-view calendar ---
            st.subheader("Calendar View")

            # Assign a consistent color per instructor so sessions are
            # visually distinguishable at a glance, like Google Calendar.
            palette = ["#1a3a5c", "#8c1c1c", "#2e7d32", "#6a1b9a", "#e65100", "#00838f"]
            instructor_color = {}
            for row in table_rows:
                name = row["Instructor"]
                if name not in instructor_color:
                    instructor_color[name] = palette[len(instructor_color) % len(palette)]

            calendar_events = []
            for row in table_rows:
                start_time_str, end_time_str = row["Time"].split("-")
                calendar_events.append({
                    "title": f"{row['Task']} ({row['Instructor']})",
                    "start": f"{row['Date']}T{start_time_str}:00",
                    "end": f"{row['Date']}T{end_time_str}:00",
                    "backgroundColor": instructor_color[row["Instructor"]],
                    "borderColor": instructor_color[row["Instructor"]],
                })

            # Label blackout dates (federal holidays, etc.) within this
            # plan's window as their own all-day events, so an empty day
            # reads as "Labor Day" instead of just... blank.
            req_details = pdfexport.get_request_details(conn, st.session_state.request_id)
            req_start_date, req_end_date = req_details[2], req_details[3]
            for blackout_date, blackout_label, blackout_source in blackout.list_blackout_dates(
                conn, req_start_date, req_end_date
            ):
                calendar_events.append({
                    "title": blackout_label,
                    "start": blackout_date,
                    "allDay": True,
                    "backgroundColor": "#999999",
                    "borderColor": "#999999",
                    "display": "block",
                })

            st_calendar(
                events=calendar_events,
                options={
                    "initialView": "dayGridMonth",
                    "initialDate": table_rows[0]["Date"] if table_rows else None,
                    "headerToolbar": {
                        "left": "prev,next today",
                        "center": "title",
                        "right": "dayGridMonth,timeGridWeek",
                    },
                    "height": 650,
                },
                key=f"calendar_{st.session_state.request_id}",
            )

            # --- Manual override ---
            st.subheader("Reassign an Instructor")
            st.caption(
                "Swaps the instructor for every session of the selected task. "
                "No qualification check is applied — useful for placing developing "
                "instructors on tasks outside their current qualifications."
            )

            task_options = get_tasks_for_request(conn, st.session_state.request_id)
            task_name_to_id = {name: tid for tid, name in task_options}

            ocol1, ocol2, ocol3 = st.columns([2, 2, 1])
            with ocol1:
                override_task_name = st.selectbox(
                    "Task", list(task_name_to_id.keys()), key="override_task"
                )
            with ocol2:
                override_instructor_name = st.selectbox(
                    "New instructor", instructor_names, key="override_instructor"
                )
            with ocol3:
                st.write("")
                st.write("")
                apply_override = st.button("Apply")

            if apply_override:
                override_result = overrides.reassign_task_instructor(
                    conn,
                    st.session_state.request_id,
                    task_name_to_id[override_task_name],
                    instructor_name_to_id[override_instructor_name],
                )
                if override_result["success"]:
                    st.success(
                        f"Reassigned {override_result['segments_updated']} session(s) of "
                        f"'{override_result['task_name']}' to {override_result['new_instructor_name']}."
                    )
                    st.rerun()
                else:
                    st.error(override_result["error"])

            # --- Move a session to a different date/time ---
            st.subheader("Move a Session to a Different Date/Time")
            st.caption(
                "Reschedules ONE specific session — no check against blackout dates or "
                "other commitments. Useful for a single session that has to shift, or a "
                "standalone recurring requirement (like a quarterly drill) that needs to "
                "land on a specific date."
            )

            move_task_name = st.selectbox(
                "Task", list(task_name_to_id.keys()), key="move_task"
            )
            move_task_id = task_name_to_id[move_task_name]
            segment_options = overrides.get_segments_for_task(conn, st.session_state.request_id, move_task_id)

            if segment_options:
                segment_labels = [
                    f"{seg_date} {start_t}-{end_t} ({hrs:g}h)"
                    for _, seg_date, start_t, end_t, hrs in segment_options
                ]
                segment_label_to_id = {
                    label: seg[0] for label, seg in zip(segment_labels, segment_options)
                }

                mcol1, mcol2, mcol3, mcol4 = st.columns([2, 1.2, 1, 1])
                with mcol1:
                    move_segment_label = st.selectbox(
                        "Which session (if the task spans more than one day)",
                        segment_labels, key="move_segment_select"
                    )
                with mcol2:
                    move_new_date = st.date_input("New date", key="move_new_date")
                with mcol3:
                    current_seg = next(
                        seg for seg in segment_options if seg[0] == segment_label_to_id[move_segment_label]
                    )
                    move_new_start = st.time_input(
                        "New start time", value=datetime.strptime(current_seg[2], "%H:%M").time(),
                        key="move_new_start"
                    )
                with mcol4:
                    move_new_end = st.time_input(
                        "New end time", value=datetime.strptime(current_seg[3], "%H:%M").time(),
                        key="move_new_end"
                    )

                if st.button("Move This Session"):
                    move_result = overrides.move_segment(
                        conn,
                        segment_label_to_id[move_segment_label],
                        move_new_date.isoformat(),
                        move_new_start.strftime("%H:%M"),
                        move_new_end.strftime("%H:%M"),
                    )
                    if move_result["success"]:
                        st.success(
                            f"Moved '{move_result['task_name']}' to {move_result['new_date']} "
                            f"{move_result['new_start_time']}-{move_result['new_end_time']}."
                        )
                        st.rerun()
                    else:
                        st.error(move_result["error"])
            else:
                st.info("No sessions found for this task.")

            # --- PDF download ---
            st.subheader("Download")
            dcol1, dcol2 = st.columns(2)

            with dcol1:
                pdf_path = f"training_plan_{st.session_state.request_id}.pdf"
                pdfexport.export_plan_to_pdf(conn, st.session_state.request_id, pdf_path)
                with open(pdf_path, "rb") as f:
                    st.download_button(
                        "Download Agenda PDF (list view)",
                        data=f.read(),
                        file_name=pdf_path,
                        mime="application/pdf",
                    )

            with dcol2:
                month_pdf_path = f"training_plan_{st.session_state.request_id}_calendar.pdf"
                pdfexport.build_month_grid_pdf(conn, st.session_state.request_id, month_pdf_path)
                with open(month_pdf_path, "rb") as f:
                    st.download_button(
                        "Download Month-View PDF (calendar grid)",
                        data=f.read(),
                        file_name=month_pdf_path,
                        mime="application/pdf",
                    )

        else:
            st.error(f"Plan is not viable (Plan #{result['request_id']}).")
            st.write("Reasons:")
            for r in result["reasons"]:
                st.write(f"- **{r['reason_type'].replace('_', ' ').title()}**: {r['detail']}")

            st.subheader("Download")
            pdf_path = f"infeasibility_report_{st.session_state.request_id}.pdf"
            pdfexport.export_plan_to_pdf(conn, st.session_state.request_id, pdf_path)
            with open(pdf_path, "rb") as f:
                st.download_button(
                    "Download Infeasibility Report (PDF)",
                    data=f.read(),
                    file_name=pdf_path,
                    mime="application/pdf",
                )

with tab_manage:
    st.header("Manage Instructors, Competencies & Tasks")
    st.caption(
        "Changes here take effect immediately for any NEW plan you generate. "
        "Existing generated plans are never altered by changes made here."
    )

    manage_instructors_tab, manage_competencies_tab = st.tabs(["Instructors", "Competencies & Tasks"])

    # ==========================================================
    # INSTRUCTORS
    # ==========================================================
    with manage_instructors_tab:
        st.subheader("Add an Instructor")
        with st.form("add_instructor_form", clear_on_submit=True):
            new_instructor_name = st.text_input("Instructor name")
            add_instructor_submitted = st.form_submit_button("Add Instructor")

        if add_instructor_submitted:
            result = dataadmin.add_instructor(conn, new_instructor_name)
            if result["success"]:
                st.success(f"Added instructor.")
                st.rerun()
            else:
                st.error(result["error"])

        st.divider()
        st.subheader("Edit Qualifications")

        current_instructors = dataadmin.list_instructors(conn)
        if not current_instructors:
            st.info("No instructors yet — add one above.")
        else:
            instructor_display_names = [name for _, name in current_instructors]
            instructor_display_to_id = {name: iid for iid, name in current_instructors}

            selected_instructor_for_edit = st.selectbox(
                "Select an instructor", instructor_display_names, key="manage_instructor_select"
            )
            edit_instructor_id = instructor_display_to_id[selected_instructor_for_edit]

            all_tasks = dataadmin.list_all_tasks_grouped(conn)
            task_label_to_id = {}
            task_labels = []
            for task_id, comp_name, task_name in all_tasks:
                label = f"{comp_name}: {task_name}"
                task_label_to_id[label] = task_id
                task_labels.append(label)

            current_qualified_ids = dataadmin.get_instructor_qualifications(conn, edit_instructor_id)
            current_qualified_labels = [
                label for label, tid in task_label_to_id.items() if tid in current_qualified_ids
            ]

            selected_labels = st.multiselect(
                f"Tasks {selected_instructor_for_edit} is qualified to teach",
                task_labels,
                default=current_qualified_labels,
                key=f"quals_{edit_instructor_id}",
            )

            if st.button("Save Qualifications"):
                selected_ids = {task_label_to_id[label] for label in selected_labels}
                result = dataadmin.set_instructor_qualifications(conn, edit_instructor_id, selected_ids)
                st.success(f"Updated: {result['added']} added, {result['removed']} removed.")
                st.rerun()

            st.divider()
            st.subheader("Remove an Instructor")
            st.caption("Blocked if the instructor has already been used in a generated plan.")
            if st.button(f"Delete {selected_instructor_for_edit}", type="secondary"):
                result = dataadmin.delete_instructor(conn, edit_instructor_id)
                if result["success"]:
                    st.success(f"Deleted {result['name']}.")
                    st.rerun()
                else:
                    st.error(result["error"])

    # ==========================================================
    # COMPETENCIES & TASKS
    # ==========================================================
    with manage_competencies_tab:
        st.subheader("Add a Competency")
        with st.form("add_competency_form", clear_on_submit=True):
            new_competency_name = st.text_input("Competency name")
            add_competency_submitted = st.form_submit_button("Add Competency")

        if add_competency_submitted:
            result = dataadmin.add_competency(conn, new_competency_name)
            if result["success"]:
                st.success("Added competency.")
                st.rerun()
            else:
                st.error(result["error"])

        st.divider()
        st.subheader("Manage Tasks")

        current_competencies = dataadmin.list_competencies(conn)
        if not current_competencies:
            st.info("No competencies yet — add one above.")
        else:
            competency_display_names = [name for _, name in current_competencies]
            competency_display_to_id = {name: cid for cid, name in current_competencies}

            selected_competency_for_edit = st.selectbox(
                "Select a competency", competency_display_names, key="manage_competency_select"
            )
            edit_competency_id = competency_display_to_id[selected_competency_for_edit]

            st.markdown("**Add a task to this competency**")
            with st.form(f"add_task_form_{edit_competency_id}", clear_on_submit=True):
                tcol1, tcol2 = st.columns([3, 1])
                with tcol1:
                    new_task_name = st.text_input("Task name")
                with tcol2:
                    new_task_duration = st.number_input("Duration (hrs)", min_value=0.5, step=0.5, value=1.0)
                add_task_submitted = st.form_submit_button("Add Task")

            if add_task_submitted:
                result = dataadmin.add_task(conn, edit_competency_id, new_task_name, new_task_duration)
                if result["success"]:
                    st.success(f"Added task at sequence #{result['sequence_order']}.")
                    st.rerun()
                else:
                    st.error(result["error"])

            st.markdown("**Current task sequence** (fixed teaching order)")
            tasks = dataadmin.list_tasks_for_competency(conn, edit_competency_id)

            if not tasks:
                st.info("No tasks yet for this competency — add one above.")
            else:
                for idx, (task_id, task_name, duration_hours, sequence_order) in enumerate(tasks):
                    row = st.columns([0.5, 3, 1.2, 0.6, 0.6, 1])
                    row[0].write(f"#{sequence_order}")
                    row[1].write(task_name)
                    row[2].write(f"{duration_hours:g} hrs")
                    if row[3].button("↑", key=f"up_{task_id}", disabled=(idx == 0)):
                        dataadmin.move_task(conn, task_id, "up")
                        st.rerun()
                    if row[4].button("↓", key=f"down_{task_id}", disabled=(idx == len(tasks) - 1)):
                        dataadmin.move_task(conn, task_id, "down")
                        st.rerun()
                    if row[5].button("Delete", key=f"del_{task_id}"):
                        result = dataadmin.delete_task(conn, task_id)
                        if result["success"]:
                            st.rerun()
                        else:
                            st.error(result["error"])

            st.divider()
            st.subheader("Remove This Competency")
            st.caption("Blocked if it still has tasks defined, or has been used in a generated plan.")
            if st.button(f"Delete {selected_competency_for_edit}", type="secondary"):
                result = dataadmin.delete_competency(conn, edit_competency_id)
                if result["success"]:
                    st.success(f"Deleted {result['name']}.")
                    st.rerun()
                else:
                    st.error(result["error"])

with tab_blackout:
    st.header("Blackout Dates")
    st.caption(
        "Dates listed here are automatically excluded from every plan you generate, "
        "regardless of which training days you select."
    )

    st.subheader("Federal Holidays")
    from datetime import date as _date
    current_year = _date.today().year

    hcol1, hcol2 = st.columns([1, 1])
    with hcol1:
        holiday_start_year = st.number_input(
            "From year", min_value=2000, max_value=2100, value=current_year, step=1
        )
    with hcol2:
        holiday_end_year = st.number_input(
            "Through year", min_value=2000, max_value=2100, value=current_year + 2, step=1
        )

    if st.button("Populate Federal Holidays for This Range"):
        if holiday_end_year < holiday_start_year:
            st.error("End year must be on or after the start year.")
        else:
            inserted = blackout.populate_federal_holidays(conn, int(holiday_start_year), int(holiday_end_year))
            st.success(f"Added {inserted} new federal holiday date(s). Already-populated years are skipped safely.")
            st.rerun()

    st.divider()
    st.subheader("Add a Specific Blackout Date")
    st.caption(
        "For anything not covered by federal holidays — base standdowns, "
        "unit-specific closures, a single day you know is off-limits."
    )
    with st.form("add_blackout_form", clear_on_submit=True):
        bcol1, bcol2 = st.columns([1, 2])
        with bcol1:
            new_blackout_date = st.date_input("Date")
        with bcol2:
            new_blackout_label = st.text_input("Label", placeholder="e.g. Base Standdown")
        add_blackout_submitted = st.form_submit_button("Add Blackout Date")

    if add_blackout_submitted:
        result = blackout.add_manual_blackout_date(
            conn, new_blackout_date.isoformat(), new_blackout_label
        )
        if result["success"]:
            st.success(f"Added {new_blackout_date.isoformat()} as a blackout date.")
            st.rerun()
        else:
            st.error(result["error"])

    st.divider()
    st.subheader("Currently Blacked-Out Dates")

    all_blackouts = blackout.list_blackout_dates(conn)
    if not all_blackouts:
        st.info("No blackout dates yet — populate federal holidays above to get started.")
    else:
        blackout_rows = [
            {"Date": d, "Label": label, "Source": source.replace("_", " ").title()}
            for d, label, source in all_blackouts
        ]
        st.dataframe(blackout_rows, width='stretch', hide_index=True)

        st.divider()
        st.subheader("Remove a Blackout Date")
        st.caption("Useful if a federal holiday shouldn't apply to your unit, or to undo a manual entry.")
        blackout_labels = [f"{d} — {label}" for d, label, _ in all_blackouts]
        blackout_label_to_date = {f"{d} — {label}": d for d, label, _ in all_blackouts}

        selected_blackout_label = st.selectbox("Select a date to remove", blackout_labels)
        if st.button("Remove Selected Blackout Date"):
            date_to_remove = blackout_label_to_date[selected_blackout_label]
            result = blackout.remove_blackout_date(conn, date_to_remove)
            if result["success"]:
                st.success(f"Removed {date_to_remove} ({result['label']}).")
                st.rerun()
            else:
                st.error(result["error"])

with tab_dashboard:
    st.header("Instructor Workload Dashboard")
    st.caption(
        "The scheduler balances load WITHIN a single plan, but has no memory of what "
        "an instructor has already taught in OTHER plans. This view shows the real "
        "picture across everything you've generated, so you can spot and correct "
        "long-term imbalance yourself."
    )

    overall_min_date, overall_max_date = dashboard.get_overall_date_range(conn)

    if overall_min_date is None:
        st.info("No plans have been generated yet — generate at least one plan to see workload data here.")
    else:
        use_date_filter = st.checkbox("Restrict to a date range (unchecked = all-time totals)")

        filter_start, filter_end = None, None
        if use_date_filter:
            fcol1, fcol2 = st.columns(2)
            with fcol1:
                filter_start_input = st.date_input(
                    "From", value=datetime.strptime(overall_min_date, "%Y-%m-%d").date()
                )
            with fcol2:
                filter_end_input = st.date_input(
                    "Through", value=datetime.strptime(overall_max_date, "%Y-%m-%d").date()
                )
            filter_start = filter_start_input.isoformat()
            filter_end = filter_end_input.isoformat()

        summary = dashboard.get_instructor_hours_summary(conn, filter_start, filter_end)

        st.subheader("Total Hours Taught, by Instructor")
        chart_data = {row["name"]: row["total_hours"] for row in summary}
        st.bar_chart(chart_data)

        st.subheader("Summary")
        summary_rows = [
            {
                "Instructor": row["name"],
                "Total Hours": row["total_hours"],
                "Sessions": row["session_count"],
                "Distinct Tasks": row["distinct_tasks"],
                "Plans Involved In": row["distinct_plans"],
            }
            for row in summary
        ]
        st.dataframe(summary_rows, width='stretch', hide_index=True)

        st.subheader("Hours by Competency")
        breakdown = dashboard.get_instructor_competency_breakdown(conn, filter_start, filter_end)
        if not breakdown:
            st.info("No sessions in this range yet.")
        else:
            breakdown_df = pd.DataFrame(breakdown, columns=["Instructor", "Competency", "Hours"])
            pivot = breakdown_df.pivot_table(
                index="Instructor", columns="Competency", values="Hours", fill_value=0, aggfunc="sum"
            )
            st.dataframe(pivot, width='stretch')

        st.subheader("Drill Into an Instructor")
        instructor_names_dash = [row["name"] for row in summary]
        if instructor_names_dash:
            selected_dash_instructor = st.selectbox(
                "Instructor", instructor_names_dash, key="dashboard_instructor_select"
            )
            selected_dash_id = next(
                row["instructor_id"] for row in summary if row["name"] == selected_dash_instructor
            )
            activity = dashboard.get_instructor_activity_detail(
                conn, selected_dash_id, filter_start, filter_end
            )
            if not activity:
                st.info(f"No sessions for {selected_dash_instructor} in this range.")
            else:
                activity_rows = [
                    {
                        "Date": a[0],
                        "Task": a[1],
                        "Competency": a[2],
                        "Hours": a[3],
                        "Plan #": a[4],
                    }
                    for a in activity
                ]
                st.dataframe(activity_rows, width='stretch', hide_index=True)

with tab_concurrent:
    st.header("Plan Multiple Competencies Concurrently")
    st.caption(
        "Build several competencies together, each with its own dates, daily hours, and "
        "training days. Instructors are automatically kept from being double-booked across "
        "them — if the same person would be needed in two places at once, the tool picks a "
        "different qualified instructor instead, or flags it if no alternative exists."
    )

    if "concurrent_components" not in st.session_state:
        st.session_state.concurrent_components = []
    if "concurrent_result" not in st.session_state:
        st.session_state.concurrent_result = None

    st.subheader("1. Add Competencies to This Batch")

    concurrent_competencies = dataadmin.list_competencies(conn)
    concurrent_instructors = dataadmin.list_instructors(conn)

    if not concurrent_competencies or not concurrent_instructors:
        st.info("Add at least one competency and one instructor in the Manage Data tab first.")
    else:
        comp_names = [name for _, name in concurrent_competencies]
        comp_name_to_id = {name: cid for cid, name in concurrent_competencies}
        inst_names = [name for _, name in concurrent_instructors]
        inst_name_to_id = {name: iid for iid, name in concurrent_instructors}

        with st.form("add_concurrent_component_form", clear_on_submit=True):
            ccol1, ccol2 = st.columns(2)
            with ccol1:
                cc_competency = st.selectbox("Competency", comp_names, key="cc_competency")
                cc_start = st.date_input("Start date", value=date.today() + timedelta(days=7), key="cc_start")
                cc_end = st.date_input("End date", value=date.today() + timedelta(days=28), key="cc_end")
                cc_start_time = st.time_input("Daily start time", value=time(8, 0), key="cc_start_time")
                cc_end_time = st.time_input("Daily end time (hard stop)", value=time(16, 0), key="cc_end_time")
            with ccol2:
                cc_days = st.multiselect(
                    "Allowed training days", DAY_NAMES,
                    default=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"], key="cc_days"
                )
                cc_instructors = st.multiselect(
                    "Available instructors", inst_names, default=inst_names, key="cc_instructors"
                )

            add_component_submitted = st.form_submit_button("Add to Batch")

        if add_component_submitted:
            if cc_end < cc_start:
                st.error("End date cannot be before start date.")
            elif cc_end_time <= cc_start_time:
                st.error("Daily end time must be after daily start time.")
            elif not cc_days:
                st.error("Select at least one allowed training day.")
            elif not cc_instructors:
                st.error("Select at least one available instructor.")
            else:
                st.session_state.concurrent_components.append({
                    "competency_name": cc_competency,
                    "competency_id": comp_name_to_id[cc_competency],
                    "start_date": cc_start.isoformat(),
                    "end_date": cc_end.isoformat(),
                    "daily_start_time": cc_start_time.strftime("%H:%M"),
                    "daily_end_time": cc_end_time.strftime("%H:%M"),
                    "allowed_days_of_week": [DAY_NAME_TO_INT[d] for d in cc_days],
                    "allowed_days_display": ", ".join(cc_days),
                    "available_instructor_ids": [inst_name_to_id[n] for n in cc_instructors],
                    "available_instructor_names": ", ".join(cc_instructors),
                })
                st.rerun()

    st.subheader("2. Current Batch")
    if not st.session_state.concurrent_components:
        st.info("No competencies added to this batch yet.")
    else:
        for idx, comp in enumerate(st.session_state.concurrent_components):
            with st.container(border=True):
                bcol1, bcol2 = st.columns([5, 1])
                with bcol1:
                    st.markdown(f"**{comp['competency_name']}**")
                    st.caption(
                        f"{comp['start_date']} to {comp['end_date']} | "
                        f"{comp['daily_start_time']}-{comp['daily_end_time']} | "
                        f"{comp['allowed_days_display']} | "
                        f"Instructors: {comp['available_instructor_names']}"
                    )
                with bcol2:
                    if st.button("Remove", key=f"remove_cc_{idx}"):
                        st.session_state.concurrent_components.pop(idx)
                        st.rerun()

        gcol1, gcol2 = st.columns([1, 1])
        with gcol1:
            generate_concurrent_clicked = st.button("Generate Concurrent Plan", type="primary")
        with gcol2:
            clear_batch_clicked = st.button("Clear Batch")

        if clear_batch_clicked:
            st.session_state.concurrent_components = []
            st.session_state.concurrent_result = None
            st.rerun()

        if generate_concurrent_clicked:
            batch_label = f"Batch generated {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            result = scheduler.create_multi_competency_plan(
                conn, st.session_state.concurrent_components, label=batch_label
            )
            st.session_state.concurrent_result = result

    concurrent_result = st.session_state.concurrent_result
    if concurrent_result is not None:
        st.subheader("3. Results")
        batch_id = concurrent_result["batch_id"]

        for r in concurrent_result["results"]:
            if r["feasible"]:
                st.success(f"{r['competency_name']}: feasible ({len(r['segments'])} sessions)")
            else:
                st.error(f"{r['competency_name']}: not viable")
                for reason in r["reasons"]:
                    st.write(f"- **{reason['reason_type'].replace('_', ' ').title()}**: {reason['detail']}")

        feasible_results = [r for r in concurrent_result["results"] if r["feasible"]]

        if feasible_results:
            st.subheader("Combined Calendar")

            batch_palette = ["#1a3a5c", "#8c1c1c", "#2e7d32", "#6a1b9a", "#e65100", "#00838f"]
            competency_color = {}
            batch_segments = pdfexport.get_batch_segments(conn, batch_id)

            calendar_events = []
            for seg_date, start_t, end_t, task_name, hours, instr_name, comp_name, req_id in batch_segments:
                if comp_name not in competency_color:
                    competency_color[comp_name] = batch_palette[len(competency_color) % len(batch_palette)]
                calendar_events.append({
                    "title": f"{task_name} ({instr_name})",
                    "start": f"{seg_date}T{start_t}:00",
                    "end": f"{seg_date}T{end_t}:00",
                    "backgroundColor": competency_color[comp_name],
                    "borderColor": competency_color[comp_name],
                })

            legend_html = " &nbsp;&nbsp; ".join(
                f'<span style="color:{color}">\u25A0</span> {name}'
                for name, color in competency_color.items()
            )
            st.markdown(legend_html, unsafe_allow_html=True)

            st_calendar(
                events=calendar_events,
                options={
                    "initialView": "dayGridMonth",
                    "initialDate": calendar_events[0]["start"][:10] if calendar_events else None,
                    "headerToolbar": {
                        "left": "prev,next today",
                        "center": "title",
                        "right": "dayGridMonth,timeGridWeek",
                    },
                    "height": 650,
                },
                key=f"concurrent_calendar_{batch_id}",
            )

            st.subheader("Reassign an Instructor")
            st.caption(
                "Pick which competency's plan you're adjusting, then the task and new instructor. "
                "No qualification check is applied."
            )

            # Label by BOTH competency name and its date range, and map that
            # label directly to a request_id — matching on name alone breaks
            # the moment the same competency appears more than once in a
            # batch (e.g. the same quarterly drill added four times).
            batch_component_dates = {
                request_id: (start_date, end_date)
                for request_id, _, start_date, end_date, _ in pdfexport.get_batch_components(conn, batch_id)
            }
            component_label_to_request_id = {}
            for r in feasible_results:
                start_date, end_date = batch_component_dates[r["request_id"]]
                label = f"{r['competency_name']} ({start_date} to {end_date})"
                component_label_to_request_id[label] = r["request_id"]

            rcol1, rcol2, rcol3 = st.columns([2, 2, 2])
            with rcol1:
                override_comp_choice = st.selectbox(
                    "Competency", list(component_label_to_request_id.keys()), key="concurrent_override_comp"
                )
            override_request_id = component_label_to_request_id[override_comp_choice]
            override_task_options = get_tasks_for_request(conn, override_request_id)
            override_task_name_to_id = {name: tid for tid, name in override_task_options}
            with rcol2:
                override_task_choice = st.selectbox(
                    "Task", list(override_task_name_to_id.keys()), key="concurrent_override_task"
                )
            with rcol3:
                override_instructor_choice = st.selectbox(
                    "New instructor", inst_names, key="concurrent_override_instructor"
                )

            if st.button("Apply Reassignment", key="concurrent_apply_override"):
                override_result = overrides.reassign_task_instructor(
                    conn,
                    override_request_id,
                    override_task_name_to_id[override_task_choice],
                    inst_name_to_id[override_instructor_choice],
                )
                if override_result["success"]:
                    st.success(
                        f"Reassigned {override_result['segments_updated']} session(s) of "
                        f"'{override_result['task_name']}' to {override_result['new_instructor_name']}."
                    )
                    st.rerun()
                else:
                    st.error(override_result["error"])

            st.subheader("Move a Session to a Different Date/Time")
            st.caption(
                "Reschedules ONE specific session within the competency you pick above — "
                "no check against blackout dates or other commitments in the batch. "
                "Useful for a standalone recurring requirement (like a quarterly drill) "
                "that needs to land on a specific date."
            )
            move_task_choice = st.selectbox(
                "Task", list(override_task_name_to_id.keys()), key="concurrent_move_task"
            )
            move_task_id = override_task_name_to_id[move_task_choice]
            concurrent_segment_options = overrides.get_segments_for_task(conn, override_request_id, move_task_id)

            if concurrent_segment_options:
                concurrent_segment_labels = [
                    f"{seg_date} {start_t}-{end_t} ({hrs:g}h)"
                    for _, seg_date, start_t, end_t, hrs in concurrent_segment_options
                ]
                concurrent_segment_label_to_id = {
                    label: seg[0] for label, seg in zip(concurrent_segment_labels, concurrent_segment_options)
                }

                mcol1, mcol2, mcol3, mcol4 = st.columns([2, 1.2, 1, 1])
                with mcol1:
                    concurrent_move_segment_label = st.selectbox(
                        "Which session", concurrent_segment_labels, key="concurrent_move_segment_select"
                    )
                current_concurrent_seg = next(
                    seg for seg in concurrent_segment_options
                    if seg[0] == concurrent_segment_label_to_id[concurrent_move_segment_label]
                )
                with mcol2:
                    concurrent_move_new_date = st.date_input("New date", key="concurrent_move_new_date")
                with mcol3:
                    concurrent_move_new_start = st.time_input(
                        "New start time", value=datetime.strptime(current_concurrent_seg[2], "%H:%M").time(),
                        key="concurrent_move_new_start"
                    )
                with mcol4:
                    concurrent_move_new_end = st.time_input(
                        "New end time", value=datetime.strptime(current_concurrent_seg[3], "%H:%M").time(),
                        key="concurrent_move_new_end"
                    )

                if st.button("Move This Session", key="concurrent_move_button"):
                    move_result = overrides.move_segment(
                        conn,
                        concurrent_segment_label_to_id[concurrent_move_segment_label],
                        concurrent_move_new_date.isoformat(),
                        concurrent_move_new_start.strftime("%H:%M"),
                        concurrent_move_new_end.strftime("%H:%M"),
                    )
                    if move_result["success"]:
                        st.success(
                            f"Moved '{move_result['task_name']}' to {move_result['new_date']} "
                            f"{move_result['new_start_time']}-{move_result['new_end_time']}."
                        )
                        st.rerun()
                    else:
                        st.error(move_result["error"])
            else:
                st.info("No sessions found for this task.")

            st.subheader("Download")
            dcol1, dcol2 = st.columns(2)
            with dcol1:
                batch_agenda_path = f"concurrent_plan_{batch_id}_agenda.pdf"
                pdfexport.build_batch_plan_pdf(conn, batch_id, batch_agenda_path)
                with open(batch_agenda_path, "rb") as f:
                    st.download_button(
                        "Download Combined Agenda PDF",
                        data=f.read(),
                        file_name=batch_agenda_path,
                        mime="application/pdf",
                    )
            with dcol2:
                batch_month_path = f"concurrent_plan_{batch_id}_calendar.pdf"
                pdfexport.build_batch_month_grid_pdf(conn, batch_id, batch_month_path)
                with open(batch_month_path, "rb") as f:
                    st.download_button(
                        "Download Combined Month-View PDF",
                        data=f.read(),
                        file_name=batch_month_path,
                        mime="application/pdf",
                    )
