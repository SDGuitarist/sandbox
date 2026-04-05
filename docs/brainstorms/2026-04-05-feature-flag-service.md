---
title: "Feature Flag Management Service"
date: 2026-04-05
status: complete
origin: "conversation"
---

# Feature Flag Management Service — Brainstorm

## Problem
Build a REST API for managing feature flags with rollout rules. Operators need to:
1. Create/update/delete flags with rollout rules (percentage-based, user allowlist, environment targeting)
2. Evaluate a flag for a given user/context — returns enabled/disabled
3. Track how many times each flag has been evaluated
4. Support flag dependencies: flag B can only be enabled if flag A evaluates to enabled

Without this, teams use hardcoded feature toggles scattered across code. A centralized service enables gradual rollouts, targeted rollouts (beta users), and environment-specific control.

## Context
- Stack: Flask + SQLite
- Prior patterns available:
  - Atomic counter increment: `UPDATE t SET count = count + 1 WHERE id = ?` (url-shortener lesson)
  - BEGIN IMMEDIATE for multi-step atomic ops (api-key-manager lesson)
  - Rate limit + insert merged in single transaction to avoid TOCTOU (chat API lesson)
  - Cursor pagination: `id > after_id`, `next_cursor = rows[limit-1]["id"]`
  - db_path through `current_app.config.get("DB_PATH")`
  - init_db with raw connection (not through get_db) — executescript implicit COMMIT footgun
- New challenge: percentage rollout must be **deterministic per user** — the same user must always get the same result for a given flag, regardless of which server handles the request

## Options

### Option A: Percentage rollout via `hash(flag_key + user_id) % 100`
Deterministic: compute `int(hashlib.md5((flag_key + user_id).encode()).hexdigest(), 16) % 100`. If result < percentage_threshold, user is in the rollout.

**Pros:** No DB lookup per evaluation for percentage check. Same user always gets same result. Consistent across server instances.
**Cons:** MD5 is not cryptographically strong, but it's fine for non-security purposes here. SHA-256 is better but slower — use sha256 to be safe.

### Option B: Persistent user assignment table
Store `flag_evaluations(flag_id, user_id, result)` — first time a user evaluates, write the result; subsequent evaluations use the stored result.

**Pros:** Results are stable even if percentage changes.
**Cons:** Unbounded table growth. Complex. Overkill — percentage rollout by hash is the industry standard (LaunchDarkly, Unleash all use hashing).

### Option C: Random per-evaluation (no determinism)
On each evaluation, roll a random number. If < threshold, return enabled.

**Pros:** Simplest code.
**Cons:** Same user gets different results on different requests — fundamentally broken for feature flags. Never do this.

## Tradeoffs for Dependency Evaluation

### Option X: Recursive evaluate(flag) at runtime
When evaluating flag B, recursively evaluate flag A. If A is disabled, B is disabled.

**Pros:** Always reflects current state of dependencies.
**Cons:** N+1 queries for deep chains. Cycle detection needed at evaluation time.

### Option Y: Validate no cycles at flag creation/update time
Store dependencies as `flag_dependencies(flag_key, depends_on_flag_key)`. On create/update, run a DFS to detect cycles and reject if found. At evaluation time, evaluate dependencies in order (topological).

**Pros:** Cycle detection happens once at write time, not on every read. Evaluation is predictable.
**Cons:** Slightly more complex write path.

**Decision: Option Y** — validate no cycles at write time, evaluate dependencies at read time with a depth limit as a safety backstop.

## Rollout Rule Priority

When multiple rules apply, need a priority order:
1. **Disabled globally** — if flag is globally disabled, return false regardless
2. **Environment mismatch** — if flag is scoped to specific environments and context doesn't match, return false
3. **User allowlist** — if user is in the allowlist, return true
4. **Percentage rollout** — check hash-based percentage
5. **Default** — if no rule matches, return the flag's `default_enabled` value

## Decision

**Schema:**
```sql
CREATE TABLE flags (
    key         TEXT PRIMARY KEY,     -- e.g. "dark_mode"
    name        TEXT NOT NULL,
    description TEXT,
    enabled     INTEGER NOT NULL DEFAULT 1,  -- global kill switch
    default_enabled INTEGER NOT NULL DEFAULT 0,
    environments TEXT,               -- JSON array, e.g. ["production", "staging"], NULL = all
    allowlist   TEXT,                -- JSON array of user_ids
    percentage  INTEGER,             -- 0-100, NULL = disabled
    eval_count  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE flag_dependencies (
    flag_key        TEXT NOT NULL REFERENCES flags(key),
    depends_on_key  TEXT NOT NULL REFERENCES flags(key),
    PRIMARY KEY (flag_key, depends_on_key)
);
```

**Endpoints:**
- `POST /flags` — create flag
- `GET /flags` — list flags
- `GET /flags/<key>` — get flag
- `PATCH /flags/<key>` — update flag
- `DELETE /flags/<key>` — delete flag
- `POST /flags/<key>/evaluate` — evaluate for `{user_id, environment}` context; increments eval_count atomically
- `POST /flags/<key>/dependencies` — add dependency
- `DELETE /flags/<key>/dependencies/<dep_key>` — remove dependency

**Evaluation algorithm:**
1. Check `flag.enabled` — if False, return `{enabled: false, reason: "disabled"}`
2. Check `flag.environments` — if set and context env not in list, return `{enabled: false, reason: "environment_mismatch"}`
3. Evaluate each dependency — if any dependency evaluates to false, return `{enabled: false, reason: "dependency_disabled", dependency: key}`
4. Check allowlist — if user_id in allowlist, return `{enabled: true, reason: "allowlist"}`
5. Check percentage — if percentage set, compute `int(sha256(flag_key + user_id), 16) % 100 < percentage`, return result
6. Return `{enabled: flag.default_enabled, reason: "default"}`

**Eval count:** Increment `eval_count` with `UPDATE flags SET eval_count = eval_count + 1` atomically in the same transaction as the evaluation read.

## Open Questions
1. Should evaluation be idempotent (no count increment if called multiple times)? → No — each API call increments. Callers should cache.
2. Should deleted flags cascade-delete dependencies? → Yes — FK ON DELETE CASCADE on flag_dependencies.
3. What depth limit for dependency chains? → 10 levels max as safety backstop.
4. Should percentage + allowlist both be checked (OR logic)? → Yes — if user is in allowlist, they're always in, regardless of percentage.

## Feed-Forward
- **Hardest decision:** Percentage rollout determinism — chose SHA-256 hash of `(flag_key + ":" + user_id)` to get a stable 0-99 bucket per user per flag. The hash must be stable: same inputs always produce same output. Using Python's `hashlib.sha256` (not `random`, not `hash()` which is salted per-process in Python 3.3+).
- **Rejected alternatives:** Random per-evaluation (non-deterministic, broken), persistent assignment table (unbounded storage, overkill), MD5 (less collision resistant though acceptable — using SHA-256 to be safe).
- **Least confident:** Cycle detection in the dependency graph at write time. A simple DFS works for a tree, but the dependency graph can be a DAG where multiple flags share a common dependency. Need to verify that the DFS starting from the new flag's node correctly detects all cycles without false positives when diamonds (A→B, A→C, B→D, C→D) exist. This is the highest-risk piece of the plan.
