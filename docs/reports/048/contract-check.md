# Spec Contract Check Report

**Plan:** client-music-planner-plan.md
**Date:** 2026-05-19
**Total checks:** 90 | **PASS:** 67 | **FAIL:** 23

## Critical Failures (Must Fix)

### portal_playlist (13 failures)
- Blueprint hardcodes `url_prefix='/portal'` -> double-prefix `/portal/portal/...`
- `playlist()` passes `items` not `playlist_items`, omits `song_requests` and `is_approved`
- `add_to_playlist` ignores `g.portal_event`, re-queries with nonexistent `musician_id` column
- `add_to_playlist` bypasses `add_playlist_item()` model, does direct SQL INSERT with NO `db.commit()`
- `remove_from_playlist` reads `item_id` form field (spec says `song_id`)
- `remove_from_playlist` bypasses `remove_playlist_item()` model, does direct SQL with NO `db.commit()`
- Three `url_for('portal_landing.index')` calls -> nonexistent blueprint -> `BuildError`
- `playlist.html` uses `{% block portal_content %}` but `portal_base.html` defines `{% block content %}`

### repertoire_import (5 failures)
- `__init__.py` exports `repertoire_import_bp` not `bp` -> `ImportError` at startup
- No `@login_required` on any route
- `import_confirm` calls `bulk_insert_repertoire` (nonexistent) instead of `bulk_create_songs`
- `import_confirm` uses `get_db()` not `get_db(immediate=True)`, no `db.commit()`
- `import_preview` passes wrong render_template variables

STATUS: FAIL

## Fix Attempt

**Errors addressed:** 23
**Files modified:**
- `client-music-planner/app/portal_playlist/__init__.py` -- removed hardcoded `url_prefix='/portal'` that caused double-prefix `/portal/portal/...`
- `client-music-planner/app/portal_playlist/routes.py` -- full rewrite: uses `g.portal_event` throughout, calls model functions (`get_playlist_items`, `get_song_requests`, `get_next_position`, `add_playlist_item`, `remove_playlist_item`), adds `db.commit()` on all write paths, uses `get_db(immediate=True)` for writes, removes all `url_for('portal_landing.index')` calls, uses `song_id` not `item_id` for remove form field
- `client-music-planner/app/templates/portal_playlist/playlist.html` -- fixed `{% block portal_content %}` to `{% block content %}`, uses `playlist_items` not `items`, shows `is_approved` state and `song_requests` section, fixes remove form hidden field from `item_id` to `song_id`, adds `csrf_token()` to forms
- `client-music-planner/app/repertoire_import/__init__.py` -- exports `bp` (not `repertoire_import_bp`), removes hardcoded `url_prefix` (set in app factory), uses relative import for routes
- `client-music-planner/app/repertoire_import/routes.py` -- adds `@login_required` to all three routes, fixes `import_confirm` to call `bulk_create_songs(db, user_id, rows)` with `get_db(immediate=True)` and `db.commit()`, fixes `import_preview` render_template to use spec variables (`songs`, `filename`, `error_rows`, `valid_count`), fixes blueprint reference from `repertoire_import_bp` to `bp`, fixes imports to use relative paths

**Fixes applied:**
1. `portal_playlist/__init__.py`: removed `url_prefix='/portal'` -- the app factory already registers this blueprint at `/portal`, so this caused every URL to be `/portal/portal/...`
2. `portal_playlist/routes.py` `playlist()`: now uses `g.portal_event['id']` (set by `@require_portal_token` decorator) instead of re-querying; calls `get_playlist_items()` and `get_song_requests()` model functions; passes `playlist_items`, `song_requests`, and `is_approved` to template
3. `portal_playlist/routes.py` `add_to_playlist()`: uses `get_next_position()` and `add_playlist_item()` model functions; wraps in `get_db(immediate=True)`; calls `db.commit()`; catches `IntegrityError` for duplicate-song case; uses `url_for('portal_browse.browse')` on invalid input
4. `portal_playlist/routes.py` `remove_from_playlist()`: reads `song_id` form field (not `item_id`); calls `remove_playlist_item()` model function; wraps in `get_db(immediate=True)`; calls `db.commit()`
5. `playlist.html`: changed `{% block portal_content %}` to `{% block content %}` to match `portal_base.html` block name; changed `items` to `playlist_items` throughout; added `is_approved` conditional to show read-only vs. editable view; added `song_requests` display section; fixed remove form to send `song_id` hidden field; added `csrf_token()` to all forms
6. `repertoire_import/__init__.py`: renamed `repertoire_import_bp` to `bp` to match app factory import (`from .repertoire_import import bp as repertoire_import_bp`); removed redundant `url_prefix`; changed absolute import to relative import for routes
7. `repertoire_import/routes.py`: added `@login_required` decorator to `import_form`, `import_preview`, and `import_confirm`; fixed `import_confirm` to use `bulk_create_songs(db, user_id, rows)` instead of nonexistent `bulk_insert_repertoire`; fixed to use `get_db(immediate=True)` and `db.commit()`; added `session['user_id']` lookup for ownership; fixed `import_preview` to pass `songs`, `filename`, `error_rows`, `valid_count` to template; changed all imports to relative paths

STATUS: FIXED
