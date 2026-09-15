"""
TPCT Overrides
--------------
Manual, after-the-fact edits to a finalized (already-generated)
training plan — "game day audibles" trusted entirely to the caller's
judgment, with no re-validation against qualifications, blackout
dates, or instructor availability.

Two kinds of override:
  - Instructor reassignment (reassign_task_instructor): swaps EVERY
    segment belonging to a task to a new instructor in one shot.
  - Date/time move (move_segment): reschedules ONE specific segment
    to a different date and/or time — e.g. a single session that has
    to shift because life intervened, or a standalone recurring
    requirement (a quarterly drill, etc.) that needs to land on a
    specific out-of-cycle date the scheduler wouldn't have picked on
    its own.

Run directly (python3 overrides.py) to see a demo: generates a real
plan, prints it, overrides one task's instructor, prints it again.
"""

import sqlite3
from datetime import datetime

DB_PATH = "tpct.db"


# ------------------------------------------------------------
# LOOKUPS / DISPLAY
# ------------------------------------------------------------

def get_plan_segments(conn, request_id):
    """
    Returns all segments for a request, ordered chronologically,
    joined with task and instructor names for display purposes.
    """
    cur = conn.cursor()
    cur.execute(
        """
        SELECT ps.segment_id, ps.task_id, t.name AS task_name,
               ps.assigned_instructor_id, i.name AS instructor_name,
               ps.segment_date, ps.start_time, ps.end_time, ps.hours_this_segment
        FROM plan_segments ps
        JOIN tasks t ON ps.task_id = t.task_id
        JOIN instructors i ON ps.assigned_instructor_id = i.instructor_id
        WHERE ps.request_id = ?
        ORDER BY ps.segment_date, ps.start_time
        """,
        (request_id,)
    )
    return cur.fetchall()


def print_plan(conn, request_id):
    segments = get_plan_segments(conn, request_id)
    if not segments:
        print(f"No segments found for request_id={request_id}. "
              f"(Either it doesn't exist, or it was infeasible and has no plan.)")
        return

    print(f"--- Plan for request_id={request_id} ---")
    for seg in segments:
        (segment_id, task_id, task_name, instructor_id, instructor_name,
         segment_date, start_time, end_time, hours) = seg
        print(f"  {segment_date} {start_time}-{end_time} | {task_name} ({hours}h) "
              f"| Instructor: {instructor_name}")


def get_task_id_by_name(conn, request_id, task_name):
    """
    Resolves a task_name to a task_id, scoped to the competency used
    in this specific request (so it works correctly even if the same
    task name existed under a different competency elsewhere).
    """
    cur = conn.cursor()
    cur.execute(
        """
        SELECT t.task_id
        FROM tasks t
        JOIN training_plan_requests r ON t.competency_id = r.competency_id
        WHERE r.request_id = ? AND t.name = ?
        """,
        (request_id, task_name)
    )
    row = cur.fetchone()
    return row[0] if row else None


def get_instructor_id_by_name(conn, instructor_name):
    cur = conn.cursor()
    cur.execute("SELECT instructor_id FROM instructors WHERE name = ?", (instructor_name,))
    row = cur.fetchone()
    return row[0] if row else None


# ------------------------------------------------------------
# THE OVERRIDE
# ------------------------------------------------------------

def reassign_task_instructor(conn, request_id, task_id, new_instructor_id):
    """
    Reassigns EVERY segment belonging to (request_id, task_id) to
    new_instructor_id. No qualification check — this is a manual
    override, trusted entirely to the caller's judgment.

    Returns dict: {success, segments_updated, old_instructor_names, new_instructor_name, task_name}
    or {success: False, error: "..."} if nothing matched.
    """
    cur = conn.cursor()

    # Confirm the task actually has segments in this plan
    cur.execute(
        """
        SELECT DISTINCT ps.assigned_instructor_id, i.name
        FROM plan_segments ps
        JOIN instructors i ON ps.assigned_instructor_id = i.instructor_id
        WHERE ps.request_id = ? AND ps.task_id = ?
        """,
        (request_id, task_id)
    )
    old_instructors = cur.fetchall()  # list of (instructor_id, name) — normally just one

    if not old_instructors:
        return {
            "success": False,
            "error": f"No segments found for task_id={task_id} in request_id={request_id}."
        }

    # Confirm the new instructor actually exists
    cur.execute("SELECT name FROM instructors WHERE instructor_id = ?", (new_instructor_id,))
    row = cur.fetchone()
    if not row:
        return {
            "success": False,
            "error": f"No instructor found with instructor_id={new_instructor_id}."
        }
    new_instructor_name = row[0]

    cur.execute("SELECT name FROM tasks WHERE task_id = ?", (task_id,))
    task_name = cur.fetchone()[0]

    # Perform the reassignment across ALL segments of this task
    cur.execute(
        """
        UPDATE plan_segments
        SET assigned_instructor_id = ?
        WHERE request_id = ? AND task_id = ?
        """,
        (new_instructor_id, request_id, task_id)
    )
    segments_updated = cur.rowcount
    conn.commit()

    return {
        "success": True,
        "segments_updated": segments_updated,
        "old_instructor_names": [name for _, name in old_instructors],
        "new_instructor_name": new_instructor_name,
        "task_name": task_name,
    }


def reassign_task_instructor_by_name(conn, request_id, task_name, new_instructor_name):
    """
    Convenience wrapper — same as reassign_task_instructor, but takes
    task/instructor names instead of ids. Easiest entry point for
    interactive/manual use.
    """
    task_id = get_task_id_by_name(conn, request_id, task_name)
    if task_id is None:
        return {
            "success": False,
            "error": f"No task named '{task_name}' found for the competency used in request_id={request_id}."
        }

    new_instructor_id = get_instructor_id_by_name(conn, new_instructor_name)
    if new_instructor_id is None:
        return {
            "success": False,
            "error": f"No instructor named '{new_instructor_name}' found."
        }

    return reassign_task_instructor(conn, request_id, task_id, new_instructor_id)


# ------------------------------------------------------------
# MOVING A SESSION TO A DIFFERENT DATE/TIME
# ------------------------------------------------------------

def get_segments_for_task(conn, request_id, task_id):
    """
    Every individual segment belonging to (request_id, task_id),
    ordered chronologically — used to let the caller pick WHICH one
    to move when a task was split across more than one day.

    Returns list of (segment_id, segment_date, start_time, end_time, hours_this_segment).
    """
    cur = conn.cursor()
    cur.execute(
        """
        SELECT segment_id, segment_date, start_time, end_time, hours_this_segment
        FROM plan_segments
        WHERE request_id = ? AND task_id = ?
        ORDER BY segment_date, start_time
        """,
        (request_id, task_id)
    )
    return cur.fetchall()


def move_segment(conn, segment_id, new_date, new_start_time, new_end_time):
    """
    Manually reschedules ONE specific segment to a different date
    and/or time. Same "game day audible" philosophy as
    reassign_task_instructor() — no check against blackout dates,
    instructor availability, or conflicts with anything else already
    on the calendar. This is for exactly the cases the scheduler
    itself can't handle: a single session that has to move because
    something came up, or a standalone recurring requirement (e.g. a
    quarterly drill) that needs to land on a specific date outside
    normal generation.

    hours_this_segment is recomputed from the new start/end time, so
    the stored duration always matches the actual time span — if you
    only change the date and leave the times as they were, the hours
    stay exactly the same automatically.

    Returns dict: {success, task_name, new_date, new_start_time, new_end_time, new_hours}
    or {success: False, error: "..."}.
    """
    cur = conn.cursor()
    cur.execute(
        "SELECT task_id FROM plan_segments WHERE segment_id = ?",
        (segment_id,)
    )
    row = cur.fetchone()
    if not row:
        return {"success": False, "error": f"No segment found with segment_id={segment_id}."}
    task_id = row[0]

    cur.execute("SELECT name FROM tasks WHERE task_id = ?", (task_id,))
    task_name = cur.fetchone()[0]

    try:
        start_dt = datetime.strptime(new_start_time, "%H:%M")
        end_dt = datetime.strptime(new_end_time, "%H:%M")
    except ValueError:
        return {"success": False, "error": "Times must be in HH:MM format."}

    if end_dt <= start_dt:
        return {"success": False, "error": "New end time must be after new start time."}

    new_hours = (end_dt - start_dt).total_seconds() / 3600.0

    cur.execute(
        """
        UPDATE plan_segments
        SET segment_date = ?, start_time = ?, end_time = ?, hours_this_segment = ?
        WHERE segment_id = ?
        """,
        (new_date, new_start_time, new_end_time, new_hours, segment_id)
    )
    conn.commit()

    return {
        "success": True,
        "task_name": task_name,
        "new_date": new_date,
        "new_start_time": new_start_time,
        "new_end_time": new_end_time,
        "new_hours": new_hours,
    }


# ------------------------------------------------------------
# DEMO
# ------------------------------------------------------------

if __name__ == "__main__":
    import scheduler

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    cur.execute("SELECT competency_id FROM competencies WHERE name = ?",
                ("Security Team Watchstander - Initial",))
    row = cur.fetchone()
    if not row:
        print("No 'Security Team Watchstander - Initial' competency found. Run seed.py first.")
        exit(1)
    competency_id = row[0]

    cur.execute("SELECT instructor_id FROM instructors")
    all_instructor_ids = [r[0] for r in cur.fetchall()]

    print("=" * 60)
    print("Generating a plan to demo the override on")
    print("=" * 60)
    result = scheduler.create_training_plan(
        conn,
        competency_id=competency_id,
        start_date="2026-09-01",
        end_date="2026-09-21",
        daily_start_time="08:00",
        daily_end_time="16:00",
        allowed_days_of_week=[0, 1, 2, 3, 4],
        available_instructor_ids=all_instructor_ids,
    )

    if not result["feasible"]:
        print("Plan came back infeasible — can't demo an override without a real plan.")
        for r in result["reasons"]:
            print(f"  - {r['detail']}")
        exit(1)

    request_id = result["request_id"]
    print(f"Plan generated (request_id={request_id}).\n")

    print("=" * 60)
    print("BEFORE override")
    print("=" * 60)
    print_plan(conn, request_id)

    print()
    print("=" * 60)
    print("Overriding '1-06: Defense and Control Group 3' -> ME3 Wood")
    print("(a deliberately unqualified instructor, for training purposes)")
    print("=" * 60)
    override_result = reassign_task_instructor_by_name(
        conn, request_id, "1-06: Defense and Control Group 3", "ME3 Wood"
    )
    if override_result["success"]:
        print(f"Success: {override_result['segments_updated']} segment(s) reassigned "
              f"from {override_result['old_instructor_names']} to {override_result['new_instructor_name']} "
              f"for task '{override_result['task_name']}'.")
    else:
        print(f"Failed: {override_result['error']}")

    print()
    print("=" * 60)
    print("AFTER override")
    print("=" * 60)
    print_plan(conn, request_id)

    conn.close()
