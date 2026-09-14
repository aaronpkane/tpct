-- ============================================================
-- Training Plan Creation Tool (TPCT) — SQLite Schema
-- ============================================================

PRAGMA foreign_keys = ON;

-- ------------------------------------------------------------
-- COMPETENCIES
-- The top-level training category (e.g., "Boarding Procedures")
-- ------------------------------------------------------------
CREATE TABLE competencies (
    competency_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL UNIQUE
);

-- ------------------------------------------------------------
-- TASKS
-- Tasks are exclusive to a single competency (per your call —
-- "Radio Communications" under two competencies = two separate
-- rows/task_ids, not a shared task).
-- sequence_order defines the FIXED order tasks must be taught in
-- for that competency (1, 2, 3, ...).
-- ------------------------------------------------------------
CREATE TABLE tasks (
    task_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    competency_id   INTEGER NOT NULL,
    name            TEXT NOT NULL,
    duration_hours  REAL NOT NULL,
    sequence_order  INTEGER NOT NULL,
    FOREIGN KEY (competency_id) REFERENCES competencies(competency_id),
    UNIQUE (competency_id, sequence_order)  -- no two tasks in the same competency can share a sequence slot
);

-- ------------------------------------------------------------
-- INSTRUCTORS
-- ------------------------------------------------------------
CREATE TABLE instructors (
    instructor_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL
);

-- ------------------------------------------------------------
-- INSTRUCTOR QUALIFICATIONS
-- Many-to-many: which instructors can teach which tasks.
-- No limit on how many tasks an instructor can be qualified for.
-- ------------------------------------------------------------
CREATE TABLE instructor_qualifications (
    instructor_id   INTEGER NOT NULL,
    task_id         INTEGER NOT NULL,
    PRIMARY KEY (instructor_id, task_id),
    FOREIGN KEY (instructor_id) REFERENCES instructors(instructor_id),
    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
);

-- ------------------------------------------------------------
-- MULTI-PLAN BATCHES
-- Groups several training_plan_requests together as one "concurrent
-- plan" — e.g. two competencies running in the same time window,
-- each with their own days/hours, generated together so instructor
-- assignments don't clash across them. A request with a NULL
-- batch_id is an ordinary single-competency plan, generated exactly
-- as before — this is purely additive.
-- ------------------------------------------------------------
CREATE TABLE multi_plan_batches (
    batch_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    label        TEXT,              -- optional friendly name, e.g. "Fall Quals Cycle"
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ------------------------------------------------------------
-- TRAINING PLAN REQUESTS
-- One row per generated plan attempt (successful or not).
-- allowed_days_of_week stored as comma-separated ints: 0=Mon ... 6=Sun
-- batch_id is NULL for an ordinary single-competency plan, or points
-- to a multi_plan_batches row when generated as part of a concurrent
-- multi-competency plan.
-- ------------------------------------------------------------
CREATE TABLE training_plan_requests (
    request_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    competency_id        INTEGER NOT NULL,
    start_date            TEXT NOT NULL,   -- ISO format: YYYY-MM-DD
    end_date               TEXT NOT NULL,   -- ISO format: YYYY-MM-DD, defines the allotted window
    daily_start_time      TEXT NOT NULL,   -- HH:MM, 24hr
    daily_end_time         TEXT NOT NULL,   -- HH:MM, 24hr — hard stop for the day
    allowed_days_of_week   TEXT NOT NULL,   -- e.g. "0,1,2" for Mon/Tue/Wed
    batch_id               INTEGER,          -- NULL = standalone single-competency plan
    created_at             TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (competency_id) REFERENCES competencies(competency_id),
    FOREIGN KEY (batch_id) REFERENCES multi_plan_batches(batch_id)
);

-- ------------------------------------------------------------
-- REQUEST INSTRUCTORS
-- Many-to-many: which instructors were marked available for a
-- given plan request (available for the ENTIRE plan duration).
-- ------------------------------------------------------------
CREATE TABLE request_instructors (
    request_id      INTEGER NOT NULL,
    instructor_id   INTEGER NOT NULL,
    PRIMARY KEY (request_id, instructor_id),
    FOREIGN KEY (request_id) REFERENCES training_plan_requests(request_id),
    FOREIGN KEY (instructor_id) REFERENCES instructors(instructor_id)
);

-- ------------------------------------------------------------
-- PLAN SEGMENTS
-- The generated output. A task may be split across multiple
-- segments/days; multiple segments (from different tasks) can
-- share the same date as long as they're in the same competency
-- and fit within the daily cap.
-- ------------------------------------------------------------
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

-- ------------------------------------------------------------
-- BLACKOUT DATES
-- Dates automatically excluded from ANY plan's eligible training
-- days, regardless of what allowed_days_of_week says. Starts with
-- federal holidays (source='FEDERAL_HOLIDAY'), extensible later to
-- manually-added blackout dates (source='MANUAL') — e.g. base
-- standdowns, unit-specific closures.
-- ------------------------------------------------------------
CREATE TABLE blackout_dates (
    blackout_date   TEXT PRIMARY KEY,   -- ISO format: YYYY-MM-DD
    label           TEXT NOT NULL,      -- e.g. "Independence Day"
    source          TEXT NOT NULL       -- 'FEDERAL_HOLIDAY' or 'MANUAL'
);

-- ------------------------------------------------------------
-- INFEASIBILITY REPORTS
-- If a plan request cannot be satisfied, log every specific
-- blocking reason here instead of generating segments.
-- ------------------------------------------------------------
CREATE TABLE infeasibility_reasons (
    reason_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id      INTEGER NOT NULL,
    reason_type     TEXT NOT NULL,   -- 'SHORTFALL', 'NO_INSTRUCTOR', 'INVALID_TIME_WINDOW',
                                      -- or 'INSTRUCTOR_CONFLICT' (concurrent-plan double-booking)
    task_id         INTEGER,          -- nullable — SHORTFALL reasons aren't task-specific
    detail          TEXT NOT NULL,   -- human-readable, e.g. "Shortfall: 6 hours over allotted range"
    FOREIGN KEY (request_id) REFERENCES training_plan_requests(request_id),
    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
);
