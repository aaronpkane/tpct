import sqlite3

DB_PATH = "tpct.db"

def reset(cur):
    """
    Wipes existing data so this script can be re-run safely as you
    edit tasks/instructors/qualifications, without needing to delete
    and rebuild tpct.db from scratch each time.
 
    Deleted in an order that respects foreign key dependencies
    (children before parents). Only touches the tables this script
    populates — training_plan_requests / plan_segments /
    infeasibility_reasons (Day 2+ data) are left untouched.
    """
    cur.execute("DELETE FROM instructor_qualifications")
    cur.execute("DELETE FROM tasks")
    cur.execute("DELETE FROM instructors")
    cur.execute("DELETE FROM competencies")

    cur.execute(
        "DELETE FROM sqlite_sequence WHERE name IN "
        "('instructor_qualifications', 'tasks', 'instructors', 'competencies')"
    )
    print("Cleared existing seed data.\n")

def seed():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    reset(cur)

    # ------------------------------------------------------------
    # 1. COMPETENCY
    # ------------------------------------------------------------
    cur.execute(
        "INSERT INTO competencies (name) VALUES (?)",
        ("Security Team Watchstander - Initial",)
    )
    competency_id = cur.lastrowid
    print(f"Created competency: Security Team Watchstander - Initial (id={competency_id})")

    # ------------------------------------------------------------
    # 2. TASKS
    # Each task needs: name, duration_hours, sequence_order
    # sequence_order MUST be unique per competency (1, 2, 3, ...)
    # and defines the fixed order tasks are taught in.
    # ------------------------------------------------------------
    tasks = [
        # (name, duration_hours, sequence_order)
        ("1-01: Physical Fitness Standards", 1.0, 1),
        ("1-03: Use of Force Policy", 3.0, 2),
        ("Use of Force Policy Reinforcement", 2.0, 3),
        ("1-04: Defense and Control Group 1", 4.0, 4),
        ("1-05: Defense and Control Group 2", 6.0, 5),
        ("1-06: Defense and Control Group 3", 12.0, 6),
        ("1-07: Defense and Control Group 4", 4.0, 7),
        ("1-08: Defense and Control Group 5", 4.0, 8),
        ("1-09: Deadly Force", 2.0, 9),
        ("1-10: Two Person Use of Force", 4.0, 10),
        ("1-18: Frisk Search", 2.0, 11),
        ("1-20: Law Enforcement Equipment", 4.0, 12),
        ("1-22: Chemical Irritants", 1.0, 13),
    ]

    task_ids = {}  # name -> task_id, useful for wiring up qualifications below

    for name, duration_hours, sequence_order in tasks:
        cur.execute(
            """
            INSERT INTO tasks (competency_id, name, duration_hours, sequence_order)
            VALUES (?, ?, ?, ?)
            """,
            (competency_id, name, duration_hours, sequence_order)
        )
        task_ids[name] = cur.lastrowid
        print(f"  Added task: {name} ({duration_hours} hrs, seq #{sequence_order})")

    # ------------------------------------------------------------
    # 3. INSTRUCTORS
    # ------------------------------------------------------------
    instructors = [
        "ME1 Kane",
        "ME2 Smith",
        "ME3 Wood",
    ]

    instructor_ids = {}  # name -> instructor_id

    for name in instructors:
        cur.execute("INSERT INTO instructors (name) VALUES (?)", (name,))
        instructor_ids[name] = cur.lastrowid
        print(f"Added instructor: {name} (id={cur.lastrowid})")

    # ------------------------------------------------------------
    # 4. INSTRUCTOR QUALIFICATIONS
    # Which instructor can teach which task. An instructor can be
    # qualified for any number of tasks, across any competencies.
    # ------------------------------------------------------------
    qualifications = [
        # (instructor_name, task_name)
        ("ME1 Kane", "1-01: Physical Fitness Standards"),
        ("ME1 Kane", "1-03: Use of Force Policy"),
        ("ME1 Kane", "Use of Force Policy Reinforcement"),
        ("ME1 Kane", "1-04: Defense and Control Group 1"),
        ("ME1 Kane", "1-05: Defense and Control Group 2"),
        ("ME1 Kane", "1-06: Defense and Control Group 3"),
        ("ME1 Kane", "1-07: Defense and Control Group 4"),
        ("ME1 Kane", "1-08: Defense and Control Group 5"),
        ("ME1 Kane", "1-09: Deadly Force"),
        ("ME1 Kane", "1-10: Two Person Use of Force"),
        ("ME1 Kane", "1-18: Frisk Search"),
        ("ME1 Kane", "1-20: Law Enforcement Equipment"),
        ("ME1 Kane", "1-22: Chemical Irritants"),
        ("ME2 Smith", "1-01: Physical Fitness Standards"),
        ("ME2 Smith", "1-04: Defense and Control Group 1"),
        ("ME2 Smith", "1-05: Defense and Control Group 2"),
        ("ME2 Smith", "1-06: Defense and Control Group 3"),
        ("ME2 Smith", "1-07: Defense and Control Group 4"),
        ("ME2 Smith", "1-08: Defense and Control Group 5"),
        ("ME2 Smith", "1-10: Two Person Use of Force"),
        ("ME2 Smith", "1-18: Frisk Search"),
        ("ME3 Wood", "1-01: Physical Fitness Standards"),
        ("ME3 Wood", "1-03: Use of Force Policy"),
        ("ME3 Wood", "Use of Force Policy Reinforcement"),
        ("ME3 Wood", "1-09: Deadly Force"),
        ("ME3 Wood", "1-18: Frisk Search"),
        ("ME3 Wood", "1-20: Law Enforcement Equipment"),
        ("ME3 Wood", "1-22: Chemical Irritants"),
    ]

    for instructor_name, task_name in qualifications:
        cur.execute(
            """
            INSERT INTO instructor_qualifications (instructor_id, task_id)
            VALUES (?, ?)
            """,
            (instructor_ids[instructor_name], task_ids[task_name])
        )
        print(f"  {instructor_name} qualified to teach: {task_name}")

    conn.commit()
    conn.close()
    print("\nSeed complete.")


if __name__ == "__main__":
    seed()
