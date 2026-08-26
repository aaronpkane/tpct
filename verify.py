import sqlite3
 
DB_PATH = "tpct.db"
 
 
def verify():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
 
    print("=" * 60)
    print("COMPETENCIES")
    print("=" * 60)
    cur.execute("SELECT competency_id, name FROM competencies")
    competencies = cur.fetchall()
    if not competencies:
        print("  (none found)")
    for comp_id, name in competencies:
        print(f"  [{comp_id}] {name}")
 
    print()
    print("=" * 60)
    print("TASKS (grouped by competency, in sequence order)")
    print("=" * 60)
    for comp_id, comp_name in competencies:
        print(f"\n  {comp_name}:")
        cur.execute(
            """
            SELECT sequence_order, name, duration_hours
            FROM tasks
            WHERE competency_id = ?
            ORDER BY sequence_order
            """,
            (comp_id,)
        )
        tasks = cur.fetchall()
        if not tasks:
            print("    (no tasks found)")
        for seq, name, hours in tasks:
            print(f"    #{seq}: {name} ({hours} hrs)")
 
    print()
    print("=" * 60)
    print("INSTRUCTORS")
    print("=" * 60)
    cur.execute("SELECT instructor_id, name FROM instructors")
    instructors = cur.fetchall()
    if not instructors:
        print("  (none found)")
    for inst_id, name in instructors:
        print(f"  [{inst_id}] {name}")
 
    print()
    print("=" * 60)
    print("INSTRUCTOR QUALIFICATIONS")
    print("=" * 60)
    for inst_id, inst_name in instructors:
        cur.execute(
            """
            SELECT t.name
            FROM instructor_qualifications iq
            JOIN tasks t ON iq.task_id = t.task_id
            WHERE iq.instructor_id = ?
            """,
            (inst_id,)
        )
        qualified_tasks = [row[0] for row in cur.fetchall()]
        print(f"\n  {inst_name} is qualified to teach:")
        if not qualified_tasks:
            print("    (nothing yet)")
        for task_name in qualified_tasks:
            print(f"    - {task_name}")
 
    conn.close()
    print()
    print("=" * 60)
    print("Verification complete.")
    print("=" * 60)
 
 
if __name__ == "__main__":
    verify()
