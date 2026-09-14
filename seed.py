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
        ("LEQB: Law Enforcement Qualification Board", 1.0, 14),
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
        ("LEQB: Law Enforcement Qualification Board", 1.0, 12),
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
        ("1-29: Radiation Detection Level 1 Initial Training ", 2.0, 29),
        ("LEQB: Law Enforcement Qualification Board", 1.0, 30),
    ],

    "Damage Control - Initial": [
        ("BDC-01: Damage Control - General", 2.0, 1),
        ("BDC-02: Personal Protection Equipment", 2.0, 2),
        ("BDC-03: Flooding", 2.0, 3),
        ("BDC-04: Detwatering", 2.0, 4),
        ("BDC-05: P-100 Pump", 2.0, 5),
        ("ADC-01: P-100 High Suction Lift Operating Procedures", 2.0, 6),
        ("ADC-02: P-100 Tandem Operating Procedures", 2.0, 7),
        ("BDC-08: Firefighting", 2.0, 8),
        ("BDC-09: Fire Watchstander", 2.0, 9),
        ("BDC-10: First Aid", 2.0, 10),
        ("BDC-11: Hazardous Materials & Toxic Gas", 2.0, 11),
        ("BDC-12: Loss of Electrical Power", 2.0, 12),
        ("BDC-13: Chemical Biological, Radiological, & Nuclear Defense", 2.0, 13),
        ("ADC-03: AFFF Station Operator", 2.0, 14),
        ("ADC-04: Investigator", 2.0, 15),
        ("ADC-05: Attack Team Leader", 2.0, 16),
        ("ADC-06: On-Scene Leader", 2.0, 17),
        ("ADC-07: Repair Locker Leader", 2.0, 18),
        ("DCQB: Damage Control Qualification Board", 1.0, 19),
    ],
}
 
# ------------------------------------------------------------------
# INSTRUCTORS
# ------------------------------------------------------------------
INSTRUCTORS = [
    "ME1 Kane",
    "ME2 Smith",
    "ME3 Wood",
    "DCC Smith",
    "DC1 Johnson",
    "MKC Davis",
    "MK1 Lee",
    "MK2 Patel",
    "HSC Brown",
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
    ("ME1 Kane", "Security Team Watchstander - Initial", "LEQB: Law Enforcement Qualification Board"),

    ("ME2 Smith", "Security Team Watchstander - Initial", "1-01: Physical Fitness Standards"),
    ("ME2 Smith", "Security Team Watchstander - Initial", "1-04: Defense and Control Group 1"),
    ("ME2 Smith", "Security Team Watchstander - Initial", "1-05: Defense and Control Group 2"),
    ("ME2 Smith", "Security Team Watchstander - Initial", "1-06: Defense and Control Group 3"),
    ("ME2 Smith", "Security Team Watchstander - Initial", "1-07: Defense and Control Group 4"),
    ("ME2 Smith", "Security Team Watchstander - Initial", "1-08: Defense and Control Group 5"),
    ("ME2 Smith", "Security Team Watchstander - Initial", "1-10: Two Person Use of Force"),
    ("ME2 Smith", "Security Team Watchstander - Initial", "1-18: Frisk Search"),
    ("ME2 Smith", "Security Team Watchstander - Initial", "LEQB: Law Enforcement Qualification Board"),

    ("ME3 Wood", "Security Team Watchstander - Initial", "1-01: Physical Fitness Standards"),
    ("ME3 Wood", "Security Team Watchstander - Initial", "1-03: Use of Force Policy"),
    ("ME3 Wood", "Security Team Watchstander - Initial", "Use of Force Policy Reinforcement"),
    ("ME3 Wood", "Security Team Watchstander - Initial", "1-09: Deadly Force"),
    ("ME3 Wood", "Security Team Watchstander - Initial", "1-18: Frisk Search"),
    ("ME3 Wood", "Security Team Watchstander - Initial", "1-20: Law Enforcement Equipment"),
    ("ME3 Wood", "Security Team Watchstander - Initial", "1-22: Chemical Irritants"),
    ("ME3 Wood", "Security Team Watchstander - Initial", "LEQB: Law Enforcement Qualification Board"),
 
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
    ("ME1 Kane", "Security Team Watchstander - Recurrent", "LEQB: Law Enforcement Qualification Board"),

    ("ME2 Smith", "Security Team Watchstander - Recurrent", "1-01: Physical Fitness Standards"),
    ("ME2 Smith", "Security Team Watchstander - Recurrent", "1-04: Defense and Control Group 1"),
    ("ME2 Smith", "Security Team Watchstander - Recurrent", "1-05: Defense and Control Group 2"),
    ("ME2 Smith", "Security Team Watchstander - Recurrent", "1-06: Defense and Control Group 3"),
    ("ME2 Smith", "Security Team Watchstander - Recurrent", "1-07: Defense and Control Group 4"),
    ("ME2 Smith", "Security Team Watchstander - Recurrent", "1-08: Defense and Control Group 5"),
    ("ME2 Smith", "Security Team Watchstander - Recurrent", "1-10: Two Person Use of Force"),
    ("ME2 Smith", "Security Team Watchstander - Recurrent", "1-18: Frisk Search"),
    ("ME2 Smith", "Security Team Watchstander - Recurrent", "LEQB: Law Enforcement Qualification Board"),

    ("ME3 Wood", "Security Team Watchstander - Recurrent", "1-01: Physical Fitness Standards"),
    ("ME3 Wood", "Security Team Watchstander - Recurrent", "1-03: Use of Force Policy"),
    ("ME3 Wood", "Security Team Watchstander - Recurrent", "Use of Force Policy Reinforcement"),
    ("ME3 Wood", "Security Team Watchstander - Recurrent", "1-09: Deadly Force"),
    ("ME3 Wood", "Security Team Watchstander - Recurrent", "1-18: Frisk Search"),
    ("ME3 Wood", "Security Team Watchstander - Recurrent", "LEQB: Law Enforcement Qualification Board"),

    ("ME1 Kane", "Boarding Team Member - Initial", "1-01: Physical Fitness Standards"),
    ("ME1 Kane", "Boarding Team Member - Initial", "1-02: Authority and Jurisdiction"),
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
    ("ME1 Kane", "Boarding Team Member - Initial", "LEQB: Law Enforcement Qualification Board"),

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
    ("ME2 Smith", "Boarding Team Member - Initial", "LEQB: Law Enforcement Qualification Board"),

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
    ("ME3 Wood", "Boarding Team Member - Initial", "LEQB: Law Enforcement Qualification Board"),

    ("DCC Smith", "Damage Control - Initial", "BDC-01: Damage Control - General"),
    ("DCC Smith", "Damage Control - Initial", "BDC-02: Personal Protection Equipment"),
    ("DCC Smith", "Damage Control - Initial", "BDC-03: Flooding"),
    ("DCC Smith", "Damage Control - Initial", "BDC-04: Detwatering"),
    ("DCC Smith", "Damage Control - Initial", "BDC-05: P-100 Pump"),
    ("DCC Smith", "Damage Control - Initial", "ADC-01: P-100 High Suction Lift Operating Procedures"),
    ("DCC Smith", "Damage Control - Initial", "ADC-02: P-100 Tandem Operating Procedures"),
    ("DCC Smith", "Damage Control - Initial", "BDC-08: Firefighting"),
    ("DCC Smith", "Damage Control - Initial", "BDC-09: Fire Watchstander"),
    ("DCC Smith", "Damage Control - Initial", "BDC-11: Hazardous Materials & Toxic Gas"),
    ("DCC Smith", "Damage Control - Initial", "BDC-12: Loss of Electrical Power"),
    ("DCC Smith", "Damage Control - Initial", "BDC-13: Chemical Biological, Radiological, & Nuclear Defense"),
    ("DCC Smith", "Damage Control - Initial", "ADC-03: AFFF Station Operator"),
    ("DCC Smith", "Damage Control - Initial", "ADC-04: Investigator"),
    ("DCC Smith", "Damage Control - Initial", "ADC-05: Attack Team Leader"),
    ("DCC Smith", "Damage Control - Initial", "ADC-06: On-Scene Leader"),
    ("DCC Smith", "Damage Control - Initial", "ADC-07: Repair Locker Leader"),
    ("DCC Smith", "Damage Control - Initial", "DCQB: Damage Control Qualification Board"),

    ("DC1 Johnson", "Damage Control - Initial", "BDC-01: Damage Control - General"),
    ("DC1 Johnson", "Damage Control - Initial", "BDC-02: Personal Protection Equipment"),
    ("DC1 Johnson", "Damage Control - Initial", "BDC-03: Flooding"),
    ("DC1 Johnson", "Damage Control - Initial", "BDC-04: Detwatering"),
    ("DC1 Johnson", "Damage Control - Initial", "BDC-05: P-100 Pump"),
    ("DC1 Johnson", "Damage Control - Initial", "ADC-01: P-100 High Suction Lift Operating Procedures"),
    ("DC1 Johnson", "Damage Control - Initial", "ADC-02: P-100 Tandem Operating Procedures"),
    ("DC1 Johnson", "Damage Control - Initial", "BDC-08: Firefighting"),
    ("DC1 Johnson", "Damage Control - Initial", "BDC-09: Fire Watchstander"),
    ("DC1 Johnson", "Damage Control - Initial", "BDC-11: Hazardous Materials & Toxic Gas"),
    ("DC1 Johnson", "Damage Control - Initial", "BDC-12: Loss of Electrical Power"),
    ("DC1 Johnson", "Damage Control - Initial", "BDC-13: Chemical Biological, Radiological, & Nuclear Defense"),
    ("DC1 Johnson", "Damage Control - Initial", "ADC-03: AFFF Station Operator"),
    ("DC1 Johnson", "Damage Control - Initial", "ADC-04: Investigator"),
    ("DC1 Johnson", "Damage Control - Initial", "ADC-05: Attack Team Leader"),
    ("DC1 Johnson", "Damage Control - Initial", "ADC-06: On-Scene Leader"),
    ("DC1 Johnson", "Damage Control - Initial", "ADC-07: Repair Locker Leader"),
    ("DC1 Johnson", "Damage Control - Initial", "DCQB: Damage Control Qualification Board"),

    ("MKC Davis", "Damage Control - Initial", "BDC-01: Damage Control - General"),
    ("MKC Davis", "Damage Control - Initial", "BDC-02: Personal Protection Equipment"),
    ("MKC Davis", "Damage Control - Initial", "BDC-03: Flooding"),
    ("MKC Davis", "Damage Control - Initial", "BDC-04: Detwatering"),
    ("MKC Davis", "Damage Control - Initial", "BDC-05: P-100 Pump"),
    ("MKC Davis", "Damage Control - Initial", "ADC-01: P-100 High Suction Lift Operating Procedures"),
    ("MKC Davis", "Damage Control - Initial", "ADC-02: P-100 Tandem Operating Procedures"),
    ("MKC Davis", "Damage Control - Initial", "BDC-08: Firefighting"),
    ("MKC Davis", "Damage Control - Initial", "BDC-09: Fire Watchstander"),
    ("MKC Davis", "Damage Control - Initial", "BDC-11: Hazardous Materials & Toxic Gas"),
    ("MKC Davis", "Damage Control - Initial", "BDC-12: Loss of Electrical Power"),
    ("MKC Davis", "Damage Control - Initial", "BDC-13: Chemical Biological, Radiological, & Nuclear Defense"),
    ("MKC Davis", "Damage Control - Initial", "ADC-03: AFFF Station Operator"),
    ("MKC Davis", "Damage Control - Initial", "ADC-04: Investigator"),
    ("MKC Davis", "Damage Control - Initial", "ADC-05: Attack Team Leader"),
    ("MKC Davis", "Damage Control - Initial", "ADC-06: On-Scene Leader"),
    ("MKC Davis", "Damage Control - Initial", "ADC-07: Repair Locker Leader"),
    ("MKC Davis", "Damage Control - Initial", "DCQB: Damage Control Qualification Board"),

    ("MK1 Lee", "Damage Control - Initial", "BDC-01: Damage Control - General"),
    ("MK1 Lee", "Damage Control - Initial", "BDC-02: Personal Protection Equipment"),
    ("MK1 Lee", "Damage Control - Initial", "BDC-03: Flooding"),
    ("MK1 Lee", "Damage Control - Initial", "BDC-04: Detwatering"),
    ("MK1 Lee", "Damage Control - Initial", "BDC-05: P-100 Pump"),
    ("MK1 Lee", "Damage Control - Initial", "ADC-01: P-100 High Suction Lift Operating Procedures"),
    ("MK1 Lee", "Damage Control - Initial", "ADC-02: P-100 Tandem Operating Procedures"),
    ("MK1 Lee", "Damage Control - Initial", "BDC-08: Firefighting"),
    ("MK1 Lee", "Damage Control - Initial", "BDC-09: Fire Watchstander"),
    ("MK1 Lee", "Damage Control - Initial", "BDC-11: Hazardous Materials & Toxic Gas"),
    ("MK1 Lee", "Damage Control - Initial", "BDC-12: Loss of Electrical Power"),
    ("MK1 Lee", "Damage Control - Initial", "BDC-13: Chemical Biological, Radiological, & Nuclear Defense"),
    ("MK1 Lee", "Damage Control - Initial", "ADC-03: AFFF Station Operator"),
    ("MK1 Lee", "Damage Control - Initial", "ADC-04: Investigator"),
    ("MK1 Lee", "Damage Control - Initial", "ADC-05: Attack Team Leader"),
    ("MK1 Lee", "Damage Control - Initial", "ADC-06: On-Scene Leader"),
    ("MK1 Lee", "Damage Control - Initial", "ADC-07: Repair Locker Leader"),
    ("MK1 Lee", "Damage Control - Initial", "DCQB: Damage Control Qualification Board"),

    ("MK2 Patel", "Damage Control - Initial", "BDC-01: Damage Control - General"),
    ("MK2 Patel", "Damage Control - Initial", "BDC-02: Personal Protection Equipment"),
    ("MK2 Patel", "Damage Control - Initial", "BDC-03: Flooding"),
    ("MK2 Patel", "Damage Control - Initial", "BDC-04: Detwatering"),
    ("MK2 Patel", "Damage Control - Initial", "BDC-05: P-100 Pump"),
    ("MK2 Patel", "Damage Control - Initial", "ADC-01: P-100 High Suction Lift Operating Procedures"),
    ("MK2 Patel", "Damage Control - Initial", "ADC-02: P-100 Tandem Operating Procedures"),
    ("MK2 Patel", "Damage Control - Initial", "BDC-08: Firefighting"),
    ("MK2 Patel", "Damage Control - Initial", "BDC-09: Fire Watchstander"),
    ("MK2 Patel", "Damage Control - Initial", "BDC-11: Hazardous Materials & Toxic Gas"),
    ("MK2 Patel", "Damage Control - Initial", "BDC-12: Loss of Electrical Power"),
    ("MK2 Patel", "Damage Control - Initial", "BDC-13: Chemical Biological, Radiological, & Nuclear Defense"),
    ("MK2 Patel", "Damage Control - Initial", "ADC-03: AFFF Station Operator"),
    ("MK2 Patel", "Damage Control - Initial", "ADC-04: Investigator"),
    ("MK2 Patel", "Damage Control - Initial", "ADC-05: Attack Team Leader"),
    ("MK2 Patel", "Damage Control - Initial", "ADC-06: On-Scene Leader"),
    ("MK2 Patel", "Damage Control - Initial", "ADC-07: Repair Locker Leader"),
    ("MK2 Patel", "Damage Control - Initial", "DCQB: Damage Control Qualification Board"),

    ("HSC Brown", "Damage Control - Initial", "BDC-10: First Aid"),
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
