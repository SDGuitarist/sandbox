# Review Context — distributed-task-scheduler

## Risk Chain

**Brainstorm risk:** SQLite WAL mode behavior under concurrent writes from scheduler process + Flask workers simultaneously.

**Plan mitigation:** Enable WAL + busy_timeout=5000ms on every connection; wrap claim + job_run insert in BEGIN IMMEDIATE transaction.

**Work finding:** WAL smoke test passed. However, `_next_run_at` was being computed OUTSIDE the BEGIN IMMEDIATE block — a stale `now` snapshot from an earlier poll iteration could set `next_run_at` in the past, causing the schedule to immediately re-fire. Fixed by moving computation inside the transaction.

**Review resolution:** 5 P1, 9 P2, 6 P3 findings. Key: (1) Unhandled croniter exception killed entire poll loop — fixed with per-schedule try/except+continue; (2) _next_run_at computed outside transaction — confirmed and fixed; (3) PATCH crash on non-string status — fixed with isinstance guard; (4) commit() before rowcount check in PATCH — fixed; (5) deleted→active state machine — added 409 guard. All P1/P2 fixed, P3 fixed. 20-test suite passes.

## Files to Scrutinize

| File | What changed | Risk area |
|------|-------------|-----------|
| task_scheduler/scheduler.py | Created — poll loop with BEGIN IMMEDIATE claim | Atomicity, per-schedule error isolation |
| task_scheduler/routes.py | Created — 5 endpoints + dashboard | Input validation, state machine, response consistency |
| task_scheduler/db.py | Created — WAL setup, init_db | Connection safety, schema error handling |

## Plan Reference

`docs/plans/2026-04-05-feat-distributed-task-scheduler-plan.md`

---

# Review Context — api-key-manager

## Risk Chain

**Brainstorm risk:** Atomic rate limit check via UPDATE WHERE window_count < rate_limit_rpm — TOCTOU-safe in SQLite?

**Plan mitigation:** Two-step approach: reset expired window (idempotent) then check-and-increment. Noted that SQLite serialized writes make this safe, but two separate commits are two separate transactions.

**Work risk (from Feed-Forward):** The window reset + check-and-increment across two separate db.commit() calls — another request could interleave between them.

**Review resolution:** 11 findings (P1 x3, P2 x4, P3 x4). Key: (1) Unsalted SHA-256 enables rainbow table attacks — fixed with per-key salt + hmac.compare_digest; (2) ISO8601 T-separator silently nulls datetime() — fixed with Python normalization at write; (3) BEGIN IMMEDIATE added to make both rate-limit steps atomic. All 11 findings fixed, 15-test suite passes.

## Files to Scrutinize

| File | What changed | Risk area |
|------|-------------|-----------|
| api-key-manager/app.py | Created — 6 endpoints, rate limit with BEGIN IMMEDIATE, prefix-based lookup | Atomicity, expiry check, constant-time comparison |
| api-key-manager/database.py | Created — schema with key_salt + prefix index | Schema completeness (key_salt column, correct index) |
| api-key-manager/keys.py | Created — salted SHA-256, verify_key with hmac.compare_digest | Cryptographic correctness |

## Plan Reference

`docs/plans/2026-04-05-api-key-manager.md`
