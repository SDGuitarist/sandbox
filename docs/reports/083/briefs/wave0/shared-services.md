# Worker Brief — WAVE 0 — shared-services agent (Run 083 swarmlimit)

You are a swarm worker rooted on a worktree that CONTAINS the converged spec at
`docs/plans/2026-07-21-feat-082-swarmlimit-shared-interface-spec.md`. **READ THAT SPEC FIRST — it is
authoritative.** This brief points you at your files and sections; it does not restate the spec.

## Your assignment
You own EXACTLY TWO files:
- **`swarmlimit/refs.py`** (cross-resource ext_ref uniqueness owner)
- **`swarmlimit/models/audit_models.py`** (write-only audit lib + admin read)

Read the spec sections that govern your files:
- "### refs.py (shared-services — cross-resource ext_ref uniqueness owner)"
- "### audit_models.py (shared-services — WRITE-ONLY lib, imported by ALL mutating routes)"
- §1a/§1d (`assert_ext_ref_unique`, `record` — exact signatures)
- §4 Audit + In-tx helper discipline; §5 (assert_ext_ref_unique is a class-C read-only guard;
  `record` is class-A, route-post-commit only).

## refs.py (exact signature)
- `assert_ext_ref_unique(conn, ext_ref) -> None` — on the **caller-supplied `conn`** (in-tx, NO
  commit). Raises `ValueError('ext_ref exists')` if `ext_ref` appears in **either** `orders` OR
  `returns`. It is a SELECT that raises on collision; writes nothing. Single authority for
  cross-resource uniqueness. Called inside `create_order` and `process_return` BEFORE the insert.

## audit_models.py (exact signatures)
- `record(actor_id, action, entity_type, entity_id=None, detail=None) -> None` — inserts ONE
  audit_logs row; persists immediately via SQLite autocommit; NO `conn.commit()`. Class-A. Called
  **post-commit, route-level only**. **NEVER inside a `transaction()`** and never by a model writer.
- `list_audit(entity_type=None, limit=200) -> list[dict]` — admin audit view source (`GET /audit`,
  hosted by the scaffold in `__init__.py`).

```
## Known Pitfalls (from prior builds — MUST follow)
- FC1 (naming): Use EXACT names from the spec §1 Export Names Table / §1d Orchestration Entrypoints. Never invent a name crossing a file boundary.
- FC2 (wrong usage): Match the spec RETURN TYPE. int return → name var <x>_id; transaction() → always `with`; INTEGER → ints not strings.
- FC3 (dead wiring): Every export you create must have a consumer in §2 Cross-Boundary Wiring; don't leave a prescribed call unwired.
- FC4 (validation gap): Validate ALL inputs in YOUR handler for EVERY method per §3 — never assume another layer validates.
- FC5 (swarm consistency): Match cross-cutting patterns EXACTLY (error(...) envelope, response objects, audit record(...) signature) per §4.
- FC6 (non-transactional): Class-B units use the ONE transaction(); class-C in-tx helpers take caller conn and NEVER commit; class-A autocommit (no conn.commit(), no transaction()).
- FC7 (route paths): NO url_prefix on any blueprint; every @bp.route declares the FULL absolute path EXACTLY = the manifest (no trailing slash on collections).
- FC8 (bash): One command per Bash call. No &&/;/cd/loops/echo >/python3 -c. Use git -C and the Write tool.
- FC9 (mock/data): Read EXACT field/param names from the spec; never guess.
- FC10 (fail-closed): guards fail CLOSED on error; every route except returns an error status; never fall through without a return.

## Bash rules (MANDATORY)
One command per Bash call. (1) no `cd x && y` — use `git -C`; (2) no `source venv/activate` — full path; (3) no for-loops; (4) no `python3 -c` — Write a file; (5) no `echo` for content — Write tool; (6) no `&&`/`;` chaining.
```

## Per-role pitfalls (shared-services)
- FC6/FC29: `assert_ext_ref_unique` takes the caller `conn` and NEVER commits (class-C read-only
  guard); `record` is class-A autocommit and is NEVER called inside a `transaction()`.
- FC50 (orchestration-entrypoint signatures — read the Full Signature in §1d for
  `assert_ext_ref_unique` and `record`, never guess arity/name).
- FC63 return shapes: `list_audit` returns `list[dict]` (convert `sqlite3.Row` → plain dict).

## Strict rules
1. Create ONLY your assigned file(s). No other files. (smoke-author also writes its two docs/reports/083 artifacts.)
2. Use EXACT names from the spec for all functions, routes, classes, variables.
3. Do not make design decisions — the spec at docs/plans/2026-07-21-feat-082-swarmlimit-shared-interface-spec.md decides everything. READ IT FIRST.
4. Do not import from other agents' files except as §2 Cross-Boundary Wiring defines.
5. Follow the spec's directory structure exactly (swarmlimit/ namespace).
6. If the spec is ambiguous, pick the simplest interpretation.
7. No TODOs, no placeholders — production-quality code.
8. Create any directories your files need.
9. When done, commit ALL your files with a descriptive message (one Bash call: git -C <worktree> add -A ; then a separate git -C <worktree> commit -m "...").
