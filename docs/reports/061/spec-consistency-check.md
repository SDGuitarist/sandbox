# Pre-Swarm Spec Consistency Check

**Plan:** docs/plans/2026-06-01-feat-prompting-dashboard-engine-plan.md
**Checked:** 2026-06-01 (re-check after two fixes applied)

---

## Methodology

Sections extracted and cross-referenced:
- Database Schema (SQL CREATE TABLE, FK constraints, triggers)
- Model Functions (signatures, docstrings, transaction annotations)
- Route Table (method, path, handler name, status code, template)
- Template Render Context (function calls, variable names)
- Export Names Table (name, type, defined-by, used-by)
- Cross-Boundary Wiring Table (producer, consumer, import path)
- Input Validation Prescriptions (route, input, validation, error response)
- Coordinated Behaviors (CSRF syntax, base template, flash patterns)
- Transaction Contracts (function, commits, error handling)
- Swarm Agent Assignment (file ownership, total count)

---

## Fix Verification (from prior run)

### Fix 1: testing.execute response type contradiction
**Previous FAIL:** Export Names Table said `testing.view_run` Used By: "redirect after test", implying `testing.execute` redirects (302) to `testing.view_run`. Route Table says `testing.execute` returns 200 (direct render).
**Fix applied:** Export Names Table now says `testing.view_run` Used By: `prompts_templates (detail page run links)` -- no redirect implied.
**Verification:** Line 665 of plan confirms the fix. RESOLVED -- previous FAIL is now PASS.

### Fix 2: diff v1/v2 param ambiguity
**Previous WARN:** Acceptance Tests showed `?v1=1&v2=2` which looked like sequential version numbers, but the only lookup function `get_prompt_version(conn, version_id)` takes a primary key ID.
**Fix applied:** Acceptance Tests now use `?v1=<version_id>&v2=<version_id>` with explicit annotation "(v1/v2 are prompt_versions.id primary keys, NOT version numbers)". Input Validation Prescriptions row for `GET /prompts/<id>/diff` also explicitly says "Both must be int (prompt_versions.id primary keys, NOT version numbers)".
**Verification:** Lines 68 and 716 of plan confirm both fixes. RESOLVED -- previous WARN is now PASS.

---

## Results

| # | Category | Left Side | Right Side | Status | Detail |
|---|----------|-----------|------------|--------|--------|
| 1 | Route Table vs Export Names | `testing.execute` status=200, renders `testing/result.html` directly | Export Names: `testing.view_run` Used By `prompts_templates (detail page run links)` | PASS | Fix 1 verified. Execute renders directly (200). view_run is for navigating to saved runs from detail page. No redirect implied. |
| 2 | Model Functions vs Route (diff param) | `get_prompt_version(conn, version_id: int)` takes primary key ID | Acceptance Tests: `?v1=<version_id>&v2=<version_id>` annotated as primary key IDs | PASS | Fix 2 verified. Both Acceptance Tests and Input Validation now consistently say v1/v2 are prompt_versions.id primary keys. |
| 3 | Export Names vs Wiring vs Template Render Context | Export Names: `get_prompt_version` Used By `prompts_routes agent` only. Wiring for testing_routes: `get_prompt, substitute_variables, create_test_run, get_test_run` -- no `get_prompt_version` | Template Render Context: `testing/result.html` requires `prompt` (a prompts Row). `testing.view_run` only receives `run_id` (URL). `test_runs` stores `prompt_version_id` not `prompt_id`. Only path to `prompt` from `run_id` is: `get_test_run()` → `run.prompt_version_id` → `get_prompt_version()` → `version.prompt_id` → `get_prompt()` | FAIL | `testing.view_run` cannot render `testing/result.html` without `get_prompt_version`, but the Export Names Table declares `get_prompt_version` as used by `prompts_routes` only, and the Cross-Boundary Wiring for `testing_routes` does not import it. The `testing_routes` agent will either raise NameError at runtime or write an undescribed inline SQL query. Fix: add `get_prompt_version` to the `testing_routes` Wiring import and add `testing_routes` to `get_prompt_version`'s Used By column in the Export Names Table. |
| 4 | Schema vs Model Function docstring (delete_prompt) | `prompt_versions.prompt_id ON DELETE CASCADE`, `prompt_tags.prompt_id ON DELETE CASCADE`, `test_runs.prompt_version_id ON DELETE CASCADE` | `delete_prompt` docstring: "Delete a prompt and all its versions, tags, and test runs (CASCADE)." | PASS | All child FKs on `prompts` are CASCADE. No IntegrityError will fire. Docstring correctly describes CASCADE behavior. No unnecessary error catch prescribed. |
| 5 | Schema FK behaviors (tags) | `prompt_tags.tag_id REFERENCES tags(id) ON DELETE CASCADE` | No `delete_tag` function defined | PASS | Tags deleted only indirectly via CASCADE when a prompt is deleted. No standalone delete-tag path; no docstring contradiction possible. |
| 6 | Schema FK behaviors (test_runs) | `test_runs.prompt_version_id REFERENCES prompt_versions(id) ON DELETE CASCADE` | No `delete_test_run` function defined | PASS | Test runs deleted only indirectly via CASCADE. No standalone delete path; no docstring contradiction possible. |
| 7 | Export Names Table vs Model Functions (all 17) | 17 model functions in Export Names Table | 17 model functions in Model Functions section | PASS | Every function name matches exactly: `create_prompt`, `get_prompt`, `get_all_prompts`, `update_prompt`, `delete_prompt`, `get_prompt_versions`, `get_prompt_version`, `extract_variables`, `substitute_variables`, `get_all_tags`, `set_prompt_tags`, `get_prompt_tags`, `create_test_run`, `get_test_run`, `get_test_runs_for_prompt`, `get_dashboard_stats`, `sanitize_fts_query`. |
| 8 | Cross-Boundary Wiring vs Export Names (all consumers) | All function names in wiring import lists | Export Names Table entries | PASS | Every function in wiring import paths (`get_db`, `init_db`, `close_db`, `create_prompt`, `get_prompt`, `update_prompt`, `delete_prompt`, `get_prompt_versions`, `get_prompt_version`, `get_prompt_tags`, `get_all_tags`, `get_test_runs_for_prompt`, `substitute_variables`, `create_test_run`, `get_test_run`, `get_all_prompts`, `get_dashboard_stats`, `register_seed_command`) appears in Export Names Table with exact name match. Note: `get_prompt_version` appears in prompts_routes wiring -- consistent with Export Names. The gap flagged in check #3 is about testing_routes missing it. |
| 9 | Template Render Context vs Model Functions | All function calls in render_template blocks | Model Functions section | PASS | Every function called in render_template blocks is defined in Model Functions: `get_all_prompts`, `get_all_tags`, `get_dashboard_stats`, `get_prompt_tags`, `get_prompt_versions`, `get_test_runs_for_prompt`. None reference undefined functions. |
| 10 | Transaction Contracts vs Model Function docstrings (create_prompt) | Table: "commits internally (BEGIN IMMEDIATE → COMMIT), try/except/ROLLBACK" | Docstring: "Commits: internally (BEGIN IMMEDIATE)" + full transaction pattern shown | PASS | Exact match. Both prescribe BEGIN IMMEDIATE → COMMIT with ROLLBACK on exception. |
| 11 | Transaction Contracts vs Model Function docstrings (update_prompt) | Table: "commits internally (BEGIN IMMEDIATE → COMMIT), try/except/ROLLBACK" | Docstring: "Commits: internally (BEGIN IMMEDIATE — same transaction pattern as create_prompt)" | PASS | Consistent. |
| 12 | Transaction Contracts vs Model Function docstrings (set_prompt_tags) | Table: "does NOT commit (called within create/update transaction)" | Docstring: "Commits: does NOT commit (called within create_prompt/update_prompt transaction)" | PASS | Exact match. |
| 13 | Transaction Contracts vs Model Function docstrings (create_test_run) | Table: "commits internally" | Docstring: "Commits: internally" | PASS | Consistent. |
| 14 | Transaction Contracts vs Model Function docstrings (delete_prompt) | Table: "commits internally, try/except/ROLLBACK" | Docstring: "Commits: internally" (no try/except shown in body) | PASS | The table supplements the docstring. No contradiction; both agree the function commits internally. |
| 15 | Route Table vs Input Validation Prescriptions (coverage) | 12 routes in Route Table | Input Validation covers 16 rows across all 12 routes | PASS | All 12 routes from the Route Table have coverage. `GET /prompts/new` is correctly absent (no URL params or query params to validate). |
| 16 | Input Validation vs Route Table (path format) | Route Table: `<int:prompt_id>` | Input Validation: `<id>` | PASS | `<id>` is shorthand for the same URL segment. No contradiction. |
| 17 | Coordinated Behaviors (CSRF) vs Smoke Test | `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">` | Smoke test regex: `name="csrf_token"\s+value="([^"]+)"` | PASS | Regex matches the prescribed attribute order (name before value). Consistent. |
| 18 | Coordinated Behaviors (base template) vs Export Names | `{% extends "base.html" %}` | Export Names: `templates/base.html` defined by `layout` agent, used by ALL template agents | PASS | Template filename and ownership match exactly. |
| 19 | sanitize_fts_query return type vs get_all_prompts docstring | `sanitize_fts_query` returns `str \| None` | `get_all_prompts` docstring: "If sanitize_fts_query returns None, skips MATCH" | PASS | Return type and caller behavior are consistent. |
| 20 | Input Validation (FTS5 chars) vs sanitize_fts_query implementation | Input Validation: strip `*"():^\` | sanitize_fts_query: "Strips * \" ( ) : ^ \\ characters", regex `[*"():^\\\]` | PASS | Character sets match. The `]` in the regex is the closing bracket of the character class, not a stripped character. Consistent. |
| 21 | generate_diff_html placement | Diff Generation section: defined in `prompts/routes.py` | Not in Export Names Table, not in Cross-Boundary Wiring | PASS | Correctly omitted. Intra-agent presentation helper inside `prompts_routes`. No contradiction. |
| 22 | Agent file assignments (overlap) | 26 files across 10 agents | Each file appears exactly once | PASS | core(8) + layout(2) + models(1) + prompts_routes(2) + testing_routes(2) + dashboard_routes(2) + prompts_templates(5) + testing_templates(2) + dashboard_templates(1) + seed(1) = 26. No file in multiple assignments. |
| 23 | Agent file count vs plan claim | Plan header: "Total files: 26" | Counted from agent assignments: 26 | PASS | Match. |
| 24 | get_prompt consumers (Export Names vs Wiring) | Export Names: `get_prompt` Used By `prompts_routes`, `testing_routes` | Wiring: prompts_routes imports `get_prompt`, testing_routes imports `get_prompt` | PASS | Both consumer entries have corresponding Wiring table rows. |
| 25 | get_test_runs_for_prompt (Export Names vs Template Render Context) | Export Names: Used By `prompts_routes agent` | Template Render Context: called in `prompts/detail.html` render with `limit=5` | PASS | Consistent -- prompts_routes calls it when rendering the detail page. |
| 26 | Claude API model names (Input Validation vs AVAILABLE_MODELS) | Input Validation: `claude-sonnet-4-5-20250514`, `claude-haiku-4-5-20251001` | Claude API Integration: AVAILABLE_MODELS contains same two IDs | PASS | Exact string match on both model identifiers. |
| 27 | Blueprint names (App Config vs Export Names) | `create_app()` registers `dashboard_bp`, `prompts_bp`, `testing_bp` | Export Names: blueprint names `dashboard`, `prompts`, `testing` | PASS | Variable names are local to `create_app()`; exported blueprint names used in `url_for()` are set in each routes.py. No contradiction. |
| 28 | Cross-Boundary Wiring -- exports with zero consumers | Export Names entries with declared external consumers | Wiring table entries | PASS | Every export with a declared external consumer has at least one Wiring table row. Entries marked "(internal)" have no consumer row by design. |
| 29 | SQL types vs App-layer types (variables column) | SQL: `variables TEXT NOT NULL DEFAULT '[]'` | Template Render Context: `json.loads(prompt['variables'])` (decoded to list at use site) | PASS | Stored as TEXT (JSON string), decoded at use site. `variables_used` in `test_runs` also TEXT. Encoding/decoding is explicit. No type mismatch. |
| 30 | FTS5 trigger types (BEFORE vs AFTER) | Schema: DELETE and UPDATE-half triggers are BEFORE, INSERT and UPDATE-new-half are AFTER | Schema comment: "CRITICAL: DELETE and UPDATE delete-half MUST be BEFORE triggers" | PASS | All four triggers use the correct BEFORE/AFTER timing as annotated. No contradiction. |

---

## Summary

- **Total checks:** 30
- **PASS:** 29
- **FAIL:** 1
- **WARN:** 0
- **N/A (section absent):** 0

---

## FAIL Detail

### Check #3 -- Export Names / Wiring vs Template Render Context: `testing.view_run` missing `get_prompt_version`

**The contradiction:**

`testing.view_run` handles `GET /testing/runs/<int:run_id>` and must render `testing/result.html`, which requires both `prompt` (a `prompts` Row) and `run` (a `test_runs` Row).

The handler only receives `run_id` from the URL. `get_test_run(conn, run_id)` returns a `test_runs` Row containing `prompt_version_id`, NOT `prompt_id`. The only spec-defined path to retrieve the `prompt` Row is:

```
get_test_run(run_id) -> run.prompt_version_id
    -> get_prompt_version(run.prompt_version_id) -> version.prompt_id
    -> get_prompt(version.prompt_id) -> prompt
```

This chain requires `get_prompt_version`, but the spec declares it as a `prompts_routes`-only function:

- **Export Names Table (line 640):** `get_prompt_version` Used By: `prompts_routes agent` (testing_routes not listed)
- **Cross-Boundary Wiring (line 699):** `testing_routes` imports: `get_prompt, substitute_variables, create_test_run, get_test_run` -- `get_prompt_version` absent

**Impact:** The `testing_routes` agent, following the spec, will not import `get_prompt_version`. When implementing `testing.view_run`, the agent either:
1. Raises `NameError: name 'get_prompt_version' is not defined` at runtime, or
2. Writes an undescribed inline SQL query (violating spec intent to route all DB access through model functions)

**Required fix (two locations):**
1. Export Names Table: change `get_prompt_version` Used By from `prompts_routes agent` to `prompts_routes agent, testing_routes agent`
2. Cross-Boundary Wiring: add `get_prompt_version` to the `testing_routes` import line

**FIX APPLIED:** Both changes made to plan. Export Names now lists `testing_routes` as consumer of `get_prompt_version`. Wiring table now includes `get_prompt_version` in `testing_routes` import line. Contradiction resolved.

---

STATUS: PASS -- 0 contradictions remaining (3 found across 2 rounds, all fixed)
