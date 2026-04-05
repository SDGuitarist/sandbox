---
title: "Feature Flag Management Service"
date: 2026-04-05
tags: [flask, sqlite, flags, rollout, dag]
module: flags
lesson: SHA-256 hash bucket gives stable per-user percentage rollout; cycle detection must be iterative DFS (not recursive) to handle diamond DAGs without false positives
origin_plan: docs/plans/2026-04-05-feat-feature-flag-service-plan.md
origin_brainstorm: docs/brainstorms/2026-04-05-feature-flag-service.md
---

# Feature Flag Management Service

## Problem

Services need the ability to roll out features gradually — to a percentage of users, to specific users (allowlist), or only in certain environments — without deploying new code. Dependencies between flags (flag B requires flag A enabled) enable gating features on infrastructure flags.

## Solution

Flask + SQLite REST API with:
- **CRUD** for flags (`key`, `name`, `enabled`, `default_enabled`, `environments`, `allowlist`, `percentage`, `eval_count`)
- **Evaluation** (`POST /flags/<key>/evaluate`) returning `{enabled, reason, flag_key, eval_count}`
- **Dependency DAG** with cycle detection at write time
- **8 routes** covering create, list, get, patch, delete, evaluate, add-dep, remove-dep

## Why This Approach

- **SHA-256 over Python's `hash()`**: `hash()` is process-salted in Python 3.3+ — non-deterministic across restarts. SHA-256 gives the same bucket for the same `(flag_key, user_id)` pair forever.
- **Iterative DFS over recursive**: Recursive DFS in Python hits the recursion limit on deep chains and has no natural `visited` set, causing false positives on diamond DAGs. Iterative DFS with a `visited` set handles all cases.
- **Cycle detection at write time, not eval time**: Prevents invalid state from ever entering the DB. Eval time detection would require traversal on every evaluation.
- **`BEGIN IMMEDIATE` for cycle detection**: The check-then-insert for `add_dependency` is a two-step operation that must be atomic. Without `BEGIN IMMEDIATE`, a concurrent insert could slip in between and create a cycle.

## Risk Resolution

> **Flagged risk:** "Cycle detection in the dependency DAG uses DFS from the new node. Must verify DFS correctly handles diamonds (A→B, A→C, B→D, C→D) without false positives"

**What actually happened:** The iterative DFS with a `visited` set handles diamonds correctly. When B and C both point to D, and we walk from D, we visit D once (via B), then skip D when encountered again via C. 10 explicit tests (linear, diamond, true cycles, long chains) all passed without false positives.

**Lesson learned:** Diamond DAGs are the canonical false-positive trap for cycle detection. Always write a specific diamond test first — it's fast to write and immediately exposes whether the visited set is working.

## Key Decisions

| Decision | Chosen | Rejected | Reason |
|----------|--------|----------|--------|
| Rollout hash | SHA-256 | Python `hash()`, random | Deterministic across processes/restarts |
| Cycle detection | Iterative DFS | Recursive DFS | Python recursion limit; visited set prevents diamond false positives |
| Priority ordering | allowlist → environment → deps → % → default | environment before allowlist | Allowlisted users (beta testers) must get features regardless of environment |
| Eval count tracking | `RETURNING eval_count` in UPDATE | SELECT after UPDATE | Single round-trip; SQLite 3.35+ supports it |

## Evaluation Priority Order

1. `disabled` — global kill switch
2. `allowlist` — explicit user inclusion (bypasses environment check)
3. `environment_mismatch` — flag not active in this environment
4. `dependency_disabled` — a required dependency flag is off
5. `percentage` — hash-bucket rollout
6. `default` — flag's default_enabled value

## Gotchas

- **Allowlist bypasses environment**: This is intentional. Beta users on the allowlist should get the feature regardless of which environment they're in. The non-obvious ordering caused a P1 review finding — document it explicitly with a comment in `evaluate_flag`.
- **TOCTOU in dependency chain evaluation**: `evaluate_flag` commits its transaction before recursively evaluating dependencies. A concurrent writer could flip a dependency flag between recursive calls. Documented in code — fixing it would require loading all flags into memory first and evaluating offline.
- **`executescript` implicit COMMIT**: `init_db` uses a raw `sqlite3.connect` instead of `get_db()` because `executescript()` issues an implicit `COMMIT` before running, which would bypass the context manager's transaction semantics. WAL pragma must be set before `executescript`.
- **Column quoting in PATCH**: `update_flag` builds `SET` clause from `_PATCHABLE_COLUMNS` (a frozenset — injection-safe), but column names should still be double-quoted to future-proof against reserved word collisions.
- **`RETURNING` clause**: `UPDATE ... RETURNING eval_count` eliminates a second `SELECT` round-trip. Requires SQLite 3.35+. Verified available (3.51.2 in this environment).

## Feed-Forward

- **Hardest decision:** Evaluation priority ordering — allowlist before or after environment. Industry standard (allowlist wins) conflicted with naive ordering. Fixed after review caught it as P1.
- **Rejected alternatives:** Recursive DFS for cycle detection; Python `hash()` for bucket assignment; SELECT-after-UPDATE for eval_count.
- **Least confident:** The TOCTOU gap in cross-transaction dependency evaluation is documented but not fixed. Under high concurrency, a dependency flag could change state mid-chain-evaluation. Acceptable for this use case but worth revisiting if strict consistency is needed.
