# ShelfTrack — Brainstorm

**Date:** 2026-06-30
**Mode:** Autopilot (simplest-option decisions, no interactive prompts)
**Status:** Throwaway validation build (vehicle for G1+G3 Step 3 coexistence re-validation). Minimal but real.

## App Brief

**Name:** ShelfTrack
**Target user:** Multiple registered users; each user has a private reading list. Public self-registration. A user only ever sees/edits their own books (per-user ownership).
**Tech stack:** Flask + SQLite (stdlib `sqlite3`) + Jinja2 server-rendered templates. Sandbox standard. Spec template: `docs/templates/shared-spec-flask.md`.

**Core features (Phase 1 — this build):**
- Register / log in / log out (session-cookie auth; password hashing)
- Add a Book: `title`, `author`, `status` ∈ {want, reading, done}
- Edit / delete your **own** books (role+ownership auth)
- List your books, filter by status
- Server-rendered templates, navbar, flash messages
- CSRF protection on all POST forms

**Explicitly out of scope for MVP:**
- Cover images, external book metadata APIs (hard requirement: no external APIs)
- Ratings, reviews, notes, tags
- Search, sort, pagination
- Password reset / email verification
- Sharing / social / public shelves
- Admin role (the only roles are "logged-in owner" and "anonymous")

## Roadmap

**Phase 1 (MVP — this build):**
- Session auth (register/login/logout)
- Book CRUD scoped to the owning user
- Status filter (want/reading/done)
- Navbar + flash messages + CSRF

**Phase 2 (future):**
- Search + sort by title/author/date
- Notes / rating per book
- Pagination for large shelves

**Phase 3 (if needed):**
- Reading stats (counts per status, books/month)
- CSV export

## Key Design Decisions (simplest option chosen)

1. **Auth model:** Server-side session cookie holding `user_id`. Passwords hashed with Werkzeug `generate_password_hash` / `check_password_hash`. No JWT, no external auth. *Simplest that is still real.*
2. **Ownership enforcement:** Every book row has `user_id` FK. Every book route (view/edit/delete/update) filters `WHERE id=? AND user_id=?` — ownership is verified in the same query, not as a separate check-then-act (avoids FC35 IDOR and FC43 TOCTOU).
3. **Status as a constrained enum:** `status TEXT NOT NULL CHECK(status IN ('want','reading','done'))` at the DB layer AND validated in the route. Belt-and-suspenders per FC4.
4. **Filter:** `GET /books?status=reading` — validate the query param against the allowlist; unknown/absent → show all. No dynamic SQL string-building (parameterized only).
5. **One blueprint or two?** Two blueprints: `auth` (register/login/logout) and `books` (list/new/create/edit/update/delete). Keeps ownership boundaries clean for a swarm split.
6. **Templates:** `base.html` (navbar + flash block) + `register.html`, `login.html`, `books/list.html`, `books/form.html`. Jinja2 autoescape ON, no custom `Markup` filters (avoids FC47).
7. **SECRET_KEY:** Read from env, **fail-closed** — the app factory raises if `SECRET_KEY` is unset (no dev fallback). Per Feedback Board + Client Intake lessons.
8. **DB writes:** `with conn:` context-managed transactions (reliable under Python 3.14 autocommit); ownership-scoped UPDATE/DELETE.

## Acceptance Criteria (preview — formalized in plan as EARS)

- Register with valid unique username → 302 to login, user row created (hashed password).
- Register with duplicate username → re-render form with flash, no row created.
- Login valid → session set, 302 to book list. Login invalid → flash, no session.
- Add book with valid fields → row created with `user_id` = current user, 302 to list.
- Edit/delete a book you don't own → 404 (not 403 — don't leak existence).
- Filter `?status=reading` → only that user's reading books.
- Any POST without CSRF token → 400.

## Feed-Forward

- **Hardest decision:** Whether editing/deleting someone else's book should return 403 or 404. Chose **404** — returning 403 leaks that the resource exists. The ownership filter is baked into the SELECT/UPDATE/DELETE `WHERE`, so a non-owner simply gets zero rows → 404. This is the single most security-relevant decision (FC35 IDOR).
- **Rejected alternatives:** (a) Single monolithic `app.py` — rejected because it doesn't exercise the swarm ownership-boundary split that this run is validating. (b) Flask-Login extension — rejected as over-engineering; a plain session `user_id` + a `@login_required` decorator is simpler and real. (c) SQLAlchemy ORM — rejected; stdlib `sqlite3` matches the sandbox Flask template and keeps transaction semantics explicit.
- **Least confident:** The ownership enforcement path — specifically that EVERY book route (not just delete) filters by `user_id` in-query. A single route that queries by `id` alone is a silent IDOR. This is the flow the review's flow-trace and the plan's Feed-Forward risk should scrutinize.
