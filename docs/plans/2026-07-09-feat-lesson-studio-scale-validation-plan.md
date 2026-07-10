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

> **PLAN STATUS: `draft` — backbone only.** This pass contains the load-bearing core:
> App Config, complete Database Schema, Data Ownership, and the ~30-agent Roster. The six
> MANDATORY contract sections (Export Names, Cross-Boundary Wiring, Input Validation,
> Coordinated Behaviors, Transaction Contracts, Authorization Matrix) + Model Functions +
> Route Table + EARS Acceptance Tests are authored in the following passes BEFORE this
> flips to `status: active` and enters convergence hardening. Do NOT launch on a draft.

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

## Remaining passes (authored before `status: active`)

1. **Model Functions** — full signature + return-shape for every function in each
   `*_models.py` (the Export Names contract depends on these).
2. **Route Table** — every blueprint, url_prefix, path, method, auth mode.
3. **The 6 MANDATORY contract sections** (spec-completeness-checker gates these):
   Export Names Table (with Full Signatures + orchestration entrypoints) · Cross-Boundary
   Wiring Table · Input Validation Prescriptions · Coordinated Behaviors · Transaction
   Contracts · Authorization Matrix.
4. **EARS Acceptance Tests** (Happy Path + Error Cases + Verification Commands).
5. **Feed-Forward** (plan-level) + Codex handoff prompt.

Then: convergence hardening (Codex review → fixes → NotebookLM if external data → human
P0 structural pass) → flip to `active` → launch as the next run-id.
