# Flow-Trace Review -- Prompt Dashboard

**Date:** 2026-06-01
**Reviewer:** cross-flow data integrity agent
**Plan:** docs/plans/2026-06-01-feat-prompting-dashboard-engine-plan.md
**Scope:** prompt-dashboard/app/ -- 5 flows traced across 3+ files each

---

## Files Traced

- `prompt-dashboard/app/blueprints/prompts/routes.py`
- `prompt-dashboard/app/blueprints/testing/routes.py`
- `prompt-dashboard/app/blueprints/dashboard/routes.py`
- `prompt-dashboard/app/models.py`
- `prompt-dashboard/app/database.py`
- `prompt-dashboard/app/schema.sql`

---

## Flow 1: Create Prompt

**Files:** `prompts/routes.py` -> `models.py:create_prompt()` -> `schema.sql` (INSERT prompts + INSERT prompt_versions + FTS5 trigger + set_prompt_tags)

**Data traced:** `prompt_id` (lastrowid from INSERT prompts), `variables` (JSON from extract_variables), `version_count=1`, FTS5 sync

**Storage steps:**
- `models.py:117-122` -- INSERT into prompts with variables and version_count=1
- `models.py:124-129` -- INSERT into prompt_versions with version_number=1 and same variables
- `schema.sql:65-68` -- `prompts_ai` trigger fires AFTER INSERT, syncs FTS5
- `models.py:130` -- `set_prompt_tags()` inserts tags within same transaction
- `models.py:131` -- `COMMIT`

**Code paths checked:**
- Happy path: all four writes happen inside one `BEGIN IMMEDIATE` / `COMMIT` block
- Exception path: `ROLLBACK` at `models.py:133`, exception re-raised, no partial write persists
- Empty tag list: `set_prompt_tags` loops over nothing, DELETE from prompt_tags (no rows) is harmless

**Transaction boundary:** `create_prompt` issues `BEGIN IMMEDIATE` at line 113 and `COMMIT` at line 131. The FTS5 trigger fires at `COMMIT` time for external-content tables (SQLite executes the trigger SQL within the same transaction). All four writes are atomic.

**Result:** PASS

---

## Flow 2: Update Prompt (TOCTOU Check)

**Files:** `prompts/routes.py:update()` -> `models.py:get_prompt()` [connection 1] -> `models.py:update_prompt()` [connection 2?]

**Data traced:** `prompt_id` existence check in block 1, then used in block 2 for UPDATE

**Storage steps:**
- `routes.py:113-116` -- first `with get_db() as conn:` block calls `get_prompt(conn, prompt_id)`; aborts 404 if None
- `routes.py:140-141` -- second `with get_db() as conn:` block calls `update_prompt(conn, prompt_id, ...)`
- `models.py:200-203` -- inside `update_prompt`, re-fetches `version_count` from prompts table

**Code paths checked:**
- Prompt deleted between block 1 and block 2 (TOCTOU window)
- Normal update path
- Exception inside update_prompt

**Connection identity:** `database.py:15-16` shows `get_db()` checks `if 'db' not in g` and reuses `g.db` if already set. Both `with get_db()` blocks in the same request therefore yield the SAME connection object. There is no isolation difference between block 1 and block 2 from a separate-connection perspective.

**TOCTOU analysis -- P2 bug found:**

The first block validates existence (404 gate) but does NOT hold a lock. The second block opens a new `BEGIN IMMEDIATE` inside `update_prompt` at `models.py:194`. Between the first block's exit and the second block's `BEGIN IMMEDIATE`, another request can DELETE the prompt.

If that happens, `models.py:200-203`:

```python
row = conn.execute(
    'SELECT version_count FROM prompts WHERE id = ?', (prompt_id,)
).fetchone()
new_version_number = row['version_count'] + 1   # row is None -> TypeError
```

`row` is `None` because the DELETE cascade removed the prompts row. `row['version_count']` raises `TypeError: 'NoneType' object is not subscriptable`. This propagates as an unhandled 500 instead of a clean 404.

The window is narrow (two sequential HTTP requests), but it is a real code path -- e.g., a user double-submits delete from another tab while the edit form is being submitted.

**Result:** FAIL

- **Bug:** `update_prompt()` does not guard against the prompt being deleted between the route's existence check and the model function's `BEGIN IMMEDIATE`. `row` is `None` at `models.py:203` causing `TypeError`.
- **File:** `prompt-dashboard/app/models.py:203`
- **Impact:** Unhandled 500 instead of 404 when prompt is concurrently deleted. Does not corrupt data (ROLLBACK fires), but crashes the response.
- **Fix:** Add a None check in `update_prompt` before accessing `row['version_count']`: `if row is None: raise ValueError(f'Prompt {prompt_id} not found')` and catch that in the route as a 404, OR merge the existence check into `update_prompt`'s `BEGIN IMMEDIATE` block so it is guarded by the write lock.
- **Severity:** P2 -- runtime 500 under concurrent delete, no data corruption

---

## Flow 3: Test Execution

**Files:** `testing/routes.py:execute()` -> `models.py:create_test_run()` -> `prompts` table (`last_tested_at`)

**Data traced:** `version_id` (from latest prompt_versions row), Claude API response, `run_id` (returned from `create_test_run`), `last_tested_at` update

**Storage steps:**
- `testing/routes.py:87-96` -- SELECT latest version_id; aborts 404 if none
- `testing/routes.py:103-113` or `168-178` -- `create_test_run(conn, version_id, ...)` called on both the no-API-key path and the normal path
- `models.py:283-289` -- INSERT into test_runs
- `models.py:293-299` -- UPDATE prompts SET last_tested_at via subquery on version_id
- `models.py:301` -- COMMIT

**Code paths checked:**
- No API key configured: `create_test_run` called at line 103 with `error=` set, response_text=None. PASS.
- APITimeoutError: `create_test_run` called at line 168 with error set. PASS.
- APIConnectionError: same as above. PASS.
- APIStatusError: same as above. PASS.
- All exception branches set all four output variables (response_text, input_tokens, output_tokens, duration_ms) before `create_test_run` is called. No uninitialized variable risk.

**`create_test_run` inside outer `with get_db()` block:** The outer block at `testing/routes.py:64` yields `g.db`. Inside `create_test_run`, `conn.execute('BEGIN IMMEDIATE')` is called. With `isolation_level=""` (default), Python's sqlite3 module does NOT start an implicit transaction on SELECT statements, so there is no open transaction at call time. The `BEGIN IMMEDIATE` succeeds.

**`last_tested_at` update:** The UPDATE at `models.py:294-299` uses a correlated subquery `WHERE id = (SELECT prompt_id FROM prompt_versions WHERE id = ?)`. Since `version_id` was just verified to exist (line 93-96), the subquery returns a valid `prompt_id`. The UPDATE is inside the same `BEGIN IMMEDIATE` / `COMMIT` block as the INSERT. PASS.

**`run_id` consumed at line 181:** `get_test_run(conn, run_id)` is called immediately after `create_test_run` returns. The run was just committed, so it is visible on the same connection. PASS.

**Result:** PASS

---

## Flow 4: Search (FTS5)

**Files:** `dashboard/routes.py` -> `models.py:get_all_prompts()` -> `models.py:sanitize_fts_query()` -> FTS5 `prompts_fts` table

**Data traced:** `search_query` (from `request.args.get('q')`), `tag_name` (from `request.args.get('tag')`), FTS5 MATCH value

**Storage steps (read-only flow):**
- `dashboard/routes.py:12` -- `search_query = request.args.get('q')` (None if absent, "" if present but empty)
- `models.py:157` -- `if search_query:` -- falsy check correctly handles both None and ""
- `models.py:158` -- `sanitize_fts_query(search_query)` called only when search_query is truthy
- `models.py:40` -- strips `* " ( ) : ^ \` characters, collapses whitespace, wraps in double quotes
- `models.py:161` -- `conditions.append('prompts_fts MATCH ?')` -- parameterized, not interpolated
- `models.py:162` -- `params.append(safe_query)` -- value goes through binding

**Code paths checked:**
- `q` absent: `search_query=None`, falsy, FTS join skipped entirely. PASS.
- `q=""`: `search_query=""`, falsy, FTS join skipped. PASS.
- `q="normal text"`: sanitized to `'"normal text"'`, phrase search. PASS.
- `q="OR AND NOT"`: wrapped in quotes -> `'"OR AND NOT"'`, phrase search, operators neutralized. PASS.
- `q="-secret"`: `-` is NOT stripped by the regex. Inside double-quotes in FTS5, `-` is a literal character. The result is a phrase search for "-secret". PASS (quotes neutralize the NOT operator).
- `q="*"`: sanitized to `'""'` (empty after stripping `*`), `sanitize_fts_query` returns None, FTS join skipped. PASS.
- Tag filter: `tag_name` used in parameterized `t.name = ?`. PASS.
- Both filters active: `fts_join` and `tag_join` both non-empty, `WHERE` has both conditions joined by `AND`. SQL is built with f-string but values are parameterized. PASS.

**One observation (not a bug):** The SQL at `models.py:178-183` builds the query using f-string interpolation for `fts_join`, `tag_join`, and `where_clause`. These strings contain only SQL keywords and column names (no user data), so there is no injection risk. User values travel through `params` list to parameterized binding.

**Result:** PASS

---

## Flow 5: Diff

**Files:** `prompts/routes.py:diff()` -> `models.py:get_prompt_version()` -> `generate_diff_html()` -> template with `|safe`

**Data traced:** `v1`, `v2` query params (should be `prompt_versions.id` PK values), ownership check, XSS safety in labels

**Code paths checked:**
- `v1`/`v2` non-integer: caught by `int()` at `routes.py:187-188`, redirects with flash. PASS.
- `v1`/`v2` integer but not found: `get_prompt_version` returns None, check at `routes.py:196-198` redirects. PASS.
- Version belongs to different prompt: ownership check at `routes.py:201-203` validates `version['prompt_id'] != prompt_id`. PASS.
- **Label XSS:** Labels passed to `generate_diff_html` are `f'Version {version1["version_number"]}'` where `version_number` is an INTEGER from the database (`INTEGER NOT NULL` in schema.sql). Integer-to-string interpolation cannot produce HTML-injection content. Additionally, `generate_diff_html` at `routes.py:32-33` explicitly calls `html_module.escape(label1)` and `html_module.escape(label2)` before passing to `difflib.HtmlDiff.make_table`. Double-escaped, but safe. PASS.
- **`|safe` on diff HTML:** `generate_diff_html` returns `Markup(table)` at `routes.py:37`. `difflib.HtmlDiff` escapes content lines internally in Python 3 (documented in the function docstring). The labels are also escaped before passing in. PASS.
- `get_prompt_version` fetches by `id` (PK), NOT by `version_number`. The route docstring confirms `v1` and `v2` are `prompt_versions.id` values. The query at `models.py:264-265` uses `WHERE id = ?`. PASS.

**Result:** PASS

---

## Summary of All Flows

| Flow | Files Crossed | Result | Severity |
|---|---|---|---|
| Create prompt | routes.py -> models.py -> schema.sql | PASS | -- |
| Update prompt | routes.py (2 blocks) -> models.py | FAIL | P2 |
| Test execution | testing/routes.py -> models.py -> prompts table | PASS | -- |
| Search / FTS5 | dashboard/routes.py -> models.py -> prompts_fts | PASS | -- |
| Diff | prompts/routes.py -> models.py -> generate_diff_html | PASS | -- |

---

## Issue Detail

### P2 -- Unhandled TypeError on Concurrent Delete During Update

**Flow:** Update prompt (routes.py block 1 -> routes.py block 2 -> models.py)

**Bug:** `prompts/routes.py` performs the 404 existence check in one `with get_db()` block (lines 113-116), then calls `update_prompt()` in a separate `with get_db()` block (lines 140-141). Although both blocks reuse the same `g.db` connection, there is no write lock held between the two blocks. If the prompt is concurrently deleted between block 1 completing and block 2's `BEGIN IMMEDIATE` acquiring, `update_prompt()` at `models.py:200-203` executes:

```python
row = conn.execute(
    'SELECT version_count FROM prompts WHERE id = ?', (prompt_id,)
).fetchone()
new_version_number = row['version_count'] + 1
```

`row` is `None` (prompt was deleted). `row['version_count']` raises `TypeError: 'NoneType' object is not subscriptable`. The `except Exception` at `models.py:227` catches this and calls `ROLLBACK`, then re-raises -- producing an unhandled 500.

**File:** `prompt-dashboard/app/models.py:203`

**Impact:** 500 response instead of 404 when a prompt is concurrently deleted. No data corruption (transaction is rolled back). Observed under: browser tab with edit form open while another tab deletes the same prompt, or any concurrent delete.

**Fix (choose one):**
1. Guard in `update_prompt`: add `if row is None: raise LookupError(f'Prompt {prompt_id} not found')` at `models.py:203`, then in `routes.py:update()` catch `LookupError` and `abort(404)`.
2. Merge the existence check into `update_prompt`'s `BEGIN IMMEDIATE` block so the DELETE cannot race the version_count fetch.

---

STATUS: FAIL -- 5 flows traced, 1 issue found (P2)
