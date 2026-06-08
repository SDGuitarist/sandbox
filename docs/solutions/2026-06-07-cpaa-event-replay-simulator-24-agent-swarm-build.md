---
title: "CPAA Shadow Lab Event-Replay Simulator: 24-Agent Swarm Validates 2× Scale Ceiling"
date: 2026-06-07
run_id: "069"
category: swarm-build
severity: none
problem_type: feature-build / architecture-validation
tags:
  - swarm-build
  - 24-agent
  - flask
  - sqlite3
  - jinja2
  - event-sourcing
  - determinism-validation
  - canonical-hash
  - context-death
  - delegation-architecture
  - spec-eval-gate
  - architecture-validation
  - cpaa
  - shadow-lab
components:
  - cpaa-replay/app/__init__.py
  - cpaa-replay/app/constants.py
  - cpaa-replay/app/serialization.py
  - cpaa-replay/app/event_models.py
  - cpaa-replay/app/run_models.py
  - cpaa-replay/app/snapshot_models.py
  - cpaa-replay/app/validation_models.py
  - cpaa-replay/app/replay_engine.py
  - cpaa-replay/app/ingest.py
  - cpaa-replay/app/validator.py
  - cpaa-replay/app/ingest_routes.py
  - cpaa-replay/app/replay_routes.py
  - cpaa-replay/app/validator_routes.py
  - cpaa-replay/app/dashboard_routes.py
  - cpaa-replay/schema/shadow_schema.sql
  - cpaa-replay/tools/compute_golden.py
root_cause: >
  Primary goal: build a shadow-lab event-replay simulator (Flask + SQLite
  + Jinja2, 24 agents, 43 files, ~3742 LOC) with append-only event log,
  deterministic projection reconstruction, and a determinism-validation
  harness. Secondary goal: validate the 3-stage delegation architecture at
  2× the prior validated ceiling (12 → 24 agents) and measure orchestrator
  context pressure. KEY FINDING: every cross-cluster entrypoint left UNPINNED
  by the spec diverged at scale (2/2 unpinned diverged; 0/N pinned diverged).
resolution: >
  All 24 agents completed with 0 merge conflicts (disjoint file sets, cherry-
  pick assembly). 5 post-assembly defects fixed in resolve-todos (4 P1 + 1 P2):
  2 pre-diagnosed cross-cluster wiring gaps (ingest import name + replay arity),
  1 wrong EMPTY_PROJECTION_HASH placeholder, 1 dedup canonicalization gap,
  1 missing login_required on validator detail endpoint. Smoke 12/12 PASS,
  tests 30/30 PASS (1 expected skip: golden corpus hash deferred). Orchestrator
  survived all 24 inline spawns + 4 pre-swarm gates with no context death.
review_findings:
  p1_count: 4
  p2_count: 2
  p3_count: 1
  all_p1_fixed: true
  all_p2_fixed: true
  fix_commits:
    - "56a3b35"
    - "09c1f37"
related_runs:
  - "068"
  - "067"
  - "065"
failure_class: "FC1/FC2 (unpinned cross-cluster entrypoints)"
recurrence_risk: medium
predecessor: docs/solutions/2026-06-06-gig-outcome-tracker-12-agent-swarm-build.md
---

# CPAA Shadow Lab Event-Replay Simulator: 24-Agent Swarm Validates 2× Scale Ceiling

## Problem / Goal

Build a shadow-lab event-replay simulator for CPAA (Pacific Flow Entertainment)
as a 24-agent swarm, and use it to validate the autopilot architecture at 2×
the previously validated ceiling. The prior proven ceiling was 12 agents (Run
068). The question: do inline deepening + 24-agent worker spawn cause orchestrator
context death?

The Feed-Forward risk from the plan: "Inline deepening + worker spawn may saturate
orchestrator context at 20-25 agents — unproven above 12. PLUS the cross-section
P0 class (canonical-hash byte recipe, run-lock atomicity + reaper, NON_DETERMINISTIC
as comparison-result-not-run-status, and the live-hash writer/isolation) that
single-section review misses."

## What Was Built

Flask app-factory + SQLite (stdlib `sqlite3`, Python 3.14) + Jinja2. 24 agents,
43 files, ~3742 LOC of new application code.

### Domain Model

An **append-only event log** that ingests CPAA gala telemetry from a read-only
`live.db` corpus (1,595 synthetic events, `seed=42`, 2026-06-15 gala) into a
writable `shadow.db`, then replays them deterministically:

- **source_events** — immutable corpus in live.db (READ-ONLY forever)
- **events** — shadow append log with dedup (INSERT OR IGNORE + dup_exact/dup_conflict
  classification via `dedup_counters` and `anomalies`)
- **station_state / auction_state / environmental_state / system_state** — four
  projection tables, each owned by a single handler module
- **replay_runs** — state machine: `{PENDING, RUNNING, COMPLETE_PASS, ABORTED}`
  (NON_DETERMINISTIC is a comparison *result*, not a run status)
- **projection_snapshots** — persisted per-run projection for field-level diffing
- **determinism_results / determinism_diffs** — validator verdict + per-field diff

### Agent Assignment (24 agents, disjoint file sets)

| Cluster | Agent | Files |
|---------|-------|-------|
| A | A1-scaffold | app/__init__.py, auth_bp, config.py |
| A | A2-db | db.py (get_db, open_live_ro), live_guard.py |
| A | A3-schema | shadow_schema.sql, live_schema.sql, init_db.py |
| A | A4-generator | tools/generate_source.py |
| A | A5-constants | app/constants.py |
| A | A6-serialization | app/serialization.py, tools/compute_golden.py |
| A | A7-event-models | app/event_models.py |
| A | A8-anomaly-models | app/anomaly_models.py |
| A | A9-run-models | app/run_models.py |
| A | A10-snapshot-models | app/snapshot_models.py |
| B | B1-payload | app/payload.py |
| B | B2-ingest | app/ingest.py |
| B | B3-ingest-routes | app/ingest_routes.py |
| C | C1-replay-engine | app/replay_engine.py |
| C | C2-proj-station | app/proj_station.py |
| C | C3-proj-auction | app/proj_auction.py |
| C | C4-proj-environmental | app/proj_environmental.py |
| C | C5-proj-system | app/proj_system.py |
| C | C6-replay-routes | app/replay_routes.py |
| V | V1-validation-models | app/validation_models.py |
| V | V2-validator | app/validator.py, app/validator_routes.py |
| E | E1-dashboard | app/dashboard_routes.py + 6 Jinja2 templates |
| F | F1-unit-tests | conftest.py, test_dedup.py, test_determinism.py, test_patch_semantics.py |
| F | F2-int-tests | test_pointintime.py, test_isolation.py, smoke_test.py |

## Key Technical Decisions

### 1. NON_DETERMINISTIC is a comparison result, not a run status

The state machine has exactly four states: `{PENDING, RUNNING, COMPLETE_PASS, ABORTED}`.
A determinism verdict lives in `determinism_results.match` (0 = mismatch, 1 = match),
NOT in the run's status column. This matters because the original brainstorm assumed
`NON_DETERMINISTIC` was a run state, which would have created a validator-writes-replay_runs
ownership contradiction.

```python
# WRONG (original brainstorm assumption):
replay_runs.status = 'NON_DETERMINISTIC'  # ← contradiction: validator would write run_models' table

# CORRECT (frozen decision):
determinism_results.match = 0             # ← validator's own table; run stays COMPLETE_PASS
```

### 2. Canonical hash byte recipe (§8.8, RFC 8785-aligned)

The projection hash is deterministic across runs. The recipe:

```python
# Only hashes the 4 projection tables in FIXED ORDER from _PROJECTION_TABLES
# NEVER includes: replay_runs, events, anomalies, projection_snapshots, dedup_counters
# Byte-level recipe:
UNIT_SEP = b"\x1f"
RECORD_SEP = b"\x1e"
ROW_SEP = b"\x00"

# Per table: header = table_name + UNIT_SEP + str(row_count)
# Zero rows → just header; else → header + ROW_SEP + ROW_SEP.join(row_jsons)
# Row JSON: sort_keys=True, separators=(",",":"), ensure_ascii=False, allow_nan=False
# Final payload: RECORD_SEP.join(blocks)
# Hash: hashlib.sha256(payload).hexdigest()
```

**Critical lesson:** `EMPTY_PROJECTION_HASH` is NOT `"0" * 64`. It must be computed
from real empty projection tables. The actual value is:
`ea57071981cf4432a8cabdbbb554451676343f1c978ea547126f03797433c3fc`

A5 shipped a placeholder `"0" * 64` because the constant is computed post-assembly
by `tools/compute_golden.py`. This is the expected assembly gap, documented in
known-integration-defects.md §DEFECT 3 — but the review found it and froze the
correct value into `constants.py`.

### 3. Run-lock atomicity (single guarded INSERT)

The run-lock is a single atomic INSERT with a NOT EXISTS guard:

```python
cur = conn.execute(
    "INSERT INTO replay_runs(run_id, status, started_at) "
    "SELECT ?, 'RUNNING', datetime('now') "
    "WHERE NOT EXISTS (SELECT 1 FROM replay_runs WHERE status = 'RUNNING')",
    (run_id,),
)
acquired = cur.rowcount == 1
```

The reaper (`reap_stale_runs`) runs BEFORE the lock attempt in T1, within the same
`BEGIN IMMEDIATE` transaction, so stale RUNNING rows can't block the guard.

### 4. 3-transaction replay sequence (T1/T2/T3)

```
T1: BEGIN IMMEDIATE → reap_stale + start_run (guarded INSERT) → COMMIT
    (T1 commits so a concurrent 409 path can read the RUNNING row)

T2: BEGIN IMMEDIATE → live_hash_pre → reset_* → apply_all → write_snapshot
    → canonical_hash → live_hash_post → mark_complete_pass → COMMIT

T3: IF T2 raises: BEGIN IMMEDIATE → mark_aborted → COMMIT
```

T2 uses `current_app.config['LIVE_DB']` (not a bare module import) because
`run_replay()` is called inside a Flask request context. Agent C1 incorrectly
imported `LIVE_DB` from `app.config` as a module-level constant — the fix was
to use `current_app.config['LIVE_DB']` inside the function.

### 5. Live-hash isolation proof

Two hash bookends prove live.db did not change during a replay:

```python
live_hash_pre  = live_content_hash(open_live_ro(live_db_path))  # before reset
# ... reset + apply_all ...
live_hash_post = live_content_hash(open_live_ro(live_db_path))  # after mark_complete_pass
```

`live_content_hash` hashes the CONTENT (via SQL query over source_events), NOT
the file bytes. This makes it stable across WAL/checkpoint differences. The validator
checks `pre == post AND post == current_live` before recording any verdict — fails
closed.

### 6. Dedup canonicalization (append_event)

The dedup comparison must be order-insensitive. `append_event` receives
`payload_canonical` (pre-canonicalized by the ingest layer in production), but
the comparison path must also work when payloads weren't pre-canonicalized:

```python
def _canonicalize(payload: str) -> str:
    try:
        return json.dumps(json.loads(payload), sort_keys=True,
                         separators=(",",":"), ensure_ascii=False, allow_nan=False)
    except (ValueError, TypeError):
        return payload

# In append_event dedup path:
if _canonicalize(existing["payload"]) == _canonicalize(payload_canonical):
    # dup_exact
else:
    # dup_conflict
```

Both sides are canonicalized before comparison. This caught a test failure where
agent F1's `test_canonical_payload_comparison_is_order_insensitive` called
`append_event` directly (bypassing the ingest layer) with non-canonical payloads.

## Cross-Cluster Integration Defects (the Meta-Goal Finding)

### The 2-of-2 Rule: Every Unpinned Entrypoint Diverged

This is the run's KEY FINDING, confirmed at 24-agent scale:

| Entrypoint | Spec §5/§6 pinned? | Diverged? | How |
|---|---|---|---|
| `ingest_source(conn, live_db_path)` | NO — only model-layer exports pinned | YES | B3 called `ingest()` (no-exist); B2 exported `ingest_source` |
| `run_replay()` (0 args) | NO — only model-layer exports pinned | YES | C6 called `run_replay(conn)` (wrong arity); C1 defined no-arg |
| All model-layer exports in §5 | YES | NO | All 24 agents used the exact pinned names |

**Conclusion:** The spec's Export Names Table (§5) exhaustively pinned model-layer
exports. EVERY name §5 explicitly pinned held clean across all 24 agents (0 of N
diverged). EVERY route→orchestration entrypoint left UNPINNED diverged (2 of 2).
This is a clean FC1/FC2 confirmation at 24-agent scale.

**Carry-forward:** Specs must pin route→orchestration and tool→constants entrypoint
names+signatures, not just model-layer exports. Add an "Orchestration Entrypoints"
row-class to the Export Names Table requirement.

### The Two Pre-Diagnosed P1 Defects

**DEFECT 1 (B2↔B3, app-breaking at import):**
```python
# B3 wrote (wrong — 'ingest' doesn't exist):
from app.ingest import ingest
ingest(conn)

# Fix (B2's signature is authoritative):
from app.ingest import ingest_source
ingest_source(conn, current_app.config['LIVE_DB'])
```
This ImportError cascaded to create_app() failure — the entire app failed to start.

**DEFECT 2 (C1↔C6, runtime TypeError):**
```python
# C6 wrote (wrong — run_replay owns its own T1/T2/T3 connections):
with get_db(immediate=True) as conn:
    run_id, acquired = run_replay(conn)

# Fix (C1's signature is authoritative; route drops the outer context manager):
run_id, acquired = run_replay()
```

### Additional Review-Found P1s

**DEFECT 3a (EMPTY_PROJECTION_HASH wrong value):**
A5 shipped placeholder `"0" * 64`. Real value: `ea57071981cf...` (computed from
empty projection tables via canonical hash recipe). Fixed by computing from real
tables and freezing in constants.py.

**DEFECT 3b (dedup comparison not order-insensitive):**
`append_event` compared raw stored payload against raw incoming payload. When
called with non-canonical input, equal-payload-different-order was misclassified
as `dup_conflict`. Fixed by canonicalizing both sides before comparison.

## Architecture Validation Results

### Orchestrator Context (the Meta-Goal measurement)

24 agents spawned inline. No context death. No manual resume. Orchestrator survived:
- 11-agent deepening (Step 6)
- 4 pre-swarm gates (completeness, consistency, verification, spec-eval)
- 24 worker spawns + cherry-pick assembly
- Tail delegation (tail-runner in fresh context window)

**Verdict:** 24-agent inline spawn PASSES. The 12-agent ceiling from Run 068 was a
conservative lower bound — the architecture handles 2× without saturation.

### Spec-Eval Gate (9w.8) — WAIVED_BY_HUMAN

The spec-eval gate returned FAIL (111/155 claims passed; 44 failed). Analysis:
- 18 failures: empty evidence (harness produced no scorable code)
- 15 failures: truncated single-shot output (1024-token cutoff artifacts)
- 11 failures: spec-COMPLIANT behavior misscored (e.g., `:memory:` throwaway for
  `build_projection_at` is explicitly allowed by §8.1 exception (b))

The gate was WAIVED by human operator (Alex Guillen, 2026-06-07). The spec passed
both binding structural gates (completeness PASS, consistency PASS with 2 LOW WARNs).
The waiver is documented in `docs/reports/069/spec-eval-waiver.md`.

**Self-audit note:** The spec-eval gate was human-WAIVED. Do NOT claim it PASSED.
The scorer produces false-FAILs on (a) spec-allowed exceptions and (b) truncated/empty
single-shot output. This is a harness artifact, not a spec gap.

### Assembly Quality

- 24/24 workers merged via cherry-pick (zero conflicts)
- 37 files assigned, 0 overlap (ownership gate PASS)
- 0 merge conflicts — all workers touched only disjoint new files
- 43 files total, 3,742 insertions in merge commit ee8ea25

## Risk Resolution

### What Was Flagged as a Risk

The plan's Feed-Forward risk was two-headed:
1. **Context saturation** — 24-agent inline spawn might kill the orchestrator context
   (unproven above 12 agents)
2. **Cross-section P0 class** — canonical-hash byte recipe, run-lock atomicity,
   NON_DETERMINISTIC-as-result-not-status, live-hash writer — that single-section
   review misses

### What Actually Happened

**Context saturation:** DID NOT OCCUR. The orchestrator completed all 24 agent spawns,
4 pre-swarm gates, and cherry-pick assembly without context death and well below the
~70% context flag threshold. 24 agents is within the delegation architecture's
safe operating range for inline spawn.

**Cross-section P0 class:** CORRECTLY IDENTIFIED AND FIXED. The review agent
scrutinized all four risk areas:
- Canonical hash byte recipe: VERIFIED correct (RFC 8785-aligned, correct table set)
- Run-lock atomicity: VERIFIED correct (single guarded INSERT + reaper in T1)
- NON_DETERMINISTIC as result-not-status: VERIFIED correct (match in determinism_results)
- live_hash_pre == live_hash_post: VERIFIED correct (_assert_live_unchanged fails closed)

The UNPINNED cross-cluster entrypoints were the actual failure class — not the
P0 areas the plan was tracking. The P0 areas (all in the spec) held; the gaps were
in the spec's SCOPE (what it didn't pin).

### What Was Learned (Delta)

**Expected:** Context saturation would manifest at 20-25 agents due to inline deepening
accumulating tokens before spawn.
**Actual:** No saturation. The delegation architecture absorbs 24 agents cleanly.

**Expected:** Cross-section P0s in the canonicalization / locking / determinism logic.
**Actual:** Those held. The P0 class that fired was UNPINNED ENTRYPOINTS — not the
areas the plan was watching. This is FC1/FC2 at 24-agent scale: the spec is only
as safe as what it explicitly pins.

**New finding:** `EMPTY_PROJECTION_HASH` is a post-assembly computed constant, but
the placeholder value (`"0" * 64`) was shipped and the `compute_golden.py` tool
was not run as part of assembly. The tool also had a CSRF bug that prevented the
golden corpus hash computation. Both should be surfaced as carry-forwards.

## Tests

Final state after resolve-todos:
- **Smoke:** 12/12 PASS
- **Unit + integration:** 30/30 PASS, 1 SKIP (golden corpus hash — deferred pending
  `compute_golden.py` CSRF fix)

Test coverage:
- `test_dedup.py` — monotonic event_id, dup_exact/dup_conflict counters, anomaly rows,
  order-insensitive payload comparison
- `test_determinism.py` — EMPTY_PROJECTION_HASH, identical runs → identical hash,
  forced mismatch → match=0 + field diffs, per-column readback types, idx_events_ts
  existence (NOT query plan — SQLite doesn't use composite index for range+different-sort)
- `test_isolation.py` — RO connection rejects writes, live.db hash stable, replay
  leaves live.db unchanged
- `test_patch_semantics.py` — parse_patch present/null/absent, additive counters,
  unknown key anomaly
- `test_pointintime.py` — events_at_time inclusive, ordered, boundary conditions

## Carry-Forwards

1. **Spec §5 must add "Orchestration Entrypoints" row-class.** Pin route→orchestration
   and tool→constants entrypoints (name + full signature), not just model exports.
   At 24-agent scale: 2/2 unpinned diverged, 0/N pinned diverged.

2. **`compute_golden.py` has a CSRF bug.** The tool reuses the HTML form token for
   API endpoints, but Flask-WTF generates per-session tokens that differ. The tool
   needs to use the Flask test client's session or extract the token differently.
   Until fixed: compute EMPTY_PROJECTION_HASH manually and freeze; skip the golden
   corpus hash (F1 golden test gracefully skips with SKIPPED, not FAIL).

3. **Spec-eval gate (9w.8) false-FAILs on spec-allowed exceptions.** The scorer
   misflags `:memory:` throwaway DBs (explicitly allowed in §8.1(b)) and stale-reaper
   SQL as spec violations. Log to agent-pitfalls.md: gate output must be read with
   awareness of single-shot-agent artifacts; structural gates (completeness, consistency)
   are the authoritative signal.

4. **Assembly worktree cleanup:** F2's worktree remained (live session constraint).
   This is a known autopilot cleanup gap — the orchestrator cannot remove a worktree
   while its spawning session is still active. Manual cleanup: `git worktree remove
   --force <path>` after session ends.

## Solution Doc Cross-References

- Architecture: [3-Stage Context-Death Delegation](2026-06-05-autopilot-context-death-delegation-architecture.md)
- Run 068 (12-agent ceiling): [Gig Outcome Tracker](2026-06-06-gig-outcome-tracker-12-agent-swarm-build.md)
- Spec convergence loop: [Spec Convergence Loop](2026-04-30-spec-convergence-loop.md)
- Event sourcing patterns: [Event-Sourced Audit Log](2026-04-05-event-sourced-audit-log.md)
- Swarm orchestration: [Swarm Orchestration](2026-04-09-autopilot-swarm-orchestration.md)
