"""Database connection, schema initialization, query helper, and transaction manager.

Owned by the `database` agent. Provides the infrastructure exports consumed by every
model agent and the scaffold app factory:

- `get_db() -> sqlite3.Connection` — one connection per request, cached on Flask `g`.
- `query(sql, params=(), one=False)` — thin read helper returning plain dicts.
- `init_db() -> None` — runs schema.sql then inserts seed rows.
- `transaction()` — context manager wrapping the single request connection in
  `BEGIN IMMEDIATE`, committing on clean exit and rolling back on exception.
"""

import os
import sqlite3
from contextlib import contextmanager

from flask import current_app, g
from werkzeug.security import generate_password_hash

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


def get_db() -> sqlite3.Connection:
    """Return the request-scoped SQLite connection, opening it on first use.

    Sets ``row_factory = sqlite3.Row`` and enforces ``PRAGMA foreign_keys = ON``
    per-connection. The connection is cached on Flask ``g`` and closed by the
    registered teardown. The DB path is read ONLY from the app config (never the
    env var directly) so scaffold/database/smoke-test agree on one source of truth.
    """
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(exception=None) -> None:
    """Teardown callback: close the request connection if one was opened."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query(sql, params=(), one=False):
    """Run a read query and return plain dicts (never leak sqlite3.Row).

    Returns a ``list[dict]`` normally, or a single ``dict`` / ``None`` when
    ``one=True``.
    """
    cur = get_db().execute(sql, params)
    rows = cur.fetchall()
    cur.close()
    if one:
        return dict(rows[0]) if rows else None
    return [dict(row) for row in rows]


@contextmanager
def transaction():
    """Wrap the single request connection in a ``BEGIN IMMEDIATE`` transaction.

    Yields the SAME ``get_db()`` connection every model function uses, so reads
    done inside the block see the transaction's own uncommitted writes. Commits on
    clean exit; rolls back on any exception. Nested use is forbidden by contract.
    """
    conn = get_db()
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    else:
        conn.commit()


def init_db() -> None:
    """Create the schema then insert seed rows.

    The app factory calls this only when the DB file does not already exist. The
    schema is applied via ``executescript`` as a standalone sequence (never inside
    a ``with conn:`` block), then seed rows are inserted and committed once.
    """
    conn = get_db()
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        conn.executescript(f.read())
    _seed(conn)


def _seed(conn: sqlite3.Connection) -> None:
    """Insert seed data satisfying every NOT NULL / CHECK / UNIQUE constraint.

    1 admin, 2 instructor users + rows, 3 student users + rows, 3 rooms,
    4 instruments, 3 courses, plus enrollments / lessons / invoices with real
    relationships. Invoice statuses respect ``ux_one_draft_per_student`` (at most
    ONE draft per student): student A -> draft, student B -> paid, student C -> sent.
    """
    # ---------- users ----------
    admin_id = conn.execute(
        "INSERT INTO users (email, password_hash, role, name) VALUES (?, ?, 'admin', ?)",
        ("admin@studio.test", generate_password_hash("studiopass"), "Studio Admin"),
    ).lastrowid

    instr_user_1 = conn.execute(
        "INSERT INTO users (email, password_hash, role, name) VALUES (?, ?, 'instructor', ?)",
        ("bach@studio.test", generate_password_hash("studiopass"), "Johann Bach"),
    ).lastrowid
    instr_user_2 = conn.execute(
        "INSERT INTO users (email, password_hash, role, name) VALUES (?, ?, 'instructor', ?)",
        ("ella@studio.test", generate_password_hash("studiopass"), "Ella Fitz"),
    ).lastrowid

    stud_user_a = conn.execute(
        "INSERT INTO users (email, password_hash, role, name) VALUES (?, ?, 'student', ?)",
        ("amy@studio.test", generate_password_hash("studiopass"), "Amy Adams"),
    ).lastrowid
    stud_user_b = conn.execute(
        "INSERT INTO users (email, password_hash, role, name) VALUES (?, ?, 'student', ?)",
        ("ben@studio.test", generate_password_hash("studiopass"), "Ben Baker"),
    ).lastrowid
    stud_user_c = conn.execute(
        "INSERT INTO users (email, password_hash, role, name) VALUES (?, ?, 'student', ?)",
        ("cara@studio.test", generate_password_hash("studiopass"), "Cara Cole"),
    ).lastrowid

    # ---------- instructors ----------
    instr_1 = conn.execute(
        "INSERT INTO instructors (user_id, first_name, last_name, email, phone, bio, hourly_rate_cents) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (instr_user_1, "Johann", "Bach", "bach@studio.test", "555-0101", "Piano and theory.", 6000),
    ).lastrowid
    instr_2 = conn.execute(
        "INSERT INTO instructors (user_id, first_name, last_name, email, phone, bio, hourly_rate_cents) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (instr_user_2, "Ella", "Fitz", "ella@studio.test", "555-0102", "Voice and jazz.", 7000),
    ).lastrowid

    # ---------- students ----------
    stud_a = conn.execute(
        "INSERT INTO students (user_id, first_name, last_name, email, phone, skill_level) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (stud_user_a, "Amy", "Adams", "amy@studio.test", "555-0201", "beginner"),
    ).lastrowid
    stud_b = conn.execute(
        "INSERT INTO students (user_id, first_name, last_name, email, phone, skill_level) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (stud_user_b, "Ben", "Baker", "ben@studio.test", "555-0202", "intermediate"),
    ).lastrowid
    stud_c = conn.execute(
        "INSERT INTO students (user_id, first_name, last_name, email, phone, skill_level) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (stud_user_c, "Cara", "Cole", "cara@studio.test", "555-0203", "advanced"),
    ).lastrowid

    # ---------- rooms ----------
    room_1 = conn.execute(
        "INSERT INTO rooms (name, capacity, location) VALUES (?, ?, ?)",
        ("Studio A", 1, "Ground floor"),
    ).lastrowid
    room_2 = conn.execute(
        "INSERT INTO rooms (name, capacity, location) VALUES (?, ?, ?)",
        ("Studio B", 2, "Ground floor"),
    ).lastrowid
    conn.execute(
        "INSERT INTO rooms (name, capacity, location) VALUES (?, ?, ?)",
        ("Recital Hall", 30, "Second floor"),
    )

    # ---------- instruments ----------
    # One instrument is seeded as checked_out; a matching checkout row is created below.
    inst_guitar = conn.execute(
        "INSERT INTO instruments (name, category, serial_number, condition, status) "
        "VALUES (?, ?, ?, ?, 'available')",
        ("Yamaha Acoustic Guitar", "guitar", "GTR-001", "good"),
    ).lastrowid
    inst_violin = conn.execute(
        "INSERT INTO instruments (name, category, serial_number, condition, status) "
        "VALUES (?, ?, ?, ?, 'checked_out')",
        ("Student Violin", "strings", "VLN-001", "good"),
    ).lastrowid
    conn.execute(
        "INSERT INTO instruments (name, category, serial_number, condition, status) "
        "VALUES (?, ?, ?, ?, 'available')",
        ("Roland Keyboard", "keyboard", "KBD-001", "fair"),
    )
    conn.execute(
        "INSERT INTO instruments (name, category, serial_number, condition, status) "
        "VALUES (?, ?, ?, ?, 'maintenance')",
        ("Pearl Snare Drum", "percussion", "DRM-001", "needs_repair"),
    )

    # ---------- courses ----------
    course_piano = conn.execute(
        "INSERT INTO courses (name, description, instructor_id, level, capacity, price_cents) "
        "VALUES (?, ?, ?, 'beginner', ?, ?)",
        ("Beginner Piano", "Intro to piano.", instr_1, 8, 12000),
    ).lastrowid
    course_voice = conn.execute(
        "INSERT INTO courses (name, description, instructor_id, level, capacity, price_cents) "
        "VALUES (?, ?, ?, 'intermediate', ?, ?)",
        ("Intermediate Voice", "Vocal technique.", instr_2, 6, 15000),
    ).lastrowid
    course_theory = conn.execute(
        "INSERT INTO courses (name, description, instructor_id, level, capacity, price_cents) "
        "VALUES (?, ?, ?, 'beginner', ?, ?)",
        ("Music Theory 101", "Free community course.", instr_1, 20, 0),
    ).lastrowid

    # ---------- enrollments (unique student_id, course_id pairs) ----------
    conn.execute(
        "INSERT INTO enrollments (student_id, course_id, status) VALUES (?, ?, 'active')",
        (stud_a, course_piano),
    )
    conn.execute(
        "INSERT INTO enrollments (student_id, course_id, status) VALUES (?, ?, 'active')",
        (stud_a, course_theory),
    )
    conn.execute(
        "INSERT INTO enrollments (student_id, course_id, status) VALUES (?, ?, 'active')",
        (stud_b, course_voice),
    )
    conn.execute(
        "INSERT INTO enrollments (student_id, course_id, status) VALUES (?, ?, 'completed')",
        (stud_c, course_theory),
    )

    # ---------- lessons (ends_at > starts_at) ----------
    conn.execute(
        "INSERT INTO lessons (course_id, instructor_id, student_id, room_id, starts_at, ends_at, status) "
        "VALUES (?, ?, ?, ?, ?, ?, 'scheduled')",
        (course_piano, instr_1, stud_a, room_1, "2026-07-15T10:00:00", "2026-07-15T11:00:00"),
    )
    conn.execute(
        "INSERT INTO lessons (course_id, instructor_id, student_id, room_id, starts_at, ends_at, status) "
        "VALUES (?, ?, ?, ?, ?, ?, 'scheduled')",
        (course_voice, instr_2, stud_b, room_2, "2026-07-16T14:00:00", "2026-07-16T15:00:00"),
    )
    lesson_completed = conn.execute(
        "INSERT INTO lessons (course_id, instructor_id, student_id, room_id, starts_at, ends_at, status) "
        "VALUES (?, ?, ?, ?, ?, ?, 'completed')",
        (course_piano, instr_1, stud_a, room_1, "2026-07-08T10:00:00", "2026-07-08T11:00:00"),
    ).lastrowid

    # ---------- attendance (one row per lesson/student) ----------
    conn.execute(
        "INSERT INTO attendance (lesson_id, student_id, present, marked_by) VALUES (?, ?, 1, ?)",
        (lesson_completed, stud_a, instr_user_1),
    )

    # ---------- instrument checkout (consistent with inst_violin status='checked_out') ----------
    conn.execute(
        "INSERT INTO instrument_checkouts (instrument_id, student_id, due_at, status) "
        "VALUES (?, ?, ?, 'out')",
        (inst_violin, stud_b, "2026-08-01T00:00:00"),
    )

    # ---------- invoices (<= 1 draft per student: A->draft, B->paid, C->sent) ----------
    inv_a = conn.execute(
        "INSERT INTO invoices (student_id, description, status, due_at, created_by) "
        "VALUES (?, ?, 'draft', ?, ?)",
        (stud_a, "Tuition", "2026-08-01T00:00:00", admin_id),
    ).lastrowid
    inv_b = conn.execute(
        "INSERT INTO invoices (student_id, description, status, due_at, paid_at, created_by) "
        "VALUES (?, ?, 'paid', ?, ?, ?)",
        (stud_b, "Voice tuition", "2026-07-01T00:00:00", "2026-07-02T09:00:00", admin_id),
    ).lastrowid
    inv_c = conn.execute(
        "INSERT INTO invoices (student_id, description, status, due_at, created_by) "
        "VALUES (?, ?, 'sent', ?, ?)",
        (stud_c, "Theory materials", "2026-08-15T00:00:00", admin_id),
    ).lastrowid

    # ---------- invoice items (total = SUM(items); no stored total column) ----------
    conn.execute(
        "INSERT INTO invoice_items (invoice_id, description, amount_cents, source_type, source_id) "
        "VALUES (?, ?, ?, 'enrollment', ?)",
        (inv_a, "Beginner Piano", 12000, course_piano),
    )
    conn.execute(
        "INSERT INTO invoice_items (invoice_id, description, amount_cents, source_type) "
        "VALUES (?, ?, ?, 'manual')",
        (inv_b, "Intermediate Voice", 15000),
    )
    conn.execute(
        "INSERT INTO invoice_items (invoice_id, description, amount_cents, source_type) "
        "VALUES (?, ?, ?, 'manual')",
        (inv_c, "Sheet music bundle", 2500),
    )

    # ---------- practice logs (student self-service) ----------
    conn.execute(
        "INSERT INTO practice_logs (student_id, minutes, notes) VALUES (?, ?, ?)",
        (stud_a, 30, "Scales practice"),
    )
    conn.execute(
        "INSERT INTO practice_logs (student_id, minutes, notes) VALUES (?, ?, ?)",
        (stud_b, 45, "Warm-up exercises"),
    )

    # ---------- announcements (role-scoped audience) ----------
    conn.execute(
        "INSERT INTO announcements (author_id, title, body, audience) VALUES (?, ?, ?, 'all')",
        (admin_id, "Welcome", "Welcome to the studio.", ),
    )
    conn.execute(
        "INSERT INTO announcements (author_id, title, body, audience) VALUES (?, ?, ?, 'students')",
        (admin_id, "Recital sign-up", "Sign up for the summer recital.", ),
    )

    conn.commit()
