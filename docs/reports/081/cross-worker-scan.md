# Cross-Worker Batch-Scan — run 081 (M38/FC52)

Aggregate scan over all 30 worker completion summaries, run AFTER all workers finished
and BEFORE the ownership gate.

## 1. Spec-version agreement — PASS

All 30 workers reported `SPEC_BLOB: 233b2558d7769c606e0b20380dc0bafd1718511b` — the exact
blob the 9w.5/9w.6 gates validated and the 9w.9.5 provenance gate verified on
origin/master. Zero drift, zero "missing section" reports. FC52 clean.

## 2. Divergent gap-fills / judgment calls (SPEC_ISSUES aggregation)

RESOLVED at spawn time (orchestrator pinned in briefs after scaffold's early report):
- Nav url_for targets `invoices.list_invoices` and `practice.list_practice_logs`
  (scaffold assumed; route-invoice + route-practice-log briefs pinned; both CONFIRMED
  the exact view names).
- Import-shadowing hazard (view names == model function names): all route agents
  confirmed module-qualified imports.

CONFIRMED-MATCHED seams:
- route-course expects `instructor_name` from course_models joins → model-course
  explicitly emits `instructor_name`. MATCH.
- Admin dashboard keys: model-dashboard emits `students, instructors, active_courses,
  lessons_this_week, outstanding_invoice_cents, instruments_out`; route-dashboard
  guessed the identical set. MATCH.

OPEN FLAGS for contract-check / review (FC30 join-alias & dict-key class — all
non-crashing blank-render risks, not 500s):
- F1. instructor/student summary dict keys: route-dashboard guessed
  `my_courses, my_students, upcoming_lessons` (instructor) and `balance_cents,
  practice_minutes_this_week, attendance_rate, upcoming_lessons, enrollments`
  (student); model-dashboard did not report its exact key names. VERIFY at assembly.
- F2. checkouts.html expects `instrument_name` / `student_name` from
  checkout_models.list_checkouts joins; model-checkout did not report aliases. VERIFY.
- F3. lessons templates expect `instructor_name/student_name/course_name/room_name`
  from lesson_models joins; model-lesson used a shared `_LESSON_SELECT` with name
  joins — aliases unconfirmed. VERIFY.
- F4. Template-context `current_user`: spec App Config says dict-or-None; §1a lists the
  callable. route-student templates use `current_user.role` (dict); scaffold injects it —
  form unconfirmed. VERIFY base.html + context processor agree (dict access everywhere
  or callable everywhere).
- F5. auth registration does NOT auto-create a students/instructors row (auth-core,
  simplest reading). Consequence: a freshly registered 'student' user has NO students
  row → `current_student_id()` is None → practice/new returns 403 even for a "student".
  smoke-test registers fresh users for role flows, so its student self-service tests may
  FAIL legitimately at assembly unless they use a seeded linked student (seed emails are
  the database agent's private choice; only admin@studio.test is spec-pinned). EXPECT
  possible smoke failures here — treat as an integration finding, not a harness bug.
- F6. search: student actors get instructors=[] (inferred from "self + public course
  catalog"). Acceptable reading; noted for review.
- F7. attendance nav (instructor) points at lessons.list_lessons because the attendance
  blueprint has no index route (scaffold gap-fill). Acceptable.

## 3. Empirical-wall reports — NONE

No worker reported a spec impossibility. model-dashboard noted interpretive choices
(week = Monday-UTC half-open; outstanding = draft+sent; my-students = DISTINCT lesson
students) — documented, plausible, non-blocking.

## Verdict

No FC52 drift; no two workers filled the SAME gap differently in a conflicting way
(the one near-miss — nav view names — was pinned into briefs mid-spawn and confirmed
on both sides). Open flags F1–F5 route to the swarm-runner contract-check and the
review phase.
