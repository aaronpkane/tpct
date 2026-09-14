import holidays
 
 
def populate_federal_holidays(conn, start_year, end_year):
   
    years = list(range(start_year, end_year + 1))
    us_holidays = holidays.US(years=years)
 
    cur = conn.cursor()
    inserted = 0
    for holiday_date, label in us_holidays.items():
        cur.execute(
            """
            INSERT OR IGNORE INTO blackout_dates (blackout_date, label, source)
            VALUES (?, ?, 'FEDERAL_HOLIDAY')
            """,
            (holiday_date.isoformat(), label)
        )
        if cur.rowcount > 0:
            inserted += 1
 
    conn.commit()
    return inserted
 
 
def list_blackout_dates(conn, start_date=None, end_date=None):
    
    cur = conn.cursor()
    if start_date and end_date:
        cur.execute(
            """
            SELECT blackout_date, label, source FROM blackout_dates
            WHERE blackout_date BETWEEN ? AND ?
            ORDER BY blackout_date
            """,
            (start_date, end_date)
        )
    else:
        cur.execute(
            "SELECT blackout_date, label, source FROM blackout_dates ORDER BY blackout_date"
        )
    return cur.fetchall()
 
 
def get_blackout_date_set(conn):
    
    cur = conn.cursor()
    cur.execute("SELECT blackout_date FROM blackout_dates")
    return set(row[0] for row in cur.fetchall())
 
 
def add_manual_blackout_date(conn, date_str, label):
    
    label = label.strip()
    if not label:
        return {"success": False, "error": "Label cannot be blank."}
 
    cur = conn.cursor()
    cur.execute("SELECT label FROM blackout_dates WHERE blackout_date = ?", (date_str,))
    existing = cur.fetchone()
    if existing:
        return {"success": False, "error": f"{date_str} is already blacked out ('{existing[0]}')."}
 
    cur.execute(
        "INSERT INTO blackout_dates (blackout_date, label, source) VALUES (?, ?, 'MANUAL')",
        (date_str, label)
    )
    conn.commit()
    return {"success": True}
 
 
def remove_blackout_date(conn, date_str):
    cur = conn.cursor()
    cur.execute("SELECT label FROM blackout_dates WHERE blackout_date = ?", (date_str,))
    row = cur.fetchone()
    if not row:
        return {"success": False, "error": "That date isn't currently blacked out."}
 
    cur.execute("DELETE FROM blackout_dates WHERE blackout_date = ?", (date_str,))
    conn.commit()
    return {"success": True, "label": row[0]}
