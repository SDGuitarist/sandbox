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
  risk: "The lessons (schedule) row is a 4-way FK seam (instructor + student + room + course) and is consumed by lesson routes + attendance + dashboard — the densest cross-boundary coupling in the spec. A single name/return-type mismatch there fails the schedule page AND the aggregates that read it. This is the deliberately-hardest seam, chosen to stress the contract machinery. (Search deliberately does NOT read lessons — private-record leakage; see search_models scope boundary.)"
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
```

**SEED DATA (database agent inserts in `init_db`):** 1 admin user
(`admin@studio.test` / `studiopass`), 2 instructor users + rows, 3 student users + rows,
3 rooms, 4 instruments, 3 courses, a handful of enrollments/lessons/invoices so the
smoke suite exercises real relationships (dynamic surface must be genuinely LIT, not
trivially green — see brainstorm Open Questions).
**Seed invoice statuses MUST respect `ux_one_draft_per_student`:** seed **at most ONE
`draft` invoice per student** (give student A one `draft`, student B one `paid`, student C
one `sent`) — never two drafts for the same student, or `init_db` fails on the partial
unique index. Every seeded row must satisfy all NOT NULL / CHECK / UNIQUE constraints
(roles ∈ enum, `ends_at > starts_at` on lessons, unique enrollment pairs, instrument status
consistent with any seeded checkout).

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

**Cross-boundary write rule:** no agent writes another agent's table with raw SQL; every
cross-agent write goes through the *owning* agent's model function. Reads may import any
model's getters freely (see §2). The sanctioned cross-agent WRITE calls are exactly four:
`audit_models.record` (post-commit, route-level), and the three in-tx helpers threaded on a
caller `conn` — `instrument_models.set_instrument_status` (from checkout_models),
`invoice_models.add_item_in_tx` + `get_or_create_draft_invoice_in_tx` (from enrollment_models).
No others.

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
| lessons | lesson_models | lesson routes | **4-way FK** (instructor+student+room+course); read by attendance, dashboard (NOT search — private records) |
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
- **Transaction helper:** `transaction()` — a context manager that wraps the **single
  `get_db()` request connection** (one connection per request, cached on `g`) with
  `BEGIN IMMEDIATE`; commits on clean exit, rolls back on exception. Because it is the SAME
  connection every model function uses, any read done DURING the transaction (e.g.
  `count_enrolled`, `get_course` inside `enroll`) sees the transaction's own uncommitted
  writes — so the in-tx capacity/active/availability guards are consistent. `BEGIN IMMEDIATE`
  takes the write lock up front, so two concurrent class-B transactions on separate requests
  serialize (the second blocks, then re-reads current state) — no lost-update / double-book.
  Nested `transaction()` is forbidden (a class-B writer never calls another class-B writer).

All model functions convert `sqlite3.Row` → plain `dict` before returning (never leak Row
across a boundary — FC2). "Returns dict" below means a plain dict with the table's columns.

---

## Model Functions (full signatures — Export Names contract derives from these)

Convention: single-row getters return `dict | None`; listers return `list[dict]`; creators
return the new `int` id; mutators return `None`. Every writer **commits internally** unless
it is one of the three self-contained atomic units that own a `transaction()` internally
(`checkout_instrument`, `return_instrument`, `enroll`) or an in-tx helper that takes a
caller `conn` and does NOT commit (`set_instrument_status`, `add_item_in_tx`,
`get_or_create_draft_invoice_in_tx`) — see Transaction Contracts.

**Audit rule (Codex fix — audit can NEVER commit inside a transaction):** model writers do
NOT call `audit_models.record`. The **route** calls `audit_models.record(...)` exactly once,
**after** the model mutation has returned and committed. So the audit insert is always a
separate post-commit statement, never nested inside the checkout/return/enroll transaction.

### auth_models.py  (auth-core agent)
- `create_user(email, password, role, name) -> int` — hashes password (`werkzeug` or
  hashlib+salt); raises `ValueError('email exists')` on UNIQUE violation. commits.
- `get_user(user_id) -> dict | None`
- `get_user_by_email(email) -> dict | None`
- `verify_credentials(email, password) -> dict | None` — user dict if password matches, else None.

### studio/auth.py  (auth-core agent — decorators & session helpers, NOT a model)
- `login_user(user: dict) -> None` / `logout_user() -> None` — set/clear session.
- `current_user() -> dict | None` — the logged-in user row (cached on `g`).
- `current_student_id() -> int | None` — the `students.id` for a logged-in student user (via `students.user_id`); None for staff/admin. **Direct `get_db()` query — no entity-model import (keeps foundational auth.py free of model coupling).**
- `current_instructor_id() -> int | None` — the `instructors.id` for a logged-in instructor user (via `instructors.user_id`); None for admin/student; direct `get_db()` query. **Identity mapping for instructor-scoped views (dashboard, "my students/lessons").**
- `login_required(view)` — 302→/auth/login when anonymous.
- `role_required(*roles)` — decorator; 403 when `current_user().role not in roles`.

**Ownership-Scoped Getter Contract (UNIFORM across all 4 owning agents — student, lesson,
invoice, practice; run-080 IDOR lesson).** To prevent per-agent drift (FC5), every
ownership-scoped getter obeys the SAME actor-based SQL-predicate rule:

- Signature: `get_<x>_for(<id>, actor) -> dict | None` and `list_<x>_for(actor, **filters) -> list[dict]`. `actor` is the `current_user()` dict (`{id, role, ...}`), always the trailing arg on getters.
- The ownership check is a **SQL WHERE predicate in the query itself**, never a fetch-then-compare in Python. The predicate is exactly:
  - `actor['role'] == 'admin'` → **no ownership restriction** (admin sees all);
  - `actor['role'] == 'instructor'` → **no restriction for student-owned entities** (students, invoices, practice logs — an instructor is staff over those). **Lessons are the ONE exception:** a lesson has BOTH a student and an instructor owner, so for `list_lessons_for`/`get_lesson_for` an instructor is scoped to `instructor_id = (SELECT id FROM instructors WHERE user_id = :actor_id)` (an instructor sees only THEIR OWN lessons, not every lesson). Admin still sees all.
  - `actor['role'] == 'student'` → restrict to rows whose `student_id = (SELECT id FROM students WHERE user_id = :actor_id)`.
- A non-owner therefore gets **0 rows → `None`/`[]`**; the route does `row = get_<x>_for(...) or abort(404)`. No 403, no existence leak.

> **Instructor-scope note:** the instructor exception applies ONLY to lessons (dual-owner
> entity). For students / invoices / practice-logs, instructors are full staff (see all).
> This is the single asymmetry in the contract — called out here so the four owning agents
> don't diverge on it.

`require_self_or_staff(student_id) -> None` remains only as a pre-write guard on `role+own`
POST routes (abort 404 if a student's supplied `student_id` isn't their own); all `role+own`
**reads** go through the `*_for` getters below.

### student_models.py  (student model agent)
- `list_students(active_only=False, q=None) -> list[dict]` — `q` LIKE-matches name/email.
- `get_student(sid) -> dict | None` — unscoped (staff-only callers).
- `get_student_for(sid, actor) -> dict | None` — **Ownership-Scoped Getter Contract**. The
  students table is the ownership root, so the predicate specializes to: `WHERE students.id = :sid
  AND (:staff OR students.user_id = :actor_id)`. Non-owner → `None`. `/students/<sid>` → `abort(404)`.
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
- `update_instrument(iid, **fields) -> None` — whitelist incl. `status` (admin maintenance toggle, standalone; commits internally).
- `set_instrument_status(conn, iid, status) -> None` — writes on the **caller-supplied** connection; **does NOT commit**. Called ONLY by checkout_models inside its transaction (see Transaction Contracts). Distinct from `update_instrument` (which commits).

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
- `enroll(student_id, course_id, created_by) -> int` — **OWNS one `transaction()` internally** (`with transaction() as conn`, one atomic unit). **All guards run INSIDE the BEGIN IMMEDIATE** (no route-level pre-check is authoritative — avoids TOCTOU): (1) re-read the course on `conn` and require `course['active'] == 1` (else `ValueError('course inactive')`) — a concurrent deactivation can't slip through; (2) capacity — `count_enrolled(course_id) < course['capacity']` (else `ValueError('course full')`); (3) insert the enrollment, relying on the DB `UNIQUE(student_id,course_id)` → `ValueError('already enrolled')` on conflict. If `course.price_cents > 0`, thread the SAME `conn` through `get_or_create_draft_invoice_in_tx(conn, student_id, created_by)` then `add_item_in_tx(conn, invoice_id, description=course['name'], amount_cents=course['price_cents'], source_type='enrollment', source_id=<new enrollment id>)`. Any failure rolls back the whole unit — no orphan invoice_item, no over-capacity enrollment. **Does NOT audit** (route audits post-commit). See Transaction Contracts.
- `set_enrollment_status(eid, status) -> None` — commits.

### lesson_models.py  (lesson model agent — THE 4-way seam)
- `list_lessons(student_id=None, instructor_id=None, room_id=None, date_from=None, date_to=None, status=None) -> list[dict]` — joins instructor/student/room/course names (unscoped; staff callers).
- `list_lessons_for(actor, **filters) -> list[dict]` — **Ownership-Scoped Getter Contract** (extended for the instructor role, since a lesson has both a student and an instructor owner): admin → all (honoring `filters`); student → predicate `student_id = (SELECT id FROM students WHERE user_id=:actor_id)`; instructor → predicate `instructor_id = (SELECT id FROM instructors WHERE user_id=:actor_id)`. Applied in SQL. `/lessons` list uses this.
- `get_lesson(lid) -> dict | None` — unscoped (staff callers).
- `get_lesson_for(lid, actor) -> dict | None` — **Ownership-Scoped Getter Contract** (student OR instructor owner): `WHERE lessons.id = :lid AND (:admin OR student_id = <actor student> OR instructor_id = <actor instructor>)`; else `None`. `/lessons/<lid>` → `abort(404)`.
- `create_lesson(instructor_id, student_id, starts_at, ends_at, course_id=None, room_id=None, notes=None) -> int` — validates FKs exist + `ends_at > starts_at`; commits.
- `update_lesson(lid, **fields) -> None`
- `set_lesson_status(lid, status) -> None`
- `check_conflicts(instructor_id, room_id, starts_at, ends_at, exclude_lesson_id=None) -> list[dict]` — overlapping lessons for instructor OR room (coordinated behavior; used by lesson routes to warn).

### attendance_models.py  (attendance model agent)
- `list_attendance(lesson_id=None, student_id=None) -> list[dict]`
- `mark_attendance(lesson_id, present, marked_by) -> None` — **single-student per lesson**: `lessons.student_id` is NOT NULL, so each lesson has exactly ONE student; this looks up that student_id from the lesson and UPSERTs one row (UNIQUE(lesson_id,student_id)). Raises `ValueError` if the lesson does not exist. Commits internally. **Does NOT audit** (route audits post-commit).
- `attendance_rate(student_id) -> float` — present / total (dashboard aggregate helper).

> Contradiction resolved (Codex): the earlier bulk `student_id[]/present[]` route input was
> wrong — a lesson is 1:1 with a student, so attendance is a single mark, and `student_id`
> is derived from the lesson, never supplied by the client.

### checkout_models.py  (checkout model agent — inventory transaction)
- `list_checkouts(student_id=None, status=None) -> list[dict]` — joins instrument + student.
- `get_checkout(cid) -> dict | None`
- `checkout_instrument(instrument_id, student_id, due_at) -> int` — **OWNS one `transaction()` internally**: opens `with transaction() as conn`, guards `instrument.status == 'available'` (else `ValueError`), inserts the checkout row, calls `instrument_models.set_instrument_status(conn, instrument_id, 'checked_out')` on the SAME conn, commits as one unit. **Does NOT audit** (route audits post-commit).
- `return_instrument(checkout_id) -> None` — **OWNS one `transaction()` internally**: sets `returned_at` + status='returned' and flips the instrument back to 'available' via `set_instrument_status(conn, iid, 'available')` on the SAME conn, one atomic unit. **Does NOT audit** (route audits post-commit).

### invoice_models.py  (invoice model agent — multi-table transaction)
- `list_invoices(student_id=None, status=None) -> list[dict]` — each row includes computed `total_cents = SUM(items)` (unscoped; staff callers).
- `get_invoice(iid) -> dict | None` — dict includes `items: list[dict]` and `total_cents` (unscoped; staff callers).
- `get_invoice_for(iid, actor) -> dict | None` — **Ownership-Scoped Getter Contract**: `WHERE invoices.id = :iid AND (:staff OR student_id = (SELECT id FROM students WHERE user_id=:actor_id))`; returns the invoice with `items` + `total_cents`, else `None`. `/invoices/<iid>` → `abort(404)`.
- `create_invoice(student_id, description=None, due_at=None, created_by=None) -> int` — **get-or-create the student's single `draft`** (index-safe): if a `draft` already exists for the student, returns it (optionally updating description/due_at); else inserts one. This guarantees `create_invoice` can NEVER violate `ux_one_draft_per_student`. Commits. (The staff "New invoice" route lands the user on that one open draft to add items.)
- `add_item(invoice_id, description, amount_cents, source_type='manual', source_id=None) -> int` — commits (standalone, staff manual add). No index interaction (invoice_items is unconstrained by the draft index).
- `add_item_in_tx(conn, invoice_id, description, amount_cents, source_type, source_id) -> int` — inserts on the **caller-supplied** `conn`; **does NOT commit**. Called only by `enroll` inside its transaction.
- `get_or_create_draft_invoice_in_tx(conn, student_id, created_by) -> int` — on the **caller-supplied** `conn`; returns the student's SINGLE open `draft` invoice id, or creates one (recording `created_by`); **does NOT commit**. Called only by `enroll` inside its transaction. **Invariant: at most one `draft` invoice per student** — enforced by selecting the most-recent `draft` for reuse (a draft only leaves `draft` when staff explicitly `set_invoice_status` to `sent`), so enroll-driven items always accrete onto one open draft; no duplicate drafts.
- `set_invoice_status(iid, status) -> None` — commits; on 'paid' sets `paid_at`. **Forward-only transitions** (`draft→sent`, `sent→paid`, `draft|sent→void`); it MUST reject any transition BACK to `draft` (`ValueError('cannot reopen to draft')`) so it can never mint a second draft and collide with `ux_one_draft_per_student`. Once an invoice leaves `draft`, the student's next enroll get-or-creates a fresh draft. **Does NOT audit** (route audits post-commit).

### practice_log_models.py  (practice_log model agent — ownership-scoped)
- `list_practice_logs_for(actor, target_student_id=None) -> list[dict]` — **Ownership-Scoped Getter Contract**: student → predicate `student_id = (SELECT id FROM students WHERE user_id=:actor_id)` (the `target_student_id` arg is IGNORED for students — they can never widen scope); staff → all, or scoped to `target_student_id` when supplied. `/practice` list source.
- `get_practice_log_for(log_id, actor) -> dict | None` — **Ownership-Scoped Getter Contract**: `WHERE practice_logs.id = :log_id AND (:staff OR student_id = (SELECT id FROM students WHERE user_id=:actor_id))`; else `None`. `/practice/<log_id>/delete` → `abort(404)` BEFORE deleting.
- `create_practice_log(student_id, minutes, notes=None) -> int` — commits.
- `delete_practice_log(log_id) -> None` — commits (called only after `get_practice_log_for` passes).
- `total_minutes(student_id, since=None) -> int` — dashboard aggregate helper.

> **Practice-creation authorization (Codex round 2):** practice logging is **student
> self-service ONLY**. The `/practice/new` route requires `current_student_id() is not None`
> and always sets `student_id = current_student_id()` — a client-supplied `student_id` is
> ignored. Staff have no student identity, so a staff POST to `/practice/new` → **403**
> (staff can VIEW a student's logs via `?target_student_id`, never create on their behalf).

### announcement_models.py  (announcement model agent — role-scoped)
- `list_for_role(role) -> list[dict]` — returns announcements whose `audience IN ('all', <role-bucket>)` (student→'students', instructor→'instructors', admin→all).
- `get_announcement(aid) -> dict | None`
- `create_announcement(author_id, title, body, audience='all') -> int` — commits. **Does NOT audit** (route audits post-commit).
- `delete_announcement(aid) -> None` — commits.

### audit_models.py  (audit agent — WRITE-ONLY lib, imported by ALL mutating routes)
- `record(user_id, action, entity_type, entity_id=None, detail=None) -> None` — inserts one
  audit_log row; commits. Imported by every mutating route; called post-commit (one of the
  four sanctioned cross-agent write calls — see Data Ownership).
- `list_audit(entity_type=None, limit=200) -> list[dict]` — admin audit view (routes/dashboard.py `/audit`).

### dashboard_models.py  (dashboard agent — cross-entity aggregates; READ-only)
- `admin_summary() -> dict` — simple counts (students, instructors, active courses, lessons_this_week, outstanding_invoice_cents, instruments_out) computed via **direct `get_db()` COUNT/SUM queries** (no student/instructor/course/instrument model imports — keeps the cross-boundary surface to exactly the FIVE relational imports below).
- `instructor_summary(instructor_id) -> dict` — my upcoming lessons, my courses, my students count.
- `student_summary(student_id) -> dict` — my upcoming lessons, my enrollments, my balance_cents, my practice_minutes_this_week, my attendance_rate.
- **Imports exactly FIVE model modules** for the per-actor aggregates — lesson (upcoming lessons), invoice (balance), enrollment (my enrollments), attendance (attendance_rate), practice_log (practice minutes) — matching §2. Plain admin counts use direct SQL, NOT model imports.

### search_models.py  (search agent — cross-entity)
- `search_all(q, role, actor_student_id=None) -> dict` — `{students:[...], instructors:[...], courses:[...]}`; results role-filtered (a student sees only self + the public course catalog; staff see all matches). LIKE-based.
- **Scope boundary (Codex — lessons/search):** search covers ONLY students, instructors, and
  courses. It deliberately does NOT search lessons, attendance, invoices, or practice logs —
  those are per-student private records whose cross-student exposure a keyword search could
  leak. So `search_models` imports only student/instructor/course models (see §2), never
  lesson/attendance/invoice models.

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
| GET | /<int:sid> | view_student → `get_student_for(sid, current_user()) or abort(404)` | role+own |
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
| POST | /enroll | `enroll(student_id, course_id, created_by=current_user()['id'])` | role:admin,instructor |
| POST | /<int:eid>/withdraw | withdraw | role:admin,instructor |

### lessons  (/lessons — lesson route agent)
| GET | / | list_lessons → `list_lessons_for(current_user(), **filters)` | role+own |
| GET/POST | /new | create_lesson | role:admin,instructor |
| GET | /<int:lid> | view_lesson → `get_lesson_for(lid, current_user()) or abort(404)` | role+own |
| GET/POST | /<int:lid>/edit | edit_lesson | role:admin,instructor |
| POST | /<int:lid>/status | set_status | role:admin,instructor |

### attendance  (/attendance — attendance route agent)
| GET | /lesson/<int:lid> | lesson_attendance (shows the lesson's ONE student) | role:admin,instructor |
| POST | /lesson/<int:lid>/mark | `mark_attendance(lid, present, marked_by=current_user()['id'])` — student derived from lesson | role:admin,instructor |

### invoices  (/invoices — invoice route agent)
| GET | / | list_invoices | role:admin,instructor |
| GET/POST | /new | create_invoice | role:admin,instructor |
| GET | /<int:iid> | view_invoice → `get_invoice_for(iid, current_user()) or abort(404)` | role+own |
| POST | /<int:iid>/items | add_item | role:admin,instructor |
| POST | /<int:iid>/status | set_status | role:admin,instructor |

### practice  (/practice — practice_log route agent)
| GET | / | `list_practice_logs_for(current_user(), request.args.get('target_student_id'))` | role+own |
| POST | /new | student-only: `sid = current_student_id() or abort(403)` → `create_practice_log(sid, minutes, notes)` | role+own |
| POST | /<int:log_id>/delete | `get_practice_log_for(log_id, current_user()) or abort(404)` → delete_log | role+own |

### announcements  (/announcements — announcement route agent)
| GET | / | list_announcements (role-scoped) | auth |
| GET/POST | /new | create_announcement | role:admin,instructor |
| POST | /<int:aid>/delete | delete_announcement | role:admin,instructor |

### dashboard  (NO url_prefix — owns the site root; the SOLE prefix-less blueprint)
Registered as `Blueprint('dashboard', __name__)` with **no** `url_prefix` (so it serves
`/`). Do NOT give it `/dashboard` — that would move the index off root. `url_for` targets:
`dashboard.index`, `dashboard.audit_log_view`.
| Method | Path | View | Auth |
|--------|------|------|------|
| GET | / | index (role-dispatched: admin/instructor/student summary) | auth |
| GET | /audit | audit_log_view | admin |

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
| `transaction` | context mgr | studio/database.py | checkout_models, enrollment_models (the two class-B openers; invoice's in-tx helpers receive the conn, they don't open one) | `transaction() -> ContextManager[sqlite3.Connection]` |
| `init_db` | function | studio/database.py | scaffold (__init__) | `init_db() -> None` |
| `login_required` | decorator | studio/auth.py | ALL route agents | `login_required(view) -> view` |
| `role_required` | decorator | studio/auth.py | ALL route agents | `role_required(*roles) -> Callable[[view], view]` |
| `current_user` | function | studio/auth.py | ALL route agents + base.html | `current_user() -> dict | None` |
| `current_student_id` | function | studio/auth.py | lesson/invoice/practice routes, dashboard route | `current_student_id() -> int | None` |
| `current_instructor_id` | function | studio/auth.py | lesson route, dashboard route | `current_instructor_id() -> int | None` |
| `require_self_or_staff` | function | studio/auth.py | student/practice write routes | `require_self_or_staff(student_id) -> None  # aborts 404 if unauthorized` |
| `login_user` / `logout_user` | function | studio/auth.py | auth routes | `login_user(user: dict) -> None` / `logout_user() -> None` |
| `record` | function | studio/models/audit_models.py | ALL mutating route agents | `record(user_id, action, entity_type, entity_id=None, detail=None) -> None` |

### 1b. Model-function exports (complete inventory — reconciled with §2 Cross-Boundary Wiring)
Every model function is a cross-boundary export (signatures = Model Functions section).
"Used by" here MUST match §2 exactly; the ownership-scoped `*_for` getters and the
transaction-changed signatures are included.

| Function | Defined By | Used By (consumers = §2) |
|----------|-----------|--------------------------|
| create_user, get_user, get_user_by_email, verify_credentials | auth_models.py | routes/auth.py, studio/auth.py (INTRA-agent: all auth-core; not a cross-agent boundary) |
| list_students, get_student, `get_student_for(sid, actor)`, create_student, update_student, set_student_active | student_models.py | routes/students.py; routes/lessons.py, routes/invoices.py, routes/enrollments.py (name lookups); search_models.py |
| list_instructors, get_instructor, create_instructor, update_instructor, set_instructor_active | instructor_models.py | routes/instructors.py; routes/courses.py, routes/lessons.py; search_models.py |
| list_rooms, get_room, create_room, update_room, set_room_active | room_models.py | routes/rooms.py (scaffold); routes/lessons.py |
| list_instruments, get_instrument, create_instrument, update_instrument, `set_instrument_status(conn, iid, status)` | instrument_models.py | routes/instruments.py; **checkout_models.py** (set_instrument_status, in-tx) |
| list_courses, get_course, create_course, update_course, set_course_active, count_enrolled | course_models.py | routes/courses.py, routes/enrollments.py, routes/lessons.py; **enrollment_models.py** (in-tx capacity/price/name read by enroll); search_models.py |
| list_enrollments, get_enrollment, `enroll(student_id, course_id, created_by)`, set_enrollment_status | enrollment_models.py | routes/enrollments.py; dashboard_models.py |
| list_lessons, `list_lessons_for(actor, **filters)`, get_lesson, `get_lesson_for(lid, actor)`, create_lesson, update_lesson, set_lesson_status, check_conflicts | lesson_models.py | routes/lessons.py, routes/attendance.py; dashboard_models.py |
| list_attendance, `mark_attendance(lesson_id, present, marked_by)`, attendance_rate | attendance_models.py | routes/attendance.py; dashboard_models.py |
| list_checkouts, get_checkout, checkout_instrument, return_instrument | checkout_models.py | routes/instruments.py |
| list_invoices, get_invoice, `get_invoice_for(iid, actor)`, create_invoice, add_item, `add_item_in_tx(conn,...)`, `get_or_create_draft_invoice_in_tx(conn,...)`, set_invoice_status | invoice_models.py | routes/invoices.py; **enrollment_models.py** (in-tx helpers); dashboard_models.py (balance) |
| `list_practice_logs_for(actor, target_student_id=None)`, `get_practice_log_for(log_id, actor)`, create_practice_log, delete_practice_log, total_minutes | practice_log_models.py | routes/practice.py; dashboard_models.py |
| list_for_role, get_announcement, create_announcement, delete_announcement | announcement_models.py | routes/announcements.py |
| record, list_audit | audit_models.py | ALL mutating routes (record); routes/dashboard.py (list_audit) |
| admin_summary, instructor_summary, student_summary | dashboard_models.py | routes/dashboard.py |
| search_all | search_models.py | routes/search.py |

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
| `invoice_models.add_item_in_tx` | orchestration entrypoint | invoice_models.py | enrollment_models.enroll (SAME conn) | `add_item_in_tx(conn, invoice_id, description, amount_cents, source_type, source_id) -> int  # no commit` |
| `invoice_models.get_or_create_draft_invoice_in_tx` | orchestration entrypoint | invoice_models.py | enrollment_models.enroll (SAME conn) | `get_or_create_draft_invoice_in_tx(conn, student_id, created_by) -> int  # no commit` |
| `instrument_models.set_instrument_status` | orchestration entrypoint | instrument_models.py | checkout_models.checkout_instrument / return_instrument (SAME conn) | `set_instrument_status(conn, iid, status) -> None  # no commit` |
| `dashboard_models.*_summary` | orchestration entrypoint | dashboard_models.py | dashboard.index | `admin_summary() -> dict` / `instructor_summary(instructor_id) -> dict` / `student_summary(student_id) -> dict` |
| `lesson_models.check_conflicts` | orchestration entrypoint | lesson_models.py | lessons.create_lesson/edit_lesson | `check_conflicts(instructor_id, room_id, starts_at, ends_at, exclude_lesson_id=None) -> list[dict]` |
| `course_models.count_enrolled` / `get_course` | orchestration entrypoint | course_models.py | enrollment_models.enroll (in-tx capacity/price/name read) | `count_enrolled(cid) -> int` / `get_course(cid) -> dict | None` |
| `search_models.search_all` | orchestration entrypoint | search_models.py | search.search | `search_all(q, role, actor_student_id=None) -> dict` |

---

## 2. Cross-Boundary Wiring Table (producer file → consumer file → import)

| Producer | Consumer | Import |
|----------|----------|--------|
| studio/database.py | every model **+ studio/auth.py** (current_user / current_student_id / current_instructor_id direct queries) | `from studio.database import get_db, query, transaction` |
| studio/auth.py | every route | `from studio.auth import login_required, role_required, current_user, current_student_id, current_instructor_id, require_self_or_staff` |
| studio/models/student_models.py | routes/students.py, routes/lessons.py, routes/invoices.py, routes/enrollments.py, search_models.py | `from studio.models.student_models import ...` |
| studio/models/instructor_models.py | routes/instructors.py, routes/courses.py, routes/lessons.py, search_models.py | `from studio.models.instructor_models import ...` |
| studio/models/audit_models.py | every mutating route (`record`); routes/dashboard.py (`list_audit`) | `from studio.models.audit_models import record  # or list_audit` |
| studio/models/room_models.py | routes/rooms.py (scaffold), routes/lessons.py | `from studio.models.room_models import ...` |
| studio/models/course_models.py | routes/courses.py, routes/enrollments.py, routes/lessons.py, **enrollment_models.py** (enroll reads get_course + count_enrolled in-tx), search_models.py | `from studio.models.course_models import ...` |
| studio/models/enrollment_models.py | routes/enrollments.py, dashboard_models.py | `from studio.models.enrollment_models import ...` |
| studio/models/invoice_models.py | routes/invoices.py, **enrollment_models.py** (in-tx helpers), dashboard_models.py (balance) | `from studio.models.invoice_models import ...  # add_item_in_tx + get_or_create_draft_invoice_in_tx for enroll; list/get for routes+dashboard` |
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
| POST /auth/logout | (none) | `_csrf` only | 400 on CSRF mismatch; else 302→/auth/login |
| POST /students/new, /edit | first_name, last_name, email?, skill_level | names non-empty; skill_level ∈ enum | 400 + re-render |
| POST /students/<sid>/deactivate | (sid path) | student exists | 404 if absent; 403 if non-admin |
| POST /instructors/new, /edit | first_name, last_name, hourly_rate_cents? | names non-empty; rate ≥ 0 int | 400 + re-render |
| POST /rooms/new, /edit | name, capacity | name non-empty; capacity ≥ 1 int | 400 |
| POST /instruments/new, /edit | name, category, condition | name+category non-empty; condition ∈ enum | 400 |
| POST /instruments/<iid>/checkout | student_id, due_at | presence: student exists + due_at future ISO (route-level). **The `status=='available'` guard is AUTHORITATIVE inside `checkout_instrument`'s BEGIN IMMEDIATE** (not a route pre-check — avoids TOCTOU) | 400 on bad input; flash "instrument unavailable" when the in-tx guard raises |
| POST /instruments/checkouts/<cid>/return | (cid path) | checkout exists + status=='out' | 404 / 400 |
| POST /courses/new, /edit | name, level, capacity, price_cents, instructor_id? | name non-empty; level ∈ enum; capacity ≥ 1; price ≥ 0; instructor exists if given | 400 |
| POST /enrollments/enroll | student_id, course_id | presence: student + course exist and course is `active` (route-level). **The `already-enrolled` (UNIQUE) and `under-capacity` guards are AUTHORITATIVE inside `enroll`'s BEGIN IMMEDIATE** (not route pre-checks — avoids TOCTOU) | 400 + flash "already enrolled / course full" when the in-tx guard raises |
| POST /enrollments/<eid>/withdraw | (eid path) | enrollment exists | 404 |
| POST /lessons/new, /edit | instructor_id, student_id, starts_at, ends_at, room_id?, course_id? | FKs exist; `ends_at > starts_at`; ISO datetimes | 400 + re-render; conflicts → warn flash (non-blocking) |
| POST /lessons/<lid>/status | status | status ∈ enum | 400 |
| POST /attendance/lesson/<lid>/mark | present (bool) | lesson exists (else 404); student is derived from `lessons.student_id`, NOT client-supplied | 400 on bad `present`; 404 on missing lesson |
| POST /invoices/new | student_id, description?, due_at? | student exists | 400 |
| POST /invoices/<iid>/items | description, amount_cents, source_type | description non-empty; amount_cents int (may be negative for credit); source_type ∈ enum | 400 |
| POST /invoices/<iid>/status | status | status ∈ enum; 'paid' sets paid_at | 400 |
| POST /practice/new | minutes, notes? | minutes int > 0; **actor must be a student** (`current_student_id()` not None) — student_id is derived, never client-supplied | 400 on bad minutes; **403** if a staff/admin actor (no student identity) |
| POST /practice/<log_id>/delete | (path) | log exists AND belongs to actor (or staff) | 404 |
| POST /announcements/new | title, body, audience | title+body non-empty; audience ∈ enum | 400 |
| POST /announcements/<aid>/delete | (path) | announcement exists | 404 |

**Global:** every POST/PUT/PATCH/DELETE also validates the `_csrf` session token → **400**
on mismatch (before_request, scaffold). Typed URL params (`<int:...>`) → Flask 404 on
non-int. Unknown row id on any GET detail → 404.

---

## 4. Coordinated Behaviors (must be consistent across all ~30 agents)

- **Blueprint registration:** all blueprints registered in `studio/__init__.py` in a fixed
  order (dashboard, auth, students, instructors, rooms, instruments, courses, enrollments,
  lessons, attendance, invoices, practice, announcements, search). Each route agent exposes
  `bp = Blueprint('<name>', __name__, url_prefix='/<name>')` — **two exceptions:** `dashboard`
  has **no** `url_prefix` (owns `/` and `/audit`), and `rooms` is exposed by the scaffold
  agent (not a dedicated route agent) but still as `Blueprint('rooms', __name__, url_prefix='/rooms')`.
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
- **Audit:** every create/update/delete/checkout/return/pay **view** (route) calls
  `audit_models.record(...)` exactly once, AFTER the model call returns and has committed —
  **never inside a `transaction()` block, never from a model writer.** This guarantees the
  audit insert cannot commit-nested inside the checkout/return/enroll atomic units.

---

## 5. Transaction Contracts (every DB writer annotated)

Three writer classes — every DB-writing function is in exactly one:

**(A) Commit internally (self-contained, single logical write):** `create_*`, `update_*`
(incl. `update_instrument` status toggle), `set_*_active`, `set_lesson_status`,
`set_enrollment_status`, `set_invoice_status`, `mark_attendance`, `create_practice_log`,
`delete_practice_log`, `create_announcement`, `delete_announcement`, `create_invoice`,
`add_item`, `record`. Each opens no explicit transaction; the write auto-commits.

**(B) Own ONE explicit `transaction()` internally (BEGIN IMMEDIATE; commit as one atomic
unit):** exactly three, each opens `with transaction() as conn:` itself and threads that
SAME `conn` into its in-tx helpers — the ROUTE just calls them and never manages a transaction:
- `checkout_models.checkout_instrument(instrument_id, student_id, due_at)` — guard
  `available` → insert checkout → `set_instrument_status(conn, iid, 'checked_out')`. Rolls back both on any failure.
- `checkout_models.return_instrument(checkout_id)` — set returned/status → `set_instrument_status(conn, iid, 'available')`.
- `enrollment_models.enroll(student_id, course_id, created_by)` — insert enrollment → (if
  priced) `get_or_create_draft_invoice_in_tx(conn, student_id, created_by)` →
  `add_item_in_tx(conn, invoice_id, ...)`. A UNIQUE('already enrolled') violation rolls back
  the whole unit — no orphan invoice/invoice_item.

**(C) In-tx helpers — take a caller `conn`, do NOT commit, NEVER called outside a class-(B)
transaction:** `instrument_models.set_instrument_status(conn, iid, status)`,
`invoice_models.add_item_in_tx(conn, ...)`, `invoice_models.get_or_create_draft_invoice_in_tx(conn, ...)`.

**Audit is NOT a writer class here:** `audit_models.record` (class A) is called only by the
ROUTE, after the class-(A)/(B) call returns and commits — so it is a separate post-commit
statement, never nested inside a class-(B) transaction.

**Invariant (total):** the invoice total is always `SUM(invoice_items.amount_cents)` computed
at read time — never a stored column — so a partially-applied item write can never desync a
persisted total.

**Invariant (one draft/student):** schema-enforced by `ux_one_draft_per_student`. Every path
that could touch a `draft` respects it: `enroll`→`get_or_create_draft_invoice_in_tx` (reuse),
`create_invoice` (get-or-create, never a raw insert), `set_invoice_status` (forward-only,
never back to `draft`), and seed data (≤1 draft/student). No path issues a second draft, so
the unique index never fires at runtime — it is a backstop, not a hot error path.

---

## 6. Authorization Matrix (every protected route)

| Route | Mode | Rule |
|-------|------|------|
| /auth/register, /auth/login | public | anonymous allowed; authenticated → redirect to / |
| /auth/logout | auth | any logged-in |
| /students (list, new, edit) | role:admin,instructor | staff manage students |
| /students/<sid> (view) | role+own | admin/instructor OR the student themselves; else **404** |
| /students/<sid>/deactivate | admin | admin only |
| /instructors (list, view) | role:admin,instructor | staff |
| /instructors/new, /edit | admin | admin only |
| /rooms (list) | role:admin,instructor | staff may view rooms (needed for lesson scheduling) |
| /rooms/new | admin | admin only |
| /rooms/<rid>/edit | admin | admin only |
| /instruments (list, checkouts) | role:admin,instructor | |
| /instruments/new,/edit | admin | |
| /instruments/<iid>/checkout, /return | role:admin,instructor | staff perform checkouts |
| /courses (list, view) | auth | any logged-in may browse catalog |
| /courses/new, /edit | role:admin,instructor | |
| /enrollments/* | role:admin,instructor | staff enroll/withdraw |
| /lessons (list) | role+own | `list_lessons_for(actor)` forces student→own / instructor→own; staff→all |
| /lessons/<lid> (view) | role+own | `get_lesson_for(lid, actor)` returns None → **404** for non-owner student/instructor |
| /lessons/new, /edit, /status | role:admin,instructor | |
| /attendance/* | role:admin,instructor | staff mark |
| /invoices (list, new, items, status) | role:admin,instructor | staff billing |
| /invoices/<iid> (view) | role+own | `get_invoice_for(iid, actor)` → None → **404** for non-owner student |
| /practice (list) | role+own | `list_practice_logs_for(actor, ?target_student_id)`; student forced to own, staff may pass `?target_student_id` |
| /practice/new | role+own (**student self-service ONLY**) | student → creates own log; **staff → 403** (no student identity; cannot log for a student) |
| /practice/<log_id>/delete | role+own | `get_practice_log_for(log_id, actor)` → None → **404** before delete |
| /announcements (list) | auth | role-scoped audience filter (`list_for_role`) |
| /announcements/new, /delete | role:admin,instructor | |
| / (dashboard index) | auth | role-dispatched summary |
| /audit | admin | admin-only audit log (dashboard blueprint, no prefix) |
| /search | auth | results role-filtered (student sees only self + public catalog) |

**404-not-403 rule (run-080 IDOR lesson):** every `role+own` **read** returns 404 for a
non-owner, enforced by the ownership-scoped `*_for(actor, ...)` getters returning `None`/`[]`
(0 rows) → `abort(404)` — NOT a post-fetch conditional. `role+own` **writes**
(practice/new, delete) additionally guard via `require_self_or_staff` / `get_*_for` before
mutating. Staff (admin/instructor) bypass ownership by role.

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
- WHEN `/` (dashboard index) loads THE SYSTEM SHALL render the summary for the caller's role (admin→admin_summary, instructor→instructor_summary(current_instructor_id()), student→student_summary(current_student_id())).
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

### Invariant Coverage (concurrency / uniqueness / practice-auth / ownership — round 2/3)
- WHEN a student is enrolled in a second course that is also priced THE SYSTEM SHALL add the new `invoice_item` to that student's **existing single draft** invoice (no second draft created).
  - Verify (smoke): after two priced enrollments, `SELECT COUNT(*) FROM invoices WHERE student_id=? AND status='draft'` == 1.
- WHEN a raw second `draft` invoice is attempted for a student who already has one THE SYSTEM SHALL reject it (`ux_one_draft_per_student` IntegrityError) — and `create_invoice` avoids it by get-or-create.
  - Verify (smoke): a direct `INSERT` of a 2nd draft for the same student raises `sqlite3.IntegrityError`.
- WHEN a student enrolls in a course already at `capacity` THE SYSTEM SHALL return **400** ("course full") and create NO enrollment and NO invoice_item (in-tx capacity guard).
- WHEN a student enrolls in an `inactive` course THE SYSTEM SHALL return **400** ("course inactive") with no enrollment (in-tx active guard).
- WHEN a staff/admin (no student identity) POSTs `/practice/new` THE SYSTEM SHALL return **403** (practice is student self-service only).
- WHEN a student requests another student's GET `/lessons/<lid>` THE SYSTEM SHALL return **404**; WHEN an instructor requests a lesson that is not theirs THE SYSTEM SHALL return **404** (instructor-scoped lesson ownership).
- WHEN a student lists `/lessons` THE SYSTEM SHALL return only lessons where they are the student; WHEN an instructor lists `/lessons` THE SYSTEM SHALL return only lessons they teach.
- WHEN two checkouts race for the same `available` instrument THE SYSTEM SHALL let exactly one succeed and the other get **400** (BEGIN IMMEDIATE serialization; the loser sees `status != 'available'`).

### Verification Commands
- `python3 test_smoke.py` — full happy-path + IDOR-404 + transaction-atomicity + CSRF + SECRET_KEY suite (must PASS; this is the dynamic surface that keeps the 080-W5 compounded-darkness gate LIT).
- `python3 -m compileall studio` — byte-compile every module (parse check; NOT `python3 -c`, per repo Bash rules).
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
> (3) any writer whose §Transaction Contracts class (A commit-internally / B owns-one-
> transaction / C in-tx-no-commit-helper) contradicts its Model-Functions signature — esp.
> the class-B trio (checkout_instrument, return_instrument, enroll) and their class-C helpers
> (set_instrument_status, add_item_in_tx, get_or_create_draft_invoice_in_tx); (4) any FK in
> §Database Schema with no owning model function; (5) any `url_for` target or blueprint name
> that won't resolve. Report P0s only; each section is internally plausible — the risk is
> incompatibility ACROSS sections.

**Round-1 Codex review: COMPLETE (2026-07-09).** All findings applied — one-transaction-each
for checkout/return/enroll with post-commit route audit; `created_by` threaded through enroll
and one `conn` through all in-tx helpers; Export Names ↔ Cross-Boundary Wiring reconciled
(complete §1b inventory); lessons/search + singular-lesson/attendance contradictions resolved;
dashboard registered prefix-less; ownership-scoped `*_for` getters (student/lesson/invoice/
practice) that return None→404; two missing validation rows + `current_instructor_id` mapping
+ explicit room-route authz. Self-review round 2 additionally reconciled the "sanctioned
cross-agent write" rule (4 calls, not 1) and the `transaction()` opener set.

**Round-2 Codex review: COMPLETE (2026-07-10).** Applied: (1) uniform Ownership-Scoped Getter
Contract — all four `*_for` getters standardized as actor-based SQL predicates (kills FC5
drift); (2) practice creation resolved to student-self-service-ONLY (staff→403); (3) removed
the stale `/ , /dashboard` §6 row + reconciled EARS to `/`; (4) moved the checkout
availability + enroll capacity/UNIQUE guards INSIDE `BEGIN IMMEDIATE` (TOCTOU-safe; §3 rows
now mark them advisory-only at route level); (5) pinned the enroll invoice-item values
(description=course.name, amount=price_cents, source_type='enrollment', source_id=enrollment id);
(6) enforced one-draft-per-student in the SCHEMA (`ux_one_draft_per_student` partial unique
index); (7) fully reconciled dashboard + infra wiring — `database.py`→`auth.py`,
`dashboard_models` consumes invoice+enrollment (the FIVE-module claim now holds), `course_models`
→`enrollment_models` (in-tx capacity/price/name read) added to §1b/§1d/§2; (8) lessons/search
fully reconciled (search never reads lessons). Fresh cross-section re-review (Model Functions ×
§1a/§1b/§1d/§2/§3/§5/§6/schema/Route Table/EARS) found no remaining contradictions.

**Round-3 Codex review: COMPLETE (2026-07-10).** Applied: (1) clarified the instructor-scope
lesson-ownership exception in the uniform contract (instructor scoped to own lessons only;
full staff over students/invoices/practice); (2) moved the `course.active` guard INSIDE
enroll's BEGIN IMMEDIATE (concurrent-deactivation-safe); (3) reconciled every class-A invoice
path with the partial index — `create_invoice` = get-or-create draft, `set_invoice_status` =
forward-only (never back to draft), +§5 one-draft invariant; (4) pinned seed invoice statuses
(≤1 draft/student) + all-constraint seed note; (5) removed the stale `dashboard_models`→
`student_models` edge (§1b + §2); (6) documented `transaction()` = the single `get_db()`
request connection (so in-tx reads see uncommitted state; BEGIN IMMEDIATE serializes writers);
(7) added an EARS "Invariant Coverage" block for one-draft, in-tx capacity/active rejection,
practice-403, instructor/student lesson ownership, and checkout race. Fresh full cross-section
re-review: no remaining P0.

Then: **human P0 structural pass (Alex — non-optional cross-section field-matching)** → flip
`status: draft`→`active` → launch as the next run-id via autopilot swarm
(`dangerouslySkipPermissions` already set; inject agent-pitfalls per CLAUDE.md; copy
BUILD_TRACKING template).
