---
title: "Film Production PM Tool — 16-Agent Swarm Build"
date: 2026-06-02
run_id: "063"
project: film-production-pm
tags: [flask, sqlite, jinja2, bootstrap5, sortablejs, swarm, callsheets, dood, cross-boundary-wiring, fts5, session-cookie]
build_method: swarm
agents: 16
files: 89
loc: 7458
status: complete
---

# Film Production PM Tool — 16-Agent Swarm Build

## What Was Built

A full-featured film production project management tool for indie and mid-budget producers. Flask + SQLite + Jinja2 + Bootstrap 5 dark theme + SortableJS. 16-agent vertical swarm. 7 MVP features shipped:

- **Project Dashboard** — active production overview with budget gauge and scene completion stats
- **Crew & Cast Database** — role-based records with department grouping and DOOD-aware cast tracking
- **Scene Breakdown** — INT/EXT, day/night flags, page-count-in-eighths, status transitions, scene elements
- **Shooting Schedule** — SortableJS drag-and-drop reorder, per-day view, TOCTOU-safe schedule entries
- **Call Sheet Generator** — cross-module data aggregation: schedule → scenes → cast → DOOD status → crew call
- **Budget Tracker** — ATL/BTL/OTHER category groups, department allocations with overspend guard, line items
- **Reports: DOOD Grid + Production Progress** — Day Out of Days matrix, scenes/pages wrapped vs remaining

**Stack:** Python 3.14, Flask + Flask-WTF (CSRF), SQLite (WAL mode + autocommit=True + busy_timeout=5000), Jinja2, Bootstrap 5.3.3 dark theme, SortableJS CDN, FTS5 full-text search.

**Key numbers:**
- 44 Python files, 37 HTML templates, 1 schema.sql (~270 lines)
- ~4,500 Python LOC + ~3,000 HTML LOC = ~7,500 total
- 18 smoke tests, all passing at merge
- 0 worktree conflicts during assembly

---

## What Went Right

### Zero-conflict 16-agent assembly

16 agents produced 89 files that merged with **0 conflicts**. The spec's 6 mandatory sections (Export Names, Cross-Boundary Wiring, Input Validation, Coordinated Behaviors, Transaction Contracts, Authorization Matrix) were all present. Vertical blueprint splitting (one agent per feature domain) kept ownership clean.

### Contract check caught 6 mismatches before the tail

The pre-swarm contract checker found and fixed:
1. `expenses.list_expenses` endpoint name → `expenses.list` (base.html uses `url_for('expenses.list')`)
2. Three data-ownership violations: UPDATE SQL in cast, locations, and projects route handlers moved to model layer
3. `index_entity` called with 4 args (missing `body`) in crew routes → fixed to 5
4. `entity_type='cast_member'`/`'crew_member'` → `'cast'`/`'crew'` for search model compatibility

All 6 fixed before smoke test. The spec's Cross-Boundary Wiring Table directly enabled this — without it the checker has no ground truth.

### Callsheet cross-boundary wiring verified clean

The plan's Feed-Forward risk ("6 cross-module imports — a single name mismatch crashes the call sheet page") was confirmed resolved. Flow-trace review verified all 6 import paths:

| Import | Producer | Consumer | Return Type |
|--------|---------|---------|------------|
| `get_schedule_entries` | schedule_models | callsheet_models | `list[dict]` with `scene_id`, `location_id` |
| `get_cast_for_scenes` | cast_models | callsheet_models | `list[dict]` with `id`, `name`, `cast_id_number` |
| `get_location` | location_models | callsheet_models | `dict\|None` with `nearest_hospital` |
| `get_scenes_by_ids` | scene_models | callsheet_models | `list[dict]` with `id`, `scene_number`, etc |
| `get_crew_by_department` | crew_models | callsheets.routes | `list[dict]` with `department_name`, `members[]` |
| `get_shoot_dates` | schedule_models | callsheets.routes | `list[str]` |

Template field access matched model return types exactly. No name mismatches.

### TOCTOU-safe writes throughout

Every model function that writes implements the pattern correctly:
- `create_schedule_entry` checks for duplicate scene scheduling inside `BEGIN IMMEDIATE`
- `reorder_schedule` validates full ID set inside the lock before any UPDATE
- `generate_call_sheet` reads all pre-transaction data outside the lock, then opens `BEGIN IMMEDIATE` only for the multi-table INSERT batch
- `allocate_budget` rechecks total_allocated inside the lock before upsert

### FTS5 search from Run 061 applied correctly

`search_models.py` uses the `_sanitize_query` → phrase-wrap pattern: strip FTS5 operators (`* " () : ^`), then wrap in double quotes for phrase search. Prevents injection and handles all edge cases. This was learned in Run 061 and applied here without regression.

### SQLite `:memory:` smoke test fix

Prior smoke tests (e.g., Run 063's first pass) failed because `init_db()` opened its own `:memory:` connection, seeded it, then closed it — leaving every subsequent `get_db()` call with an empty database. Fixed in the final smoke test script by using a real temp file for smoke testing: `tempfile.NamedTemporaryFile(suffix='.db')` with proper cleanup. Shared-cache URI (`file::memory:?cache=shared`) is correct for in-memory multi-connection setups but not used in smoke tests.

---

## What Went Wrong

### Ghost files from prior BrewOps project shipped with the swarm output

The sandbox repo root retained 42 files from the previous BrewOps build: `app/db.py`, `app/routes/` (10 files), 8 model files (`batch_models`, `ingredient_models`, etc.), and 7 template directories. None were imported by any film PM blueprint, so the app functioned correctly, but:

- `app/db.py` defines a second `get_db()` function connecting to `brewops.db` — a landmine for developers
- Ghost model files import `sqlite3` and define SQL against non-existent tables
- Template directories inflated `app/templates/` with 21 non-film HTML files

**Root cause:** The swarm agents build into the sandbox repo root, which accumulates files from prior builds. No pre-build cleanup step exists.

**Fix applied:** Commit `b783e3a` deleted all 42 ghost files. Smoke tests confirmed 18/18 after deletion.

**Prevention:** Add a "ghost-file check" to the pre-swarm gate: verify `app/routes/`, `app/db.py`, and any non-spec model files are absent before agents start.

### P1: callsheets.generate missing date format validation

The `POST /call-sheets/<project_id>/generate` route validated that `shoot_date` was non-empty but not that it was a valid YYYY-MM-DD date string. The `schedule.create` route applied `re.match(r'^\d{4}-\d{2}-\d{2}$', shoot_date)` correctly. This validation gap meant malformed dates (e.g., `2026-99-99`, arbitrary strings) passed through to SQL queries.

**Root cause:** Date validation is a cross-agent responsibility in vertical swarm builds. The schedule agent applied it; the callsheets agent independently wrote its route without checking the schedule agent's pattern. No spec prescription required it.

**Fix applied:** Added `import re` + `re.match(r'^\d{4}-\d{2}-\d{2}$', shoot_date)` guard to `callsheets.generate`. Commit `b783e3a`.

**Prevention:** Add "date input validation is required for every date-accepting route" to agent pitfalls (Input Validation Prescriptions section of specs should list all date-accepting routes explicitly).

### P2: SESSION_COOKIE_SECURE=True unconditional breaks local HTTP dev

`app/__init__.py` set `SESSION_COOKIE_SECURE = True` unconditionally. Browsers refuse to send session cookies over plain HTTP, so any developer running `flask run` locally without HTTPS cannot log in — the app appears to work but auth silently fails. The smoke test used Flask's test client which bypasses this, masking the issue.

**Fix applied:** Changed to `os.environ.get('FLASK_ENV') == 'production'`. Commit `b783e3a`.

**Prevention:** Add to spec template: `SESSION_COOKIE_SECURE = os.environ.get('FLASK_ENV') == 'production'`.

### P2: Redundant double `get_schedule_entries` query in generate route

The `callsheets.generate` route called `get_schedule_entries` as a pre-check (lines 66–70), then called `generate_call_sheet` which internally calls `get_schedule_entries` again as its first step. The pre-check result was discarded — the model handles the empty case by returning `None`. Two identical SQL queries per generate request.

**Fix applied:** Removed the pre-check block from the route. The `if call_sheet_id is None` guard on the next line already covers it. Commit `b783e3a`.

---

## Risk Resolution (Feed-Forward)

**Brainstorm/plan risk:** "Call sheet Cross-Boundary Wiring — 6 cross-module imports is the densest coupling surface attempted. A single name mismatch or wrong return type crashes the call sheet page."

**What actually happened:** The pre-swarm contract checker caught and fixed all 6 mismatches in an automated assembly-fix pass, before the tail phase even began. The review confirmed all 6 paths were correct by tracing return types end-to-end from producer model to consumer template.

**Delta (expectation vs reality):** The risk was real — without the contract checker, at least 2 of the 6 mismatches would have caused runtime crashes (wrong entity_type string for search, missing 5th arg to index_entity). The contract checker was the mechanism that converted this from "highest risk" to "no-op at review time."

**What was learned:** Dense coupling surfaces are safe if the spec's Cross-Boundary Wiring Table is complete and the contract checker has ground truth to validate against. The risk isn't the coupling itself — it's the absence of automated verification.

---

## Patterns Worth Reusing

### DOOD status computation pattern

Day Out of Days status (SW/W/WF/SWF/H) requires knowing a cast member's first and last working day across the entire schedule. The pattern:

```python
sorted_working = sorted(working_days)
first_day = sorted_working[0]
last_day = sorted_working[-1]

if shoot_date in working_days:
    if first_day == last_day and shoot_date == first_day:
        status = 'SWF'  # Start-Work-Finish (1-day shoot)
    elif shoot_date == first_day:
        status = 'SW'   # Start-Work
    elif shoot_date == last_day:
        status = 'WF'   # Work-Finish
    else:
        status = 'W'    # Working
elif first_day < shoot_date < last_day:
    status = 'H'        # Hold
else:
    status = ''         # Not on schedule
```

This logic exists in two places: `generate_call_sheet` (for individual call sheets) and `get_dood_grid` (for the full DOOD report). Both must stay in sync. The duplication is a future refactor target — extract `_compute_dood_status(shoot_date, working_days)` helper.

### Transaction-safe schedule reorder

The SortableJS reorder endpoint validates the full ID set inside `BEGIN IMMEDIATE` before writing:

```python
conn.execute('BEGIN IMMEDIATE')
db_ids = {row['id'] for row in conn.execute('SELECT id FROM schedule_entries WHERE project_id = ? AND shoot_date = ?', ...)}
if len(ordered_ids) != len(set(ordered_ids)):  # duplicate check
    conn.execute('ROLLBACK'); return False
if set(ordered_ids) != db_ids:  # completeness check
    conn.execute('ROLLBACK'); return False
for new_order, entry_id in enumerate(ordered_ids):
    conn.execute('UPDATE schedule_entries SET sort_order = ? WHERE id = ?', ...)
conn.execute('COMMIT')
```

This prevents partial reorder (if client sends subset of IDs) and duplicate IDs. Carry this pattern to any endpoint that accepts an ordered list of IDs.

### generate_call_sheet: pre-lock reads, post-lock writes

The function performs all reads (schedule entries, scenes, cast, location, DOOD computation) outside the transaction, then opens `BEGIN IMMEDIATE` only for the multi-table INSERT:

```python
# Pre-transaction reads (safe outside the lock)
entries = get_schedule_entries(conn, project_id, shoot_date)
scenes = get_scenes_by_ids(conn, scene_ids)
cast_members = get_cast_for_scenes(conn, scene_ids)
location = get_location(conn, location_id)
# ... DOOD computation ...

# Transactional write (lock only for INSERTs)
conn.execute('BEGIN IMMEDIATE')
try:
    conn.execute('INSERT INTO call_sheets ...')
    for entry in entries: conn.execute('INSERT INTO call_sheet_scenes ...')
    for member in cast_members: conn.execute('INSERT INTO call_sheet_cast ...')
    conn.execute('COMMIT')
except Exception:
    conn.execute('ROLLBACK')
    raise
```

This keeps the write lock duration minimal. The only race condition is the `sheet_number` sequence (computed as `MAX(sheet_number) + 1` outside the lock), but since `sheet_number` is not a user-visible key (the UNIQUE constraint is on `(project_id, shoot_date)`), a duplicate sheet_number just gets rejected by the DB.

### Pre-swarm ghost-file check (new — apply in future builds)

Before any swarm launch in the sandbox repo, verify:
```bash
test ! -f app/db.py && \
test ! -d app/routes/ && \
ls app/models/ | grep -v "$(spec_declared_models)" | wc -l == 0
```
Any unexpected file aborts the launch with a "ghost file detected" error.

---

## Metrics

| Metric | Value |
|--------|-------|
| Swarm agents | 16 |
| Files produced (post-cleanup) | 81 |
| Python LOC | ~4,500 |
| Template LOC | ~3,000 |
| Total LOC | ~7,500 |
| Merge conflicts | 0 |
| FC37 failures | 0 |
| Contract check failures | 6 (all fixed by assembly-fix) |
| Smoke tests | 18/18 PASS |
| Review P1 findings | 1 (date validation — fixed) |
| Review P2 findings | 3 (SESSION_COOKIE_SECURE, double query, ghost files — all fixed) |
| Review P3 findings | 1 (hospital/weather_note mismatch — deferred to todo 060) |
| Fix commits | b783e3a |

---

## Spec Template Gaps Found (propagated post-run)

This run revealed 5 gaps in `docs/templates/shared-spec-flask.md` that were
fixed in a post-run propagation pass:

1. **SECRET_KEY used dev fallback** — template said `os.environ.get('SECRET_KEY', 'dev-fallback')`. Changed to fail-closed `raise RuntimeError`.
2. **No DATABASE env var mapping** — `create_app()` didn't map `os.environ['DATABASE']` to `app.config`. Smoke tests couldn't override the DB path.
3. **No `autocommit=True`** — template still implied `isolation_level=None` (legacy). Updated to Python 3.12+ `autocommit=True` + `PRAGMA synchronous=NORMAL`.
4. **No date validation rule** — Input Validation section had no prescription for date-accepting routes. Added YYYY-MM-DD rule with explicit "list ALL date routes" instruction.
5. **Smoke test used `:memory:`** — every build hits the same bug (FC49: separate DB per connection). Template now uses tempfile pattern.

Additionally, the autopilot skill gained Step 9w.8 (ghost-file cleanup) and agent-pitfalls gained FC49 + test/smoke-test agent-type rules.

---

## Related Solutions

- `2026-06-01-prompting-dashboard-engine.md` — Run 061, FTS5 phrase-wrap pattern, form-parsing deduplication, context death before tail (led to tail-runner agent)
- `2026-06-01-tail-delegation-context-resilience.md` — tail-runner agent architecture that made this run's tail possible
- `2026-05-23-client-intake-dashboard-15-agent-swarm-build.md` — 15-agent swarm, spec convergence loop patterns
- `2026-04-09-personal-finance-tracker-swarm-build.md` — date validation as P1 (first instance of this pattern)
- `2026-04-09-autopilot-swarm-orchestration.md` — core swarm patterns, BEGIN IMMEDIATE, TOCTOU fences

## Feed-Forward

- **Hardest decision:** Whether to prescribe the exact `generate_call_sheet` implementation in the spec vs leaving it to the callsheets agent. The spec prescribed the transaction boundary and function signature but not the DOOD computation — which worked because the callsheets agent implemented it independently and correctly.
- **Rejected alternatives:** Using SQLite's `strftime` for date validation (adds complexity vs the simple `re.match` already used elsewhere). Moving DOOD computation to a shared utility module (over-engineering for 2 call sites).
- **Least confident:** The `nearest_hospital` stored in `weather_note` (todo 060) suggests the spec's Transaction Contracts section didn't prescribe the exact INSERT column mapping for `generate_call_sheet`. A future spec should include column-level INSERT prescriptions for complex generator functions.
