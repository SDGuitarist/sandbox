# Pre-Swarm Spec Consistency Check

**Plan:** client-music-planner-plan.md
**Checked:** 2026-05-19

## Results

| # | Category | Left Side | Right Side | Status | Detail |
|---|----------|-----------|------------|--------|--------|
| 1 | Schema vs Route | CSV format: column `key` | `bulk_create_songs` dict key `musical_key` | FAIL | CSV header row (line 862) uses `key`; `bulk_create_songs` reads `s.get('musical_key', '')` (line 586) and preview render context says dict keys include `musical_key` (line 1026). The repertoire-import agent must map `key` -> `musical_key` but this mapping is never specified. An agent reading the CSV format section will produce dicts with key `key`, which `bulk_create_songs` will silently ignore (returning `''` via `.get('musical_key', '')`). All songs will be imported with blank `musical_key`. |
| 2 | Schema vs Route | `musical_key` (schema column, model params, form fields, preview dict) | CSV header `key` | FAIL | Same contradiction as row 1, stated from the other direction. The form field spec says `musical_key` (line 1015), the `create_song` signature says `musical_key` (line 556), the `UPDATE song SET musical_key=?` uses `musical_key` (line 568). Only the CSV format section (line 862) uses the shorter name `key`. |
| 3 | Export vs Import | `get_event_by_token(db, token)` in decorators.py | `from .models import get_event_by_token` in decorators.py | PASS | Import statement matches function definition exactly. |
| 4 | Export vs Import | `approve_event(db, event_id)` signature | `approve_event(db, g.portal_event['id'])` in portal_approve route | PASS | Argument count and types match. |
| 5 | Export vs Import | `update_playlist_positions(db, event_id, item_ids_in_order)` | `update_playlist_positions(db, event['id'], item_ids)` in api_playlist | PASS | Matches. item_ids are mapped to int by JS before sending. |
| 6 | Export vs Import | `toggle_playlist_flag(db, event_id, song_id, flag_type)` | `toggle_playlist_flag(db, g.portal_event['id'], song_id, flag_type)` in portal_flags | PASS | Matches. |
| 7 | Export vs Import | `get_playlist_items(db, event_id)` | called in event_dashboard, api_playlist | PASS | Both call sites use single `event_id` int argument. |
| 8 | Route Methods vs Route Table | `confirm_approval POST /<token>/approve/confirm` (Endpoint Registry) | Same definition in Cross-Boundary Wiring and Transaction Boundary Rules | PASS | All three sections agree on method and path. |
| 9 | Route Methods vs Route Table | All 14 blueprints in App Factory | All 14 blueprint url_for prefixes in Endpoint Registry | PASS | App Factory registers blueprints: auth, dashboard, repertoire, repertoire_import, events, event_dashboard, event_export, portal_browse, portal_playlist, portal_flags, portal_requests, portal_approve, api_playlist, api_filters. All match Endpoint Registry sections exactly. |
| 10 | Export vs Import | `url_for('dashboard.index')` in App Factory index() | `dashboard.index` in Endpoint Registry | PASS | Matches. |
| 11 | Export vs Import | `url_for('auth.login')` in login_required decorator | `auth.login` in Endpoint Registry | PASS | Matches. |
| 12 | Export vs Import | `url_for('portal_browse.browse', token=token)` in require_portal_writable | `portal_browse.browse` in Endpoint Registry | PASS | Matches. |
| 13 | Export vs Import | `url_for('portal_playlist.add_to_playlist', token=...)` in browse.html wiring | `portal_playlist.add_to_playlist` in Endpoint Registry | PASS | Matches. |
| 14 | Export vs Import | `url_for('portal_playlist.playlist', token=token)` in add_to_playlist route | `portal_playlist.playlist` in Endpoint Registry | PASS | Matches. |
| 15 | SQL Types vs App Types | `energy INTEGER` in schema | `int(energy)` in create_song, update_song, bulk_create_songs | PASS | All model functions explicitly cast to int before INSERT/UPDATE. |
| 16 | SQL Types vs App Types | `client_approved INTEGER` in schema | `bool(event['client_approved'])` in require_portal_token | PASS | Valid Python: 0 -> False, 1 -> True. |
| 17 | SQL Types vs App Types | `is_archived INTEGER NOT NULL DEFAULT 0` in schema | `event['is_archived']` used as truthy in decorator and api routes | PASS | Truthy check on 0/1 integer is correct. |
| 18 | SQL Types vs App Types | `position INTEGER NOT NULL DEFAULT 0` in schema | `get_next_position` returns int from SQL COALESCE | PASS | Types align. |
| 19 | Schema vs Route | `playlist_item.client_note TEXT` (schema column) | No model function reads or writes `client_note` | WARN | The `client_note` column exists in the schema but no model function references it. `add_playlist_item` does not accept a `client_note` parameter. It is unclear if this column is intentionally unused or if it was meant to be populated. If unused, it is dead schema. If it should be settable by the client, a model function and route field are missing. |
| 20 | Jinja2 Filters vs Templates | `format_date`, `format_duration`, `format_genre`, `format_energy` registered in filters.py | Same four names used in template usage section | PASS | Exact string match for all four filter names. |
| 21 | Mock/Fixture Data vs Schema | seed.py is assigned but no content given | N/A | N/A | Seed data content is not specified in the plan. Cannot verify mock data field names against schema. Seed agent must independently derive field names from the schema section. |
| 22 | Template Render Context | `portal_requests/requests.html` receives `requests=requests` | `requests` is the list variable name | WARN | The template variable is named `requests` (plural). This does not conflict with Flask's `request` object (singular), but it shadows the `requests` third-party library name in Python scope if that library is ever imported. Agents may find this confusing. No functional breakage, but the variable name is unusual. |
| 23 | Cross-Boundary Wiring | `get_song_request_count(db, event_id)` exported from models.py | No code block in any section calls this function | WARN | The function is defined but has no declared consumer in the Endpoint Registry, Cross-Boundary Wiring, or Template Render Context sections. The Data Ownership table lists `song_request` readers as `portal-requests, portal-playlist, portal-approve, event-dashboard, event-export` -- but none of their code blocks show a call to `get_song_request_count`. Likely intended for `events/detail.html` context (`request_count=request_count` is in the render context), but the wiring for how `request_count` is computed is not shown. |
| 24 | Cross-Boundary Wiring | `get_user_by_id(db, user_id)` exported from models.py | No code block in any section calls this function | WARN | Likely used by auth or dashboard to look up the current user's display name, but no route handler code block shows the call. Agents working on auth or dashboard must infer this usage. |
| 25 | Directory Structure | `templates/dashboard/index.html` | Listed twice in Directory Structure | WARN | The directory tree lists `templates/dashboard/` with `index.html` at two separate locations in the tree (once near line 1500, once at the end of the templates block near line 1526). One entry is a duplicate. This will not cause a build failure but may confuse the layout-static or dashboard agents when reading the spec. |
| 26 | Flash Message Consistency | `flash("Your selections have been approved!", "success")` in Transaction Boundary Rules example | `flash("Your selections have been approved! Thank you.", "success")` in Cross-Boundary Wiring section | WARN | The same `confirm_approval` route shows two different flash messages across two spec sections. Agents will produce one or the other depending on which section they read last. The difference is cosmetic but creates an inconsistency between sections describing the same route. |
| 27 | Schema vs Route | `portal_requests` Endpoint Registry form fields for `add_request`: `title` (str, required), `artist` (str), `notes` (str) | `add_song_request(db, event_id, title, artist, notes)` model function | PASS | Form field names match model function parameters. All three match schema column names (`title`, `artist`, `notes`). |
| 28 | Schema vs Route | `portal_playlist` Endpoint Registry form fields for `add_to_playlist` and `remove_from_playlist`: `song_id` (int) | `add_playlist_item(db, event_id, song_id, position)` and `remove_playlist_item(db, event_id, song_id)` | PASS | Form field `song_id` matches both model function parameters and schema column name. |
| 29 | Schema vs Route | `portal_flags` Endpoint Registry form fields: `song_id` (int), `flag_type` (str) | `toggle_playlist_flag(db, event_id, song_id, flag_type)` model function | PASS | Form fields match model function parameters exactly. |
| 30 | Schema vs Route | `events` form fields: `name`, `event_date`, `event_type`, `venue`, `client_name`, `client_email`, `notes` | `create_event(db, user_id, name, event_date, event_type, venue, client_name, client_email, portal_token)` and `update_event(db, ..., name, event_date, event_type, venue, client_name, client_email, notes)` | PASS | All form fields appear as model function parameters. `portal_token` in `create_event` is generated server-side (not a form field). `notes` is absent from `create_event` but present in `update_event` and schema -- the CREATE form allows notes but the model function does not accept notes as a parameter. Minor omission in `create_event` signature but not a cross-section naming contradiction. |
| 31 | Template Render Context vs Schema | `events/detail.html` context: `portal_url=portal_url` constructed as `request.host_url.rstrip('/') + url_for('portal_browse.browse', token=event['portal_token'])` | Schema column: `portal_token` | PASS | Column name `portal_token` matches the access pattern `event['portal_token']`. |
| 32 | API Response vs JS Consumer | `api_filters` returns `{"songs": [{"id", "title", "artist", "genre", "energy", "duration_seconds", "in_playlist"}]}` | JS reads `data.songs` and passes to `renderSongList` | PASS | Top-level key `songs` matches. Individual field names align with schema column names (`id`, `title`, `artist`, `genre`, `energy`, `duration_seconds`) plus computed field `in_playlist`. |
| 33 | API Response vs JS Consumer | `api_playlist` reorder returns `{"success": true}` or `{"error": "message"}` | JS reads `result.data.success` and `result.data.error` | PASS | Field names match. |
| 34 | API Response vs JS Consumer | `portal_flags` returns `{"success": true, "is_must_play": 0, "is_do_not_play": 1}` | JS reads `data.success`, `data.is_must_play`, `data.is_do_not_play` | PASS | Field names match exactly. |
| 35 | Schema vs Route | `portal_flags` returns `jsonify(success=True, **result)` where result is `{'is_must_play': new_must, 'is_do_not_play': 0}` | Schema columns: `is_must_play`, `is_do_not_play` | PASS | JSON response field names match schema column names. |
| 36 | Export vs Import | Blueprint `__init__.py` template says `bp = Blueprint('{blueprint_name}', __name__)` with name matching url_for prefix | All 14 blueprint names in App Factory match Endpoint Registry url_for prefixes | PASS | Verified all 14: auth, dashboard, repertoire, repertoire_import, events, event_dashboard, event_export, portal_browse, portal_playlist, portal_flags, portal_requests, portal_approve, api_playlist, api_filters. |
| 37 | Template Paths | All `render_template()` paths in Template Render Context section | All corresponding entries in Directory Structure `templates/` tree | PASS | Every template path matches. No template is referenced but missing from the directory tree, and no template is in the directory tree but missing from render_template calls (except portal_flags which correctly has no template, being AJAX-only). |
| 38 | Decorator vs Route | `require_portal_writable` redirects to `url_for('portal_browse.browse', token=token)` | `portal_browse.browse` accepts `token` URL parameter | PASS | Endpoint Registry confirms `browse` takes `/<token>` path parameter. |
| 39 | Schema vs Route | `create_event` model function does NOT include `notes` parameter | `update_event` DOES include `notes` parameter; form fields include `notes` | WARN | The event CREATE form lists `notes` as a form field, but `create_event(db, user_id, name, event_date, event_type, venue, client_name, client_email, portal_token)` has no `notes` parameter. The schema column `notes TEXT NOT NULL DEFAULT ''` has a default empty string, so omitting it from INSERT is safe (it will be empty). But the musician's notes entered on the create form will be silently discarded. The events agent must either (a) pass notes to the INSERT or (b) call `create_event` then `update_event` to set notes. This is a cross-section gap, not a naming mismatch, but worth flagging. |
| 40 | Schema vs Route | `api_playlist reorder` uses `get_db()` for read then `get_db(immediate=True)` for write in two separate connection blocks | `get_event_by_token` Row object used across the connection boundary | PASS | `sqlite3.Row` data is fully materialized in memory after fetchone(), so the row can be safely read after the connection closes. No dangling reference. |

## Detailed Finding: Row 1 and 2 (FAIL)

The CSV import has a field naming gap that will cause silent data loss:

**CSV header spec (Endpoint Registry, CSV format block):**
```
title,artist,genre,key,tempo,energy,duration_seconds,notes
```

**`bulk_create_songs` model function (models.py Song Functions):**
```python
s.get('musical_key', '')   # expects key named 'musical_key'
```

**Preview render context (Template Render Context, repertoire_import section):**
```python
songs=parsed_songs,  # list[dict] with keys: title, artist, genre, musical_key, ...
```

**Repertoire form field name (Form Field Names section):**
```
create/edit: title, artist, genre, musical_key, ...
```

The CSV column is `key`. The dict key expected everywhere else is `musical_key`. The repertoire-import agent will parse CSV column `key` into a dict with key `key`. When `bulk_create_songs` is called with that dict, `s.get('musical_key', '')` returns empty string every time. All imported songs will have blank `musical_key` regardless of what the CSV contained. No error is raised.

**Fix required:** Change CSV format spec to `musical_key` OR add explicit mapping instruction `'musical_key': row['key']` in the import parsing code block.

## Detailed Finding: Row 19 (WARN)

The `playlist_item.client_note` column is defined in the schema but no model function references it:

- `add_playlist_item(db, event_id, song_id, position)` -- no `client_note` parameter
- `toggle_playlist_flag` -- does not touch `client_note`
- `get_playlist_items` -- selects `pi.*` which includes `client_note`, so it IS read in JOINed results

The column appears to be intended for a future feature (client can annotate a playlist item). Since `get_playlist_items` uses `pi.*`, the data is available in templates. But there is no write path -- clients cannot set `client_note` through any specified route. This is either intentional (column reserved for future use) or an incomplete feature. Either way, no agent needs to actively handle it, but the tests agent should not expect to write to it.

## Detailed Finding: Row 39 (WARN)

Event `create_event` model function signature omits `notes`:

```python
def create_event(db, user_id, name, event_date, event_type, venue, client_name, client_email, portal_token):
```

But the events form field list includes `notes`, and `update_event` accepts `notes`. A musician who fills in notes on the event creation form will have those notes silently discarded at INSERT time. The schema default is `''` so no error occurs. The events agent must either add `notes` to `create_event` or perform a two-step create+update.

## Summary

- **Total checks:** 40
- **PASS:** 29
- **FAIL:** 2 (rows 1 and 2 -- same underlying contradiction counted separately from each direction)
- **WARN:** 9 (rows 19, 22, 23, 24, 25, 26, 30, 39, and the `client_note` detail)
- **N/A (section absent):** 1 (seed.py mock data -- content not specified in plan)

### WARN Disposition Summary

| Row | WARN Description | Risk Level | Recommendation |
|-----|-----------------|------------|----------------|
| 19 | `client_note` column has no write path | LOW | Document as intentional or add to future scope. No agent action needed. |
| 22 | Template variable `requests` is unusual name | LOW | Cosmetic. Agents unlikely to be confused. |
| 23 | `get_song_request_count` has no declared consumer | MEDIUM | Events detail route uses `request_count` in render context but no code block shows how it is computed. Events agent must infer. |
| 24 | `get_user_by_id` has no declared consumer | LOW | Auth/dashboard agents will infer usage. |
| 25 | `dashboard/index.html` listed twice in directory tree | LOW | Cosmetic documentation error. No build impact. |
| 26 | Flash message text differs between sections for same route | LOW | Cosmetic. Portal-approve agent will pick one version. |
| 30 | `create_event` has no `notes` param (same as row 39) | MEDIUM | Silently discards notes at creation. Events agent must add `notes` to call. |
| 39 | `create_event` signature omits `notes` (detailed) | MEDIUM | Same as row 30 with full detail. |

---

STATUS: FAIL -- 1 contradiction found

**The critical contradiction is the CSV column name `key` vs the application-wide field name `musical_key`.** Every other part of the spec uses `musical_key` (schema, model functions, form fields, render context), but the CSV format header uses `key`. This will cause silent data loss on all CSV imports -- the musical key column will always be blank. The spec author must fix this before the swarm launches.
