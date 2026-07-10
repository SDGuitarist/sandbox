# Human P0 Structural Pass — Lesson-Studio Scale-Validation Spec

**Spec:** `docs/plans/2026-07-09-feat-lesson-studio-scale-validation-plan.md` (commit e3c8bae, Codex-converged 3 rounds)
**Gate:** launch is blocked until this worksheet reports **zero P0s**. Convergence criterion = Codex clean AND human finds zero P0s.
**Why this is non-optional:** P0s are *cross-section contradictions* — each section is internally consistent but incompatible across sections. AI review reliably misses these; the human field-match catches them. You are not re-reading the spec — you are checking that named fields AGREE across the sections listed on each line.

**How to use:** for each check, open the two (or more) referenced sections and confirm the named thing matches. `[ ]` = not yet checked, `[x]` = matches, `[!]` = **P0 found** (log it in the table at the bottom). Work top-down; the hardest seams are first.

---

## A. The 4-way lessons seam (highest risk — Feed-Forward flagged)
- [ ] **A1** `create_lesson(instructor_id, student_id, starts_at, ends_at, course_id, room_id, notes)` (Model Functions) — every param maps to a real `lessons` column (Schema) and to a form input; no extra/missing field.
- [ ] **A2** `list_lessons_for` / `get_lesson_for` ownership predicate (Ownership Contract) == the `/lessons` rows in §6 Authorization Matrix (student→own, instructor→own-taught, admin→all).
- [ ] **A3** Route Table `/lessons` view calls (`list_lessons_for(current_user())`, `get_lesson_for(lid, current_user())`) == the function names/signatures in Model Functions and §1b.
- [ ] **A4** §2 lists lesson_models consumers = routes/lessons, routes/attendance, dashboard_models — and NOT search (search scope boundary). Matches the Feed-Forward risk line and Cluster→Seam table.
- [ ] **A5** Attendance is **single-student**: `mark_attendance(lesson_id, present, marked_by)` (Model Functions) derives student from `lessons.student_id`; §3 validation row and Route Table agree (no client `student_id`). Schema `lessons.student_id` is NOT NULL.
- [ ] **A6** `check_conflicts` (§1d entrypoint) signature == its Model Functions definition == its caller in the lessons routes.

## B. enroll → invoice cross-agent transaction (second-hardest)
- [ ] **B1** `enroll(student_id, course_id, created_by)` — signature matches across Model Functions, §1b, §1d, and the Route Table call `enroll(..., created_by=current_user()['id'])`.
- [ ] **B2** In-tx helpers threaded on ONE `conn`: `get_or_create_draft_invoice_in_tx(conn, student_id, created_by)` then `add_item_in_tx(conn, invoice_id, description=course.name, amount_cents=course.price_cents, source_type='enrollment', source_id=<enrollment id>)` — every arg matches §1d + invoice_models signatures.
- [ ] **B3** `source_type='enrollment'` is in the `invoice_items.source_type` CHECK enum (Schema). `amount_cents`/`price_cents` are integer cents (no float).
- [ ] **B4** One-draft reconciliation is airtight: `enroll` (get_or_create), `create_invoice` (get-or-create), `set_invoice_status` (forward-only, never→draft), seed (≤1 draft/student) — all four respect `ux_one_draft_per_student` (Schema). No 5th path inserts a draft.
- [ ] **B5** In-tx guards (course.active, capacity via `count_enrolled`, UNIQUE) all live inside enroll's `BEGIN IMMEDIATE`; §3 marks route-level checks advisory-only. `count_enrolled`/`get_course` read the same `get_db()` connection (Database Connection note).

## C. Ownership contract + the one asymmetry
- [ ] **C1** All four `*_for` getters (student, lesson, invoice, practice) state the SAME actor-based SQL-predicate shape; none does fetch-then-check; none returns 403.
- [ ] **C2** The **instructor exception applies to lessons ONLY** — instructor is full staff over students/invoices/practice, but scoped to own lessons. Confirm this in the Ownership Contract note AND each of the 4 getters AND §6.
- [ ] **C3** `get_student_for` specializes correctly (ownership by `students.user_id`, not a `student_id` FK).
- [ ] **C4** §6 `role+own` rows (students/<sid>, lessons, invoices/<iid>, practice) all say **404** for non-owner, and the Route Table views call the matching `*_for(...) or abort(404)`.
- [ ] **C5** Practice creation = student-self-service-ONLY: Route Table (`sid = current_student_id() or abort(403)`), §3 (403 for staff), §6, and the practice-auth note all agree.

## D. Type consistency (the classic silent P0)
- [ ] **D1** Money is integer **cents** everywhere: `price_cents`, `amount_cents`, `hourly_rate_cents`, `outstanding_invoice_cents`, `balance_cents` — schema columns, model returns, and the `cents` Jinja filter (§4). No float, no bare "price".
- [ ] **D2** Timestamps are ISO-8601 TEXT (schema) and rendered via the shared `dt` filter (§4); `starts_at`/`ends_at`/`due_at` consistent.
- [ ] **D3** Booleans stored as INTEGER (`active`, `present`) — model returns and templates treat them as 0/1, not Python bool literals in SQL.
- [ ] **D4** Enum values match between schema CHECK and model/route usage: role, skill_level, level, instrument.status/condition, lesson.status, enrollment.status, invoice.status, source_type, audience.

## E. Fixtures / seed (convergence-loop's named human catch)
- [ ] **E1** Seed satisfies ALL constraints: ≤1 `draft` invoice per student; every role ∈ enum; every lesson `ends_at > starts_at`; enrollment pairs unique; any seeded checkout leaves `instrument.status` consistent.
- [ ] **E2** Seed is rich enough that `test_smoke.py` exercises REAL relationships (so the dynamic surface is genuinely LIT for the 080-W5 gate) — not empty tables.

## F. Route ↔ §3 ↔ §6 bijection + blueprints
- [ ] **F1** Every mutating (POST) route in the Route Table appears in §3 Input Validation, and vice-versa (spot-check logout, deactivate, checkout, return, enroll, mark, add_item, practice/new).
- [ ] **F2** Every protected route appears in §6 Authorization Matrix; no route lacks a mode.
- [ ] **F3** Dashboard is prefix-less (owns `/` and `/audit`); no other blueprint claims `/`; `url_for` targets (`dashboard.index`, `dashboard.audit_log_view`, `students.view_student`, …) resolve to defined blueprint+view names.

## G. Cross-agent write rule
- [ ] **G1** Exactly FOUR sanctioned cross-agent WRITE calls (Data Ownership): `audit_models.record` + `set_instrument_status` + `add_item_in_tx` + `get_or_create_draft_invoice_in_tx`. No model writes another agent's table with raw SQL.
- [ ] **G2** Audit is route-level + post-commit everywhere (never inside a class-B transaction, never in a model writer) — §4, §5, and each model function agree.

---

## P0 Log (record any `[!]`)
| # | Section(s) in conflict | The contradiction | Proposed fix |
|---|------------------------|-------------------|--------------|
|   |                        |                   |              |

## Exit
- [ ] **Zero P0s** → tell the session; it flips the plan to `status: active` and sets up the swarm launch (inject agent-pitfalls, copy BUILD_TRACKING, verify namespace `studio/`).
- [ ] **≥1 P0** → hand the log back; the session applies fixes, then (if structural) one more Codex round before re-running this pass.
