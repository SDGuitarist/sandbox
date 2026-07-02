STATUS: PASS

# Deepening Applied — Run 080

**Plan:** docs/plans/2026-06-30-shelftrack-reading-list.md

## Corrections Applied

| # | Section | Change | Rationale |
|---|---------|--------|-----------|
| 1 | App Configuration (`app/__init__.py`) | Moved `app.teardown_appcontext(_close_db)` to ABOVE the init-db `with app.app_context()` block; added inline comment. | teardown registered after the init block leaks the init connection (kieran-python P2). |
| 2 | Database Connection (`app/database.py`) | Added bold note under Rules: Python ≥ 3.12 requirement for `autocommit=` kwarg and unsupported `DATABASE=:memory:` warning with reasoning. | kieran-python P1/P2. |
| 3 | Password hashing (Model Functions + Input Validation Prescriptions) | Added explicit prescription block: register route uses `generate_password_hash`, login uses `check_password_hash`, `create_user` stores already-hashed value. | Hash function was never named; prevents a weak improvised scheme (security-sentinel P2-1). |
| 4 | Route Table | Added explicit `methods=` prescriptions for every endpoint beneath the Route Table note; explained collision/405 risk. | Two endpoints on one path collide or 405 without disjoint methods (spec-flow Gap1). |
| 5 | Input Validation Prescriptions (GET /books status filter row) | Pinned enforcement site: `status = request.args.get('status'); if status not in (...): status = None`; passes sanitized value to model and template as `current_status`. | Enforcement site must be pinned or swarm agents diverge (spec-flow Gap4). |
| 6 | Template Render Context (books/form.html) | Added sticky-form re-render signatures for new-error and edit-error; `statuses=` on every render; None-safe template idiom; note against StrictUndefined; edit-error uses URL's `book_id` not `book['id']`. | Empty status select on edit + wiped fields on error + None-attr safety (kieran P2, spec-flow Gap2/Gap6/Gap7). |
| 7 | Template Render Context (books/list.html) + empty states | Added two distinct empty-state message prescriptions (no filter vs active filter with zero matches) and four success flash messages. | Zero-match filter looks broken; success closure (spec-flow Gap3/Gap7 minor). |
| 8 | Coordinated Behaviors (logout CSRF) | Added Logout CSRF row to the table: base.html navbar logout form must include CSRF hidden input. | CSRFProtect 400s every logout without it (security-sentinel P2-5). |
| 9 | NEW section: "Deferred Hardening (throwaway validation build)" | Added section listing consciously deferred items: timing enumeration, rate limiting, security headers, password min-length, next-URL redirect, custom error templates. | security-sentinel P2-2/3/4/7 + spec-flow Gap5 — flagged, not silently omitted. |

## Unapplied (if any)

| Section | Reason |
|---------|--------|
