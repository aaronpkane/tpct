-- ============================================================
-- Training Plan Creation Tool (TPCT) — SQLite Schema
-- ============================================================
 
PRAGMA foreign_keys = ON;

CREATE TABLE competencies (
    competency_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL UNIQUE
);

CREATE TABLE tasks (
    task_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    competency_id   INTEGER NOT NULL,
    name            TEXT NOT NULL,
    duration_hours  REAL NOT NULL,
    sequence_order  INTEGER NOT NULL,
    FOREIGN KEY (competency_id) REFERENCES competencies(competency_id),
    UNIQUE (competency_id, sequence_order)  -- no two tasks in the same competency can share a sequence slot
);

CREATE TABLE instructors (
    instructor_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL
);

CREATE TABLE instructor_qualifications (
    instructor_id   INTEGER NOT NULL,
    task_id         INTEGER NOT NULL,
    PRIMARY KEY (instructor_id, task_id),
    FOREIGN KEY (instructor_id) REFERENCES instructors(instructor_id),
    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
);

CREATE TABLE training_plan_requests (
    request_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    competency_id        INTEGER NOT NULL,
    start_date            TEXT NOT NULL,   -- ISO format: YYYY-MM-DD
    end_date               TEXT NOT NULL,   -- ISO format: YYYY-MM-DD
    daily_start_time      TEXT NOT NULL,   -- HH:MM, 24hr
    allowed_days_of_week   TEXT NOT NULL,   -- e.g. "0,1,2" for Mon/Tue/Wed
    created_at             TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (competency_id) REFERENCES competencies(competency_id)
);

CREATE TABLE request_instructors (
    request_id      INTEGER NOT NULL,
    instructor_id   INTEGER NOT NULL,
    PRIMARY KEY (request_id, instructor_id),
    FOREIGN KEY (request_id) REFERENCES training_plan_requests(request_id),
    FOREIGN KEY (instructor_id) REFERENCES instructors(instructor_id)
);

CREATE TABLE plan_segments (
    segment_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id          INTEGER NOT NULL,
    task_id              INTEGER NOT NULL,
    assigned_instructor_id INTEGER NOT NULL,
    segment_date          TEXT NOT NULL,   -- ISO format: YYYY-MM-DD
    start_time            TEXT NOT NULL,   -- HH:MM
    end_time               TEXT NOT NULL,   -- HH:MM
    hours_this_segment      REAL NOT NULL,
    FOREIGN KEY (request_id) REFERENCES training_plan_requests(request_id),
    FOREIGN KEY (task_id) REFERENCES tasks(task_id),
    FOREIGN KEY (assigned_instructor_id) REFERENCES instructors(instructor_id)
);

CREATE TABLE infeasibility_reasons (
    reason_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id      INTEGER NOT NULL,
    reason_type     TEXT NOT NULL,   -- e.g. 'SHORTFALL', 'NO_INSTRUCTOR'
    task_id         INTEGER,          -- nullable — SHORTFALL reasons aren't task-specific
    detail          TEXT NOT NULL,   -- human-readable, e.g. "Shortfall: 6 hours over allotted range"
    FOREIGN KEY (request_id) REFERENCES training_plan_requests(request_id),
    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
);
