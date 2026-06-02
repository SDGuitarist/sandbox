# Deepening Applied — Run 064

## Date: 2026-06-02

## Research Agents Used
1. framework-docs-researcher (Fernet encryption patterns)
2. best-practices-researcher (Flask security, share tokens)
3. architecture-strategist (12-agent split, transaction safety)
4. performance-oracle (Fernet benchmarks, N+1 queries)

## P1 Fixes Applied

### 1. Transaction atomicity for multi-INSERT operations
**Section:** Model Functions > Prompt Models
**Change:** Wrapped `create_prompt` and `update_prompt` in explicit `BEGIN`/`COMMIT` with `try/except/rollback`.
**Why:** With `autocommit=True`, each `conn.execute()` auto-commits immediately. Without explicit BEGIN, a failure on the 6th component INSERT leaves an orphan prompt row with 5 of 12 components committed.

### 2. Double-decrypt bug in export_user_prompts_csv
**Section:** Model Functions > Export Models
**Change:** Decrypt each component's content once, store in variable, reuse for both filter check and output.
**Why:** Original code called `decrypt_field(c['content'])` twice per component — once in the `if` condition and once in the f-string. Wastes CPU and would double-count if Fernet had side effects (it doesn't, but the pattern is wrong).

### 3. Fernet key validation at startup
**Section:** App Configuration
**Change:** Added `Fernet(key)` call in `create_app()` to validate key format before storing in config.
**Why:** Without validation, an invalid key (wrong length, not base64) would cause `InvalidToken` errors on first encrypt/decrypt, not at startup. Fail-closed means fail at startup.

## P2 Improvements Applied

### 1. Fernet performance is NOT a bottleneck
**Finding:** Benchmarked at 115,634 decrypts/sec (0.009ms each). 1500 decrypts (worst case: 100 prompts × 15 encrypted fields) = 13ms total. No optimization needed.

### 2. Token lookup timing attack mitigated by SQL
**Finding:** SHA-256 is sufficient for token hashing. The timing of `WHERE token_hash = ?` is dominated by SQLite B-tree index lookup, not string comparison. No `hmac.compare_digest` needed at the application layer.

### 3. FTS5 trigger ordering corrected
**Finding:** BEFORE INSERT does not have NEW.id for AUTOINCREMENT tables. Corrected to: AFTER INSERT, BEFORE DELETE, split BEFORE+AFTER UPDATE. Removed duplicate trigger block from schema.

### 4. Transaction Contracts table updated
**Finding:** `create_prompt` and `update_prompt` now annotated with "explicit BEGIN for atomicity" and "try/except/rollback" error handling, matching the actual prescribed code.
