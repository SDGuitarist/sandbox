# Worker Brief — WAVE 0 — smoke-author agent (Run 083 swarmlimit)

You are a swarm worker rooted on a worktree that CONTAINS the converged spec at
`docs/plans/2026-07-21-feat-082-swarmlimit-shared-interface-spec.md`. **READ THAT SPEC FIRST — it is
authoritative.** This brief points you at your files and sections; it does not restate the spec.

## Your assignment
You own EXACTLY THREE artifacts:
- **`swarmlimit/smoke.py`** (the smoke harness)
- **`docs/reports/083/planned-manifest.json`** (the frozen immutable manifest)
- **`docs/reports/083/pitfalls-baseline.txt`** (frozen agent-pitfalls baseline)

Read the spec sections that govern your work:
- "Namespace & Build Convention" (canonical location + `python -m swarmlimit.smoke` + Temp-DB pin)
- "Acceptance Tests (EARS)" + "The 10 Path-B `--case` harness" table (EXACT case names + assertions)
- "Immutable Planned Manifest" block (the EXACT JSON + the exercised-set capture pin)
- §1a `_TX_FAULT` seams; §5 fault-injection seam.

## smoke.py must contain
- Entry `python -m swarmlimit.smoke` — an `if __name__ == '__main__':` block with `argparse` accepting
  `--case <name>` and `--manifest <path>` (both absent → full default suite).
- Builds its OWN app via `from swarmlimit import create_app` against a temp DB at a
  **NOT-YET-EXISTING child path** of a `tempfile.TemporaryDirectory()` (e.g.
  `<tempdir>/swarmlimit.sqlite`) so `create_app()`'s init_db-if-file-absent check fires and `init_db()`
  runs once. **NEVER `:memory:`, NEVER a pre-created `NamedTemporaryFile`/`mkstemp` path** (FC49 — an
  existing file makes the absence check false → schema never created).
- The **10 Path-B `--case` harness** — EXACT case names + assertions from the spec's "The 10 Path-B
  `--case` harness" table: `state-machine-legal`, `state-machine-illegal` (three sub-checks, each
  409 + status preserved), `uniqueness-ok`, `uniqueness-collision`, `soft-delete`, `soft-delete-order`,
  `process-return`, `process-return-rollback`, `process-return-guard-refund`,
  `process-return-guard-shipment`. Each returns exit 0 on pass, non-0 on fail.
- Core (default-suite) cases: create_order value assertions (integer ids, no `{'`/`[object Object]`),
  concurrency stock-race, create_order mid-tx rollback via `order_models._TX_FAULT` (value-compare
  stock), IDOR-404, admin-403, anon-401, CSRF-400, SECRET_KEY fail-closed (assert `create_app()`
  raises), **register-role-ignored** (register `role=admin` → customer, 201, no session; then login,
  read `csrf_token` from login body, POST an admin route → 403), **shipment-unique** (2nd
  `POST /orders/<oid>/shipments` → 409, no row, incl. after first shipment `returned`).
- **`_TX_FAULT` seams:** for rollback cases, set `order_models._TX_FAULT` / `return_models._TX_FAULT`
  to a raising callable, drive a VALID unit, assert the exception propagated OUT of the `with` block
  (→ ROLLBACK), then RESET to `None`. Assert INSERT counts unchanged AND UPDATE-VALUES unchanged
  (shipment status still `delivered`, product stock unchanged).
- **Manifest-equality via per-request capture:** register a Flask `after_request` that appends
  `(request.method, request.url_rule.rule)` to a module-level set (SKIP requests where
  `request.url_rule is None`). Do NOT infer the exercised set from `app.url_map`. Under
  `--manifest <R>/planned-manifest.json` compare the exercised set against the manifest `endpoints`.
- **Report writing:** under `--manifest <R>/planned-manifest.json`, DERIVE `<R>` from the manifest's
  parent dir and write **`<R>/c2-smoke-report.md`** with **line-1 `STATUS: PASS|FAIL`**, the exercised
  set, `planned_minus_exercised` + `exercised_minus_planned` deltas, and be **expected-status-aware**:
  asserted negatives (400/401/403/404/409) are EXPECTED and pass; only an unexpected/unasserted status
  mismatch fails C2. Plain no-arg run does NOT write the report and does NOT run manifest-equality.

## planned-manifest.json
Write the **EXACT JSON** from the spec's "Immutable Planned Manifest" block (run, resources, the 31
endpoints, the two transactions), with **`content_hash` computed** = SHA-256 over the canonicalized
JSON with the `content_hash` field removed.

## pitfalls-baseline.txt
Read `~/.claude/docs/agent-pitfalls.md` and freeze the current failure-class-ID set + the file line
count into this file.

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

## Per-role pitfalls (smoke-author)
- FC49: real on-disk SQLite file inside a `TemporaryDirectory` at a NOT-YET-EXISTING child path; never
  `:memory:`, never a pre-created `NamedTemporaryFile`/`mkstemp` path (init_db must run).
- Exercised-set capture: per-request `(request.method, request.url_rule.rule)` via `after_request`
  (skip `url_rule is None`) — NEVER inferred from `app.url_map`.
- `content_hash` = SHA-256 over canonicalized JSON with the `content_hash` field REMOVED.
- Report line-1 must be exactly `STATUS: PASS` or `STATUS: FAIL`; be expected-status-aware.

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
