import sqlite3
 
 
def get_instructor_hours_summary(conn, start_date=None, end_date=None):
    
    cur = conn.cursor()
 
    date_filter = ""
    params = []
    if start_date and end_date:
        date_filter = "AND ps.segment_date BETWEEN ? AND ?"
        params = [start_date, end_date]
 
    cur.execute(
        f"""
        SELECT
            i.instructor_id,
            i.name,
            COALESCE(SUM(ps.hours_this_segment), 0) AS total_hours,
            COUNT(ps.segment_id) AS session_count,
            COUNT(DISTINCT ps.task_id) AS distinct_tasks,
            COUNT(DISTINCT ps.request_id) AS distinct_plans
        FROM instructors i
        LEFT JOIN plan_segments ps ON ps.assigned_instructor_id = i.instructor_id {date_filter}
        GROUP BY i.instructor_id, i.name
        ORDER BY total_hours DESC, i.name
        """,
        params
    )
 
    rows = cur.fetchall()
    return [
        {
            "instructor_id": r[0],
            "name": r[1],
            "total_hours": r[2],
            "session_count": r[3],
            "distinct_tasks": r[4],
            "distinct_plans": r[5],
        }
        for r in rows
    ]
 
 
def get_instructor_competency_breakdown(conn, start_date=None, end_date=None):
    
    cur = conn.cursor()
 
    date_filter = ""
    params = []
    if start_date and end_date:
        date_filter = "AND ps.segment_date BETWEEN ? AND ?"
        params = [start_date, end_date]
 
    cur.execute(
        f"""
        SELECT
            i.name,
            c.name,
            SUM(ps.hours_this_segment) AS hours
        FROM plan_segments ps
        JOIN instructors i ON ps.assigned_instructor_id = i.instructor_id
        JOIN tasks t ON ps.task_id = t.task_id
        JOIN competencies c ON t.competency_id = c.competency_id
        WHERE 1=1 {date_filter}
        GROUP BY i.name, c.name
        ORDER BY i.name, c.name
        """,
        params
    )
    return cur.fetchall()
 
 
def get_instructor_activity_detail(conn, instructor_id, start_date=None, end_date=None):
    
    cur = conn.cursor()
 
    date_filter = ""
    params = [instructor_id]
    if start_date and end_date:
        date_filter = "AND ps.segment_date BETWEEN ? AND ?"
        params += [start_date, end_date]
 
    cur.execute(
        f"""
        SELECT
            ps.segment_date,
            t.name,
            c.name,
            ps.hours_this_segment,
            ps.request_id
        FROM plan_segments ps
        JOIN tasks t ON ps.task_id = t.task_id
        JOIN competencies c ON t.competency_id = c.competency_id
        WHERE ps.assigned_instructor_id = ? {date_filter}
        ORDER BY ps.segment_date DESC
        """,
        params
    )
    return cur.fetchall()
 
 
def get_overall_date_range(conn):
   
    cur = conn.cursor()
    cur.execute("SELECT MIN(segment_date), MAX(segment_date) FROM plan_segments")
    return cur.fetchone()
 
