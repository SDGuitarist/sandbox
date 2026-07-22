# Worker Brief — WAVE 2 — orders route agent (Run 083 swarmlimit)

You are a swarm worker rooted on a worktree that CONTAINS the converged spec at
`docs/plans/2026-07-21-feat-082-swarmlimit-shared-interface-spec.md`. **READ THAT SPEC FIRST — it is
authoritative.** This brief points you at your file and sections; it does not restate the spec.

## Your assignment
You own EXACTLY ONE file: **`swarmlimit/routes/orders.py`** — `Blueprint('orders', __name__)`,
**NO url_prefix**, full absolute paths.

Read the Route Table "### orders", §3 validation row for POST /orders, §6 Authorization Matrix,
§1b/§1d (order model functions + `record`), §2 wiring, §4 coordinated behaviors.

## Routes (full absolute paths EXACTLY — no trailing slash on collections)
- `GET /orders` → `list_orders_for(current_user())` | role+own (customer→own, admin→all)
- `POST /orders` → `create_order` | auth | ext_ref non-empty; items non-empty; each qty > 0 int; each product_id int (400 `validation`). **`user_id` resolution:** omitted → the current actor's id (both roles); a customer is ALWAYS forced to their own id (any supplied `user_id` ignored); only an admin may pass an explicit `user_id`. **409 `conflict`** on ext_ref collision OR insufficient stock OR unavailable product (in-tx guards raise ValueError → map to 409).
- `GET /orders/<int:oid>` → `get_order_for(oid, current_user()) or error('not_found',404)` | role+own (404 for non-owner)

`create_order` OWNS its transaction — the ROUTE just calls it and never manages a transaction. Map its
raised ValueErrors to **409 `conflict`**. Audit via `record(...)` POST-commit (after `create_order`
returns). Use `error(...)` for every error body. Enforce auth per §6.

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

## Per-role pitfalls (route cluster)
- FC50 entrypoint lookup (read the Full Signature in §1d, never guess arity/name).
- FC63 assert the model return shape you consume (`get_order_for` → dict|None with `items`+`total_cents`).
- FC35 order = check existence (404) before role (403) — 404-not-403 for role+own reads via the
  `*_for` getters; `GET /orders/<int:oid>` returns 404 (not 403) for a non-owner.
- audit `record(...)` is POST-commit only, never inside a transaction (never pass it into `create_order`).
- FC7 full absolute paths, no url_prefix.
- FC4 validate every input per §3.

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
