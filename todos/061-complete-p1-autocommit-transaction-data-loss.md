---
status: complete
priority: p1
issue_id: "061"
tags: [code-review, database, sqlite, transaction, python314, run-064]
dependencies: []
---

# P1: Python 3.14 autocommit=True + explicit BEGIN/commit Does Not Persist Data

## Problem Statement

`create_prompt()` and `update_prompt()` use `conn.execute('BEGIN')` + `conn.commit()` with `autocommit=True` connections. In Python 3.14, this combination silently fails to write data to disk. After `conn.close()`, all inserted rows disappear. The wizard save route returns HTTP 302 (success) but writes nothing to the database.

This is the root cause of smoke test failure: "Component content is encrypted — content appears plaintext: NULL".

## Findings

- **File:** `app/models/prompt_models.py` lines 17-33 (`create_prompt`), lines 123-140 (`update_prompt`)
- **File:** `app/database.py` — `autocommit=True` is set at connection creation
- **Confirmed via:** Direct Python 3.14 test: `conn = sqlite3.connect(db_path, autocommit=True); conn.execute('BEGIN'); conn.execute('INSERT...'); conn.commit(); conn.close()` → new connection sees 0 rows

## Proposed Solution

**Option A (Recommended):** Replace `conn.execute('BEGIN')` + `conn.commit()` with `with conn:` context manager

```python
# Before
conn.execute('BEGIN')
try:
    cursor = conn.execute('INSERT INTO prompts ...', ...)
    prompt_id = cursor.lastrowid
    for ...:
        conn.execute('INSERT INTO prompt_components ...', ...)
    conn.commit()
except Exception:
    conn.rollback()
    raise
return prompt_id

# After
with conn:
    cursor = conn.execute('INSERT INTO prompts ...', ...)
    prompt_id = cursor.lastrowid
    for ...:
        conn.execute('INSERT INTO prompt_components ...', ...)
return prompt_id
```

The `with conn:` context manager correctly handles BEGIN/COMMIT/ROLLBACK in all Python versions.

**Option B:** Switch to `isolation_level=None` (PEP 249 legacy autocommit mode) which works with explicit `conn.commit()`.

**Effort:** Small (2 functions, ~10 lines each)
**Risk:** Low — semantically equivalent, fixes the bug
**Test:** Smoke test "Component content is encrypted" should PASS after fix

## Acceptance Criteria

- [ ] `create_prompt` uses `with conn:` instead of BEGIN/commit/rollback
- [ ] `update_prompt` uses `with conn:` instead of BEGIN/commit/rollback
- [ ] Smoke test "Component content is encrypted" PASSES
- [ ] Smoke test "POST /wizard/save redirects" continues to PASS

## Work Log

- 2026-06-02: Found during Run 064 tail review. Root cause confirmed via direct Python 3.14 testing. Traced to Python 3.14 behavioral change with `autocommit=True`.
