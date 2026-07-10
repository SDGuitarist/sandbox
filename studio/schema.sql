-- ---------- identity ----------
CREATE TABLE users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('admin','instructor','student')),
    name          TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ---------- people ----------
CREATE TABLE students (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER UNIQUE REFERENCES users(id) ON DELETE SET NULL,  -- login (nullable: managed students)
    first_name   TEXT NOT NULL,
    last_name    TEXT NOT NULL,
    email        TEXT,
    phone        TEXT,
    skill_level  TEXT NOT NULL DEFAULT 'beginner'
                 CHECK (skill_level IN ('beginner','intermediate','advanced')),
    active       INTEGER NOT NULL DEFAULT 1,
    notes        TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE instructors (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER UNIQUE REFERENCES users(id) ON DELETE SET NULL,
    first_name   TEXT NOT NULL,
    last_name    TEXT NOT NULL,
    email        TEXT,
    phone        TEXT,
    bio          TEXT,
    hourly_rate_cents INTEGER NOT NULL DEFAULT 0,
    active       INTEGER NOT NULL DEFAULT 1,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ---------- facilities & inventory ----------
CREATE TABLE rooms (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    name      TEXT NOT NULL,
    capacity  INTEGER NOT NULL DEFAULT 1,
    location  TEXT,
    active    INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE instruments (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    category      TEXT NOT NULL,
    serial_number TEXT,
    condition     TEXT NOT NULL DEFAULT 'good'
                  CHECK (condition IN ('good','fair','needs_repair')),
    status        TEXT NOT NULL DEFAULT 'available'
                  CHECK (status IN ('available','checked_out','maintenance')),
    notes         TEXT
);

-- ---------- curriculum ----------
CREATE TABLE courses (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    description   TEXT,
    instructor_id INTEGER REFERENCES instructors(id) ON DELETE SET NULL,
    level         TEXT NOT NULL DEFAULT 'beginner'
                  CHECK (level IN ('beginner','intermediate','advanced')),
    capacity      INTEGER NOT NULL DEFAULT 10,
    price_cents   INTEGER NOT NULL DEFAULT 0,
    active        INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE enrollments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id  INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    course_id   INTEGER NOT NULL REFERENCES courses(id)  ON DELETE CASCADE,
    status      TEXT NOT NULL DEFAULT 'active'
                CHECK (status IN ('active','completed','withdrawn')),
    enrolled_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (student_id, course_id)
);

-- ---------- scheduling (the 4-way FK seam) ----------
CREATE TABLE lessons (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id     INTEGER REFERENCES courses(id)      ON DELETE SET NULL,
    instructor_id INTEGER NOT NULL REFERENCES instructors(id) ON DELETE CASCADE,
    student_id    INTEGER NOT NULL REFERENCES students(id)    ON DELETE CASCADE,
    room_id       INTEGER REFERENCES rooms(id)         ON DELETE SET NULL,
    starts_at     TEXT NOT NULL,
    ends_at       TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'scheduled'
                  CHECK (status IN ('scheduled','completed','cancelled','no_show')),
    notes         TEXT
);

CREATE TABLE attendance (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    lesson_id  INTEGER NOT NULL REFERENCES lessons(id)  ON DELETE CASCADE,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    present    INTEGER NOT NULL DEFAULT 0,
    marked_by  INTEGER REFERENCES users(id) ON DELETE SET NULL,
    marked_at  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (lesson_id, student_id)
);

-- ---------- inventory transactions ----------
CREATE TABLE instrument_checkouts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    instrument_id INTEGER NOT NULL REFERENCES instruments(id) ON DELETE CASCADE,
    student_id    INTEGER NOT NULL REFERENCES students(id)    ON DELETE CASCADE,
    checked_out_at TEXT NOT NULL DEFAULT (datetime('now')),
    due_at        TEXT NOT NULL,
    returned_at   TEXT,
    status        TEXT NOT NULL DEFAULT 'out'
                  CHECK (status IN ('out','returned','overdue'))
);

-- ---------- billing (multi-table transaction) ----------
CREATE TABLE invoices (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id   INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    description  TEXT,
    status       TEXT NOT NULL DEFAULT 'draft'
                 CHECK (status IN ('draft','sent','paid','void')),
    issued_at    TEXT NOT NULL DEFAULT (datetime('now')),
    due_at       TEXT,
    paid_at      TEXT,
    created_by   INTEGER REFERENCES users(id) ON DELETE SET NULL
    -- NOTE: no amount column. The invoice total is the SUM of invoice_items.amount_cents,
    -- computed in invoice_models.get_invoice() — single source of truth (avoids drift).
);
-- One-open-draft-per-student invariant is SCHEMA-ENFORCED (not just app logic): a partial
-- UNIQUE index over the draft state. get_or_create_draft_invoice_in_tx relies on this, and a
-- concurrent double-enroll can no longer create two drafts (the 2nd INSERT fails the index).
CREATE UNIQUE INDEX ux_one_draft_per_student ON invoices(student_id) WHERE status = 'draft';

CREATE TABLE invoice_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id  INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    description TEXT NOT NULL,
    amount_cents INTEGER NOT NULL,
    source_type TEXT NOT NULL DEFAULT 'manual'
                CHECK (source_type IN ('manual','enrollment','checkout_fee')),
    source_id   INTEGER
);

-- ---------- student self-service ----------
CREATE TABLE practice_logs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    minutes    INTEGER NOT NULL CHECK (minutes > 0),
    notes      TEXT,
    logged_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ---------- messaging (role-scoped visibility) ----------
CREATE TABLE announcements (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    author_id  INTEGER REFERENCES users(id) ON DELETE SET NULL,
    title      TEXT NOT NULL,
    body       TEXT NOT NULL,
    audience   TEXT NOT NULL DEFAULT 'all'
               CHECK (audience IN ('all','students','instructors')),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ---------- cross-cutting audit (written by MANY agents via audit_models) ----------
CREATE TABLE audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action      TEXT NOT NULL,             -- 'create'|'update'|'delete'|'checkout'|'return'|'pay'
    entity_type TEXT NOT NULL,             -- 'student'|'lesson'|'invoice'|...
    entity_id   INTEGER,
    detail      TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
