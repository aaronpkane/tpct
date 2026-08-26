import sqlite3
 
DB_PATH = "tpct.db"
 
 
def reset(cur):
    cur.execute("DELETE FROM instructor_qualifications")
    cur.execute("DELETE FROM tasks")
    cur.execute("DELETE FROM instructors")
    cur.execute("DELETE FROM competencies")
 
    cur.execute(
        "DELETE FROM sqlite_sequence WHERE name IN "
        "('instructor_qualifications', 'tasks', 'instructors', 'competencies')"
    )
    print("Cleared existing seed data.\n")
 
# ------------------------------------------------------------------
# COMPETENCIES
# ------------------------------------------------------------------
COMPETENCIES = {
    "Security Team Watchstander - Initial": [
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
    ],
 
    "Security Team Watchstander - Recurrent": [
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
    ],

    "Boarding Team Member - Initial": [
        ("1-01: Physical Fitness Standards", 1.0, 1),
        ("1-02: Authority and Jurisdiction", 2.0, 2),
        ("1-03: Use of Force Policy", 3.0, 3),
        ("Use of Force Policy Reinforcement", 2.0, 4),
        ("1-04: Defense and Control Group 1", 4.0, 5),
        ("1-05: Defense and Control Group 2", 6.0, 6),
        ("1-06: Defense and Control Group 3", 12.0, 7),
        ("1-07: Defense and Control Group 4", 4.0, 8),
        ("1-08: Defense and Control Group 5", 4.0, 9),
        ("1-09: Deadly Force", 2.0, 10),
        ("1-10: Two Person Use of Force", 4.0, 11),
        ("1-11: Weapons Retention", 2.0, 12),
        ("1-12: Questioning Individuals During a Boarding", 2.0, 13),
        ("1-13: Initial/Extended Safety Sweep", 4.0, 14),
        ("1-14: Hazardous Situations/Confined Spaces", 2.0, 15),
        ("1-15: Tactical Procedures", 2.0, 16),
        ("1-16: Easy Weapons Removal", 2.0, 17),
        ("1-18: Frisk Search", 2.0, 18),
        ("1-19: Search Incident to Arrest (SIA)", 2.0, 19),
        ("1-20: Law Enforcement Equipment", 4.0, 20),
        ("1-21: Ethics for Boarding Personnel", 2.0, 21),
        ("1-22: Chemical Irritants", 1.0, 22),
        ("1-23: Boarding Procedures", 2.0, 23),
        ("1-24: Found Weapon", 2.0, 24),
        ("1-25: Hostage Situation", 2.0, 25),
        ("1-26: Seizing Property", 2.0, 26),
        ("1-27: Statement Writing", 2.0, 27),
        ("1-28: Asylum Request ", 2.0, 28),
        ("1-29: Radiation Detection Level 1 Initial Training ", 2.0, 29)
    ],
}
 
# ------------------------------------------------------------------
# INSTRUCTORS
# ------------------------------------------------------------------
INSTRUCTORS = [
    "ME1 Kane",
    "ME2 Smith",
    "ME3 Wood",
]
 
# ------------------------------------------------------------------
# INSTRUCTOR QUALIFICATIONS
# ------------------------------------------------------------------
QUALIFICATIONS = [
    ("ME1 Kane", "Security Team Watchstander - Initial", "1-01: Physical Fitness Standards"),
    ("ME1 Kane", "Security Team Watchstander - Initial", "1-03: Use of Force Policy"),
    ("ME1 Kane", "Security Team Watchstander - Initial", "Use of Force Policy Reinforcement"),
    ("ME1 Kane", "Security Team Watchstander - Initial", "1-04: Defense and Control Group 1"),
    ("ME1 Kane", "Security Team Watchstander - Initial", "1-05: Defense and Control Group 2"),
    ("ME1 Kane", "Security Team Watchstander - Initial", "1-06: Defense and Control Group 3"),
    ("ME1 Kane", "Security Team Watchstander - Initial", "1-07: Defense and Control Group 4"),
    ("ME1 Kane", "Security Team Watchstander - Initial", "1-08: Defense and Control Group 5"),
    ("ME1 Kane", "Security Team Watchstander - Initial", "1-09: Deadly Force"),
    ("ME1 Kane", "Security Team Watchstander - Initial", "1-10: Two Person Use of Force"),
    ("ME1 Kane", "Security Team Watchstander - Initial", "1-18: Frisk Search"),
    ("ME1 Kane", "Security Team Watchstander - Initial", "1-20: Law Enforcement Equipment"),
    ("ME1 Kane", "Security Team Watchstander - Initial", "1-22: Chemical Irritants"),
    ("ME2 Smith", "Security Team Watchstander - Initial", "1-01: Physical Fitness Standards"),
    ("ME2 Smith", "Security Team Watchstander - Initial", "1-04: Defense and Control Group 1"),
    ("ME2 Smith", "Security Team Watchstander - Initial", "1-05: Defense and Control Group 2"),
    ("ME2 Smith", "Security Team Watchstander - Initial", "1-06: Defense and Control Group 3"),
    ("ME2 Smith", "Security Team Watchstander - Initial", "1-07: Defense and Control Group 4"),
    ("ME2 Smith", "Security Team Watchstander - Initial", "1-08: Defense and Control Group 5"),
    ("ME2 Smith", "Security Team Watchstander - Initial", "1-10: Two Person Use of Force"),
    ("ME2 Smith", "Security Team Watchstander - Initial", "1-18: Frisk Search"),
    ("ME3 Wood", "Security Team Watchstander - Initial", "1-01: Physical Fitness Standards"),
    ("ME3 Wood", "Security Team Watchstander - Initial", "1-03: Use of Force Policy"),
    ("ME3 Wood", "Security Team Watchstander - Initial", "Use of Force Policy Reinforcement"),
    ("ME3 Wood", "Security Team Watchstander - Initial", "1-09: Deadly Force"),
    ("ME3 Wood", "Security Team Watchstander - Initial", "1-18: Frisk Search"),
    ("ME3 Wood", "Security Team Watchstander - Initial", "1-20: Law Enforcement Equipment"),
    ("ME3 Wood", "Security Team Watchstander - Initial", "1-22: Chemical Irritants"),
 
    # EXAMPLE qualifications for the second competency
    ("ME1 Kane", "Security Team Watchstander - Recurrent", "1-01: Physical Fitness Standards"),
    ("ME1 Kane", "Security Team Watchstander - Recurrent", "1-03: Use of Force Policy"),
    ("ME1 Kane", "Security Team Watchstander - Recurrent", "Use of Force Policy Reinforcement"),
    ("ME1 Kane", "Security Team Watchstander - Recurrent", "1-04: Defense and Control Group 1"),
    ("ME1 Kane", "Security Team Watchstander - Recurrent", "1-05: Defense and Control Group 2"),
    ("ME1 Kane", "Security Team Watchstander - Recurrent", "1-06: Defense and Control Group 3"),
    ("ME1 Kane", "Security Team Watchstander - Recurrent", "1-07: Defense and Control Group 4"),
    ("ME1 Kane", "Security Team Watchstander - Recurrent", "1-08: Defense and Control Group 5"),
    ("ME1 Kane", "Security Team Watchstander - Recurrent", "1-09: Deadly Force"),
    ("ME1 Kane", "Security Team Watchstander - Recurrent", "1-10: Two Person Use of Force"),
    ("ME1 Kane", "Security Team Watchstander - Recurrent", "1-18: Frisk Search"),
    ("ME2 Smith", "Security Team Watchstander - Recurrent", "1-01: Physical Fitness Standards"),
    ("ME2 Smith", "Security Team Watchstander - Recurrent", "1-04: Defense and Control Group 1"),
    ("ME2 Smith", "Security Team Watchstander - Recurrent", "1-05: Defense and Control Group 2"),
    ("ME2 Smith", "Security Team Watchstander - Recurrent", "1-06: Defense and Control Group 3"),
    ("ME2 Smith", "Security Team Watchstander - Recurrent", "1-07: Defense and Control Group 4"),
    ("ME2 Smith", "Security Team Watchstander - Recurrent", "1-08: Defense and Control Group 5"),
    ("ME2 Smith", "Security Team Watchstander - Recurrent", "1-10: Two Person Use of Force"),
    ("ME2 Smith", "Security Team Watchstander - Recurrent", "1-18: Frisk Search"),
    ("ME3 Wood", "Security Team Watchstander - Recurrent", "1-01: Physical Fitness Standards"),
    ("ME3 Wood", "Security Team Watchstander - Recurrent", "1-03: Use of Force Policy"),
    ("ME3 Wood", "Security Team Watchstander - Recurrent", "Use of Force Policy Reinforcement"),
    ("ME3 Wood", "Security Team Watchstander - Recurrent", "1-09: Deadly Force"),
    ("ME3 Wood", "Security Team Watchstander - Recurrent", "1-18: Frisk Search"),

    ("ME1 Kane", "Boarding Team Member - Initial", "1-01: Physical Fitness Standards"),
    ("ME1 Kane", "Boarding Team Member - Initial", "1-03: Use of Force Policy"),
    ("ME1 Kane", "Boarding Team Member - Initial", "1-04: Defense and Control Group 1"),
    ("ME1 Kane", "Boarding Team Member - Initial", "1-05: Defense and Control Group 2"),
    ("ME1 Kane", "Boarding Team Member - Initial", "1-06: Defense and Control Group 3"),
    ("ME1 Kane", "Boarding Team Member - Initial", "1-07: Defense and Control Group 4"),
    ("ME1 Kane", "Boarding Team Member - Initial", "1-08: Defense and Control Group 5"),
    ("ME1 Kane", "Boarding Team Member - Initial", "1-09: Deadly Force"),
    ("ME1 Kane", "Boarding Team Member - Initial", "1-10: Two Person Use of Force"),
    ("ME1 Kane", "Boarding Team Member - Initial", "1-11: Weapons Retention"),
    ("ME1 Kane", "Boarding Team Member - Initial", "1-12: Questioning Individuals During a Boarding"),
    ("ME1 Kane", "Boarding Team Member - Initial", "1-13: Initial/Extended Safety Sweep"),
    ("ME1 Kane", "Boarding Team Member - Initial", "1-14: Hazardous Situations/Confined Spaces"),
    ("ME1 Kane", "Boarding Team Member - Initial", "1-15: Tactical Procedures"),
    ("ME1 Kane", "Boarding Team Member - Initial", "1-16: Easy Weapons Removal"),
    ("ME1 Kane", "Boarding Team Member - Initial", "1-18: Frisk Search"),
    ("ME1 Kane", "Boarding Team Member - Initial", "1-19: Search Incident to Arrest (SIA)"),
    ("ME1 Kane", "Boarding Team Member - Initial", "1-20: Law Enforcement Equipment"),
    ("ME1 Kane", "Boarding Team Member - Initial", "1-21: Ethics for Boarding Personnel"),
    ("ME1 Kane", "Boarding Team Member - Initial", "1-22: Chemical Irritants"),
    ("ME1 Kane", "Boarding Team Member - Initial", "1-23: Boarding Procedures"),
    ("ME1 Kane", "Boarding Team Member - Initial", "1-24: Found Weapon"),
    ("ME1 Kane", "Boarding Team Member - Initial", "1-25: Hostage Situation"),
    ("ME1 Kane", "Boarding Team Member - Initial", "1-26: Seizing Property"),
    ("ME1 Kane", "Boarding Team Member - Initial", "1-27: Statement Writing"),
    ("ME1 Kane", "Boarding Team Member - Initial", "1-28: Asylum Request "),
    ("ME1 Kane", "Boarding Team Member - Initial", "1-29: Radiation Detection Level 1 Initial Training "),
    ("ME2 Smith", "Boarding Team Member - Initial", "1-01: Physical Fitness Standards"),
    ("ME2 Smith", "Boarding Team Member - Initial", "1-04: Defense and Control Group 1"),
    ("ME2 Smith", "Boarding Team Member - Initial", "1-05: Defense and Control Group 2"),
    ("ME2 Smith", "Boarding Team Member - Initial", "1-06: Defense and Control Group 3"),
    ("ME2 Smith", "Boarding Team Member - Initial", "1-07: Defense and Control Group 4"),
    ("ME2 Smith", "Boarding Team Member - Initial", "1-08: Defense and Control Group 5"),
    ("ME2 Smith", "Boarding Team Member - Initial", "1-10: Two Person Use of Force"),
    ("ME2 Smith", "Boarding Team Member - Initial", "1-18: Frisk Search"),
    ("ME2 Smith", "Boarding Team Member - Initial", "1-15: Tactical Procedures"),
    ("ME2 Smith", "Boarding Team Member - Initial", "1-16: Easy Weapons Removal"),
    ("ME2 Smith", "Boarding Team Member - Initial", "1-19: Search Incident to Arrest (SIA)"),
    ("ME3 Wood", "Boarding Team Member - Initial", "1-01: Physical Fitness Standards"),
    ("ME3 Wood", "Boarding Team Member - Initial", "1-03: Use of Force Policy"),
    ("ME3 Wood", "Boarding Team Member - Initial", "Use of Force Policy Reinforcement"),
    ("ME3 Wood", "Boarding Team Member - Initial", "1-09: Deadly Force"),
    ("ME3 Wood", "Boarding Team Member - Initial", "1-18: Frisk Search"),
    ("ME3 Wood", "Boarding Team Member - Initial", "1-20: Law Enforcement Equipment"),
    ("ME3 Wood", "Boarding Team Member - Initial", "1-21: Ethics for Boarding Personnel"),
    ("ME3 Wood", "Boarding Team Member - Initial", "1-22: Chemical Irritants"),
    ("ME3 Wood", "Boarding Team Member - Initial", "1-23: Boarding Procedures"),
    ("ME3 Wood", "Boarding Team Member - Initial", "1-24: Found Weapon"),
    ("ME3 Wood", "Boarding Team Member - Initial", "1-25: Hostage Situation"),
    ("ME3 Wood", "Boarding Team Member - Initial", "1-26: Seizing Property"),
    ("ME3 Wood", "Boarding Team Member - Initial", "1-27: Statement Writing"),
    ("ME3 Wood", "Boarding Team Member - Initial", "1-28: Asylum Request "),
    ("ME3 Wood", "Boarding Team Member - Initial", "1-29: Radiation Detection Level 1 Initial Training "),
]
 
def seed():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()
 
    reset(cur)
 
    # --- Insert competencies + their tasks ---
    # task_ids keyed by (competency_name, task_name) since task names
    # alone aren't guaranteed unique across competencies.
    task_ids = {}
 
    for competency_name, tasks in COMPETENCIES.items():
        cur.execute(
            "INSERT INTO competencies (name) VALUES (?)",
            (competency_name,)
        )
        competency_id = cur.lastrowid
        print(f"Created competency: {competency_name} (id={competency_id})")
 
        for task_name, duration_hours, sequence_order in tasks:
            cur.execute(
                """
                INSERT INTO tasks (competency_id, name, duration_hours, sequence_order)
                VALUES (?, ?, ?, ?)
                """,
                (competency_id, task_name, duration_hours, sequence_order)
            )
            task_ids[(competency_name, task_name)] = cur.lastrowid
            print(f"  Added task: {task_name} ({duration_hours} hrs, seq #{sequence_order})")
 
    # --- Insert instructors ---
    instructor_ids = {}
    for name in INSTRUCTORS:
        cur.execute("INSERT INTO instructors (name) VALUES (?)", (name,))
        instructor_ids[name] = cur.lastrowid
        print(f"Added instructor: {name} (id={cur.lastrowid})")
 
    # --- Insert qualifications ---
    for instructor_name, competency_name, task_name in QUALIFICATIONS:
        key = (competency_name, task_name)
        if key not in task_ids:
            print(f"  WARNING: skipped qualification — no task '{task_name}' "
                  f"found under competency '{competency_name}'. Check spelling.")
            continue
 
        cur.execute(
            """
            INSERT INTO instructor_qualifications (instructor_id, task_id)
            VALUES (?, ?)
            """,
            (instructor_ids[instructor_name], task_ids[key])
        )
        print(f"  {instructor_name} qualified to teach: {task_name} ({competency_name})")
 
    conn.commit()
    conn.close()
    print("\nSeed complete.")
 
 
if __name__ == "__main__":
    seed()
