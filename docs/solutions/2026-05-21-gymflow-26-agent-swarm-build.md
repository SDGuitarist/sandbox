---
title: "GymFlow -- 26-Agent Gym Manager Swarm Build"
date: 2026-05-21
run_id: "054"
project: gymflow
agents: 26
stack: "Flask + SQLite + Jinja2 + Bootstrap 5"
build_method: swarm
status: complete
tags: [flask, sqlite, swarm, transaction-safety, feed-forward]
---

# GymFlow -- 26-Agent Gym Manager Swarm Build

## Problem

Build a single-admin gym management system (members, trainers, classes,
schedules, attendance with capacity checking, equipment, maintenance,
billing, payments, fitness assessments) using a 26-agent swarm with
vertical model/route ownership split.

The Feed-Forward risk from brainstorm: "Attendance capacity check with
BEGIN IMMEDIATE -- transaction boundary between attendance_models and
attendance_routes agents (FC29 territory)."

## Solution

26-agent swarm with strict file ownership: 1 core agent (app factory,
db, auth, filters, barrel exports, schema), 1 layout agent (base
template, CSS), 1 auth agent, 11 model agents (one per domain entity),
and 12 route agents (one per blueprint). Zero merge conflicts, 26/26
smoke tests pass.

### Key Design Decisions

1. **Single admin auth** -- no user table, password from env var,
   `@login_required` decorator on all non-auth routes.
2. **Individual class sessions** -- no recurring schedule engine. "Copy
   week" bulk action mitigates manual creation cost.
3. **BEGIN IMMEDIATE for capacity check** -- `check_in_class` acquires
   write lock before reading count, preventing TOCTOU race on class
   capacity.
4. **Integer cents for all money** -- `round(float(val) * 100)` with
   NaN/Inf guards throughout.

## What Went Wrong

### Feed-Forward Risk Confirmed: Missing ROLLBACK (P1-1)

The attendance_models agent implemented `check_in_class` with explicit
`BEGIN IMMEDIATE` / `COMMIT` / `ROLLBACK` for the capacity check. The
"class is full" error path correctly rolled back. BUT: if any other
exception occurred between BEGIN and COMMIT (e.g., `schedule_row` being
None causing TypeError), the transaction was left open with a write lock.

**Root cause:** The attendance_models agent did not follow the
try/except/ROLLBACK pattern already used by the schedule_models agent in
`copy_week_schedules`. Both agents had the same spec, but one agent
added exception safety and the other didn't. This is a classic swarm
divergence -- the spec prescribed the transaction pattern but didn't
prescribe the error handling wrapper.

**Fix:** Wrapped the entire `check_in_class` transaction block in
try/except with ROLLBACK in the except clause. Added schedule_row None
check with descriptive ValueError.

### Membership Type Agent Divergence (P1-2, P1-3)

The membership_type_models agent:
1. Set `conn.row_factory = sqlite3.Row` on every read call (redundant --
   already set in `get_db()`). No other model agent did this.
2. Used `datetime.now().strftime(...)` for timestamps instead of
   `datetime('now')` in SQL. All 10 other model agents used the SQL
   version. This produces local timezone timestamps instead of UTC.

**Root cause:** The spec showed a `get_db()` example setting
`row_factory` and a schema using `DEFAULT (datetime('now'))`, but it
didn't explicitly say "never set row_factory in model functions" or
"always use SQL datetime, never Python datetime." These are conventions
obvious to a human but not to an isolated agent.

### Spec Consistency Checker False Positives

The pre-swarm spec-consistency-check (30 checks, 12 FAILs) incorrectly
claimed FK constraints used CASCADE where the actual schema and plan
both specify RESTRICT. The learnings-researcher propagated this error as
a "P0" finding. Manual verification (grep for `ON DELETE` in both plan
and schema.sql) confirmed all critical FKs are RESTRICT.

**Root cause:** The consistency checker agent misread the ON DELETE
clauses. Likely confused by the multi-line SQL format or by the
SET NULL clauses on non-critical FKs (membership_type_id, trainer_id).

## Lessons

### For Future Specs

1. **Transaction error handling must be prescribed, not implied.**
   When a spec prescribes BEGIN IMMEDIATE, it must also prescribe the
   try/except/ROLLBACK wrapper. Add to the Transaction Contracts table:
   a "Error Handling" column with values "try/except/ROLLBACK" or "none
   needed" for each function.

2. **Negative constraints prevent agent divergence.** "Do NOT set
   row_factory in model functions -- get_db() handles it" is more
   effective than showing a get_db() example and hoping agents infer
   the constraint. Add a "DO NOT" section to specs for the top 5
   patterns agents get wrong.

3. **Timestamp convention must be explicit.** Add to Coordinated
   Behaviors: "All timestamps use SQL datetime('now'), never Python
   datetime.now()."

### For Consistency Checker

4. **False positive rate matters at scale.** 12/30 = 40% false positive
   rate undermines trust. The checker should verify FK clauses by
   extracting the exact `ON DELETE X` token, not by inferring behavior
   from context.

### Validated Patterns

5. **26-agent vertical split scales well.** Zero merge conflicts, zero
   FC37 failures, all agents committed on first try.

6. **Feed-Forward risk flagging works.** The brainstorm identified the
   exact transaction boundary risk, the plan prescribed the pattern, and
   review caught the incomplete implementation. The system worked --
   the bug was found before production.

7. **Money handling is settled.** `round(float(val) * 100)` with
   NaN/Inf/cap guards is the standard pattern across 5+ Flask builds.
   No violations found.

## Feed-Forward

- **Hardest decision:** Classifying the spec-consistency-check false
  positives. 12 FAILs looked serious until manual verification proved
  them wrong. Decided to note as false positives rather than "fix"
  correct code.
- **Rejected alternatives:** Could have added UNIQUE constraint on
  (member_id, class_schedule_id) for duplicate check-in prevention
  (security P1-2), but this is a security hardening feature, not a
  swarm code bug. Deferred to P2.
- **Least confident:** The consistency checker's 40% false positive rate
  means it either needs recalibration or its results should be manually
  verified before acting on them. Currently the learnings-researcher
  trusts consistency-check output and propagates false positives.
