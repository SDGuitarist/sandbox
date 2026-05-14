---
status: resolved
priority: p1
issue_id: "004"
tags: [code-review, performance, database]
---

# SQLite WAL Mode Not Enabled + Connections Held During I/O

## Problem Statement
1. **No WAL mode** (`app/db.py`): SQLite defaults to DELETE journal mode with exclusive write locks. Concurrent requests (registration + webhook) will block for up to 5s then error.
2. **Email engine holds connections during retries** (`app/email/engine.py:130-201`): `send_email()` holds a DB connection open for up to 7 seconds during Resend API retries.

## Proposed Solution
1. Enable WAL mode in `init_db()`: `conn.execute("PRAGMA journal_mode=WAL")`
2. Restructure `send_email()` to: (a) read DB, close connection, (b) do network I/O, (c) open new connection to log result

## Acceptance Criteria
- [ ] WAL mode enabled at DB initialization
- [ ] `send_email()` does not hold DB connection during API calls
