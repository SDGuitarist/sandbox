---
title: "Feature Flag Management Service"
type: feat
status: draft
date: 2026-04-05
origin: docs/brainstorms/2026-04-05-feature-flag-service.md
feed_forward:
  risk: "Cycle detection in the dependency DAG uses DFS from the new node. Must verify DFS correctly handles diamonds (A→B, A→C, B→D, C→D) without false positives, and detects all true cycles without false negatives."
  verify_first: true
---

# feat: Feature Flag Management Service

## Enhancement Summary

**Deepened on:** 2026-04-05
**Research agents used:** solution-doc-searcher (api-key-manager, chat, audit-log, task-scheduler, url-shortener)

### Key Corrections From Research
- `hashlib.sha256` not `random` or Python's built-in `hash()` (salted per-process in Python 3.3+) for deterministic percentage rollout
- `UPDATE flags SET eval_count = eval_count + 1` atomic SQL — never read-modify-write in Python
- `init_db` must use raw `sqlite3.connect()` + `executescript()`, NOT `get_db` — implicit COMMIT footgun
- `db_path` through `current_app.config.get("DB_PATH")` in every route
- Timestamps as `YYYY-MM-DD HH:MM:SS`; `max(1, min(limit, 200))` for pagination

## What Must Not Change

1. **Deterministic percentage rollout** — `int(hashlib.sha256(f"{flag_key}:{user_id}".encode()).hexdigest(), 16) % 100` — never use `random`, never use Python's `hash()`
2. **Atomic eval_count increment** — `UPDATE flags SET eval_count = eval_count + 1 WHERE key = ?` in SQL, never read-modify-write in Python
3. **Cycle detection at write time** — adding a dependency that creates a cycle must be rejected with 409 before committing
4. **Evaluation rule priority order** — disabled → environment → dependencies → allowlist → percentage → default (this order cannot change)
5. **Timestamps** — `YYYY-MM-DD HH:MM:SS` format everywhere
6. **db_path routing** — always via `current_app.config.get("DB_PATH")`

## Prior Phase Risk

> "Cycle detection in the dependency DAG uses DFS from the new node. Must verify DFS correctly handles diamonds (A→B, A→C, B→D, C→D) without false positives, and detects all true cycles without false negatives."

**Resolution:** Write `tests/test_flags_deps.py` with explicit test cases FIRST:
- Linear chain: A→B→C (no cycle)
- Diamond: A→B, A→C, B→D, C→D (no cycle — D has two paths to it)
- True cycle: A→B→C→A (must be detected)
- Self-cycle: A→A (must be detected)
- Adding edge D→A to diamond (creates cycle D→A→B→D — must be detected)

DFS implementation: starting from the **proposed new dependency node** (not the flag being updated), walk all its dependencies transitively. If we reach the flag being updated, we have a cycle.

**Verify first action:** Write `test_cycle_detection_*` tests covering all 5 cases before implementing any route.

## Smallest Safe Plan

### Phase 1: Database layer
**Files in scope:** `flags/schema.sql`, `flags/db.py`

- `flags/schema.sql`: `flags` table + `flag_dependencies` table with CASCADE delete
- `flags/db.py`:
  - `get_db(path, immediate)` — context manager, WAL, row_factory
  - `init_db(path)` — raw connection with executescript
  - `create_flag(key, name, description, enabled, default_enabled, environments, allowlist, percentage, db_path)` → flag dict; raises IntegrityError on duplicate key
  - `get_flag(key, db_path)` → flag dict or None
  - `list_flags(db_path)` → list of flag dicts
  - `update_flag(key, updates_dict, db_path)` → updated flag dict or None
  - `delete_flag(key, db_path)` → True/False
  - `add_dependency(flag_key, depends_on_key, db_path)` → True; raises ValueError on cycle, IntegrityError on duplicate
  - `remove_dependency(flag_key, depends_on_key, db_path)` → True/False
  - `get_dependencies(flag_key, db_path)` → list of dep keys
  - `_detect_cycle(flag_key, new_dep_key, conn)` → bool (True = cycle detected); private, called inside add_dependency transaction
  - `evaluate_flag(flag_key, user_id, environment, db_path, _depth)` → `{enabled: bool, reason: str, flag: key}`; increments eval_count atomically; depth limit 10
  - `_hash_bucket(flag_key, user_id)` → int 0-99; uses sha256

**Gate:** `tests/test_flags_deps.py` and `tests/test_flags_db.py` pass before any routes.

### Phase 2: Flask routes
**Files in scope:** `flags/routes.py`, `flags/app.py`, `flags/__init__.py`

- `POST /flags` body: `{key, name, description?, enabled?, default_enabled?, environments?, allowlist?, percentage?}` → 201; 400 missing fields; 409 duplicate key
- `GET /flags` → 200 `{flags: [...]}`
- `GET /flags/<key>` → 200 flag dict; 404 not found
- `PATCH /flags/<key>` body: any subset of mutable fields → 200 updated flag; 404 not found; 400 bad values
- `DELETE /flags/<key>` → 204; 404 not found
- `POST /flags/<key>/evaluate` body: `{user_id, environment?}` → 200 `{enabled, reason, flag_key, eval_count}`; 404 not found
- `POST /flags/<key>/dependencies` body: `{depends_on_key}` → 201; 404 flag not found; 409 cycle or duplicate
- `DELETE /flags/<key>/dependencies/<dep_key>` → 204; 404 not found

**Gate:** All 8 routes return correct HTTP status codes.

### Phase 3: Tests
**Files in scope:** `tests/test_flags_deps.py`, `tests/test_flags_db.py`, `tests/test_flags_routes.py`

**Gate:** `pytest tests/test_flags_*.py -v` passes.

## Rejected Options

- **Random per-evaluation:** Non-deterministic — same user gets different results. Broken by definition.
- **Persistent user assignment table:** Unbounded storage; overkill when hash-based assignment works.
- **Cycle detection at read time:** O(depth) on every evaluate call; runtime DFS for every evaluation is expensive; better to validate once at write time.
- **MD5 for hash bucket:** Acceptable but weaker collision resistance; using SHA-256 to match industry practice.

## Risks And Unknowns

1. **DAG cycle detection correctness** — covered by verify-first tests
2. **JSON fields in SQLite** — `environments` and `allowlist` stored as JSON strings; must parse/validate at route layer before storage
3. **Percentage validation** — must be 0-100 integer or null; `None` means disabled (no percentage check)
4. **`update_flag` partial update** — PATCH must only update provided fields; build dynamic SQL with only the changed columns
5. **Dependency evaluation recursion depth** — capped at 10; return `{enabled: false, reason: "max_depth_exceeded"}` if breached

## Most Likely Way This Plan Is Wrong

The cycle detection DFS may have an off-by-one in the direction of traversal. The DFS must walk from `new_dep_key` **following its existing dependencies** (not its dependents). If we reach `flag_key` during this walk, adding the edge `flag_key → new_dep_key` would create a cycle. The common mistake is traversing in the wrong direction (walking dependents instead of dependencies). The verify-first tests catch this.

## Scope Creep Check

Not included (not in brainstorm):
- Authentication / API keys
- Flag versioning or audit history
- A/B test result tracking beyond eval_count
- Webhook notifications on flag change
- UI / dashboard

## Acceptance Criteria

- [ ] `POST /flags` with valid body returns 201 with flag JSON
- [ ] `POST /flags` with duplicate key returns 409
- [ ] `GET /flags/<key>` returns flag; unknown key returns 404
- [ ] `PATCH /flags/<key>` updates only provided fields
- [ ] `DELETE /flags/<key>` returns 204; subsequent GET returns 404
- [ ] `POST /flags/<key>/evaluate` with disabled flag returns `{enabled: false, reason: "disabled"}`
- [ ] `POST /flags/<key>/evaluate` with env mismatch returns `{enabled: false, reason: "environment_mismatch"}`
- [ ] `POST /flags/<key>/evaluate` with user in allowlist returns `{enabled: true, reason: "allowlist"}`
- [ ] `POST /flags/<key>/evaluate` percentage=100 returns `{enabled: true, reason: "percentage"}`
- [ ] `POST /flags/<key>/evaluate` percentage=0 returns `{enabled: false, reason: "percentage"}`
- [ ] `POST /flags/<key>/evaluate` increments eval_count by 1
- [ ] Same user evaluated 10 times gets same result (determinism check)
- [ ] `POST /flags/<key>/dependencies` adding cycle returns 409
- [ ] `POST /flags/<key>/dependencies` diamond DAG (no cycle) succeeds
- [ ] Flag B disabled if dependency flag A is disabled
- [ ] `DELETE /flags/<key>/dependencies/<dep>` returns 204

## Tests Or Checks

```bash
pytest tests/test_flags_deps.py tests/test_flags_db.py tests/test_flags_routes.py -v
grep -rn "hash(" flags/  # should find no Python built-in hash() calls
```

## Rollback Plan

New module in `/workspace/flags/`. Rollback = delete `flags/` directory and `tests/test_flags_*.py`. No shared state.

## Claude Code Handoff Prompt

```text
Read docs/plans/2026-04-05-feat-feature-flag-service-plan.md.

PREREQUISITE: Write tests/test_flags_deps.py with cycle detection tests
(linear chain, diamond, true cycle, self-cycle, adding edge that creates cycle)
BEFORE implementing any routes.

Files in scope:
  - flags/schema.sql
  - flags/db.py
  - flags/routes.py
  - flags/app.py
  - flags/__init__.py
  - run_flags.py
  - tests/test_flags_deps.py
  - tests/test_flags_db.py
  - tests/test_flags_routes.py

Scope boundaries:
  - DO NOT use Python's built-in hash() — use hashlib.sha256
  - DO NOT use random for percentage rollout
  - DO NOT add authentication
  - eval_count increment must be atomic SQL (UPDATE ... SET count = count + 1)
  - init_db must use raw sqlite3.connect, not get_db

Acceptance criteria: (see plan)

Required checks:
  pytest tests/test_flags_*.py -v
  grep -rn "hash(" flags/
```

## Sources

- Brainstorm: docs/brainstorms/2026-04-05-feature-flag-service.md

## Feed-Forward

- **Hardest decision:** Evaluation rule priority order. Chose: disabled → environment → dependencies → allowlist → percentage → default. The key question was whether allowlist should override environment targeting — decided yes (if you're explicitly allowlisted, environment doesn't matter).
- **Rejected alternatives:** Random per-evaluation, persistent assignment table, runtime cycle detection.
- **Least confident:** The `update_flag` dynamic SQL builder — building a partial PATCH from a dict of only-provided fields requires careful parameterization to avoid SQL injection. Must use a whitelist of allowed column names.
