STATUS: PASS

# Pre-Swarm Spec Completeness Check

**Plan:** docs/plans/2026-06-06-feat-cpaa-event-replay-simulator-plan.md
**Checked:** 2026-06-07 (RETRY after spec author fixes)

## Results

| Surface | Status | Findings |
|---------|--------|----------|
| Export Names (FC1) | PASS | 24 function/constant/decorator entries + 10 endpoints + 5 blueprints + 10 route paths checked, 0 missing |
| Cross-Boundary Wiring (FC3) | PASS | 24 cross-boundary functions enumerated, 0 missing (login_required row now present in §6) |
| Input Validation (FC4) | PASS | 6 qualifying routes enumerated, 0 unvalidated (POST /auth/logout row now present in §7) |
| Registration Points (FC5) | PASS | 5 blueprints, 0 unregistered (§8.12 + §8.13 cover all) |
| Transaction Contracts (FC29) | PASS | 11 write functions annotated in §9, 0 unannotated |
| Authorization Mode (FC35) | PASS | 4 route groups in §10 matrix, 0 missing |

## Details

All surfaces PASS. No omissions found.

### Fix Verification

**Fix 1 confirmed — Cross-Boundary Wiring §6:**
The following row is now present in the wiring table:
```
| ingest_routes.py, replay_routes.py, validator_routes.py (all mutating routes) | __init__.py (A1) | `login_required(view)` decorator | `from app import login_required` | auth guard on every mutating route |
```
Producer `login_required` (owned by `__init__.py / A1`) is now a wiring table entry. All 24 cross-boundary functions from the Export Names table are accounted for.

**Fix 2 confirmed — Input Validation Prescriptions §7:**
The following row is now present in the validation table:
```
| `POST /auth/logout` | CSRF (no body) | CSRF token present + valid (clears `session['user']`) | 403 (CSRF fail); else 302 redirect to `auth.login` |
```
All 6 qualifying routes (POST /ingest/run, POST /replay/run, POST /validate/run, GET /validate/<int:result_id>, GET/POST /auth/login, POST /auth/logout) are now covered.

### Check-by-Check Evidence

**Check 1 — Export Names (FC1):**
Section "Mandatory Spec Section 1 — Export Names Table" found at §5. Blueprint table has a "Path" column with cells starting with `/`. All 4 identifier classes enumerated:
- Model/engine functions: 23+ entries (get_db, open_live_ro, canonical_hash, parse_json, parse_patch, append_event, get_events, events_at_time, record_anomaly, start_run, active_run, mark_complete_pass, mark_aborted, reap_stale_runs, write_snapshot, read_snapshot, apply_station, reset_station, apply_auction, reset_auction, apply_environmental, reset_environmental, apply_system, reset_system, build_projection_at, live_content_hash, record_determinism, login_required, create_app)
- Blueprint names: ingest_bp, replay_bp, validate_bp, dashboard_bp, auth_bp — all in table
- Route paths: /ingest/run, /replay/run, /replay/projection/at, /replay/run/<run_id>, /validate/run, /validate/<int:result_id>, /, /runs, /auth/login, /auth/logout — all in table

**Check 2 — Cross-Boundary Wiring (FC3):**
Section "Mandatory Spec Section 2 — Cross-Boundary Wiring Table" found at §6. All cross-boundary producers from the Export Names "Used By" column appear as producer entries: db.py (get_db, open_live_ro), __init__.py (login_required), constants.py (all constants), event_models.py (append_event, get_events, events_at_time), payload.py (parse_json, parse_patch), anomaly_models.py (record_anomaly), run_models.py (start_run, active_run, mark_*, reap_stale_runs), snapshot_models.py (write_snapshot, read_snapshot), proj_* (apply_*, reset_*), replay_engine.py (build_projection_at), live_guard.py (live_content_hash), serialization.py (canonical_hash), validation_models.py (record_determinism).

**Check 3 — Input Validation (FC4):**
Section "Mandatory Spec Section 3 — Input Validation Prescriptions" found at §7. Qualifying routes (POST or `<int:` path): POST /auth/login, POST /auth/logout, POST /ingest/run, POST /replay/run, POST /validate/run, GET /validate/<int:result_id>. All 6 appear in the §7 table with input, validation method, and error response specified. (Extra GET rows in the table for /replay/projection/at and /replay/run/<run_id> are acceptable — additional coverage, not a failure.)

**Check 4 — Registration Points (FC5):**
Section "Mandatory Spec Section 4 — Coordinated Behaviors" found at §8. §8.12 states "Blueprint registration in create_app in fixed order" covering all 5 blueprints. §8.13 lists nav links for all user-facing blueprints (dashboard.index, dashboard.runs, replay.start, ingest.run_ingest, validate.run); auth login/logout gated by session.

**Check 5 — Transaction Contracts (FC29):**
Section "Mandatory Spec Section 5 — Transaction Contracts + Data Ownership" found at §9. Transaction Contracts table covers all 11 write functions with commit pattern annotations (participates in caller's BEGIN IMMEDIATE, opens its own BEGIN IMMEDIATE, or pure/no-transaction).

**Check 6 — Authorization Mode (FC35):**
Section "Mandatory Spec Section 6 — Authorization Matrix" found at §10. Four route groups covered: public read (GET routes), public + CSRF (auth routes), role-only + CSRF (POST /ingest/run, /replay/run, /validate/run), forbidden (live.db write). All auth-protected routes have modes.

## Summary

- **Total checks:** 6
- **PASS:** 6
- **FAIL:** 0
- **WARN:** 0
- **N/A:** 0
- **BLOCKED:** 0
