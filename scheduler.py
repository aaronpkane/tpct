import sqlite3
from datetime import datetime, timedelta
 
DB_PATH = "tpct.db"
 
DAILY_BLOCK_HOURS = 4.0     # each half-day block, before/after lunch
LUNCH_HOURS = 1.0
BLOCKS_PER_DAY = 2          # morning + afternoon
DAY_CAPACITY_HOURS = DAILY_BLOCK_HOURS * BLOCKS_PER_DAY  # 8.0
 
 
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
 
def get_eligible_dates(start_date, end_date, allowed_days_of_week):
    """
    start_date, end_date: 'YYYY-MM-DD' strings
    allowed_days_of_week: set/list of ints, 0=Monday ... 6=Sunday
    Returns list of date objects, inclusive, filtered to allowed days.
    """
    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()
    allowed = set(allowed_days_of_week)
 
    dates = []
    current = start
    while current <= end:
        if current.weekday() in allowed:
            dates.append(current)
        current += timedelta(days=1)
    return dates
 
 
def build_time_blocks(eligible_dates, daily_start_time):
    """
    Turns each eligible date into two 4-hour blocks (morning / afternoon,
    split by a 1-hour lunch), in chronological order across the whole
    plan. This is the capacity queue tasks get poured into.
 
    Returns list of dicts: {date, block_start, block_end, capacity_hours, remaining_hours}
    """
    blocks = []
    start_dt = parse_time(daily_start_time)
 
    for d in eligible_dates:
        morning_start = start_dt
        morning_end = add_hours(morning_start, DAILY_BLOCK_HOURS)
        afternoon_start = add_hours(morning_end, LUNCH_HOURS)
        afternoon_end = add_hours(afternoon_start, DAILY_BLOCK_HOURS)
 
        blocks.append({
            "date": d,
            "start": format_time(morning_start),
            "end": format_time(morning_end),
            "capacity": DAILY_BLOCK_HOURS,
            "remaining": DAILY_BLOCK_HOURS,
        })
        blocks.append({
            "date": d,
            "start": format_time(afternoon_start),
            "end": format_time(afternoon_end),
            "capacity": DAILY_BLOCK_HOURS,
            "remaining": DAILY_BLOCK_HOURS,
        })
 
    return blocks
 
 
# ------------------------------------------------------------
# FEASIBILITY CHECK
# ------------------------------------------------------------
 
def check_feasibility(conn, tasks, eligible_dates, available_instructor_ids):
    """
    Returns a list of infeasibility reason dicts. Empty list = feasible.
    Each reason: {reason_type, task_id (nullable), detail}
    Checks ALL reasons, doesn't stop at the first one.
    """
    reasons = []
 
    # --- Check 1: total hours shortfall ---
    total_required = sum(t[2] for t in tasks)  # t[2] = duration_hours
    total_available = len(eligible_dates) * DAY_CAPACITY_HOURS
 
    if total_required > total_available:
        shortfall = total_required - total_available
        reasons.append({
            "reason_type": "SHORTFALL",
            "task_id": None,
            "detail": f"Shortfall: {shortfall:g} hours over allotted range "
                      f"(required {total_required:g} hrs, available {total_available:g} hrs "
                      f"across {len(eligible_dates)} eligible day(s))"
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
    """
    qualified_instructors: list of (instructor_id, name)
    Tie-break: lowest instructor_id (stable, predictable).
    """
    return min(
        qualified_instructors,
        key=lambda inst: (get_instructor_hours_loaded(load_tracker, inst[0]), inst[0])
    )
 
 
def generate_schedule(conn, tasks, blocks, available_instructor_ids):
    """
    Walks tasks in sequence, filling time blocks in order.
    Returns list of segment dicts (not yet saved to DB).
    Assumes feasibility has already been confirmed.
    """
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
# PERSISTENCE
# ------------------------------------------------------------
 
def save_request(conn, competency_id, start_date, end_date, daily_start_time,
                  allowed_days_of_week, available_instructor_ids):
    cur = conn.cursor()
    days_str = ",".join(str(d) for d in sorted(allowed_days_of_week))
    cur.execute(
        """
        INSERT INTO training_plan_requests
        (competency_id, start_date, end_date, daily_start_time, allowed_days_of_week)
        VALUES (?, ?, ?, ?, ?)
        """,
        (competency_id, start_date, end_date, daily_start_time, days_str)
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
 
def create_training_plan(conn, competency_id, start_date, end_date, daily_start_time,
                          allowed_days_of_week, available_instructor_ids):
    """
    Full pipeline: check feasibility, then either generate + save segments,
    or save + return an infeasibility report.
 
    Returns dict: {"feasible": bool, "request_id": int, "segments": [...] or "reasons": [...]}
    """
    tasks = get_tasks_for_competency(conn, competency_id)
    eligible_dates = get_eligible_dates(start_date, end_date, allowed_days_of_week)
 
    request_id = save_request(
        conn, competency_id, start_date, end_date, daily_start_time,
        allowed_days_of_week, available_instructor_ids
    )
 
    reasons = check_feasibility(conn, tasks, eligible_dates, available_instructor_ids)
 
    if reasons:
        save_infeasibility(conn, request_id, reasons)
        return {"feasible": False, "request_id": request_id, "reasons": reasons}
 
    blocks = build_time_blocks(eligible_dates, daily_start_time)
    segments = generate_schedule(conn, tasks, blocks, available_instructor_ids)
    save_segments(conn, request_id, segments)
 
    return {"feasible": True, "request_id": request_id, "segments": segments}
 
 
# ------------------------------------------------------------
# TEST RUN
# ------------------------------------------------------------
 
if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
 
    cur = conn.cursor()
    cur.execute("SELECT competency_id FROM competencies WHERE name = ?", ("Security Team Watchstander - Initial",))
    row = cur.fetchone()
    if not row:
        print("No 'Security Team Watchstander - Initial' competency found. Run seed.py first.")
        exit(1)
    competency_id = row[0]
 
    cur.execute("SELECT instructor_id FROM instructors")
    all_instructor_ids = [r[0] for r in cur.fetchall()]
 
    print("=" * 60)
    print("TEST 1: Plenty of time, all instructors available")
    print("=" * 60)
    result = create_training_plan(
        conn,
        competency_id=competency_id,
        start_date="2026-09-01",
        end_date="2026-09-12",
        daily_start_time="08:00",
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
    print("TEST 2: Not enough days (deliberately too tight)")
    print("=" * 60)
    result = create_training_plan(
        conn,
        competency_id=competency_id,
        start_date="2026-09-01",
        end_date="2026-09-01",  # just 1 day
        daily_start_time="08:00",
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
    print("TEST 3: No instructor available for one task")
    print("=" * 60)
    # Only include instructor(s) NOT qualified for "Radio Communications Procedures"
    cur.execute("SELECT instructor_id FROM instructors WHERE name = ?", ("Instructor A",))
    limited_instructors = [r[0] for r in cur.fetchall()]
    result = create_training_plan(
        conn,
        competency_id=competency_id,
        start_date="2026-09-01",
        end_date="2026-09-12",
        daily_start_time="08:00",
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
