---
title: "Lesson-Studio Manager — Scale-Validation Swarm Vehicle"
type: feat
status: draft
date: 2026-07-09
swarm: true
agents: 30
namespace: studio/
origin: docs/brainstorms/2026-07-09-scale-validation-swarm-vehicle-brainstorm.md
feed_forward:
  risk: "The lessons (schedule) row is a 4-way FK seam (instructor + student + room + course) and is consumed by attendance + dashboard + search — the densest cross-boundary coupling in the spec. A single name/return-type mismatch there fails the schedule page AND the aggregates that read it. This is the deliberately-hardest seam, chosen to stress the contract machinery."
  verify_first: true
---

# Lesson-Studio Manager — Shared Interface Spec (Scale-Validation Vehicle)

A **throwaway** lesson-studio / community-music-school manager. Flask + SQLite (stdlib
`sqlite3`) + Jinja2 + Bootstrap 5. **~30-agent vertical swarm.** The app is disposable;
its purpose is to validate the governance stack (G1 firebreak, FC58 path-pin, 080-W5
compounded-darkness gate, G3 self-audit chain, Step 1.52 telemetry) live at ≥20-agent
scale, under maximum context pressure. Domain chosen to maximize coordination-seam
surface. (See brainstorm: `docs/brainstorms/2026-07-09-scale-validation-swarm-vehicle-brainstorm.md`.)

> **PLAN STATUS: `draft` — COMPLETE, convergence-ready (NOT launch-ready).** All sections
> are authored: App Config, Database Schema, Database Connection, Model Functions, Route
> Table, the six MANDATORY contract sections (Export Names, Cross-Boundary Wiring, Input
> Validation, Coordinated Behaviors, Transaction Contracts, Authorization Matrix), EARS
> Acceptance, and the Convergence Handoff (Codex prompt). Next: Codex P0 review → fixes →
> Alex's human structural pass → flip to `status: active` → launch. **Do NOT launch on a
> draft** — the convergence loop + human P0 gate are non-optional.

---

## Namespace & Build Convention (FC59 — MANDATORY)

ALL application code lives under the top-level **`studio/`** dir — never the shared
`app/`. Confirmed free of collision on master (2026-07-09). Layout:

```
studio/
  __init__.py              # app factory, config, blueprint registration (scaffold agent)
  database.py              # get_db, init_db, seed (database agent)
  schema.sql               # DDL + seed constants (database agent)
  auth.py                  # login_required / role_required / ownership helpers (auth-core agent)
  models/
    <entity>_models.py     # one file per model agent
  routes/
    <entity>.py            # one blueprint per route agent
  templates/
    base.html              # layout + nav (scaffold agent)
    <entity>/*.html        # owned by the entity's route agent
  static/                  # css (scaffold agent)
test_smoke.py              # top-level smoke suite (smoke-test agent) — imports `from studio import create_app`
```

---

## App Configuration (studio/__init__.py — scaffold agent owns this file)

- `create_app()` application factory. Reads `SECRET_KEY` from env; **fail-closed**: if
  `SECRET_KEY` is unset AND `FLASK_ENV != development`, raise at startup (no insecure
  default in prod). In development, fall back to a fixed dev key with a logged warning.
- Session cookie: `SESSION_COOKIE_HTTPONLY=True`, `SESSION_COOKIE_SAMESITE='Lax'`,
  `SESSION_COOKIE_SECURE` = `True` when `FLASK_ENV != development`.
- CSRF: a lightweight session-token scheme (mirror ShelfTrack run 080). `csrf_token()`
  injected into Jinja globals; every mutating form posts `_csrf`; a `before_request`
  validates it on POST/PUT/PATCH/DELETE and returns **400** on mismatch.
- Registers all blueprints (see Roster). Calls `init_db()` once if the DB file is absent.
- Injects `current_user` (dict or None) and `csrf_token` into the template context.

Deferred by design (throwaway vehicle — NOT production): password complexity beyond a
min length, rate limiting, HTTPS/HSTS enforcement, email verification.

---

## Database Schema (studio/schema.sql — database agent owns this file)

Stdlib `sqlite3`, `PRAGMA foreign_keys = ON` enforced per-connection in `database.py`.
All timestamps are ISO-8601 TEXT (UTC). Money is integer **cents** (never float).

```sql
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
```

**SEED DATA (database agent inserts in `init_db`):** 1 admin user
(`admin@studio.test` / `studiopass`), 2 instructor users + rows, 3 student users + rows,
3 rooms, 4 instruments, 3 courses, a handful of enrollments/lessons/invoices so the
smoke suite exercises real relationships (dynamic surface must be genuinely LIT, not
trivially green — see brainstorm Open Questions).

---

## Data Ownership (one file → exactly one agent; FC1/FC3 registry)

| File | Owning agent |
|------|--------------|
| `studio/__init__.py`, `studio/templates/base.html`, `studio/static/*` | scaffold |
| `studio/schema.sql`, `studio/database.py` | database |
| `studio/auth.py`, `studio/models/auth_models.py`, `studio/routes/auth.py`, `studio/templates/auth/*` | auth-core |
| `studio/models/<entity>_models.py` | that entity's **model** agent |
| `studio/routes/<entity>.py`, `studio/templates/<entity>/*` | that entity's **route** agent |
| `studio/models/audit_models.py` | audit (imported cross-boundary — read-only contract) |
| `studio/models/dashboard_models.py`, `studio/routes/dashboard.py`, `studio/templates/dashboard/*` | dashboard |
| `studio/models/search_models.py`, `studio/routes/search.py`, `studio/templates/search/*` | search |
| `test_smoke.py` | smoke-test |

**Cross-boundary write rule:** only `audit_models.record(...)` may be imported and called
across agent boundaries. No agent writes another agent's table directly; all writes go
through the owning entity's model functions.

---

## Agent Roster (~30 — resolves the brainstorm's open sizing question)

**Foundational (3):** scaffold · database · auth-core.

**Model agents (14)** — own `studio/models/*_models.py`:
student · instructor · room · instrument · course · enrollment · lesson · attendance ·
checkout · invoice · practice_log · announcement · audit · dashboard.

**Route/blueprint agents (11)** — own `studio/routes/*.py` + templates:
student · instructor · course · enrollment · lesson · instrument (incl. checkout actions) ·
attendance · invoice · practice_log · announcement · dashboard.
(room + search fold into scaffold and a dedicated search agent respectively — see below.)

**Cross-cutting (2):** search (models+routes+templates) · smoke-test.

**Total: 3 + 14 + 11 + 2 = 30 agents.**

> Sizing rationale (Key Decision #2, human override): 30 matches/exceeds the run-050
> record (31) to deliberately force pre-tail orchestrator saturation. Model/route split is
> the lever that lifts the count from film-PM's 16 to 30 while keeping each agent's surface
> small (one file, one concern) — which ALSO maximizes the cross-boundary seam count
> (every route agent imports its model agent's exports = 25 model→route seams, plus the
> audit + dashboard + search cross-entity seams).

---

## Cluster → Agent → Seam summary (for the contract-section passes)

| Cluster | Model agent | Route agent | Notable seams |
|---------|-------------|-------------|---------------|
| students | student_models | student routes | consumed by enrollment, lesson, attendance, checkout, invoice, practice_log, dashboard |
| instructors | instructor_models | instructor routes | consumed by course, lesson |
| rooms | room_models | (scaffold hosts /rooms CRUD) | consumed by lesson |
| instruments | instrument_models | instrument routes | checkout flips status (transaction) |
| courses | course_models | course routes | FK→instructor; consumed by enrollment, lesson |
| enrollments | enrollment_models | enrollment routes | FK→student+course; UNIQUE; may create invoice_item |
| lessons | lesson_models | lesson routes | **4-way FK** (instructor+student+room+course); read by attendance, dashboard, search |
| attendance | attendance_models | attendance routes | FK→lesson+student |
| checkouts | checkout_models | (instrument routes host checkout/return) | **transaction**: flips instrument.status |
| invoices | invoice_models | invoice routes | **multi-table transaction** (invoice+items); total = SUM(items) |
| practice_logs | practice_log_models | practice_log routes | **ownership auth** (student sees only own) |
| announcements | announcement_models | announcement routes | **role-scoped** audience visibility |
| audit | audit_models | (none — write-only lib) | imported by ALL mutating routes |
| dashboard | dashboard_models | dashboard routes | **aggregates** across students/lessons/invoices/attendance |
| search | search_models | search routes | **cross-entity** query over students/courses/instructors |

---

## Database Connection (studio/database.py — database agent owns this file)

- `get_db() -> sqlite3.Connection` — one connection per request via Flask `g`; sets
  `row_factory = sqlite3.Row` and `PRAGMA foreign_keys = ON`. Registered teardown closes it.
- `init_db() -> None` — executes `schema.sql`, then inserts seed rows. Idempotent guard:
  the app factory calls it only when the DB file does not already exist.
- `query(sql, params=(), one=False)` — thin helper returning `list[dict]` (or one `dict`/None).
- **Transaction helper:** `transaction()` — a context manager yielding the connection with
  `BEGIN IMMEDIATE`; commits on clean exit, rolls back on exception. Used by every
  multi-statement writer (checkout, invoice, enrollment→invoice_item).

All model functions convert `sqlite3.Row` → plain `dict` before returning (never leak Row
across a boundary — FC2). "Returns dict" below means a plain dict with the table's columns.

---

## Model Functions (full signatures — Export Names contract derives from these)

Convention: single-row getters return `dict | None`; listers return `list[dict]`; creators
return the new `int` id; mutators return `None`. Every writer **commits internally** unless
annotated `requires transaction()` (see Transaction Contracts). All writers call
`audit_models.record(...)` (the one sanctioned cross-boundary write).

### auth_models.py  (auth-core agent)
- `create_user(email, password, role, name) -> int` — hashes password (`werkzeug` or
  hashlib+salt); raises `ValueError('email exists')` on UNIQUE violation. commits.
- `get_user(user_id) -> dict | None`
- `get_user_by_email(email) -> dict | None`
- `verify_credentials(email, password) -> dict | None` — user dict if password matches, else None.

### studio/auth.py  (auth-core agent — decorators & session helpers, NOT a model)
- `login_user(user: dict) -> None` / `logout_user() -> None` — set/clear session.
- `current_user() -> dict | None` — the logged-in user row (cached on `g`).
- `current_student_id() -> int | None` — the `students.id` for a logged-in student user (via `students.user_id`).
- `login_required(view)` — 302→/auth/login when anonymous.
- `role_required(*roles)` — decorator; 403 when `current_user().role not in roles`.
- `require_self_or_staff(student_id)` — helper: True if admin/instructor, or student whose
  `current_student_id() == student_id`; else abort **404** (ownership hides existence, per run-080 IDOR lesson).

### student_models.py  (student model agent)
- `list_students(active_only=False, q=None) -> list[dict]` — `q` LIKE-matches name/email.
- `get_student(sid) -> dict | None`
- `create_student(first_name, last_name, email=None, phone=None, skill_level='beginner', user_id=None) -> int`
- `update_student(sid, **fields) -> None` — whitelist: first_name,last_name,email,phone,skill_level,notes.
- `set_student_active(sid, active) -> None` — soft deactivate.

### instructor_models.py  (instructor model agent)
- `list_instructors(active_only=False) -> list[dict]`
- `get_instructor(iid) -> dict | None`
- `create_instructor(first_name, last_name, email=None, phone=None, bio=None, hourly_rate_cents=0, user_id=None) -> int`
- `update_instructor(iid, **fields) -> None`
- `set_instructor_active(iid, active) -> None`

### room_models.py  (room model agent)
- `list_rooms(active_only=False) -> list[dict]`
- `get_room(rid) -> dict | None`
- `create_room(name, capacity=1, location=None) -> int`
- `update_room(rid, **fields) -> None`
- `set_room_active(rid, active) -> None`

### instrument_models.py  (instrument model agent)
- `list_instruments(status=None, q=None) -> list[dict]`
- `get_instrument(iid) -> dict | None`
- `create_instrument(name, category, serial_number=None, condition='good', notes=None) -> int`
- `update_instrument(iid, **fields) -> None`
- `set_instrument_status(iid, status) -> None` — called BY checkout_models inside a transaction (see Transaction Contracts). `requires transaction()` (does NOT commit).

### course_models.py  (course model agent)
- `list_courses(active_only=False, instructor_id=None) -> list[dict]` — joins instructor name.
- `get_course(cid) -> dict | None`
- `create_course(name, description=None, instructor_id=None, level='beginner', capacity=10, price_cents=0) -> int`
- `update_course(cid, **fields) -> None`
- `set_course_active(cid, active) -> None`
- `count_enrolled(cid) -> int` — active enrollments (capacity check helper).

### enrollment_models.py  (enrollment model agent)
- `list_enrollments(student_id=None, course_id=None, status=None) -> list[dict]` — joins student + course names.
- `get_enrollment(eid) -> dict | None`
- `enroll(student_id, course_id) -> int` — `requires transaction()`: inserts enrollment (UNIQUE guard → raises `ValueError('already enrolled')`), and if the course `price_cents > 0` inserts a matching `invoice_item` on the student's current draft invoice via `invoice_models.add_item_in_tx(...)`. See Transaction Contracts.
- `set_enrollment_status(eid, status) -> None` — commits.

### lesson_models.py  (lesson model agent — THE 4-way seam)
- `list_lessons(student_id=None, instructor_id=None, room_id=None, date_from=None, date_to=None, status=None) -> list[dict]` — joins instructor/student/room/course names.
- `get_lesson(lid) -> dict | None`
- `create_lesson(instructor_id, student_id, starts_at, ends_at, course_id=None, room_id=None, notes=None) -> int` — validates FKs exist + `ends_at > starts_at`; commits.
- `update_lesson(lid, **fields) -> None`
- `set_lesson_status(lid, status) -> None`
- `check_conflicts(instructor_id, room_id, starts_at, ends_at, exclude_lesson_id=None) -> list[dict]` — overlapping lessons for instructor OR room (coordinated behavior; used by lesson routes to warn).

### attendance_models.py  (attendance model agent)
- `list_attendance(lesson_id=None, student_id=None) -> list[dict]`
- `mark_attendance(lesson_id, student_id, present, marked_by) -> None` — UPSERT on UNIQUE(lesson_id,student_id); commits; audits.
- `attendance_rate(student_id) -> float` — present / total (dashboard aggregate helper).

### checkout_models.py  (checkout model agent — inventory transaction)
- `list_checkouts(student_id=None, status=None) -> list[dict]` — joins instrument + student.
- `get_checkout(cid) -> dict | None`
- `checkout_instrument(instrument_id, student_id, due_at) -> int` — `requires transaction()`: guards `instrument.status == 'available'` (else `ValueError`), inserts checkout row, calls `instrument_models.set_instrument_status(instrument_id, 'checked_out')`. Atomic. See Transaction Contracts.
- `return_instrument(checkout_id) -> None` — `requires transaction()`: sets `returned_at`, status='returned', flips instrument back to 'available'. Atomic.

### invoice_models.py  (invoice model agent — multi-table transaction)
- `list_invoices(student_id=None, status=None) -> list[dict]` — each row includes computed `total_cents = SUM(items)`.
- `get_invoice(iid) -> dict | None` — dict includes `items: list[dict]` and `total_cents`.
- `create_invoice(student_id, description=None, due_at=None, created_by=None) -> int` — commits; empty draft.
- `add_item(invoice_id, description, amount_cents, source_type='manual', source_id=None) -> int` — commits.
- `add_item_in_tx(conn, invoice_id, description, amount_cents, source_type, source_id) -> int` — `requires transaction()`: same insert on a caller-supplied connection (used by `enroll`). Does NOT commit.
- `get_or_create_draft_invoice_in_tx(conn, student_id, created_by) -> int` — `requires transaction()`.
- `set_invoice_status(iid, status) -> None` — commits; on 'paid' sets `paid_at`; audits.

### practice_log_models.py  (practice_log model agent — ownership-scoped)
- `list_practice_logs(student_id) -> list[dict]` — always student-scoped.
- `create_practice_log(student_id, minutes, notes=None) -> int` — commits.
- `delete_practice_log(log_id) -> None` — commits.
- `total_minutes(student_id, since=None) -> int` — dashboard aggregate helper.

### announcement_models.py  (announcement model agent — role-scoped)
- `list_for_role(role) -> list[dict]` — returns announcements whose `audience IN ('all', <role-bucket>)` (student→'students', instructor→'instructors', admin→all).
- `get_announcement(aid) -> dict | None`
- `create_announcement(author_id, title, body, audience='all') -> int` — commits; audits.
- `delete_announcement(aid) -> None` — commits.

### audit_models.py  (audit agent — WRITE-ONLY lib, imported by ALL mutating routes)
- `record(user_id, action, entity_type, entity_id=None, detail=None) -> None` — inserts one
  audit_log row; commits. **The ONLY function importable across agent boundaries.**
- `list_audit(entity_type=None, limit=200) -> list[dict]` — admin audit view.

### dashboard_models.py  (dashboard agent — cross-entity aggregates; READ-only)
- `admin_summary() -> dict` — counts: students, instructors, active courses, lessons_this_week, outstanding_invoice_cents, instruments_out.
- `instructor_summary(instructor_id) -> dict` — my upcoming lessons, my courses, my students count.
- `student_summary(student_id) -> dict` — my upcoming lessons, my enrollments, my balance_cents, my practice_minutes_this_week, my attendance_rate.
- Reads via imports from lesson/invoice/enrollment/attendance/practice_log models (see Cross-Boundary Wiring).

### search_models.py  (search agent — cross-entity)
- `search_all(q, role, actor_student_id=None) -> dict` — `{students:[...], instructors:[...], courses:[...]}`; results role-filtered (a student sees only self + public course catalog). LIKE-based.

---

## Route Table (blueprint · url_prefix · path · method · auth mode)

Auth modes: **public** · **auth** (any logged-in) · **role:<roles>** · **role+own** (role or
ownership) · **admin**. Full rules in the Authorization Matrix.

### auth  (/auth — auth-core)
| Method | Path | View | Auth |
|--------|------|------|------|
| GET/POST | /register | register | public |
| GET/POST | /login | login | public |
| POST | /logout | logout | auth |

### students  (/students — student route agent)
| GET | / | list_students | role:admin,instructor |
| GET/POST | /new | create_student | role:admin,instructor |
| GET | /<int:sid> | view_student | role+own |
| GET/POST | /<int:sid>/edit | edit_student | role:admin,instructor |
| POST | /<int:sid>/deactivate | deactivate_student | admin |

### instructors  (/instructors — instructor route agent)
| GET | / | list_instructors | role:admin,instructor |
| GET/POST | /new | create_instructor | admin |
| GET | /<int:iid> | view_instructor | role:admin,instructor |
| GET/POST | /<int:iid>/edit | edit_instructor | admin |

### rooms  (/rooms — scaffold agent hosts)
| GET | / | list_rooms | role:admin,instructor |
| GET/POST | /new | create_room | admin |
| GET/POST | /<int:rid>/edit | edit_room | admin |

### instruments  (/instruments — instrument route agent; hosts checkout actions)
| GET | / | list_instruments | role:admin,instructor |
| GET/POST | /new | create_instrument | admin |
| GET/POST | /<int:iid>/edit | edit_instrument | admin |
| GET | /checkouts | list_checkouts | role:admin,instructor |
| POST | /<int:iid>/checkout | checkout_instrument | role:admin,instructor |
| POST | /checkouts/<int:cid>/return | return_instrument | role:admin,instructor |

### courses  (/courses — course route agent)
| GET | / | list_courses | auth |
| GET/POST | /new | create_course | role:admin,instructor |
| GET | /<int:cid> | view_course | auth |
| GET/POST | /<int:cid>/edit | edit_course | role:admin,instructor |

### enrollments  (/enrollments — enrollment route agent)
| GET | / | list_enrollments | role:admin,instructor |
| POST | /enroll | enroll (student_id, course_id) | role:admin,instructor |
| POST | /<int:eid>/withdraw | withdraw | role:admin,instructor |

### lessons  (/lessons — lesson route agent)
| GET | / | list_lessons (filters) | role+own |
| GET/POST | /new | create_lesson | role:admin,instructor |
| GET | /<int:lid> | view_lesson | role+own |
| GET/POST | /<int:lid>/edit | edit_lesson | role:admin,instructor |
| POST | /<int:lid>/status | set_status | role:admin,instructor |

### attendance  (/attendance — attendance route agent)
| GET | /lesson/<int:lid> | lesson_attendance | role:admin,instructor |
| POST | /lesson/<int:lid>/mark | mark_attendance | role:admin,instructor |

### invoices  (/invoices — invoice route agent)
| GET | / | list_invoices | role:admin,instructor |
| GET/POST | /new | create_invoice | role:admin,instructor |
| GET | /<int:iid> | view_invoice | role+own |
| POST | /<int:iid>/items | add_item | role:admin,instructor |
| POST | /<int:iid>/status | set_status | role:admin,instructor |

### practice  (/practice — practice_log route agent)
| GET | / | my_logs (or ?student_id for staff) | role+own |
| POST | /new | create_log | role+own |
| POST | /<int:log_id>/delete | delete_log | role+own |

### announcements  (/announcements — announcement route agent)
| GET | / | list_announcements (role-scoped) | auth |
| GET/POST | /new | create_announcement | role:admin,instructor |
| POST | /<int:aid>/delete | delete_announcement | role:admin,instructor |

### dashboard  (/ and /dashboard — dashboard route agent)
| GET | / | index (role-dispatched summary) | auth |
| GET | /dashboard/audit | audit_log_view | admin |

### search  (/search — search route agent)
| GET | / | search (q) | auth |

## 1. Export Names Table (every symbol crossing an agent boundary)

Model↔route is an **agent boundary** (separate agents own `models/X_models.py` vs
`routes/X.py`), so every model function a route calls is a cross-boundary export. Full
signatures are authoritative here (Model Functions section is the prose companion).

### 1a. Infrastructure exports
| Name | Type | Defined By | Used By | Full Signature |
|------|------|-----------|---------|----------------|
| `get_db` | function | studio/database.py | ALL agents | `get_db() -> sqlite3.Connection` |
| `query` | function | studio/database.py | ALL model agents | `query(sql, params=(), one=False) -> list[dict] | dict | None` |
| `transaction` | context mgr | studio/database.py | checkout, invoice, enrollment models | `transaction() -> ContextManager[sqlite3.Connection]` |
| `init_db` | function | studio/database.py | scaffold (__init__) | `init_db() -> None` |
| `login_required` | decorator | studio/auth.py | ALL route agents | `login_required(view) -> view` |
| `role_required` | decorator | studio/auth.py | ALL route agents | `role_required(*roles) -> Callable[[view], view]` |
| `current_user` | function | studio/auth.py | ALL route agents + base.html | `current_user() -> dict | None` |
| `current_student_id` | function | studio/auth.py | lesson/invoice/practice routes | `current_student_id() -> int | None` |
| `require_self_or_staff` | function | studio/auth.py | student/lesson/invoice/practice routes | `require_self_or_staff(student_id) -> None  # aborts 404 if unauthorized` |
| `login_user` / `logout_user` | function | studio/auth.py | auth routes | `login_user(user: dict) -> None` / `logout_user() -> None` |
| `record` | function | studio/models/audit_models.py | ALL mutating route agents | `record(user_id, action, entity_type, entity_id=None, detail=None) -> None` |

### 1b. Model-function exports (consumed by the entity's route agent + aggregators)
Every function listed in **Model Functions** above is a cross-boundary export with the
signature given there. Summarized by owner (full signatures = as declared in Model Functions):
auth_models (create_user, get_user, get_user_by_email, verify_credentials) ·
student_models (list_students, get_student, create_student, update_student, set_student_active) ·
instructor_models (list/get/create/update/set_active) · room_models (list/get/create/update/set_active) ·
instrument_models (list/get/create/update, set_instrument_status) · course_models (list/get/create/update/set_active, count_enrolled) ·
enrollment_models (list_enrollments, get_enrollment, enroll, set_enrollment_status) ·
lesson_models (list_lessons, get_lesson, create_lesson, update_lesson, set_lesson_status, check_conflicts) ·
attendance_models (list_attendance, mark_attendance, attendance_rate) ·
checkout_models (list_checkouts, get_checkout, checkout_instrument, return_instrument) ·
invoice_models (list_invoices, get_invoice, create_invoice, add_item, add_item_in_tx, get_or_create_draft_invoice_in_tx, set_invoice_status) ·
practice_log_models (list_practice_logs, create_practice_log, delete_practice_log, total_minutes) ·
announcement_models (list_for_role, get_announcement, create_announcement, delete_announcement) ·
dashboard_models (admin_summary, instructor_summary, student_summary) ·
search_models (search_all).

### 1c. Blueprints & route paths
Blueprint names = the entity name (`students`, `instructors`, `rooms`, `instruments`,
`courses`, `enrollments`, `lessons`, `attendance`, `invoices`, `practice`,
`announcements`, `dashboard`, `search`, `auth`). Registered in `studio/__init__.py` with
the url_prefixes in the Route Table. `url_for` targets: `<blueprint>.<view>` (e.g.
`students.view_student`, `dashboard.index`).

### 1d. Orchestration entrypoints (FC50 — route→non-model & model→model calls crossing a boundary)
| Name | Type | Defined By | Used By | Full Signature |
|------|------|-----------|---------|----------------|
| `audit_models.record` | orchestration entrypoint | audit_models.py | every mutating view | `record(user_id, action, entity_type, entity_id=None, detail=None) -> None` |
| `invoice_models.add_item_in_tx` | orchestration entrypoint | invoice_models.py | enrollment_models.enroll | `add_item_in_tx(conn, invoice_id, description, amount_cents, source_type, source_id) -> int` |
| `invoice_models.get_or_create_draft_invoice_in_tx` | orchestration entrypoint | invoice_models.py | enrollment_models.enroll | `get_or_create_draft_invoice_in_tx(conn, student_id, created_by) -> int` |
| `instrument_models.set_instrument_status` | orchestration entrypoint | instrument_models.py | checkout_models.checkout_instrument / return_instrument | `set_instrument_status(iid, status) -> None  # requires transaction()` |
| `dashboard_models.*_summary` | orchestration entrypoint | dashboard_models.py | dashboard.index | `admin_summary() -> dict` / `instructor_summary(instructor_id) -> dict` / `student_summary(student_id) -> dict` |
| `lesson_models.check_conflicts` | orchestration entrypoint | lesson_models.py | lessons.create_lesson/edit_lesson | `check_conflicts(instructor_id, room_id, starts_at, ends_at, exclude_lesson_id=None) -> list[dict]` |
| `search_models.search_all` | orchestration entrypoint | search_models.py | search.search | `search_all(q, role, actor_student_id=None) -> dict` |

---

## 2. Cross-Boundary Wiring Table (producer file → consumer file → import)

| Producer | Consumer | Import |
|----------|----------|--------|
| studio/database.py | every model | `from studio.database import get_db, query, transaction` |
| studio/auth.py | every route | `from studio.auth import login_required, role_required, current_user, current_student_id, require_self_or_staff` |
| studio/models/audit_models.py | every mutating route | `from studio.models.audit_models import record` |
| studio/models/student_models.py | routes/students.py, routes/lessons.py, routes/invoices.py, routes/enrollments.py, dashboard_models.py, search_models.py | `from studio.models.student_models import ...` |
| studio/models/instructor_models.py | routes/instructors.py, routes/courses.py, routes/lessons.py, search_models.py | `from studio.models.instructor_models import ...` |
| studio/models/room_models.py | routes/rooms.py (scaffold), routes/lessons.py | `from studio.models.room_models import ...` |
| studio/models/course_models.py | routes/courses.py, routes/enrollments.py, routes/lessons.py, search_models.py | `from studio.models.course_models import ...` |
| studio/models/enrollment_models.py | routes/enrollments.py | `from studio.models.enrollment_models import ...` |
| studio/models/invoice_models.py | routes/invoices.py, **enrollment_models.py** | `from studio.models.invoice_models import add_item_in_tx, get_or_create_draft_invoice_in_tx` |
| studio/models/instrument_models.py | routes/instruments.py, **checkout_models.py** | `from studio.models.instrument_models import set_instrument_status` |
| studio/models/checkout_models.py | routes/instruments.py | `from studio.models.checkout_models import ...` |
| studio/models/lesson_models.py | routes/lessons.py, routes/attendance.py, dashboard_models.py | `from studio.models.lesson_models import ...` |
| studio/models/attendance_models.py | routes/attendance.py, dashboard_models.py | `from studio.models.attendance_models import ...` |
| studio/models/practice_log_models.py | routes/practice.py, dashboard_models.py | `from studio.models.practice_log_models import ...` |
| studio/models/announcement_models.py | routes/announcements.py | `from studio.models.announcement_models import ...` |
| studio/models/dashboard_models.py | routes/dashboard.py | `from studio.models.dashboard_models import admin_summary, instructor_summary, student_summary` |
| studio/models/search_models.py | routes/search.py | `from studio.models.search_models import search_all` |

**Densest coupling (Feed-Forward risk):** `dashboard_models.py` imports FIVE model
modules (lesson, invoice, enrollment, attendance, practice_log); `lessons.py` imports
FOUR (instructor, student, room, course) for its FK dropdowns + create validation.

---

## 3. Input Validation Prescriptions (every mutating route)

| Route | Input | Validation | Error Response |
|-------|-------|-----------|----------------|
| POST /auth/register | email, password, name, role | email non-empty + `@`; password ≥ 8; role ∈ {student,instructor,admin} (first user forced admin) | 400 + flash; re-render form |
| POST /auth/login | email, password | both non-empty | 401 + "invalid credentials" (no field leak) |
| POST /students/new, /edit | first_name, last_name, email?, skill_level | names non-empty; skill_level ∈ enum | 400 + re-render |
| POST /instructors/new, /edit | first_name, last_name, hourly_rate_cents? | names non-empty; rate ≥ 0 int | 400 + re-render |
| POST /rooms/new, /edit | name, capacity | name non-empty; capacity ≥ 1 int | 400 |
| POST /instruments/new, /edit | name, category, condition | name+category non-empty; condition ∈ enum | 400 |
| POST /instruments/<iid>/checkout | student_id, due_at | student exists; instrument.status=='available'; due_at future ISO | 400 + flash "instrument unavailable" |
| POST /instruments/checkouts/<cid>/return | (cid path) | checkout exists + status=='out' | 404 / 400 |
| POST /courses/new, /edit | name, level, capacity, price_cents, instructor_id? | name non-empty; level ∈ enum; capacity ≥ 1; price ≥ 0; instructor exists if given | 400 |
| POST /enrollments/enroll | student_id, course_id | both exist; not already enrolled (UNIQUE); course active + under capacity | 400 + flash "already enrolled / full" |
| POST /enrollments/<eid>/withdraw | (eid path) | enrollment exists | 404 |
| POST /lessons/new, /edit | instructor_id, student_id, starts_at, ends_at, room_id?, course_id? | FKs exist; `ends_at > starts_at`; ISO datetimes | 400 + re-render; conflicts → warn flash (non-blocking) |
| POST /lessons/<lid>/status | status | status ∈ enum | 400 |
| POST /attendance/lesson/<lid>/mark | student_id[], present[] | lesson exists; each student enrolled/scheduled | 400 |
| POST /invoices/new | student_id, description?, due_at? | student exists | 400 |
| POST /invoices/<iid>/items | description, amount_cents, source_type | description non-empty; amount_cents int (may be negative for credit); source_type ∈ enum | 400 |
| POST /invoices/<iid>/status | status | status ∈ enum; 'paid' sets paid_at | 400 |
| POST /practice/new | minutes, notes? | minutes int > 0 | 400 |
| POST /practice/<log_id>/delete | (path) | log exists AND belongs to actor (or staff) | 404 |
| POST /announcements/new | title, body, audience | title+body non-empty; audience ∈ enum | 400 |
| POST /announcements/<aid>/delete | (path) | announcement exists | 404 |

**Global:** every POST/PUT/PATCH/DELETE also validates the `_csrf` session token → **400**
on mismatch (before_request, scaffold). Typed URL params (`<int:...>`) → Flask 404 on
non-int. Unknown row id on any GET detail → 404.

---

## 4. Coordinated Behaviors (must be consistent across all ~30 agents)

- **Blueprint registration:** all blueprints registered in `studio/__init__.py` in a fixed
  order (auth, dashboard, students, instructors, rooms, instruments, courses, enrollments,
  lessons, attendance, invoices, practice, announcements, search). Each route agent exposes
  `bp = Blueprint('<name>', __name__, url_prefix='/<name>')`.
- **Base template:** every page `{% extends "base.html" %}`; base owns the nav, flash
  rendering, and `{{ csrf_token() }}` availability.
- **Role-aware nav (base.html, scaffold):** admin sees all links; instructor sees
  students/courses/lessons/attendance/instruments/announcements/dashboard; student sees
  dashboard/my-lessons/my-practice/my-invoices/courses/announcements. Driven by
  `current_user().role`.
- **Flash categories:** `success` (green), `error` (red), `warning` (amber). One convention
  repo-wide.
- **CSRF:** every `<form method="post">` includes `<input type="hidden" name="_csrf" value="{{ csrf_token() }}">`.
- **Money formatting:** a shared Jinja filter `cents` (`{{ x|cents }}` → `$12.50`), registered by scaffold.
- **Datetime:** stored ISO-8601; displayed via a shared `dt` filter.
- **FK dropdowns:** create/edit forms populate select options by calling the relevant
  `list_*` model function in the view and passing to the template (never a cross-agent
  template include).
- **Audit:** every create/update/delete/checkout/return/pay view calls `audit_models.record(...)` after the successful mutation.

---

## 5. Transaction Contracts (every DB writer annotated)

**Commit internally (single-statement or self-contained):** all `create_*`, `update_*`,
`set_*_active`, `set_*_status` (except `set_instrument_status`), `mark_attendance`,
`create_practice_log`, `delete_practice_log`, `create_announcement`, `delete_announcement`,
`create_invoice`, `add_item`, `record`.

**`requires transaction()` (BEGIN IMMEDIATE; caller owns commit/rollback):**
- `checkout_models.checkout_instrument(...)` — guard availability + insert checkout +
  `instrument_models.set_instrument_status(iid,'checked_out')` — **atomic**; rolls back both on failure.
- `checkout_models.return_instrument(...)` — set returned + flip instrument to 'available' — **atomic**.
- `enrollment_models.enroll(...)` — insert enrollment + (if priced)
  `invoice_models.get_or_create_draft_invoice_in_tx` + `add_item_in_tx` — **atomic**; a
  UNIQUE violation rolls back the whole unit (no orphan invoice_item).
- `instrument_models.set_instrument_status(...)`, `invoice_models.add_item_in_tx(...)`,
  `invoice_models.get_or_create_draft_invoice_in_tx(...)` — **do NOT commit** (operate on the
  caller's connection inside the enclosing `transaction()`).

**Invariant:** the invoice total is always `SUM(invoice_items.amount_cents)` computed at
read time — never a stored column — so a partially-applied item write can never desync a
persisted total.

---

## 6. Authorization Matrix (every protected route)

| Route | Mode | Rule |
|-------|------|------|
| /auth/register, /auth/login | public | anonymous allowed; authenticated → redirect to / |
| /auth/logout | auth | any logged-in |
| / , /dashboard | auth | content dispatched by role (admin/instructor/student summary) |
| /students (list, new, edit) | role:admin,instructor | staff manage students |
| /students/<sid> (view) | role+own | admin/instructor OR the student themselves; else **404** |
| /students/<sid>/deactivate | admin | admin only |
| /instructors (list, view) | role:admin,instructor | staff |
| /instructors/new, /edit | admin | admin only |
| /rooms/* | role:admin,instructor (view), admin (write) | |
| /instruments (list, checkouts) | role:admin,instructor | |
| /instruments/new,/edit | admin | |
| /instruments/<iid>/checkout, /return | role:admin,instructor | staff perform checkouts |
| /courses (list, view) | auth | any logged-in may browse catalog |
| /courses/new, /edit | role:admin,instructor | |
| /enrollments/* | role:admin,instructor | staff enroll/withdraw |
| /lessons (list, view) | role+own | staff see all; student sees only lessons where `student_id == current_student_id()`; else filtered/404 |
| /lessons/new, /edit, /status | role:admin,instructor | |
| /attendance/* | role:admin,instructor | staff mark |
| /invoices (list, new, items, status) | role:admin,instructor | staff billing |
| /invoices/<iid> (view) | role+own | staff OR the invoice's student; else **404** |
| /practice (list, new, delete) | role+own | student operates on OWN logs; staff may view a student's logs via `?student_id` |
| /announcements (list) | auth | role-scoped audience filter |
| /announcements/new, /delete | role:admin,instructor | |
| /dashboard/audit | admin | admin-only audit log |
| /search | auth | results role-filtered (student sees only self + public catalog) |

**404-not-403 rule (run-080 IDOR lesson):** every `role+own` violation returns 404 (hide
existence), enforced by ownership-scoped queries + `require_self_or_staff`, not post-fetch
conditionals.

## Acceptance Tests (EARS)

Verified primarily by `test_smoke.py` (imports `from studio import create_app`, uses a
throwaway temp DB), with representative `curl` for the HTTP-status criteria.

### Happy Path
- WHEN a new user registers with a valid email + password (≥8) THE SYSTEM SHALL create the user and redirect (302) to /auth/login.
  - Verify: `curl -si -d 'email=a@b.co&password=studiopass&name=A&role=student&_csrf=$T' localhost:5000/auth/register | head -1` → `302`.
- WHEN valid credentials are submitted THE SYSTEM SHALL establish a session and redirect (302) to `/`.
- WHEN an admin creates a student THE SYSTEM SHALL persist it and list it at GET /students.
- WHEN a staff user checks out an `available` instrument THE SYSTEM SHALL create a checkout row AND set that instrument's status to `checked_out` **in one transaction**.
  - Verify (smoke): after checkout, `get_instrument(iid)['status'] == 'checked_out'` AND a `checkouts` row exists.
- WHEN a staff user enrolls a student in a priced course THE SYSTEM SHALL create the enrollment AND a matching `invoice_item` on the student's draft invoice **atomically**.
- WHEN a student logs practice minutes THE SYSTEM SHALL store the log under their own `student_id`.
- WHEN `/dashboard` loads THE SYSTEM SHALL render the summary for the caller's role (admin/instructor/student).
- WHEN an invoice is viewed THE SYSTEM SHALL display `total = SUM(invoice_items.amount_cents)`.

### Error Cases
- WHEN a student requests another student's GET /students/<sid> THE SYSTEM SHALL return **404** (not 403 — hide existence).
  - Verify: `curl -si -b studentB.cookie localhost:5000/students/<A_id> | head -1` → `404`.
- WHEN a student requests another student's GET /invoices/<iid> THE SYSTEM SHALL return **404**.
- WHEN a student POSTs to /instructors/new THE SYSTEM SHALL return **403**.
- WHEN a checkout is attempted on a non-`available` instrument THE SYSTEM SHALL return **400**, create NO checkout row, AND leave the instrument status unchanged (transaction rolled back).
- WHEN a student already enrolled is re-enrolled THE SYSTEM SHALL return **400** and create NO `invoice_item` (whole unit rolled back).
- WHEN a mutating POST omits/mismatches `_csrf` THE SYSTEM SHALL return **400**.
- WHEN `SECRET_KEY` is unset and `FLASK_ENV != development` THE SYSTEM SHALL refuse to start.
  - Verify (smoke): `create_app()` with no SECRET_KEY + `FLASK_ENV=production` raises.
- WHEN a lesson is created with `ends_at <= starts_at` THE SYSTEM SHALL return **400**.

### Verification Commands
- `python3 test_smoke.py` — full happy-path + IDOR-404 + transaction-atomicity + CSRF + SECRET_KEY suite (must PASS; this is the dynamic surface that keeps the 080-W5 compounded-darkness gate LIT).
- `python3 -c "import ast,glob;[ast.parse(open(f).read()) for f in glob.glob('studio/**/*.py',recursive=True)]"` — parse check (run as a file, per Bash rules).
- Contract check (Step 9w.9) + ownership gate (Step 16w) are enforced by the swarm pipeline.

---

## Scale-Validation Acceptance (the REAL deliverable — ties to the validate-at-scale plan)

Beyond the app EARS, this run's success is judged against
`docs/plans/2026-07-07-chore-validate-orchestrator-context-telemetry-at-scale-plan.md`:
- **≥20 agents actually spawned** (target ~30). A run that collapses the roster to <20 agents does not validate scale.
- **`context-telemetry.md` has a complete boundary row at every Step 1.52 checkpoint.** A MISSING row = instrument FAILURE (harden trigger), NOT a pass.
- **Firebreak:** every pinned pipeline script (incl. `tools/check_compounded_darkness.py`) runs clean under the active tail firebreak; RED probe blocked; positive-control self-validates.
- **080-W5 gate** emits a legible STATUS (OK, or COMPOUNDED_DARKNESS disposed by self-audit).
- **Honest status:** PIPELINE_PASS vs PIPELINE_PASS_WITH_DEFERRED_RISK adjudicated by the self-audit; a survived-at-30 run is reported as *resilience confirmed, death path attempted-not-reproduced* (per brainstorm Feed-Forward).

---

## Feed-Forward (plan-level)

- **Hardest decision:** whether to route the enroll→invoice coupling through a shared
  `transaction()` (cross-model, cross-agent) or keep enrollment and billing fully
  independent. Chose the shared transaction *because* the coupling is the point — it
  manufactures a real multi-agent Transaction Contract (enrollment_models calling
  invoice_models inside one BEGIN IMMEDIATE), which is exactly the seam the governance
  machinery should be stressed on. Independent tables would be simpler but a weaker test.
- **Rejected alternatives:** (a) a stored `invoices.total_cents` column — simpler, but no
  multi-table-consistency seam and a drift risk; (b) letting each route write its own audit
  rows inline — rejected for the single sanctioned cross-boundary `audit_models.record`;
  (c) collapsing model+route per entity into one agent — would drop the count below 20 and
  erase the 25 model→route seams that are the test's substance.
- **Least confident:** whether ~30 parallel worker briefs derived from this spec stay
  internally consistent through the swarm without a cross-section P0 slipping past the
  spec-completeness-checker. The 4-way `lessons` seam and the enroll→invoice transaction are
  the two places a name/return-shape drift would bite hardest. **This is precisely what the
  convergence loop (Codex + human P0 pass) must scrutinize first** (verify_first).

---

## Convergence Handoff (next phase — Plan Review)

This spec is a **complete draft, convergence-ready** — all six mandatory contract sections,
Model Functions, Route Table, and EARS are present. It is NOT yet launch-ready.

**Codex review prompt (paste to Codex, fresh context):**
> Review `docs/plans/2026-07-09-feat-lesson-studio-scale-validation-plan.md`, a ~30-agent
> Flask/SQLite swarm spec. Hunt specifically for **cross-section contradictions (P0s)**:
> (1) any model-function signature in §Model Functions that disagrees with its row in the
> §Export Names Table or its use in §Cross-Boundary Wiring; (2) any route in the §Route
> Table missing from the §Authorization Matrix or §Input Validation (or vice-versa);
> (3) any writer whose §Transaction Contracts annotation contradicts its Model-Functions
> signature (esp. the `requires transaction()` set); (4) any FK in §Database Schema with no
> owning model function; (5) any `url_for` target or blueprint name that won't resolve.
> Report P0s only; each section is internally plausible — the risk is incompatibility
> ACROSS sections.

Then: apply Codex fixes → **human P0 structural pass (Alex — non-optional cross-section
field-matching)** → flip `status: draft`→`active` → launch as the next run-id via autopilot
swarm (`dangerouslySkipPermissions` already set; inject agent-pitfalls per CLAUDE.md; copy
BUILD_TRACKING template).
