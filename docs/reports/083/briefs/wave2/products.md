# Worker Brief — WAVE 2 — products route agent (Run 083 swarmlimit)

You are a swarm worker rooted on a worktree that CONTAINS the converged spec at
`docs/plans/2026-07-21-feat-082-swarmlimit-shared-interface-spec.md`. **READ THAT SPEC FIRST — it is
authoritative.** This brief points you at your file and sections; it does not restate the spec.

## Your assignment
You own EXACTLY ONE file: **`swarmlimit/routes/products.py`** — `Blueprint('products', __name__)`,
**NO url_prefix**, full absolute paths.

Read the Route Table "### products", §3 validation rows for products, §6 Authorization Matrix,
§1b/§1d (product model functions + `record`), §2 wiring, §4 coordinated behaviors.

## Routes (full absolute paths EXACTLY — no trailing slash on collections)
- `GET /products` → `list_products` (excludes soft-deleted) | auth
- `POST /products` → `create_product` | admin | sku+name non-empty; supplier exists; price_cents ≥ 0 int; stock ≥ 0 int; category_ids all exist (400); **409** on dup sku
- `GET /products/<int:pid>` → `get_product(pid) or error('not_found',404)` (404 if soft-deleted/absent) | auth
- `PATCH /products/<int:pid>` → `update_product` | admin | whitelist name/price_cents/stock/supplier_id, types as above | 400 / 404
- `DELETE /products/<int:pid>` → `soft_delete_product` | admin | **404 only if the id never existed**; already-soft-deleted → **200** (idempotent no-op); live → **200** (sets deleted_at)
- `PUT /products/<int:pid>/categories` → `set_product_categories` | admin | category_ids = list of existing category ids | 400 / 404

Call model functions by their EXACT §1b signatures. Use `error(...)` for every error body. Audit via
`record(...)` POST-commit for create/update/delete/set-categories. Validate every input per §3. Enforce
auth per §6.

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
- FC63 assert the model return shape you consume (e.g. `get_product` includes `category_ids: list[int]`).
- FC35 order = check existence (404) before role (403) — 404-not-403 for role+own reads via the
  `*_for` getters (products are `auth`/`admin`, but keep the pattern).
- audit `record(...)` is POST-commit only, never inside a transaction.
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
