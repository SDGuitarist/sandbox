# Worker Brief — WAVE 0 — scaffold agent (Run 083 swarmlimit)

You are a swarm worker. You root on a git worktree that CONTAINS the converged shared-interface spec at
`docs/plans/2026-07-21-feat-082-swarmlimit-shared-interface-spec.md`. **READ THAT SPEC FIRST — it is
authoritative.** This brief does NOT restate it; it points you at your file and the exact sections.

## Your assignment
You own EXACTLY ONE file: **`swarmlimit/__init__.py`** (the app-factory / scaffold).

Read the spec sections that govern your file:
- "App Configuration (swarmlimit/__init__.py — scaffold agent owns this file)"
- "Namespace & Build Convention" (module-level `create_app`, init_db-if-file-absent)
- §1a Infrastructure exports (`error`, `init_db`, `list_audit`)
- §1c Blueprints & route paths (fixed registration order)
- §4 Coordinated Behaviors (response envelope, CSRF, auth-precedence, CSP)
- §6 Authorization Matrix (`GET /audit` is admin, scaffold-hosted)

## What your file must contain (all per the spec — read it for exact wording)
- `create_app(config=None)` **at MODULE LEVEL** (FC50 orchestration entrypoint). Do NOT create a
  module-level `app = create_app()` at import time.
- `SECRET_KEY` read from env, **fail-closed**: raise at startup if `SECRET_KEY` unset AND
  `FLASK_ENV != 'development'`; in development fall back to a fixed dev key with a logged warning.
- Session cookie config: `SESSION_COOKIE_HTTPONLY=True`, `SESSION_COOKIE_SAMESITE='Lax'`,
  `SESSION_COOKIE_SECURE = (FLASK_ENV != 'development')`.
- **CSRF `before_request`:** on every authenticated `POST/PUT/PATCH/DELETE`, require header
  `X-CSRF-Token == session['_csrf']` → else **400** (`error('csrf',400)` / `{"error":"csrf"}`).
  **Auth precedes CSRF:** an anonymous request has no session, so CSRF does NOT reject it — it falls
  through to the view's `login_required` → **401 `auth`**. `GET` is exempt. Login/register are exempt.
- **CSP:** static `Content-Security-Policy: default-src 'none'` response header on ALL responses.
- **`error(code: str, status: int, **extra) -> tuple[dict, int]`** helper — returns
  `({"error": code, **extra}, status)`. This is the shared error helper every route imports
  (`from swarmlimit import error`). Success convention: handlers return `(json_body, status)` with
  `json_body` always a JSON object (never a bare list).
- **Blueprint registration** in the FIXED order:
  `auth, suppliers, categories, products, orders, shipments, returns, payments`.
- **`init_db()` call-if-DB-file-absent:** call `init_db()` exactly once only when the DB file does not
  already exist (import from `swarmlimit.database`).
- **`GET /audit` admin view** hosted directly here (no blueprint) reading
  `audit_models.list_audit(...)` — admin-only auth.

**IMPORTANT (expected build ordering):** you import the route blueprints
(`suppliers, categories, products, orders, shipments, returns, payments`) and `routes.auth`, which only
exist after Wave 2. That is EXPECTED. The Wave-0 gate is **parse-only** (`python -m compileall
swarmlimit`), and full import resolves at assembly C2. Write the imports as the spec prescribes; do not
stub or work around missing modules — just ensure your own file parses.

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
- FC50 (orchestration-entrypoint signatures — read the Full Signature in §1a/§1d, never guess). Your
  `create_app` and `error` are FC50 entrypoints; `list_audit` / `init_db` are the ones you consume —
  match their exact signatures.

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
