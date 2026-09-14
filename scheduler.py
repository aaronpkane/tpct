import sqlite3
from datetime import datetime, timedelta

import blackout

DB_PATH = "tpct.db"

LUNCH_START = "11:30"       # fixed clock-time lunch window, every day
LUNCH_END = "12:30"


def _lunch_overlap_hours(daily_start_time, daily_end_time):

    day_start = parse_time(daily_start_time)
    day_end = parse_time(daily_end_time)
    lunch_start = parse_time(LUNCH_START)
    lunch_end = parse_time(LUNCH_END)

    overlap_start = max(day_start, lunch_start)
    overlap_end = min(day_end, lunch_end)
    overlap_hours = (overlap_end - overlap_start).total_seconds() / 3600.0
    return max(0.0, overlap_hours)


def compute_daily_capacity_hours(daily_start_time, daily_end_time):

    start_dt = parse_time(daily_start_time)
    end_dt = parse_time(daily_end_time)
    total_span_hours = (end_dt - start_dt).total_seconds() / 3600.0

    if total_span_hours <= 0:
        raise ValueError(
            f"Daily window ({daily_start_time}-{daily_end_time}) is invalid — "
            f"the end time must be after the start time."
        )

    lunch_hours = _lunch_overlap_hours(daily_start_time, daily_end_time)
    instructional_hours = total_span_hours - lunch_hours

    if instructional_hours <= 0:
        raise ValueError(
            f"Daily window ({daily_start_time}-{daily_end_time}) leaves no instructional "
            f"time once the {LUNCH_START}-{LUNCH_END} lunch break is excluded."
        )

    return instructional_hours


# ------------------------------------------------------------
# TIME HELPERS
# ------------------------------------------------------------

def parse_time(hhmm):
    return datetime.strptime(hhmm, "%H:%M")


def format_time(dt):
    return dt.strftime("%H:%M")


def add_hours(dt, hours):
    return dt + timedelta(hours=hours)


# ------------------------------------------------------------
# DATA LOADING
# ------------------------------------------------------------

def get_tasks_for_competency(conn, competency_id):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT task_id, name, duration_hours, sequence_order
        FROM tasks
        WHERE competency_id = ?
        ORDER BY sequence_order
        """,
        (competency_id,)
    )
    return cur.fetchall()  # list of (task_id, name, duration_hours, sequence_order)


def get_qualified_instructors(conn, task_id, available_instructor_ids):
    if not available_instructor_ids:
        return []
    cur = conn.cursor()
    placeholders = ",".join("?" * len(available_instructor_ids))
    cur.execute(
        f"""
        SELECT i.instructor_id, i.name
        FROM instructors i
        JOIN instructor_qualifications iq ON i.instructor_id = iq.instructor_id
        WHERE iq.task_id = ?
        AND i.instructor_id IN ({placeholders})
        """,
        (task_id, *available_instructor_ids)
    )
    return cur.fetchall()  # list of (instructor_id, name)


# ------------------------------------------------------------
# ELIGIBLE DATES
# ------------------------------------------------------------

def get_eligible_dates(conn, start_date, end_date, allowed_days_of_week):

    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()
    allowed = set(allowed_days_of_week)
    blackout_set = blackout.get_blackout_date_set(conn)

    dates = []
    current = start
    while current <= end:
        if current.weekday() in allowed and current.isoformat() not in blackout_set:
            dates.append(current)
        current += timedelta(days=1)
    return dates


def build_time_blocks(eligible_dates, daily_start_time, daily_end_time):
    
    blocks = []
    day_start_dt = parse_time(daily_start_time)
    day_end_dt = parse_time(daily_end_time)
    lunch_start_dt = parse_time(LUNCH_START)
    lunch_end_dt = parse_time(LUNCH_END)

    overlap_start = max(day_start_dt, lunch_start_dt)
    overlap_end = min(day_end_dt, lunch_end_dt)
    has_lunch_break = overlap_start < overlap_end  # real overlap, not just touching

    for d in eligible_dates:
        if has_lunch_break:
            pre_hours = (overlap_start - day_start_dt).total_seconds() / 3600.0
            post_hours = (day_end_dt - overlap_end).total_seconds() / 3600.0

            if pre_hours > 0:
                blocks.append({
                    "date": d,
                    "start": format_time(day_start_dt),
                    "end": format_time(overlap_start),
                    "capacity": pre_hours,
                    "remaining": pre_hours,
                })
            if post_hours > 0:
                blocks.append({
                    "date": d,
                    "start": format_time(overlap_end),
                    "end": format_time(day_end_dt),
                    "capacity": post_hours,
                    "remaining": post_hours,
                })
        else:
            full_hours = (day_end_dt - day_start_dt).total_seconds() / 3600.0
            blocks.append({
                "date": d,
                "start": format_time(day_start_dt),
                "end": format_time(day_end_dt),
                "capacity": full_hours,
                "remaining": full_hours,
            })

    return blocks


# ------------------------------------------------------------
# FEASIBILITY CHECK
# ------------------------------------------------------------

def check_feasibility(conn, tasks, eligible_dates, available_instructor_ids, daily_capacity_hours,
                       blackout_days_excluded=0):
    
    reasons = []

    # --- Check 1: total hours shortfall ---
    total_required = sum(t[2] for t in tasks)  # t[2] = duration_hours
    total_available = len(eligible_dates) * daily_capacity_hours

    if total_required > total_available:
        shortfall = total_required - total_available
        blackout_note = (
            f" (includes {blackout_days_excluded} day(s) excluded for holidays/blackouts)"
            if blackout_days_excluded > 0 else ""
        )
        reasons.append({
            "reason_type": "SHORTFALL",
            "task_id": None,
            "detail": f"Shortfall: {shortfall:g} hours over allotted range "
                      f"(required {total_required:g} hrs, available {total_available:g} hrs "
                      f"across {len(eligible_dates)} eligible day(s)){blackout_note}"
        })

    # --- Check 2: every task has at least one qualified+available instructor ---
    for task_id, name, duration_hours, seq in tasks:
        qualified = get_qualified_instructors(conn, task_id, available_instructor_ids)
        if not qualified:
            reasons.append({
                "reason_type": "NO_INSTRUCTOR",
                "task_id": task_id,
                "detail": f"Task: {name} — no available instructor"
            })

    return reasons


# ------------------------------------------------------------
# SCHEDULE GENERATION
# ------------------------------------------------------------

def get_instructor_hours_loaded(load_tracker, instructor_id):
    return load_tracker.get(instructor_id, 0.0)


def pick_least_loaded_instructor(qualified_instructors, load_tracker):
    
    return min(
        qualified_instructors,
        key=lambda inst: (get_instructor_hours_loaded(load_tracker, inst[0]), inst[0])
    )


def generate_schedule(conn, tasks, blocks, available_instructor_ids):
    
    segments = []
    load_tracker = {}  # instructor_id -> hours assigned this plan
    block_index = 0

    for task_id, task_name, duration_hours, seq in tasks:
        qualified = get_qualified_instructors(conn, task_id, available_instructor_ids)
        # Feasibility check already guarantees this is non-empty
        instructor_id, instructor_name = pick_least_loaded_instructor(qualified, load_tracker)

        remaining = duration_hours

        while remaining > 0:
            if block_index >= len(blocks):
                # Should not happen if feasibility check passed — safety guard only
                raise RuntimeError(
                    f"Ran out of schedule blocks while placing task '{task_name}'. "
                    f"This indicates a feasibility-check bug, not a bad input."
                )

            block = blocks[block_index]

            if block["remaining"] <= 0:
                block_index += 1
                continue

            hours_this_segment = min(remaining, block["remaining"])

            # Compute actual clock start/end for this segment within the block
            block_start_dt = parse_time(block["start"])
            used_so_far = block["capacity"] - block["remaining"]
            segment_start_dt = add_hours(block_start_dt, used_so_far)
            segment_end_dt = add_hours(segment_start_dt, hours_this_segment)

            segments.append({
                "task_id": task_id,
                "task_name": task_name,
                "assigned_instructor_id": instructor_id,
                "assigned_instructor_name": instructor_name,
                "segment_date": block["date"].isoformat(),
                "start_time": format_time(segment_start_dt),
                "end_time": format_time(segment_end_dt),
                "hours_this_segment": hours_this_segment,
            })

            block["remaining"] -= hours_this_segment
            remaining -= hours_this_segment
            load_tracker[instructor_id] = get_instructor_hours_loaded(load_tracker, instructor_id) + hours_this_segment

            if block["remaining"] <= 0:
                block_index += 1

    return segments


# ------------------------------------------------------------
# CONCURRENT (MULTI-COMPETENCY) SCHEDULE GENERATION
# ------------------------------------------------------------
# Used when several competencies are being planned together so they
# "fit together on the calendar" — each with its OWN date range,
# daily hours, and allowed days, but sharing an instructor pool that
# must never be double-booked across them. See create_multi_competency_plan().

def times_overlap(date1, start1, end1, date2, start2, end2):
    
    if date1 != date2:
        return False
    s1, e1 = parse_time(start1), parse_time(end1)
    s2, e2 = parse_time(start2), parse_time(end2)
    return s1 < e2 and s2 < e1


def _is_conflict_free(occupied_ledger, local_additions, instructor_id, pending_segments):
    
    existing = occupied_ledger.get(instructor_id, []) + local_additions.get(instructor_id, [])
    for seg in pending_segments:
        for (d, s, e) in existing:
            if times_overlap(seg["segment_date"], seg["start_time"], seg["end_time"], d, s, e):
                return False
    return True


def generate_schedule_with_conflict_avoidance(conn, tasks, blocks, available_instructor_ids,
                                               occupied_ledger, load_tracker):
    
    segments = []
    local_ledger_additions = {}   # instructor_id -> list of (date_iso, start_time, end_time), THIS component only
    local_load_additions = {}     # instructor_id -> hours, THIS component only
    block_index = 0

    for task_id, task_name, duration_hours, seq in tasks:
        qualified = get_qualified_instructors(conn, task_id, available_instructor_ids)
        # Feasibility pre-check guarantees at least one qualified+available
        # instructor exists — it does NOT guarantee one is conflict-free,
        # which is exactly what this function checks.

        # Phase 1: figure out exactly which blocks/dates/times this task
        # will consume, independent of who ends up teaching it.
        remaining = duration_hours
        pending_segments = []

        while remaining > 0:
            if block_index >= len(blocks):
                raise RuntimeError(
                    f"Ran out of schedule blocks while placing task '{task_name}'. "
                    f"This indicates a feasibility-check bug, not a bad input."
                )
            block = blocks[block_index]
            if block["remaining"] <= 0:
                block_index += 1
                continue

            hours_this_segment = min(remaining, block["remaining"])
            block_start_dt = parse_time(block["start"])
            used_so_far = block["capacity"] - block["remaining"]
            segment_start_dt = add_hours(block_start_dt, used_so_far)
            segment_end_dt = add_hours(segment_start_dt, hours_this_segment)

            pending_segments.append({
                "task_id": task_id,
                "task_name": task_name,
                "segment_date": block["date"].isoformat(),
                "start_time": format_time(segment_start_dt),
                "end_time": format_time(segment_end_dt),
                "hours_this_segment": hours_this_segment,
            })

            block["remaining"] -= hours_this_segment
            remaining -= hours_this_segment
            if block["remaining"] <= 0:
                block_index += 1

        # Phase 2: pick a conflict-free instructor from among those
        # qualified+available, preferring least-loaded across the
        # whole batch (shared load_tracker + this component's own
        # additions so far).
        conflict_free_candidates = [
            inst for inst in qualified
            if _is_conflict_free(occupied_ledger, local_ledger_additions, inst[0], pending_segments)
        ]

        if not conflict_free_candidates:
            conflicting_names = ", ".join(name for _, name in qualified)
            return {
                "success": False,
                "conflict_task_id": task_id,
                "conflict_detail": (
                    f"Task: {task_name} — every qualified/available instructor "
                    f"({conflicting_names}) is already committed to another "
                    f"concurrent competency at an overlapping time."
                ),
            }

        effective_load = dict(load_tracker)
        for iid, hrs in local_load_additions.items():
            effective_load[iid] = effective_load.get(iid, 0.0) + hrs

        instructor_id, instructor_name = pick_least_loaded_instructor(conflict_free_candidates, effective_load)

        for seg in pending_segments:
            seg["assigned_instructor_id"] = instructor_id
            seg["assigned_instructor_name"] = instructor_name
            segments.append(seg)

        local_ledger_additions.setdefault(instructor_id, []).extend(
            (seg["segment_date"], seg["start_time"], seg["end_time"]) for seg in pending_segments
        )
        local_load_additions[instructor_id] = local_load_additions.get(instructor_id, 0.0) + sum(
            seg["hours_this_segment"] for seg in pending_segments
        )

    return {
        "success": True,
        "segments": segments,
        "ledger_additions": local_ledger_additions,
        "load_additions": local_load_additions,
    }


# ------------------------------------------------------------
# PERSISTENCE
# ------------------------------------------------------------

def save_request(conn, competency_id, start_date, end_date, daily_start_time, daily_end_time,
                  allowed_days_of_week, available_instructor_ids):
    cur = conn.cursor()
    days_str = ",".join(str(d) for d in sorted(allowed_days_of_week))
    cur.execute(
        """
        INSERT INTO training_plan_requests
        (competency_id, start_date, end_date, daily_start_time, daily_end_time, allowed_days_of_week)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (competency_id, start_date, end_date, daily_start_time, daily_end_time, days_str)
    )
    request_id = cur.lastrowid

    for instructor_id in available_instructor_ids:
        cur.execute(
            "INSERT INTO request_instructors (request_id, instructor_id) VALUES (?, ?)",
            (request_id, instructor_id)
        )

    conn.commit()
    return request_id


def save_segments(conn, request_id, segments):
    cur = conn.cursor()
    for seg in segments:
        cur.execute(
            """
            INSERT INTO plan_segments
            (request_id, task_id, assigned_instructor_id, segment_date, start_time, end_time, hours_this_segment)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (request_id, seg["task_id"], seg["assigned_instructor_id"], seg["segment_date"],
             seg["start_time"], seg["end_time"], seg["hours_this_segment"])
        )
    conn.commit()


def save_infeasibility(conn, request_id, reasons):
    cur = conn.cursor()
    for r in reasons:
        cur.execute(
            """
            INSERT INTO infeasibility_reasons (request_id, reason_type, task_id, detail)
            VALUES (?, ?, ?, ?)
            """,
            (request_id, r["reason_type"], r["task_id"], r["detail"])
        )
    conn.commit()


# ------------------------------------------------------------
# MAIN ENTRY POINT
# ------------------------------------------------------------

def create_training_plan(conn, competency_id, start_date, end_date, daily_start_time, daily_end_time,
                          allowed_days_of_week, available_instructor_ids):
    
    tasks = get_tasks_for_competency(conn, competency_id)
    eligible_dates = get_eligible_dates(conn, start_date, end_date, allowed_days_of_week)

    request_id = save_request(
        conn, competency_id, start_date, end_date, daily_start_time, daily_end_time,
        allowed_days_of_week, available_instructor_ids
    )

    # Daily window itself might be invalid (e.g. end <= start, or too short
    # for even the lunch break) — treat that as its own infeasibility reason
    # rather than crashing.
    try:
        daily_capacity_hours = compute_daily_capacity_hours(daily_start_time, daily_end_time)
    except ValueError as e:
        reasons = [{
            "reason_type": "INVALID_TIME_WINDOW",
            "task_id": None,
            "detail": str(e),
        }]
        save_infeasibility(conn, request_id, reasons)
        return {"feasible": False, "request_id": request_id, "reasons": reasons}

    # Count how many days would have been eligible on weekday-filter alone,
    # but got excluded specifically because of a blackout date — purely
    # informational, surfaced in the SHORTFALL message if relevant.
    blackout_set = blackout.get_blackout_date_set(conn)
    start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
    end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
    allowed_set = set(allowed_days_of_week)
    raw_weekday_dates = []
    current = start_dt
    while current <= end_dt:
        if current.weekday() in allowed_set:
            raw_weekday_dates.append(current)
        current += timedelta(days=1)
    blackout_days_excluded = sum(
        1 for d in raw_weekday_dates if d.isoformat() in blackout_set
    )

    reasons = check_feasibility(
        conn, tasks, eligible_dates, available_instructor_ids, daily_capacity_hours,
        blackout_days_excluded=blackout_days_excluded
    )

    if reasons:
        save_infeasibility(conn, request_id, reasons)
        return {"feasible": False, "request_id": request_id, "reasons": reasons}

    blocks = build_time_blocks(eligible_dates, daily_start_time, daily_end_time)
    segments = generate_schedule(conn, tasks, blocks, available_instructor_ids)
    save_segments(conn, request_id, segments)

    return {"feasible": True, "request_id": request_id, "segments": segments}


# ------------------------------------------------------------
# CONCURRENT MULTI-COMPETENCY PLANS
# ------------------------------------------------------------

def create_multi_competency_plan(conn, components, label=None):
    
    cur = conn.cursor()
    cur.execute("INSERT INTO multi_plan_batches (label) VALUES (?)", (label,))
    batch_id = cur.lastrowid
    conn.commit()

    occupied_ledger = {}  # instructor_id -> list of (date_iso, start_time, end_time), confirmed across the batch
    load_tracker = {}     # instructor_id -> hours, confirmed across the batch

    results = []

    for component in components:
        competency_id = component["competency_id"]
        start_date = component["start_date"]
        end_date = component["end_date"]
        daily_start_time = component["daily_start_time"]
        daily_end_time = component["daily_end_time"]
        allowed_days_of_week = component["allowed_days_of_week"]
        available_instructor_ids = component["available_instructor_ids"]

        cur.execute("SELECT name FROM competencies WHERE competency_id = ?", (competency_id,))
        competency_name = cur.fetchone()[0]

        tasks = get_tasks_for_competency(conn, competency_id)
        eligible_dates = get_eligible_dates(conn, start_date, end_date, allowed_days_of_week)

        request_id = save_request(
            conn, competency_id, start_date, end_date, daily_start_time, daily_end_time,
            allowed_days_of_week, available_instructor_ids
        )
        cur.execute(
            "UPDATE training_plan_requests SET batch_id = ? WHERE request_id = ?",
            (batch_id, request_id)
        )
        conn.commit()

        try:
            daily_capacity_hours = compute_daily_capacity_hours(daily_start_time, daily_end_time)
        except ValueError as e:
            reasons = [{"reason_type": "INVALID_TIME_WINDOW", "task_id": None, "detail": str(e)}]
            save_infeasibility(conn, request_id, reasons)
            results.append({
                "competency_id": competency_id, "competency_name": competency_name,
                "request_id": request_id, "feasible": False, "reasons": reasons
            })
            continue

        blackout_set = blackout.get_blackout_date_set(conn)
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
        allowed_set = set(allowed_days_of_week)
        raw_weekday_dates = []
        current = start_dt
        while current <= end_dt:
            if current.weekday() in allowed_set:
                raw_weekday_dates.append(current)
            current += timedelta(days=1)
        blackout_days_excluded = sum(1 for d in raw_weekday_dates if d.isoformat() in blackout_set)

        reasons = check_feasibility(
            conn, tasks, eligible_dates, available_instructor_ids, daily_capacity_hours,
            blackout_days_excluded=blackout_days_excluded
        )
        if reasons:
            save_infeasibility(conn, request_id, reasons)
            results.append({
                "competency_id": competency_id, "competency_name": competency_name,
                "request_id": request_id, "feasible": False, "reasons": reasons
            })
            continue

        blocks = build_time_blocks(eligible_dates, daily_start_time, daily_end_time)
        gen_result = generate_schedule_with_conflict_avoidance(
            conn, tasks, blocks, available_instructor_ids, occupied_ledger, load_tracker
        )

        if not gen_result["success"]:
            reasons = [{
                "reason_type": "INSTRUCTOR_CONFLICT",
                "task_id": gen_result["conflict_task_id"],
                "detail": gen_result["conflict_detail"],
            }]
            save_infeasibility(conn, request_id, reasons)
            results.append({
                "competency_id": competency_id, "competency_name": competency_name,
                "request_id": request_id, "feasible": False, "reasons": reasons
            })
            continue

        segments = gen_result["segments"]
        save_segments(conn, request_id, segments)

        # Only a fully successful component's commitments get merged into
        # the shared batch state — a failed component never distorts
        # conflict-checking or fairness for the others.
        for iid, additions in gen_result["ledger_additions"].items():
            occupied_ledger.setdefault(iid, []).extend(additions)
        for iid, hrs in gen_result["load_additions"].items():
            load_tracker[iid] = load_tracker.get(iid, 0.0) + hrs

        results.append({
            "competency_id": competency_id, "competency_name": competency_name,
            "request_id": request_id, "feasible": True, "segments": segments
        })

    return {"batch_id": batch_id, "results": results}


# ------------------------------------------------------------
# TEST RUN
# ------------------------------------------------------------

if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    cur = conn.cursor()

    def get_competency_id(name):
        cur.execute("SELECT competency_id FROM competencies WHERE name = ?", (name,))
        row = cur.fetchone()
        if not row:
            print(f"No '{name}' competency found. Run seed.py first.")
            exit(1)
        return row[0]

    cur.execute("SELECT instructor_id FROM instructors")
    all_instructor_ids = [r[0] for r in cur.fetchall()]

    print("=" * 60)
    print("TEST 1: Security Team Watchstander - Initial (49 hrs)")
    print("Plenty of time (3 weeks, weekdays), all instructors available")
    print("=" * 60)
    result = create_training_plan(
        conn,
        competency_id=get_competency_id("Security Team Watchstander - Initial"),
        start_date="2026-09-01",
        end_date="2026-09-21",
        daily_start_time="08:00",
        daily_end_time="16:00",
        allowed_days_of_week=[0, 1, 2, 3, 4],  # Mon-Fri
        available_instructor_ids=all_instructor_ids,
    )
    if result["feasible"]:
        print(f"Plan feasible (request_id={result['request_id']}). Segments:")
        for seg in result["segments"]:
            print(f"  {seg['segment_date']} {seg['start_time']}-{seg['end_time']} "
                  f"| {seg['task_name']} ({seg['hours_this_segment']}h) "
                  f"| Instructor: {seg['assigned_instructor_name']}")
    else:
        print(f"Plan infeasible (request_id={result['request_id']}). Reasons:")
        for r in result["reasons"]:
            print(f"  - {r['detail']}")

    print()
    print("=" * 60)
    print("TEST 2: Boarding Team Member - Initial (83 hrs)")
    print("Deliberately too tight: 1 week, weekdays only (max 40 hrs available)")
    print("=" * 60)
    result = create_training_plan(
        conn,
        competency_id=get_competency_id("Boarding Team Member - Initial"),
        start_date="2026-09-01",
        end_date="2026-09-07",
        daily_start_time="08:00",
        daily_end_time="16:00",
        allowed_days_of_week=[0, 1, 2, 3, 4],
        available_instructor_ids=all_instructor_ids,
    )
    if result["feasible"]:
        print(f"Plan feasible (request_id={result['request_id']}).")
    else:
        print(f"Plan infeasible (request_id={result['request_id']}). Reasons:")
        for r in result["reasons"]:
            print(f"  - {r['detail']}")

    print()
    print("=" * 60)
    print("TEST 3: Security Team Watchstander - Recurrent (44 hrs)")
    print("Only ME2 Smith available (not qualified for every task)")
    print("=" * 60)
    cur.execute("SELECT instructor_id FROM instructors WHERE name = ?", ("ME2 Smith",))
    limited_instructors = [r[0] for r in cur.fetchall()]
    result = create_training_plan(
        conn,
        competency_id=get_competency_id("Security Team Watchstander - Recurrent"),
        start_date="2026-09-01",
        end_date="2026-09-21",
        daily_start_time="08:00",
        daily_end_time="16:00",
        allowed_days_of_week=[0, 1, 2, 3, 4],
        available_instructor_ids=limited_instructors,
    )
    if result["feasible"]:
        print(f"Plan feasible (request_id={result['request_id']}).")
    else:
        print(f"Plan infeasible (request_id={result['request_id']}). Reasons:")
        for r in result["reasons"]:
            print(f"  - {r['detail']}")

    conn.close()
