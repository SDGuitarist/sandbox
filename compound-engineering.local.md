---
review_agents:
  - learnings-researcher
  - security-sentinel
  - performance-oracle
  - flow-trace-reviewer
---

# Review Context — Sandbox (CPAA Event-Replay Simulator, Run 069)

## Risk Chain

**Brainstorm risk:** Context saturation at 24-agent inline spawn (unproven above 12) PLUS the cross-section P0 class (canonical-hash byte recipe, run-lock atomicity + reaper, NON_DETERMINISTIC as result-not-status, live-hash writer) that single-section review misses.

**Plan mitigation:** Feed-Forward risk baked into spec with Feed-Forward section + verify_first: true. Plan §8.8 froze the canonical hash byte recipe. §3.2 froze the run-lock guarded INSERT pattern and the 3-transaction T1/T2/T3 sequence. Plan deepening (11 agents) caught the NON_DETERMINISTIC status contradiction and rewrote it as a comparison result.

**Work risk (from Feed-Forward):** Whether 24 agents would diverge on unpinned cross-cluster entrypoints (the spec's §5 exhaustively pinned model exports but not route→orchestration calls).

**Review resolution:** 4 P1, 2 P2, 1 P3. All P1+P2 fixed. P3 deferred (golden corpus hash — compute_golden.py CSRF bug). P1s: ingest import mismatch (B2↔B3), replay arity mismatch (C1↔C6), LIVE_DB bare module import (C1), EMPTY_PROJECTION_HASH placeholder, dedup both-sides canonicalization. P2s: test assertion false (index SCAN vs query planner), validator detail endpoint missing login_required. All P0 risk areas (canonical hash, run-lock, NON_DETERMINISTIC verdict, live-hash isolation) verified CORRECT in the spec and implementation. The risk that fired was UNPINNED ENTRYPOINTS — not what the plan was tracking.

## Files to Scrutinize

| File | What changed | Risk area |
|------|-------------|-----------|
| cpaa-replay/app/ingest_routes.py | Fixed: ingest → ingest_source + LIVE_DB config arg | B2↔B3 cross-cluster wiring |
| cpaa-replay/app/replay_engine.py | Fixed: LIVE_DB bare import → current_app.config + run_replay(conn) → run_replay() | C1↔C6 cross-cluster wiring |
| cpaa-replay/app/replay_routes.py | Fixed: dropped outer get_db wrapper on run path | Transaction ownership |
| cpaa-replay/app/constants.py | Fixed: EMPTY_PROJECTION_HASH placeholder → computed value | Canonical hash correctness |
| cpaa-replay/app/event_models.py | Fixed: both-sides canonicalization in dedup compare + _canonicalize helper | Dedup order-insensitivity |
| cpaa-replay/app/validator_routes.py | Fixed: login_required added to GET /validate/<id> | Auth coverage |
| cpaa-replay/tests/test_determinism.py | Fixed: false query-plan assertion → DDL existence check | Test correctness |

## Plan Reference

`docs/plans/2026-06-06-feat-cpaa-event-replay-simulator-plan.md`
