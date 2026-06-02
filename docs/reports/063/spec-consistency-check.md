# Pre-Swarm Spec Consistency Check

**Plan:** film-production-pm-plan.md
**Checked:** 2026-06-02

---

## Results

| # | Category | Left Side | Right Side | Status | Detail |
|---|----------|-----------|------------|--------|--------|
| 1 | Export vs Wiring (callsheets consumer) | Export Names: `get_cast_for_scenes` Used By "callsheets routes" | Wiring Table: consumer is `app/models/callsheet_models.py` | FAIL | Who calls get_cast_for_scenes? Export Names says the routes file; Wiring Table says the model file. A swarm agent reading one section will contradict an agent reading the other. |
| 2 | Export vs Wiring (callsheets consumer) | Export Names: `get_scenes_by_ids` Used By "callsheets routes" | Wiring Table: consumer is `app/models/callsheet_models.py` | FAIL | Same contradiction as #1. Wiring shows the model as the importer; Export Names shows the routes file. |
| 3 | Export vs Wiring (callsheets consumer) | Export Names: `get_schedule_entries` Used By "schedule routes, callsheets routes" | Wiring Table (Call Sheet section): consumer is `app/models/callsheet_models.py` | FAIL | For the call-sheet use case, Wiring says the model imports get_schedule_entries; Export Names says callsheets routes does. Same pattern as #1-2. |
| 4 | Export vs Wiring (callsheets consumer) | Export Names: `get_location` Used By "locations routes, callsheets routes" | Wiring Table (Call Sheet section): consumer is `app/models/callsheet_models.py` | FAIL | Same contradiction: Wiring says callsheet_models.py imports get_location; Export Names says callsheets routes. |
| 5 | Schema vs Model return key | `cast_members.id` (schema PK column name) + Model Functions: `get_cast_for_scenes` returns `list[dict] with keys: id, name, character_name, cast_id_number` | Cross-Boundary Wiring Table: `get_cast_for_scenes` returns `list[dict] with cast_id, character_name, name` | FAIL | The model comment says the key is `id`; the wiring table says the key is `cast_id`. A consumer agent building against the wiring spec will reference `row['cast_id']` while the producer agent building against the model spec will set `row['id']`. Key access will fail at runtime. |
| 6 | Transaction Contract vs Model annotation | Transaction Contracts table: `create_user` | BEGIN IMMEDIATE | YES | Model Functions comment for `create_user`: `# Returns: int (user_id)` — no mention of commit or BEGIN IMMEDIATE | WARN | Every other write function in auth_models / project_models carries a `-- commits internally (BEGIN IMMEDIATE)` annotation. `create_user` is the only write function whose model comment is silent. An agent reading only the model comment will not know it must implement a transaction. Not a direct contradiction, but a high-risk omission. |
| 7 | Route Table vs Authorization Matrix | Route Table: `GET /scenes/<pid>/new` (scenes.new) — auth: login+member+producer/ad | Auth Matrix: no row for `GET /scenes/<pid>/new` | WARN | The auth intent is declared in the route table but missing from the matrix. Applies to 12 GET routes in total: GET /scenes/<pid>/new, GET /scenes/<pid>/<sid>/edit, GET /cast/<pid>/new, GET /cast/<pid>/<cid> (cast.detail), GET /crew/<pid>/new, GET /crew/<pid>/<cid> (crew.detail), GET /locations/<pid>/new, GET /locations/<pid>/<lid> (locations.detail), GET /schedule/<pid>/day/<date>, GET /schedule/<pid>/new, GET /budget/<pid>/line-items/new, GET /expenses/<pid>/new. These are all form-display and detail-view GET routes. The route table declares auth for each; the matrix omits them. No direct contradiction (the route table is the source of truth for these), but the matrix is incomplete. |
| 8 | Export Names vs Wiring (schedule routes consumer) | Export Names: `get_shoot_dates` Used By "schedule routes, callsheets routes, reports routes" | Cross-Boundary Wiring Table: only shows callsheets routes and reports routes as consumers; no wiring entry for schedule routes | WARN | Schedule routes is listed as a consumer in the Export Names Table but has no corresponding row in any Wiring Table subsection. Minor omission — the schedule blueprint is the owner of schedule_models so intra-blueprint use is expected to be unlisted — but the explicit "Used By" claim in Export Names creates an expectation that should be traceable. |
| 9 | Schema vs Route Table (no contradiction found) | Schema column names vs model return keys | All other model return key sets checked | PASS | get_scenes (location_name join OK), get_cast_members, get_crew_members, get_locations, get_location (name/address/nearest_hospital all match schema), get_project_stats fields are computed aggregates. No schema-vs-key mismatches beyond #5. |
| 10 | Route Table vs Route Table (all handlers present) | Route Table lists 55 routes across 13 blueprints | Every route in the table has a named handler (e.g., scenes.list, schedule.reorder) | PASS | No route listed in table without a handler name. No handler defined in a section but absent from the table (the plan prescribes handlers via the route table only, not a separate handler section). |
| 11 | File Assignment vs Swarm Agent Assignment | File Assignment Boundaries (Agents 1-16) | Swarm Agent Assignment table (rows 1-16) | PASS | Spot-checked all 16 agents. File lists match exactly for scaffold, auth, projects, scenes, cast, crew, departments, locations, schedule, callsheets, budget, expenses, reports, search, database, and tests. |
| 12 | Coordinated Behaviors vs CSRF prescription | Coordinated Behaviors: `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">` | CSRF in Templates section: same syntax; Negative Constraints #10: confirms `{{ csrf_token() }}` (with parens) | PASS | All three sections agree on CSRF token syntax. |
| 13 | Coordinated Behaviors vs session keys | Coordinated Behaviors: `session['user_id']` (int) | login_required decorator code: `session.get('user_id')`, Template Contracts: `session['user_id']`, Negative Constraints #15: "use session['user_id'] not session['logged_in']" | PASS | All references to session keys are consistent. |
| 14 | Transaction Contracts vs Model Functions (all other functions) | Transaction Contracts table entries for all write functions | Model Functions section annotations | PASS | All other annotated write functions agree: create_project, transition_project_phase, create_scene, transition_scene_status, create_cast_member, add_cast_to_scene (NO commit), remove_cast_from_scene (NO commit), update_scene (NO commit), create_crew_member, assign_department_head, create_location, create_schedule_entry, reorder_schedule, delete_schedule_entry (NO commit), generate_call_sheet, publish_call_sheet, allocate_budget, create_line_item, update_line_item, create_expense, delete_expense, approve_expense, index_entity (NO commit), remove_entity (NO commit). |
| 15 | Mock/Fixture data vs Schema fields | seed_data() in database.py inserts into users, projects, project_members, departments, budget_categories | Schema column definitions | PASS | users INSERT uses username, password_hash, display_name (all required NOT NULL columns). projects INSERT uses id, title, phase, total_budget_cents, created_by (all match schema). project_members INSERT uses project_id, user_id, role (matches schema). departments INSERT uses project_id, name. budget_categories INSERT uses project_id, account_number, name, parent_group. All required columns present; no extra columns; types match. |
| 16 | ON DELETE behaviors vs delete function docstrings | FK constraints across all tables | Model functions: delete_schedule_entry, delete_expense | PASS | delete_schedule_entry: schedule_entries has no child tables referencing it — no FK cascade risk. delete_expense: expenses has no child tables referencing it — no FK cascade risk. No delete functions for users, projects, departments, scenes, locations, cast_members, crew_members, or call_sheets exist in the spec, so ON DELETE behavior for those parents is N/A (no docstring to contradict). |
| 17 | Cross-Boundary Wiring completeness | Export Names Table "Used By" column | Wiring Table entries | PASS (with exceptions noted in #1-4 and #8) | Beyond the 5 items flagged above, all other Export Names "Used By" claims are represented in the wiring table or are intra-blueprint (expected to be omitted). |
| 18 | Blueprint url_prefix vs route table paths | `app/__init__.py`: `app.register_blueprint(callsheets_bp, url_prefix='/call-sheets')` | Route Table: all callsheet paths are relative (e.g., `/<pid>`, `/<pid>/generate`) | PASS | url_prefix values in __init__.py match exactly the Route Table section headers for all 13 blueprints. |
| 19 | SortableJS contract internal consistency | SortableJS Class-Name Contract table | schedule.js/schedule routes/schedule templates are all Agent 9 | PASS | Container ID, item class, drag handle, data-id, JSON body keys (order, shoot_date), CSRF header name all specified once and consistently within the contract table. No cross-agent naming drift visible in the spec. |
| 20 | DOOD algorithm return keys vs report_models docstring | DOOD algorithm: returns dicts with keys `cast_member_id, name, character_name, cast_id_number, days` | report_models.py docstring: `Each dict: {cast_member_id, name, character_name, cast_id_number, days: {date: status}}` | PASS | Keys match exactly. DOOD status values ('W','SW','WF','SWF','H','') consistent with call_sheet_cast allowed statuses plus empty string for non-working days (empty string is only in the DOOD display, not stored in call_sheet_cast, so no contradiction). |

---

## Detailed Notes on FAILs

### FAILs #1-4: callsheet_models.py vs callsheets routes as consumers

The Cross-Boundary Wiring Table (Call Sheet Wiring subsection) consistently shows `app/models/callsheet_models.py` as the consumer of four cross-boundary functions:

```
app/models/schedule_models.py  ->  app/models/callsheet_models.py  (get_schedule_entries)
app/models/cast_models.py      ->  app/models/callsheet_models.py  (get_cast_for_scenes)
app/models/location_models.py  ->  app/models/callsheet_models.py  (get_location)
app/models/scene_models.py     ->  app/models/callsheet_models.py  (get_scenes_by_ids)
```

The Export Names Table says all four are "Used By: callsheets routes" (not callsheet_models).

This is architecturally significant. `generate_call_sheet(conn, project_id, shoot_date)` commits a BEGIN IMMEDIATE multi-table transaction. If the model does the data aggregation (wiring table version), the model calls the other models internally. If the routes file does the aggregation (export names version), the route assembles data before/after calling the model.

The spec cannot be both. The wiring table and export names table must agree on which file imports which.

**Root cause:** The spec author likely intended the `callsheet_models.py` to import from other models (which is why the wiring table shows model-to-model imports), but then wrote the Export Names "Used By" column thinking of the feature owner (callsheets feature) rather than the exact file.

### FAIL #5: `get_cast_for_scenes` return key `id` vs `cast_id`

Model Functions section:
```python
# Returns: list[dict] with keys: id, name, character_name, cast_id_number
def get_cast_for_scenes(conn, scene_ids) -> list: ...
```

Cross-Boundary Wiring Table:
```
list[dict] with cast_id, character_name, name
```

The key `id` (model) vs `cast_id` (wiring) will cause a KeyError at runtime. The wiring table also drops `cast_id_number` from the listed keys. The producing agent will build with `row['id']`; the consuming agent will build with `row['cast_id']`.

---

## Summary

- **Total checks:** 20
- **PASS:** 13
- **FAIL:** 5
- **WARN:** 2
- **N/A (section absent):** 0

STATUS: FAIL -- 5 contradictions found
