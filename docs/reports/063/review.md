# Code Review Report — Run 063
# Film Production PM Tool

**Date:** 2026-06-02
**Reviewers:** flow-trace-reviewer (callsheet/schedule/reports surface), learnings-researcher, security-sentinel, architecture-strategist

---

## Feed-Forward Risk: Call Sheet Cross-Boundary Wiring

The plan flagged 6 cross-module imports in the call sheet surface as the highest-risk coupling point. The review verdict:

**RESOLVED — all 6 imports verified correct.** The assembly-fix pass during Run 063 pre-swarm successfully corrected all 6 contract mismatches before the tail. The callsheet cross-boundary wiring is sound:

| Import | From | To | Return Type | Verified |
|--------|------|----|-------------|---------|
| `get_schedule_entries` | schedule_models | callsheet_models | `list[dict]` with `scene_id`, `location_id` | PASS |
| `get_cast_for_scenes` | cast_models | callsheet_models | `list[dict]` with `id`, `name`, `character_name`, `cast_id_number` | PASS |
| `get_location` | location_models | callsheet_models | `dict` or `None` with `nearest_hospital` | PASS |
| `get_scenes_by_ids` | scene_models | callsheet_models | `list[dict]` with `id`, `scene_number` etc | PASS |
| `get_crew_by_department` | crew_models | callsheets.routes | `list[dict]` with `department_name`, `members[]` | PASS |
| `get_shoot_dates` | schedule_models | callsheets.routes | `list[str]` | PASS |

The template correctly iterates `crew` as `dept.department_name` + `dept.members` (matching `get_crew_by_department` return structure).

---

## Findings

### P1 Findings

| # | Finding | File | Severity | Todo |
|---|---------|------|----------|------|
| 1 | `callsheets.generate` accepts `shoot_date` without format validation | `app/blueprints/callsheets/routes.py:59` | P1 | 056 |

**Detail:** The `generate` route only checks `if not shoot_date` but does not validate YYYY-MM-DD format. The `schedule.create` route applies `re.match(r'^\d{4}-\d{2}-\d{2}$', shoot_date)` correctly. This gap means malformed dates pass through to SQL queries.

### P2 Findings

| # | Finding | File | Severity | Todo |
|---|---------|------|----------|------|
| 2 | `SESSION_COOKIE_SECURE=True` unconditional — breaks local HTTP dev | `app/__init__.py:18` | P2 | 057 |
| 3 | Redundant double `get_schedule_entries` call in `callsheets.generate` | `callsheets/routes.py:66`, `callsheet_models.py:31` | P2 | 058 |
| 4 | Ghost files from BrewOps project (app/db.py, app/routes/, 8 models, template dirs) | Multiple | P2 | 059 |

### P3 Findings

| # | Finding | File | Severity | Todo |
|---|---------|------|----------|------|
| 5 | `generate_call_sheet` stores `nearest_hospital` in `weather_note` column | `callsheet_models.py:113` | P3 | 060 |

---

## Cross-Boundary Wiring Analysis (Flow Trace)

### generate_call_sheet data flow
```
callsheets.generate (POST /<project_id>/generate)
  → get_schedule_entries(conn, project_id, shoot_date) [DUPLICATE — also called inside model]
  → generate_call_sheet(conn, project_id, shoot_date)
      → get_schedule_entries(conn, project_id, shoot_date)  ← REDUNDANT
      → get_scenes_by_ids(conn, scene_ids)                  ← CORRECT
      → get_cast_for_scenes(conn, scene_ids)                ← CORRECT
      → get_location(conn, location_id)                     ← CORRECT
      → BEGIN IMMEDIATE ... COMMIT
  → redirect to callsheets.detail
```

### callsheets.detail data flow
```
callsheets.detail (GET /<project_id>/<call_sheet_id>)
  → get_call_sheet(conn, call_sheet_id)     ← CORRECT (project ownership check)
  → get_call_sheet_scenes(conn, call_sheet_id) ← CORRECT
  → get_call_sheet_cast(conn, call_sheet_id)   ← CORRECT
  → get_crew_by_department(conn, project_id)   ← CORRECT
  → render callsheets/detail.html
      uses: call_sheet.sheet_number, call_sheet.shoot_date, call_sheet.crew_call_time
            call_sheet.status, call_sheet.weather_note, call_sheet.general_notes
            scenes[].scene_number, scenes[].int_ext, etc.
            cast[].cast_id_number, cast[].name, cast[].status, etc.
            crew[].department_name, crew[].members[].name, etc.
```

All template field access matches the return types from the model layer. No name mismatches found.

---

## Learnings-Researcher Notes

### Known Patterns Applied Correctly

- **Transaction safety (FC34):** `generate_call_sheet` uses `BEGIN IMMEDIATE` with try/except/ROLLBACK. All model functions follow the transaction contract. No nested transactions.
- **TOCTOU protection:** `reorder_schedule` validates the full ID set inside the lock. `create_schedule_entry` checks for duplicate scene scheduling inside `BEGIN IMMEDIATE`.
- **FTS5 search (from Run 061):** `search_models.py` uses sanitize + phrase-wrap pattern (`"cleaned_query"`) to prevent FTS5 operator injection. Correct.
- **Ownership checks (FC35):** `callsheets.detail` verifies `call_sheet['project_id'] == project_id`. `schedule.delete` verifies `entry['project_id'] != project_id`. Both abort(404) on mismatch.
- **Date validation (from personal-finance-tracker P1):** Partially applied — schedule routes validate, callsheets does not (todo 056).

### New Patterns for Learnings Propagation

- **Ghost files from previous project:** The sandbox repo root accumulates files from prior builds. New builds should verify no previous project's `app/routes/`, `app/db.py`, or model files are present.
- **Conditional `SESSION_COOKIE_SECURE`:** Should be conditional on deployment env, not unconditional True.
- **Double-query on pre-check:** When a model function handles the empty-result case internally (returns None), the route's pre-check query is redundant.

---

## What the Review Did NOT Find (Confirming Clean)

- No raw SQL in route handlers (contract check already fixed all 3 data ownership violations)
- No import name mismatches in the 6 callsheet cross-boundary imports
- No missing `@login_required` + `@require_project_member` on any callsheet route
- No template field mismatches for callsheet data types
- No missing CSRF tokens on POST forms (detail.html publish form has `csrf_token()`)
- No IDOR vulnerabilities in callsheet.detail or callsheet.publish (both verify project_id)
- No missing indexes on frequently-queried columns (callsheets has composite UNIQUE index)
- Auth decorators consistently applied in correct order (login_required → require_project_member → require_role)

---

## Summary

- **Total Findings:** 5
- **P1 (BLOCKS MERGE):** 1 — callsheets.generate missing date validation
- **P2 (Should Fix):** 3 — SESSION_COOKIE_SECURE, double query, ghost files
- **P3 (Nice to Have):** 1 — hospital/weather_note column mismatch
- **Feed-Forward Risk (callsheet cross-boundary wiring):** RESOLVED — all 6 imports verified correct

STATUS: REVIEW COMPLETE
