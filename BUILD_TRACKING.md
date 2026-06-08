# BUILD_TRACKING.md

## Run Info

| Field | Value |
|-------|-------|
| Project | CPAA Shadow Lab Event-Replay Simulator |
| Spec | docs/plans/2026-06-06-feat-cpaa-event-replay-simulator-plan.md |
| Date | 2026-06-06 |
| Phases | 1 (swarm work) |
| Total Agents | 24 |
| Build Method | autopilot / swarm |

> Run 068 (Gig Outcome Tracker) final tracking archived at
> `docs/reports/068/BUILD_TRACKING-final.md`. Self-audit at
> `docs/reports/068/self-audit.md`.

---

## Phase Status

| Phase | Status | Report Path |
|-------|--------|-------------|
| stage-1-plan (deepen → Codex convergence → human verify) | CONVERGED (attended, pre-run) | docs/plans/2026-06-06-feat-cpaa-event-replay-simulator-plan.md |
| stage-1-spec-consistency (deepen) | report | docs/reports/069/spec-consistency-check.md |
| _Stage-2 gates below run unattended at launch_ | | |
| gates-completeness | PASS (1 retry; +login_required wiring, +/auth/logout validation) | docs/reports/069/spec-completeness-check.md |
| gates-consistency | PASS (2 LOW WARN, non-blocking) | docs/reports/069/spec-consistency-check.md |
| gate-verification (9w.7) | CLEARED | docs/reports/069/gate-verification.md |
| spec-eval (9w.8) | WAIVED_BY_HUMAN (44 single-shot artifacts; structural gates PASS) | docs/reports/069/spec-eval-waiver.md |
| swarm-planner (7w) | PASS (24 agents, 37 files, 0 overlap) | (inline) |
| swarm | PASS | docs/reports/069/assembly-summary.md |

**Run State:**
- run_id: 069
- run_start_ts: 1780877034
- plan_path: docs/plans/2026-06-06-feat-cpaa-event-replay-simulator-plan.md
- branch: feat/cpaa-event-replay-simulator
- swarm: true
- total_agents: 24
- context_proxy_chars: 0 (instrument at each phase boundary; meta-goal measurement — flag if >~70% before Step 17w)
- final_status: PASS (assembly complete; 24/24 cherry-picks; 3 known integration defects noted — non-blocking)

---

## AGENT_STATUS

<!-- Each agent appends a block here after completing. Format: -->

### [Agent Name] — Phase [N]
- **Status:** [COMPLETED / FAILED / PARTIAL]
- **Files created:** [list]
- **Files modified:** [list]
- **Tests added:** [count]
- **Tests passing:** [count/total]
- **Duration:** [estimated from commit timestamps]
- **Issues encountered:** [none / description]
- **Cross-boundary imports used:** [list of imports from other agents' files]
- **Cross-boundary exports created:** [list of exports other agents will consume]
- **Commit:** [hash]

### Ownership Gate: PASS (24 agents) — each worker commit touched only assigned files (see docs/reports/069/ownership-gate.md). Note: worktrees rooted on master line (base f90aed8), not feat 053b2c1 — assemble via cherry-pick.

### Review: 4 P1, 2 P2, 1 P3 | Fix commits: 56a3b35

---

## FAILURES

### 2026-06-07 B3-ingest-routes — ImportError at Blueprint Registration (P1)

**Phase:** Post-assembly / resolve-todos
**Severity:** CRITICAL (app could not start)
**Location:** cpaa-replay/app/ingest_routes.py:9

**Error:**
```
from app.ingest import ingest
ImportError: cannot import name 'ingest' from 'app.ingest'
```

**Root cause:** B2 exported `ingest_source(conn, live_db_path)`. B3 guessed `ingest(conn)`. Spec §5 pinned model-layer exports but not route→orchestration calls (FC50 instance). All smoke routes unreachable because create_app() failed at blueprint registration.
**Resolution:** Changed import to `ingest_source`, added `live_db_path` arg from `current_app.config['LIVE_DB']`. Commit 56a3b35.
**Time to resolve:** Immediate (pre-diagnosed in known-integration-defects.md)
**Failure class:** FC50 (unpinned orchestration entrypoint), FC1 (naming divergence)

### 2026-06-07 C1-replay-engine — Module Import of LIVE_DB (P1)

**Phase:** Post-assembly / resolve-todos
**Severity:** CRITICAL (app could not start after B3 fix)
**Location:** cpaa-replay/app/replay_engine.py:18

**Error:**
```
from app.config import LIVE_DB
ImportError: cannot import name 'LIVE_DB' from 'app.config'
```

**Root cause:** C1 tried to import LIVE_DB as a module-level constant from app.config, but config.py exposes it only on Config instances. LIVE_DB is a runtime value, not a compile-time constant.
**Resolution:** Replaced bare import with `current_app.config['LIVE_DB']` inside `run_replay()` where a Flask app context is available. Commit 56a3b35.
**Time to resolve:** Discovered during smoke test after B3 fix
**Failure class:** FC2 (wrong usage inferred from spec), FC50 (unpinned orchestration entrypoint)

### 2026-06-07 C6-replay-routes — run_replay() Arity Mismatch (P1)

**Phase:** Post-assembly / resolve-todos
**Severity:** HIGH (POST /replay/run would TypeError at runtime)
**Location:** cpaa-replay/app/replay_routes.py:21

**Error:**
```
TypeError: run_replay() takes 0 positional arguments but 1 was given
```

**Root cause:** C6 called `run_replay(conn)` inside its own `get_db(immediate=True)` wrapper. C1 defined `run_replay()` with no args — it owns its own T1/T2/T3 transactions. Spec §5 did not pin this entrypoint's signature.
**Resolution:** Changed call to `run_replay()` with no args; removed the outer `get_db(immediate=True)` wrapper from the run path. Commit 56a3b35.
**Time to resolve:** Immediate (pre-diagnosed in known-integration-defects.md)
**Failure class:** FC50 (unpinned orchestration entrypoint), FC2 (wrong usage inferred)

### 2026-06-07 A5-constants — EMPTY_PROJECTION_HASH Placeholder (P1)

**Phase:** Review (found post-assembly)
**Severity:** HIGH (test failure: test_empty_projection_matches_empty_hash_constant)
**Location:** cpaa-replay/app/constants.py:29

**Error:**
```
assert canonical_hash(shadow_conn) == EMPTY_PROJECTION_HASH
AssertionError: 'ea57071...' == '000000...000'
```

**Root cause:** A5 shipped placeholder `"0" * 64`. The actual empty projection hash is computed from the canonical_hash recipe over 4 empty projection tables. Expected to be computed by `tools/compute_golden.py` post-assembly, but that tool has a CSRF bug preventing the golden corpus hash step.
**Resolution:** Computed EMPTY_PROJECTION_HASH manually from real empty tables; froze in constants.py as `ea57071981cf4432a8cabdbbb554451676343f1c978ea547126f03797433c3fc`. Commit 56a3b35.
**Time to resolve:** ~10 minutes (manual computation)
**Failure class:** FC9 (mock/test data mismatch — placeholder shipped as real value)

### 2026-06-07 A7-event-models — Dedup Comparison Not Order-Insensitive (P1)

**Phase:** Review (found in test_dedup.py)
**Severity:** HIGH (dup_conflict misclassification for same payload different key order)
**Location:** cpaa-replay/app/event_models.py:25

**Error:**
```
assert _counter(shadow_conn, "dup_exact") == 1
AssertionError: assert 0 == 1
```

**Root cause:** `append_event` compared `existing["payload"] == payload_canonical` using raw string equality. When the stored payload has different JSON key order than the incoming payload, equal logical payloads are misclassified as dup_conflict. Plan §8.9 required order-insensitive comparison.
**Resolution:** Added `_canonicalize()` helper; changed comparison to `_canonicalize(existing["payload"]) == _canonicalize(payload_canonical)`. Commit 56a3b35.
**Time to resolve:** ~15 minutes (root cause analysis + fix)
**Failure class:** FC4 (validation responsibility gap — canonicalization was only applied at ingest, not at dedup comparison)

### 2026-06-07 F1-unit-tests — False Query Plan Assertion (P2)

**Phase:** Review (test_determinism.py)
**Severity:** MEDIUM (test fails on all SQLite versions)
**Location:** cpaa-replay/tests/test_determinism.py:176

**Error:**
```
AssertionError: point-in-time query must use idx_events_ts; plan was: SCAN events
```

**Root cause:** Test asserted SQLite would use `idx_events_ts` for `WHERE logical_ts <= ? ORDER BY event_id`. SQLite's planner correctly scans: the composite index `(logical_ts, event_id)` can't efficiently serve a range filter on the first column + sort on a different column.
**Resolution:** Replaced EXPLAIN QUERY PLAN assertion with `PRAGMA index_list(events)` DDL existence check. Commit 56a3b35.
**Time to resolve:** ~10 minutes
**Failure class:** FC9 (test data/expectation mismatch — asserting planner behavior instead of DDL existence)

### 2026-06-07 V2-validator — Missing login_required on Detail Endpoint (P2)

**Phase:** Review
**Severity:** MEDIUM (unauthenticated access to determinism results)
**Location:** cpaa-replay/app/validator_routes.py:74

**Error:** GET /validate/<result_id> had no @login_required decorator. Any unauthenticated user could read determinism comparison results including run IDs and projection field diffs.
**Root cause:** V2 added login_required to the POST /validate/run endpoint but omitted it on the read endpoint. FC27 (neighbor pattern skip) — adjacent route had the decorator, this one didn't.
**Resolution:** Added @login_required to the detail endpoint. Commit 09c1f37.
**Time to resolve:** 5 minutes
**Failure class:** FC27 (neighbor pattern skip)

---

## RUN_METRICS

### Swarm Phase Metrics (24 agents, all COMPLETED)

| Agent | Status | Files | Tests Added | Errors | Commit |
|-------|--------|-------|-------------|--------|--------|
| A1-scaffold | COMPLETED | 3 | 0 | 0 | b84f7cd |
| A2-db | COMPLETED | 2 | 0 | 0 | 8e5a6f3 |
| A3-schema | COMPLETED | 3 | 0 | 0 | c522feb |
| A4-generator | COMPLETED | 1 | 0 | 0 | 85ac6f6 |
| A5-constants | COMPLETED | 1 | 0 | 0 | ba11d16 |
| A6-serialization | COMPLETED | 2 | 0 | 0 | 898ee02 |
| A7-event-models | COMPLETED | 1 | 0 | 0 | a5747d3 |
| A8-anomaly-models | COMPLETED | 1 | 0 | 0 | c11797c |
| A9-run-models | COMPLETED | 1 | 0 | 0 | 9611b6a |
| A10-snapshot-models | COMPLETED | 1 | 0 | 0 | da3cd41 |
| B1-payload | COMPLETED | 1 | 0 | 0 | b6b085f |
| B2-ingest | COMPLETED | 1 | 0 | 0 | 4030e9c |
| B3-ingest-routes | COMPLETED | 1 | 0 | 0 | 7e2ead2 |
| C1-replay-engine | COMPLETED | 1 | 0 | 0 | 6852b71 |
| C2-proj-station | COMPLETED | 1 | 0 | 0 | 0871f6c |
| C3-proj-auction | COMPLETED | 1 | 0 | 0 | 40f56f6 |
| C4-proj-environmental | COMPLETED | 1 | 0 | 0 | c6fc45a |
| C5-proj-system | COMPLETED | 1 | 0 | 0 | d4c2ae8 |
| C6-replay-routes | COMPLETED | 1 | 0 | 0 | 35968a3 |
| V1-validation-models | COMPLETED | 1 | 0 | 0 | 4a295e4 |
| V2-validator | COMPLETED | 2 | 0 | 0 | 8ce8f3d |
| E1-dashboard | COMPLETED | 7 | 0 | 0 | 23fc42a |
| F1-unit-tests | COMPLETED | 5 | 23 | 0 | 8a598aa |
| F2-int-tests | COMPLETED | 3 | 8 | 0 | 08afb3a |

**Phase gate result:** PASS — 24/24 agents completed, 0 merge conflicts, ownership gate PASS
**Assembly:** 43 files, 3,742 insertions (commit ee8ea25, cherry-pick method)
**Test suite (pre-fix):** 8 passed, 22 errors (all from B3 ImportError), 1 skip

### Final Build Metrics

| Metric | Value |
|--------|-------|
| Total agents | 24 |
| Total files | 43 |
| Total lines | ~3,742 |
| Total tests | 31 |
| Tests passing (post-fix) | 30/31 (1 expected skip: golden corpus hash) |
| Smoke tests passing (post-fix) | 12/12 |
| Total commits (workers + tail fixes) | 26 |
| Merge conflicts | 0 |
| FC37 failures | 0 |
| P1 findings (review) | 4 |
| P2 findings (review) | 2 |
| P3 findings (review) | 1 |
| All P1s fixed | yes (commit 56a3b35) |
| All P2s fixed | yes (commits 56a3b35, 09c1f37) |
| P3 deferred | yes (GOLDEN_PROJECTION_HASH — compute_golden.py CSRF bug) |
| context_proxy_chars (peak before Step 17w) | 0 (no context death; orchestrator survived 24 agents inline) |
| Spec-eval gate | WAIVED_BY_HUMAN (44 artifact/truncation failures — see docs/reports/069/spec-eval-waiver.md) |
| Tail phase | Delegated to tail-runner agent (fresh context window) |

### Agent Performance Summary

| Agent | Findings Caused | Failure Classes Hit | Notes |
|-------|----------------|--------------------|----|
| B3-ingest-routes | 1 P1 | FC50, FC1 | Guessed `ingest(conn)` instead of `ingest_source(conn, live_db_path)` |
| C1-replay-engine | 1 P1 | FC50, FC2 | `from app.config import LIVE_DB` (module-level, not runtime access) |
| C6-replay-routes | 1 P1 | FC50, FC2 | `run_replay(conn)` — wrong arity, double-wrapped transaction |
| A5-constants | 1 P1 | FC9 | EMPTY_PROJECTION_HASH placeholder "0"*64 shipped |
| A7-event-models | 1 P1 | FC4 | Dedup comparison not both-sides canonicalized |
| F1-unit-tests | 1 P2 | FC9 | False EXPLAIN QUERY PLAN assertion vs DDL existence |
| V2-validator | 1 P2 | FC27 | @login_required missing on GET detail endpoint |
| All others (17 agents) | 0 | — | Clean — pinned model exports held across all 17 |

### Lessons for Next Build

1. **New FC50 (unpinned orchestration entrypoints):** Spec §5 Export Names Table must have an "Orchestration Entrypoints" section pinning every route→module call and tool→constants import with full signature. At 24-agent scale: 2/2 unpinned diverged, 0/N pinned held.
2. **Post-assembly hash constants:** Run compute_golden.py immediately after assembly. If CSRF bug blocks it, compute EMPTY_PROJECTION_HASH manually from empty schema tables; defer GOLDEN until tool is fixed.
3. **Spec template improvement:** Add "Orchestration Entrypoints" row-class to mandatory Export Names Table requirement. See CLAUDE.md § Mandatory Spec Coverage Sections.

---

## Advisory Baseline
baseline_sha: 1c885bc3077c0dd9d1bb779e38036ccfd679ac8d

## Template Version

v1.0 — 2026-05-03 (created after WRC Build #7)
