# Code Review Report — Run 064: Prompting Dashboard Engine

**Date:** 2026-06-02
**Branch:** master
**Reviewer:** Multi-agent synthesis (security-sentinel, performance-oracle, architecture-strategist, flow-trace-reviewer, learnings-researcher)
**Feed-Forward Risk Scrutinized:** Fernet encryption/decryption integration with wizard form flow

---

## Summary

| Severity | Count |
|----------|-------|
| P1 (Critical) | 2 |
| P2 (Important) | 3 |
| P3 (Nice-to-have) | 1 |
| **Total** | **6** |

---

## P1 Findings

### P1-1: Python 3.14 autocommit=True + explicit BEGIN/commit Does Not Persist Data

**File:** `app/database.py`, `app/models/prompt_models.py`
**Failure Class:** FC6 (Non-Transactional Multi-Table Operations) — new variant

**Finding:** Python 3.14 introduced a behavioral change where `sqlite3.connect(db_path, autocommit=True)` with explicit `conn.execute('BEGIN')` + `conn.commit()` does NOT persist data to disk after `conn.close()`. The `in_transaction` attribute remains `True` even after `commit()` in this mode, and the write is silently lost.

**Evidence:** Confirmed via direct testing:
```
conn = sqlite3.connect(db_path, autocommit=True)
conn.execute('BEGIN')
conn.execute('INSERT INTO t (val) VALUES (?)', ('hello',))
conn.commit()
conn.close()
# New connection: SELECT COUNT(*) returns 0 — data lost!
```

**Impact:** All calls to `create_prompt()` and `update_prompt()` that use `conn.execute('BEGIN')` + `conn.commit()` fail silently in production. The wizard save route returns 302 (success redirect) but writes nothing to the database. The smoke test failure ("Component content is encrypted — content appears plaintext: NULL") is a symptom of this root cause: the prompt row doesn't exist.

**Fix:** Replace `conn.execute('BEGIN')` + `conn.commit()` with `with conn:` context manager pattern:
```python
with conn:
    cursor = conn.execute('INSERT INTO prompts ...', (...))
    prompt_id = cursor.lastrowid
    for component_id, content in component_data:
        conn.execute('INSERT INTO prompt_components ...', (...))
return prompt_id
```

The `with conn:` pattern correctly handles BEGIN/COMMIT/ROLLBACK and persists data in Python 3.12+ autocommit=True mode. Confirmed fix: data visible from new connection after `conn.close()`.

**Also affects:** `update_prompt()` in prompt_models.py (same pattern).

**Todo:** `061-pending-p1-autocommit-transaction-data-loss.md`

---

### P1-2: Industry Guidance Incorrectly Imports encrypt/decrypt But Does Not Encrypt

**File:** `app/models/industry_models.py`
**Failure Class:** FC2 (Type-Correct Spec, Wrong Usage Inferred)

**Finding:** `industry_models.py` imports `encrypt_field` and `decrypt_field` and uses them in `save_guidance()` and `get_guidance_for_industry()`. However, the spec lists `industry_guidance.guidance_text` as a plain text field, NOT an encrypted field. The guidance data is admin-authored, non-user-PII, and the spec explicitly states only `prompt_components.content`, `template_components.content`, `prompt_grades.worked_well/needs_improvement/notes` are encrypted.

**Evidence:** The agent over-applied the encryption pattern from neighboring model files. Looking at the schema:
```sql
CREATE TABLE industry_guidance (
    guidance_text TEXT NOT NULL DEFAULT '',
    ...
)
```
No encryption is specified. The `save_guidance` function calls `encrypt_field(guidance_text)` and `get_guidance_for_industry` calls `decrypt_field(r['guidance_text'])`. If the DB was seeded with plaintext guidance (which the seed script likely does), `decrypt_field` would attempt to Fernet-decrypt plaintext and crash with a `cryptography.fernet.InvalidToken` exception.

**Impact:** Admin guidance pages would crash on load if any seeded guidance exists. New guidance saves to encrypted form but old data (if any) would be unreadable.

**Fix:** Remove `encrypt_field`/`decrypt_field` from `industry_models.py`. `save_guidance` stores plaintext, `get_guidance_for_industry` returns row dict without decryption.

**Todo:** `062-pending-p1-guidance-wrongly-encrypted.md`

---

## P2 Findings

### P2-1: Fernet Singleton Cached At Import Time If Called Outside App Context

**File:** `app/encryption.py`
**Failure Class:** FC10 (Fail-Open on Infrastructure Errors)

**Finding:** `get_fernet()` uses a module-level `_fernet = None` singleton that is initialized on first call using `current_app.config['PROMPT_ENCRYPTION_KEY']`. This works correctly within a Flask request context. However, if any code path calls `encrypt_field()` or `decrypt_field()` outside an app context (e.g., during seed script, CLI command, or background task), `current_app` raises a `RuntimeError: Working outside of application context` which is not clearly caught.

Additionally, the singleton is cached at the process level. If the `PROMPT_ENCRYPTION_KEY` were rotated without restarting the process (e.g., in a hot-reload scenario during development), the old key remains cached and all new reads would fail.

**Fix:** Add explicit `RuntimeError` handling in `get_fernet()` and document that the function requires an app context. For the seed script, ensure it runs within `with app.app_context():`.

**Todo:** `063-pending-p2-fernet-singleton-context-dependency.md`

---

### P2-2: auth_helpers.py Makes One DB Query Per Authenticated Request

**File:** `app/auth_helpers.py`
**Failure Class:** FC17 (Duplicate Boilerplate)

**Finding:** Both `login_required` and `admin_required` re-query the database on every authenticated request to fetch the user row. For a single request that hits an authenticated endpoint, this adds one SELECT to every page load. The session already stores `user_id`, `username`, and `role`. For admin checks, the role is already in `session['role']`, making the DB fetch for role validation redundant.

**Impact:** Every authenticated page load runs `SELECT * FROM users WHERE id = ?` unnecessarily. With SQLite on local storage this is fast, but it's wasteful and the pattern doesn't scale.

**Additionally:** Neither decorator sets `g.user` from the session data directly — they both fetch from DB to get the full user row for `g.user`. This is the correct approach for freshness (in case user was deleted), but the admin check could short-circuit with session role before the DB query.

**Fix (P2, not P1):** In `admin_required`, check `session.get('role') != 'admin'` first and abort 403 before any DB query. This avoids a DB hit for the common case of a non-admin trying to access admin routes.

**Todo:** `064-pending-p2-auth-db-query-per-request.md`

---

### P2-3: export_user_prompts_csv Uses N+1 Query Pattern

**File:** `app/models/export_models.py`
**Failure Class:** FC17 (Duplicate Boilerplate) / Performance

**Finding:** `export_user_prompts_csv()` makes N+1 queries: one SELECT for all prompts, then one SELECT per prompt for components. For a user with 100 prompts, this is 101 queries. The plan notes this was fixed for `export_all_prompts_json` but the user-facing CSV export was not updated.

**Evidence:**
```python
for prompt in prompts:    # N prompts
    components = conn.execute(  # 1 query per prompt = N queries
        '''SELECT cd.name, pc.content FROM prompt_components pc ...
           WHERE pc.prompt_id = ?''', (prompt['id'],)
    ).fetchall()
```

**Fix:** Single JOIN query or subquery approach — the same pattern used in `export_all_prompts_json`.

**Todo:** `065-pending-p2-export-csv-n-plus-1.md`

---

## P3 Findings

### P3-1: generate_preview Route Not Protected by login_required

**File:** `app/blueprints/wizard/routes.py`, route `/wizard/generate`
**Failure Class:** FC27 (Neighbor Pattern Skip)

**Finding:** The `generate_preview()` route (POST /wizard/generate) is missing the `@login_required` decorator. All other wizard routes (`select_industry`, `new_prompt`, `from_template`, `save_prompt`, `edit_prompt`, `update_prompt_route`) use `@login_required`. The generate route processes user input and renders a template with a database connection — it should be consistent.

**Impact:** Anonymous users can submit form data to `/wizard/generate` and get a generated prompt preview. The route accesses the database via `get_db()` and calls `get_industry()`, `get_all_components()`. This is a minor information leak (component definitions are not sensitive) and a consistency violation, not a security vulnerability.

**The spec** says the generate route is for authenticated users previewing before saving. Per EARS: "WHEN an anonymous visitor tries to save a prompt THE SYSTEM SHALL redirect to login" — the generate route is intermediate, but the spec intent is authenticated-only wizard flow.

**Fix:** Add `@login_required` to `generate_preview()`.

**Todo:** `066-pending-p3-generate-preview-not-login-required.md`

---

## Feed-Forward Risk Resolution

**Risk:** "Fernet encryption/decryption integration with wizard form flow — if key missing/wrong, all saved prompts unreadable"

**What happened:** The Fernet encryption module itself is correct — startup validation, encrypt/decrypt functions, empty-string handling, singleton caching all work as designed. The encryption is applied consistently in `prompt_models.py`, `grading_models.py`, `template_models.py`.

**What went wrong:** The transaction pattern (`autocommit=True` + explicit `BEGIN`/`commit()`) silently fails to persist data in Python 3.14. The encryption is never the issue — the data never reaches the database.

**Additionally:** `industry_models.py` incorrectly applied encryption to guidance fields (non-sensitive admin data), which is a neighboring-pattern over-application (FC2). This means the guidance pages would crash if seed data existed as plaintext.

**Delta from expectation:** The brainstorm correctly identified encryption as the risk vector, but the failure mode was not "key missing/wrong" but rather "data never written due to Python 3.14 transaction behavior change." The encryption code itself was the least-buggy part of the build.

---

## Known Patterns Found (Learnings Researcher)

- FC6 (Non-Transactional Multi-Table Operations): Previously hit in WRC, GymFlow, RestaurantOps. The `autocommit=True` + `with conn:` pattern is documented in `docs/solutions/2026-04-07-flask-swarm-acid-test.md`. This run adds a new variant: Python 3.14's `autocommit=True` + explicit BEGIN/commit silently drops data.
- FC2 (Wrong Usage Inferred): Previously hit in Client Intake Dashboard (template `audit_fit` vs schema `is_audit_fit`). This run: encryption applied to non-encrypted fields.
- FC27 (Neighbor Pattern Skip): Previously hit in Film PM Tool. This run: `@login_required` missing from `generate_preview` while all adjacent routes have it.

---

## Review Agent Summary

| Agent | Focus | Top Finding |
|-------|-------|-------------|
| security-sentinel | Auth, injection, tokens | SHA-256 token hashing correct; FTS5 sanitization correct; no P1 security issues |
| performance-oracle | DB queries, encryption | N+1 in export_user_prompts_csv (P2) |
| architecture-strategist | Transaction integrity | Python 3.14 autocommit+BEGIN/commit data loss (P1) |
| flow-trace-reviewer | Encryption flow | industry_models wrongly encrypting guidance (P1) |
| learnings-researcher | Past patterns | FC6 pattern from flask ACID test doc, FC2 from client intake dashboard |

STATUS: 2 P1 findings. These must be fixed before the run can be considered clean.
