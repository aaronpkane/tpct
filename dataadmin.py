import sqlite3
 
 
# ------------------------------------------------------------
# INSTRUCTORS
# ------------------------------------------------------------
 
def list_instructors(conn):
    cur = conn.cursor()
    cur.execute("SELECT instructor_id, name FROM instructors ORDER BY name")
    return cur.fetchall()  # [(id, name), ...]
 
 
def add_instructor(conn, name):
    name = name.strip()
    if not name:
        return {"success": False, "error": "Instructor name cannot be blank."}
 
    cur = conn.cursor()
    cur.execute("SELECT instructor_id FROM instructors WHERE name = ?", (name,))
    if cur.fetchone():
        return {"success": False, "error": f"An instructor named '{name}' already exists."}
 
    cur.execute("INSERT INTO instructors (name) VALUES (?)", (name,))
    conn.commit()
    return {"success": True, "instructor_id": cur.lastrowid}
 
 
def delete_instructor(conn, instructor_id):
    cur = conn.cursor()
    cur.execute("SELECT name FROM instructors WHERE instructor_id = ?", (instructor_id,))
    row = cur.fetchone()
    if not row:
        return {"success": False, "error": "Instructor not found."}
    name = row[0]
 
    try:
        cur.execute("DELETE FROM instructor_qualifications WHERE instructor_id = ?", (instructor_id,))
        cur.execute("DELETE FROM instructors WHERE instructor_id = ?", (instructor_id,))
        conn.commit()
        return {"success": True, "name": name}
    except sqlite3.IntegrityError:
        conn.rollback()
        return {
            "success": False,
            "error": f"'{name}' can't be deleted — they're assigned to one or more existing "
                     f"training plans. Remove their qualifications instead if you don't want "
                     f"them selected for new plans."
        }
 
 
def get_instructor_qualifications(conn, instructor_id):
    """Returns the set of task_ids this instructor is currently qualified for."""
    cur = conn.cursor()
    cur.execute(
        "SELECT task_id FROM instructor_qualifications WHERE instructor_id = ?",
        (instructor_id,)
    )
    return set(row[0] for row in cur.fetchall())
 
 
def set_instructor_qualifications(conn, instructor_id, task_ids):
    
    current = get_instructor_qualifications(conn, instructor_id)
    desired = set(task_ids)
 
    to_add = desired - current
    to_remove = current - desired
 
    cur = conn.cursor()
    for task_id in to_add:
        cur.execute(
            "INSERT INTO instructor_qualifications (instructor_id, task_id) VALUES (?, ?)",
            (instructor_id, task_id)
        )
    for task_id in to_remove:
        cur.execute(
            "DELETE FROM instructor_qualifications WHERE instructor_id = ? AND task_id = ?",
            (instructor_id, task_id)
        )
    conn.commit()
    return {"added": len(to_add), "removed": len(to_remove)}
 
 
# ------------------------------------------------------------
# COMPETENCIES
# ------------------------------------------------------------
 
def list_competencies(conn):
    cur = conn.cursor()
    cur.execute("SELECT competency_id, name FROM competencies ORDER BY name")
    return cur.fetchall()
 
 
def add_competency(conn, name):
    name = name.strip()
    if not name:
        return {"success": False, "error": "Competency name cannot be blank."}
 
    cur = conn.cursor()
    cur.execute("SELECT competency_id FROM competencies WHERE name = ?", (name,))
    if cur.fetchone():
        return {"success": False, "error": f"A competency named '{name}' already exists."}
 
    cur.execute("INSERT INTO competencies (name) VALUES (?)", (name,))
    conn.commit()
    return {"success": True, "competency_id": cur.lastrowid}
 
 
def delete_competency(conn, competency_id):
    cur = conn.cursor()
    cur.execute("SELECT name FROM competencies WHERE competency_id = ?", (competency_id,))
    row = cur.fetchone()
    if not row:
        return {"success": False, "error": "Competency not found."}
    name = row[0]
 
    try:
        cur.execute("DELETE FROM competencies WHERE competency_id = ?", (competency_id,))
        conn.commit()
        return {"success": True, "name": name}
    except sqlite3.IntegrityError:
        conn.rollback()
        return {
            "success": False,
            "error": f"'{name}' can't be deleted — it still has tasks defined under it "
                     f"(or has been used in an existing plan). Delete its tasks first."
        }
 
 
# ------------------------------------------------------------
# TASKS
# ------------------------------------------------------------
 
def list_all_tasks_grouped(conn):
    
    cur = conn.cursor()
    cur.execute(
        """
        SELECT t.task_id, c.name, t.name
        FROM tasks t
        JOIN competencies c ON t.competency_id = c.competency_id
        ORDER BY c.name, t.sequence_order
        """
    )
    return cur.fetchall()
 
 
def list_tasks_for_competency(conn, competency_id):
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
    return cur.fetchall()
 
 
def add_task(conn, competency_id, name, duration_hours):
    name = name.strip()
    if not name:
        return {"success": False, "error": "Task name cannot be blank."}
    if duration_hours <= 0:
        return {"success": False, "error": "Duration must be greater than 0 hours."}
 
    cur = conn.cursor()
    cur.execute(
        "SELECT COALESCE(MAX(sequence_order), 0) FROM tasks WHERE competency_id = ?",
        (competency_id,)
    )
    next_sequence = cur.fetchone()[0] + 1
 
    cur.execute(
        """
        INSERT INTO tasks (competency_id, name, duration_hours, sequence_order)
        VALUES (?, ?, ?, ?)
        """,
        (competency_id, name, duration_hours, next_sequence)
    )
    conn.commit()
    return {"success": True, "task_id": cur.lastrowid, "sequence_order": next_sequence}
 
 
def update_task(conn, task_id, name, duration_hours):
    """Updates name/duration only — does NOT touch sequence_order (use move_task_* for that)."""
    name = name.strip()
    if not name:
        return {"success": False, "error": "Task name cannot be blank."}
    if duration_hours <= 0:
        return {"success": False, "error": "Duration must be greater than 0 hours."}
 
    cur = conn.cursor()
    cur.execute(
        "UPDATE tasks SET name = ?, duration_hours = ? WHERE task_id = ?",
        (name, duration_hours, task_id)
    )
    conn.commit()
    return {"success": True}
 
 
def delete_task(conn, task_id):
    cur = conn.cursor()
    cur.execute("SELECT name FROM tasks WHERE task_id = ?", (task_id,))
    row = cur.fetchone()
    if not row:
        return {"success": False, "error": "Task not found."}
    name = row[0]
 
    try:
        cur.execute("DELETE FROM instructor_qualifications WHERE task_id = ?", (task_id,))
        cur.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
        conn.commit()
        return {"success": True, "name": name}
    except sqlite3.IntegrityError:
        conn.rollback()
        return {
            "success": False,
            "error": f"'{name}' can't be deleted — it's already been used in an existing "
                     f"training plan."
        }
 
 
def move_task(conn, task_id, direction):

    cur = conn.cursor()
    cur.execute(
        "SELECT competency_id, sequence_order FROM tasks WHERE task_id = ?",
        (task_id,)
    )
    row = cur.fetchone()
    if not row:
        return {"success": False, "error": "Task not found."}
    competency_id, current_seq = row
 
    if direction == "up":
        cur.execute(
            "SELECT task_id, sequence_order FROM tasks WHERE competency_id = ? AND sequence_order < ? "
            "ORDER BY sequence_order DESC LIMIT 1",
            (competency_id, current_seq)
        )
    elif direction == "down":
        cur.execute(
            "SELECT task_id, sequence_order FROM tasks WHERE competency_id = ? AND sequence_order > ? "
            "ORDER BY sequence_order ASC LIMIT 1",
            (competency_id, current_seq)
        )
    else:
        return {"success": False, "error": "direction must be 'up' or 'down'."}
 
    neighbor = cur.fetchone()
    if not neighbor:
        return {"success": False, "error": "Already at that end of the sequence."}
    neighbor_id, neighbor_seq = neighbor
 
    # Route through a temporary negative placeholder to avoid ever
    # violating the UNIQUE(competency_id, sequence_order) constraint
    # mid-swap.
    cur.execute("UPDATE tasks SET sequence_order = -1 WHERE task_id = ?", (task_id,))
    cur.execute("UPDATE tasks SET sequence_order = ? WHERE task_id = ?", (current_seq, neighbor_id))
    cur.execute("UPDATE tasks SET sequence_order = ? WHERE task_id = ?", (neighbor_seq, task_id))
    conn.commit()
    return {"success": True}
