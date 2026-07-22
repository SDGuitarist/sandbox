# Worker Brief — WAVE 0 — auth-core agent (Run 083 swarmlimit)

You are a swarm worker rooted on a worktree that CONTAINS the converged spec at
`docs/plans/2026-07-21-feat-082-swarmlimit-shared-interface-spec.md`. **READ THAT SPEC FIRST — it is
authoritative.** This brief points you at your files and sections; it does not restate the spec.

## Your assignment
You own EXACTLY THREE files:
- **`swarmlimit/auth.py`** (decorators + session helpers)
- **`swarmlimit/models/auth_models.py`** (user model)
- **`swarmlimit/routes/auth.py`** (auth blueprint)

Read the spec sections that govern your files:
- "### auth_models.py (auth-core)"
- "### swarmlimit/auth.py (auth-core — decorators & session helpers, NOT a model)"
- "Ownership-Scoped Getter Contract" (you DOCUMENT it here; per-resource getters are Wave-1)
- Route Table "### auth" + the `POST /auth/register` privilege pin
- §3 validation rows for register/login/logout; §6 Authorization Matrix auth rows.

## auth_models.py (exact signatures)
- `create_user(email, password, role, name) -> int` — hashes password (`werkzeug`); raises
  `ValueError('email exists')` on UNIQUE. Persists immediately via SQLite autocommit; no `conn.commit()`.
  Keeps the `role` param for trusted seed/internal callers.
- `get_user(user_id) -> dict | None`
- `get_user_by_email(email) -> dict | None`
- `verify_credentials(email, password) -> dict | None` — user dict if password matches, else None.

## auth.py (exact signatures)
- `login_user(user: dict) -> None` / `logout_user() -> None` — set/clear session; login MINTS `session['_csrf']`.
- `current_user() -> dict | None` — logged-in user row (cached on `g`).
- `login_required(view)` — **401** (`error('auth',401)`) when anonymous (no redirect — JSON API).
- `role_required(*roles)` — **PINNED TWO-BRANCH contract, does NOT rely on decorator stacking order:**
  if `current_user()` is `None` → **401** `error('auth',401)`; ONLY if authenticated AND
  `current_user()['role']` not in `roles` → **403** `error('forbidden',403)`. Anonymous ALWAYS → 401,
  never a `None['role']` crash.
- **Ownership-Scoped Getter Contract** is DEFINED/documented here (the uniform SQL-WHERE-predicate rule
  for `get_<x>_for(<id>, actor)` / `list_<x>_for(actor, **filters)`), but the per-resource getters
  themselves are implemented by the Wave-1 model agents — you do NOT implement them.

## routes/auth.py (exact per Route Table)
- `POST /auth/register` — **ALWAYS creates a `customer`**: call
  `create_user(email=..., password=..., role='customer', name=...)`, ignoring any client-supplied
  `role`. Returns **201**, NO session established. Validation: email non-empty + `@`; password ≥ 8.
- `POST /auth/login` — validate email+password non-empty (401 `auth` on failure, no field leak); on
  success establish session and return **200** with `csrf_token` in the body.
- `POST /auth/logout` — auth; CSRF header validated (400 `csrf` on mismatch) else 200.
Blueprint: `Blueprint('auth', __name__)`, NO url_prefix, full absolute paths.

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

## Per-role pitfalls (scaffold/auth)
- scaffold/auth: SECRET_KEY fail-closed (raise if unset AND FLASK_ENV!=development); set security/CSP
  headers; session cookie HTTPONLY + SameSite=Lax + SECURE only when FLASK_ENV!=development.
- FC50 (orchestration-entrypoint signatures — read the Full Signature in §1a/§1d, never guess).
  `login_required`, `role_required`, `current_user` are consumed by every route — match §1a exactly.

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
