STATUS: PASS — 16/16 dynamic smoke checks (post-firebreak-teardown re-run)

# Smoke Test Re-run (post-teardown) — run 080

This is the documented recovery action for [SMOKE-080] / self-audit 080-W4 / disconfirmer D4
("zero executed dynamic tests against ShelfTrack code"). Executed AFTER Step 18w firebreak
teardown, so the smoke test was no longer FIREBREAK_DEFERRED.

## Root cause of the earlier deferral + a real test-harness bug found
1. During assembly (phase=build) the smoke test was FIREBREAK_DEFERRED (expected governance).
2. On first post-teardown run it FAILED with `sqlite3.OperationalError: no such table: users`.
   Root cause: the swarm-runner's `test_smoke.py` created the temp DB file via
   `tempfile.mkstemp` but did NOT unlink it before `create_app()`. The app's correct
   first-run guard `if not os.path.exists(db_path): init_db(...)` therefore saw the file
   exists and SKIPPED schema creation. This is the FC49-aware pattern the plan's smoke
   template handles with an explicit `os.unlink`. **The bug was in the test harness, not
   the app** — the app's first-run-init pattern (create shelftrack.db when absent) is
   correct and matches the sandbox Flask template.
3. Fix: added `os.unlink(_db_path)` after `mkstemp`/`close` so the app's guard triggers
   init_db. (test_smoke.py is gitignored — a throwaway harness.)

## Result — 16/16 PASS
- /health 200; /login 200
- anon /books -> 302 -> /login  (auth gate)
- register userA -> 302; login userA -> 302 -> /books  (session set, SECRET_KEY present)
- create book -> 302; list books 200 + contains "Test Book"
- filter status=want -> contains book; filter status=done -> "No books with status" empty-state
- **IDOR: user B cannot edit user A's book (/books/1/edit) -> 404**  ← plan Feed-Forward #1 risk, DYNAMICALLY CONFIRMED
- logout -> 302

## Disposition
- Closes 080-W4 (HIGH) / D4: dynamic coverage now EXISTS and PASSES for the built ShelfTrack code.
- Closes the plan's Feed-Forward "least confident" item dynamically (IDOR ownership-404 proven at runtime, not just static flow-trace).
- The app boots, wires blueprints, inits schema, and enforces per-user ownership at runtime.
- One test-harness defect found+fixed (missing unlink) — app code unchanged (it was correct).
