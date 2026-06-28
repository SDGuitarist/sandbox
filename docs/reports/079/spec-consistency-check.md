STATUS: PASS

# Pre-Swarm Spec Consistency Check

**Plan:** docs/plans/2026-06-26-g1-g3-live-validation-run-brief.md
**Checked:** 2026-06-28 (re-run after fix)

## Results

| # | Category | Left Side | Right Side | Status | Detail |
|---|----------|-----------|------------|--------|--------|
| 1 | Schema vs Route Param | Auth Matrix §6: `<int:snippet_id>` | Input Validation §3: `<int:snippet_id>`; Coordinated Behaviors §4: `<int:snippet_id>`; EARS §5: `<int:snippet_id>` | PASS | Prior FAIL resolved. All four sections (§3, §4, §6, §5) and all model function signatures now uniformly use `<int:snippet_id>`. The former `<id>` (untyped, wrong name) has been replaced everywhere. |
| 2 | Export Names vs Import Reference | Wiring Table "Producer file": `app/db.py` | Wiring Table "Import path": `from app.db import get_db` | PASS | Prior FAIL resolved. The producer file cell now reads `app/db.py`, which is exactly the module named in `from app.db import get_db`. Both cells in the wiring row are internally consistent. Also consistent with Agent 1 (scaffold) owning `validation-notes/app/db.py`. |
| 3 | SQL Types vs App-Layer Types | `id` INTEGER PRIMARY KEY | `create_snippet() -> int`; `<int:snippet_id>` in routes and model params | PASS | All uses of the primary key consistently treat it as an integer. No type mismatch. |
| 4 | SQL Types vs App-Layer Types | `title` TEXT NOT NULL; `body` TEXT NOT NULL DEFAULT '' | `create_snippet(conn, title, body)`, `update_snippet(conn, snippet_id, title, body)` | PASS | String parameters for both fields; schema default `''` for body consistent with Input Validation treating body as optional (max length only, not required). |
| 5 | Route Methods vs Route Table | Auth Matrix §6 POST routes: `POST /new`, `POST /<int:snippet_id>/edit`, `POST /<int:snippet_id>/delete` | Input Validation §3: same three POST routes | PASS | All three POST routes appear in both sections using the same `<int:snippet_id>` notation. GET routes correctly absent from Validation table. No route in one section but missing from the other. |
| 6 | Export Names vs Import References | Export Names Table: all CRUD fns Defined By models (2), Used By routes (3) | Wiring Table CRUD row: `from app.models import list_snippets, get_snippet, create_snippet, update_snippet, delete_snippet` | PASS | All five CRUD function names match exactly across both sections. Directions (producer = models, consumer = routes) match. |
| 7 | Export Names vs Import References | Export Names Table: `init_db` Defined By models (2), Used By scaffold (1) | Wiring Table: `from app.models import init_db` consumed by `app/__init__.py` | PASS | Names and direction match. `app/__init__.py` belongs to Agent 1 (scaffold). Consistent. |
| 8 | Export Names vs Import References | Export Names Table: `snippets_bp` Defined By routes (3), Used By scaffold (1) | Wiring Table: `from app.snippets.routes import snippets_bp` consumed by `app/__init__.py` | PASS | Names and direction match. |
| 9 | Cross-Boundary Wiring Completeness | Export Names Table: `create_app` Used By run.py | Cross-Boundary Wiring Table | WARN | `create_app` is documented in the Export Names Table with consumer `run.py` but is absent from the Wiring Table. Both files (run.py and app/__init__.py) belong to Agent 1 (scaffold) so no cross-agent coordination is broken; however, the Wiring Table states "every cross-module function call" and this call is omitted. Low impact — no inter-agent confusion possible. |
| 10 | Cross-Boundary Wiring Completeness | Wiring Table: `app/models.py` listed as consumer of `get_db` | Model signatures: all take `conn` as first parameter (caller passes connection) | WARN | Every model function accepts `conn` as a parameter, meaning the caller (routes) calls `get_db()` and passes the connection object. Models themselves do not need to import or call `get_db`. Listing `app/models.py` as a consumer of `get_db` in both Export Names Table and Wiring Table is misleading — only `app/snippets/routes.py` is the actual runtime consumer. Effect is limited (at worst an unused import in models.py), but the wiring documentation overstates the dependency. No inter-agent confusion since the CRUD import row covers the real models→routes boundary. |
| 11 | Schema vs Route Param (new check) | Schema column: `id` INTEGER PRIMARY KEY | Model function params: `snippet_id`; Route: `<int:snippet_id>` | PASS | The schema column is named `id`; model functions use `snippet_id` as the parameter name for the PK value. This is a standard Python/Flask convention — SQL queries inside model functions will use `WHERE id = ?` with the value passed as `snippet_id`. No structural contradiction; the naming discrepancy is expected and deliberate. |
| 12 | Mock/Fixture Data vs Schema Fields | N/A — no mock data, test fixtures, or seed data in the spec | | N/A | Section not present. |
| 13 | ON DELETE Behavior vs Docstrings | N/A — schema has a single table (`snippets`) with no FK constraints | | N/A | No REFERENCES clauses; no ON DELETE behavior to verify. |
| 14 | Transaction Contracts vs Schema | Transaction Contracts §5: write fns commit internally; read fns no commit | Schema: single-table, no cascades | PASS | `create_snippet`, `update_snippet`, `delete_snippet` each perform one statement + `conn.commit()`. `init_db` commits internally (DDL). `list_snippets`, `get_snippet` are read-only. All consistent with single-table schema. |
| 15 | Authorization Matrix completeness | Auth Matrix §6: 6 routes listed | Templates + blueprint: list.html, new.html, edit.html + delete handler | PASS | Auth Matrix covers all six routes implied by the three templates and blueprint (`GET /`, `GET /new`, `POST /new`, `GET /<int:snippet_id>/edit`, `POST /<int:snippet_id>/edit`, `POST /<int:snippet_id>/delete`). No route implied but absent; no matrix entry without a handler. |
| 16 | EARS vs Input Validation | EARS §5: "re-render `new.html` with `'Title is required.'`" | Input Validation §3: `flash('Title is required.', 'error')`, HTTP 200 (re-render `new.html`) | PASS | The flash message text and template name match exactly. EARS and Validation Prescriptions describe the same behavior. |
| 17 | Blueprint url_prefix vs Route Table | Export Names Table: `url_prefix='/'` | Auth Matrix routes: `/`, `/new`, `/<int:snippet_id>/edit`, `/<int:snippet_id>/delete` | PASS | With `url_prefix='/'`, handlers registered as `/`, `/new`, etc. map directly to the Auth Matrix paths. No mismatch. |

## Summary

- **Total checks:** 17
- **PASS:** 13
- **FAIL:** 0
- **WARN:** 2
- **N/A (section absent):** 2

## Prior FAILs — Confirmation of Resolution

### FAIL 1 (Check 1) — URL parameter name and type — RESOLVED

The prior report found `<id>` (string, wrong name) in Auth Matrix §6 and Input Validation §3, conflicting with `<int:snippet_id>` in Coordinated Behaviors §4.

Current spec: all four sections (§3, §4, §5, §6) and all three model function signatures that accept a snippet PK parameter use the identical pattern `<int:snippet_id>` / `snippet_id`. No section uses `<id>`. **Fix confirmed correct; no residual.**

### FAIL 2 (Check 2) — `get_db` producer file — RESOLVED

The prior report found the Wiring Table row for `get_db` had a contradiction between its "Producer file" cell (`app/__init__.py`) and its "Import path" cell (`from app.db import get_db`).

Current spec: "Producer file" cell reads `app/db.py`. This matches the import path (`from app.db import get_db`) and the Agent Assignment (`app/db.py (connection helper)` under Agent 1). The wiring row is internally consistent. **Fix confirmed correct; no residual.**

## Fix-Introduced Contradiction Check

The two fixes affected:
1. URL parameter notation in §3 and §6 — no other section was touched. All occurrences now agree. No new contradiction.
2. Producer file for `get_db` in Wiring Table — the Export Names Table "Defined By scaffold (1)" and the Agent Assignment both independently confirm `app/db.py` as the correct file. The "Used By" column (models (2), routes (3)) now matches the Wiring Table consumer cell (`app/models.py, app/snippets/routes.py`). No new contradiction; the pre-existing WARN about `app/models.py` not being a runtime caller of `get_db` (WARN #10 / Check 10 above) is unchanged from the prior report.

## WARN Disposition Guidance

Both WARNs are documentation accuracy issues that do not cross agent-ownership boundaries:

- **WARN 9** (`create_app` absent from Wiring Table): both files belong to Agent 1 (scaffold). No cross-agent wiring risk. Acceptable to leave for a throwaway validation build.
- **WARN 10** (`app/models.py` listed as `get_db` consumer): only affects imports in models.py. The CRUD wiring row separately documents the real models→routes dependency. Acceptable to leave; the worst outcome is an unused import in models.py.

Neither WARN blocks swarm launch.
