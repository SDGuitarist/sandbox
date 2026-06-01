# Pre-Swarm Spec Completeness Check

**Plan:** 2026-06-01-feat-prompting-dashboard-engine-plan.md
**Checked:** 2026-06-01 (re-check after route path fix)

## Results

| Surface | Status | Findings |
|---------|--------|----------|
| Export Names (FC1) | PASS | 44 identifiers checked (17 model/db functions, 12 endpoints, 3 blueprint names, 1 CLI function, 10 route paths, 9 templates), 0 missing |
| Cross-Boundary Wiring (FC3) | PASS | 10 wiring rows checked, 0 missing |
| Input Validation (FC4) | PASS | 10 qualifying routes checked, 0 unvalidated |
| Registration Points (FC5) | PASS | 3 blueprints checked, 0 unregistered |
| Transaction Contracts (FC29) | PASS | 5 write functions checked, 0 unannotated |
| Authorization Mode (FC35) | N/A | 0 auth-protected routes (single-user public tool) |

## Details

### Export Names (FC1): PASS

Route paths have been added (plan lines 670-679). All 10 distinct route paths from the Route Table (lines 542-555) are now present in the Export Names Table:

| Path | Export Names Table Row |
|------|----------------------|
| `/` | line 670 |
| `/prompts/new` | line 671 |
| `/prompts/create` | line 672 |
| `/prompts/<int:prompt_id>` | line 673 |
| `/prompts/<int:prompt_id>/edit` | line 674 |
| `/prompts/<int:prompt_id>/delete` | line 675 |
| `/prompts/<int:prompt_id>/versions` | line 676 |
| `/prompts/<int:prompt_id>/diff` | line 677 |
| `/testing/<int:prompt_id>` | line 678 |
| `/testing/runs/<int:run_id>` | line 679 |

All other identifier classes also pass:

- **Model functions (17):** `create_prompt`, `get_prompt`, `get_all_prompts`, `update_prompt`, `delete_prompt`, `get_prompt_versions`, `get_prompt_version`, `extract_variables`, `substitute_variables`, `get_all_tags`, `set_prompt_tags`, `get_prompt_tags`, `create_test_run`, `get_test_run`, `get_test_runs_for_prompt`, `get_dashboard_stats`, `sanitize_fts_query` — all present.
- **DB functions (3):** `get_db`, `init_db`, `close_db` — all present.
- **Endpoint names (12):** `dashboard.index`, `prompts.create_form`, `prompts.create`, `prompts.detail`, `prompts.edit_form`, `prompts.update`, `prompts.delete`, `prompts.versions`, `prompts.diff`, `testing.test_form`, `testing.execute`, `testing.view_run` — all present.
- **Blueprint names (3):** `dashboard`, `prompts`, `testing` — all present.
- **CLI functions (1):** `register_seed_command` — present.
- **Route paths (10):** all 10 now present (fix applied).
- **Template filenames (9):** `templates/base.html`, `templates/dashboard/index.html`, `templates/prompts/create.html`, `templates/prompts/edit.html`, `templates/prompts/detail.html`, `templates/prompts/versions.html`, `templates/prompts/diff.html`, `templates/testing/run.html`, `templates/testing/result.html` — all present.

Note: `generate_diff_html` (Diff Generation section) is explicitly scoped to `prompts/routes.py` as a presentation helper internal to the `prompts_routes` agent. It is not a cross-boundary model function and is correctly absent from the Export Names Table.

### Cross-Boundary Wiring (FC3): PASS

All 10 wiring rows cover every cross-boundary import. Producer files `app/database.py`, `app/models.py`, and `app/seed.py` are each mapped to every consumer that imports from them. All cross-boundary functions identified in the Export Names Table are reachable via a wiring row. No omissions.

### Input Validation (FC4): PASS

All qualifying routes are covered:

- 4 POST routes: `/prompts/create`, `/prompts/<int:id>/edit`, `/prompts/<int:id>/delete`, `/testing/<int:prompt_id>`
- 6 GET routes with `<int:` typed URL parameters: `/prompts/<int:id>`, `/prompts/<int:id>/edit`, `/prompts/<int:id>/versions`, `/prompts/<int:id>/diff`, `/testing/<int:prompt_id>`, `/testing/runs/<int:run_id>`
- `GET /` with query parameters also covered (FTS5 sanitization, tag filtering)

Each qualifying route has prescribed input, validation method, and error response in the Input Validation Prescriptions table.

### Registration Points (FC5): PASS

All 3 blueprints (`dashboard`, `prompts`, `testing`) are:
1. Registered in the `create_app()` code block with explicit `url_prefix` values.
2. Listed in the Coordinated Behaviors table "Blueprint registration" row.
3. Navbar covers the two user-facing entry points (`/` as Dashboard, `/prompts/new` as New Prompt).

### Transaction Contracts (FC29): PASS

All 5 write functions are annotated in the Transaction Contracts table:

| Function | Annotation |
|----------|-----------|
| `create_prompt` | commits internally (BEGIN IMMEDIATE) |
| `update_prompt` | commits internally (BEGIN IMMEDIATE) |
| `delete_prompt` | commits internally |
| `set_prompt_tags` | does NOT commit (called within create/update transaction) |
| `create_test_run` | commits internally |

### Authorization Mode (FC35): N/A

No `@login_required`, `@require_role`, or `@admin_required` decorators found in any code block. The spec explicitly declares all routes public (single-user local tool). The Authorization Matrix confirms this with a single catch-all row (`ALL routes | public`).

## Summary

- **Total checks:** 6
- **PASS:** 5
- **FAIL:** 0
- **WARN:** 0
- **N/A:** 1
- **BLOCKED:** 0

STATUS: PASS
