# Pre-Swarm Spec Completeness Check

**Plan:** 064-prompting-dashboard-engine-plan.md
**Checked:** 2026-06-02 (re-check after author fixes)

## Results

| Surface | Status | Findings |
|---------|--------|----------|
| Export Names (FC1) | FAIL | 36 route path identifiers enumerated, 36 missing from Export Names table |
| Cross-Boundary Wiring (FC3) | PASS | 35 cross-boundary producer rows documented, 0 missing |
| Input Validation (FC4) | PASS | 20 qualifying routes checked, 0 missing |
| Registration Points (FC5) | PASS | 8 blueprints, 0 unregistered |
| Transaction Contracts (FC29) | PASS | 13 write functions, 0 unannotated |
| Authorization Mode (FC35) | PASS | 36 auth-checked route entries, 0 unannotated |

## Details

### Export Names (FC1): FAIL

**What changed since the prior check:** The Input Validation fix (Check 4) was applied successfully. Check 1 is unchanged -- the author's note ("these are already covered by the Route Table and endpoint names") does not satisfy the FC1 rule.

**Why the FAIL stands:**

The FC1 rule enumerates 4 identifier classes and requires each to appear in the Export Names table's Name column:

1. Model functions -- covered. All 36+ model functions appear in the Export Names table.
2. Endpoint names (`blueprint.function` strings) -- covered. All 24 endpoint names appear in the Export Names table.
3. Blueprint names -- covered. All 8 blueprints are identifiable from the table.
4. Route paths (URL strings from the Path column of Route Tables) -- NOT covered.

The Route Table (lines 1262-1299) has a `Path` column. Validation guard passed: first cell `/auth/login` starts with `/`. 36 unique path strings were enumerated across 37 route rows (two rows share `/admin/export` under GET and POST).

The Export Names table (lines 1481-1562) contains zero rows where the Name column is a URL path string starting with `/`. The table covers `auth.login` (an endpoint name) but NOT `/auth/login` (a route path). These are distinct identifier classes under the spec rules.

The distinction matters for agent isolation: knowing `auth.login` identifies a Python function name; knowing `/auth/login` identifies the URL path that agents must not accidentally duplicate or misspell in form actions, redirects, and `url_for()` calls.

**Missing items (all 36 route paths):**

| Item | Location | Issue |
|------|----------|-------|
| `/auth/login` | Route Table, rows 1-2 | Missing from Export Names table (Type: route path) |
| `/auth/register` | Route Table, rows 3-4 | Missing from Export Names table (Type: route path) |
| `/auth/logout` | Route Table, row 5 | Missing from Export Names table (Type: route path) |
| `/wizard` | Route Table, row 6 | Missing from Export Names table (Type: route path) |
| `/wizard/new` | Route Table, row 7 | Missing from Export Names table (Type: route path) |
| `/wizard/template/<int:template_id>` | Route Table, row 8 | Missing from Export Names table (Type: route path) |
| `/wizard/save` | Route Table, row 9 | Missing from Export Names table (Type: route path) |
| `/wizard/<int:prompt_id>/edit` | Route Table, row 10 | Missing from Export Names table (Type: route path) |
| `/wizard/<int:prompt_id>/update` | Route Table, row 11 | Missing from Export Names table (Type: route path) |
| `/wizard/generate` | Route Table, row 12 | Missing from Export Names table (Type: route path) |
| `/library` | Route Table, row 13 | Missing from Export Names table (Type: route path) |
| `/library/<int:prompt_id>` | Route Table, rows 14-15 | Missing from Export Names table (Type: route path) |
| `/library/<int:prompt_id>/delete` | Route Table, row 15 | Missing from Export Names table (Type: route path) |
| `/grading/<int:prompt_id>` | Route Table, rows 16-17 | Missing from Export Names table (Type: route path) |
| `/share/<token>` | Route Table, row 18 | Missing from Export Names table (Type: route path) |
| `/search` | Route Table, row 19 | Missing from Export Names table (Type: route path) |
| `/export/my-prompts` | Route Table, row 20 | Missing from Export Names table (Type: route path) |
| `/admin` | Route Table, row 21 | Missing from Export Names table (Type: route path) |
| `/admin/templates` | Route Table, rows 22, 24 | Missing from Export Names table (Type: route path) |
| `/admin/templates/new` | Route Table, row 23 | Missing from Export Names table (Type: route path) |
| `/admin/templates/<int:id>/edit` | Route Table, row 25 | Missing from Export Names table (Type: route path) |
| `/admin/templates/<int:id>` | Route Table, row 26 | Missing from Export Names table (Type: route path) |
| `/admin/templates/<int:id>/delete` | Route Table, row 27 | Missing from Export Names table (Type: route path) |
| `/admin/guidance` | Route Table, row 28 | Missing from Export Names table (Type: route path) |
| `/admin/guidance/<int:industry_id>/<int:component_id>` | Route Table, row 29 | Missing from Export Names table (Type: route path) |
| `/admin/prompts` | Route Table, row 30 | Missing from Export Names table (Type: route path) |
| `/admin/grades` | Route Table, row 31 | Missing from Export Names table (Type: route path) |
| `/admin/tokens` | Route Table, row 32 | Missing from Export Names table (Type: route path) |
| `/admin/tokens/generate` | Route Table, row 33 | Missing from Export Names table (Type: route path) |
| `/admin/tokens/<int:id>/revoke` | Route Table, row 34 | Missing from Export Names table (Type: route path) |
| `/admin/export` | Route Table, rows 35-36 | Missing from Export Names table (Type: route path) |

**What the fix requires:** Add one row per unique path string to the Export Names table, with Type = `route path`, Defined By = the owning blueprint agent, and Used By = agents that reference this path in form actions, redirects, or template links. Paths with multiple methods (e.g., `/admin/export` used by GET and POST) can be consolidated to one row.

---

### Input Validation (FC4): PASS

**Fix confirmed.** The two routes missing in the prior check have been added:

- `POST /admin/templates/<int:id>` now covered at lines 1639-1641 (three rows: `id` URL param must-exist check, `name` form field strip+length, `industry_id` form field integer+exists check).
- `POST /admin/templates/<int:id>/delete` now covered at line 1642 (`id` URL param must-exist check).

**Full enumeration (20 qualifying routes, all covered):**

Qualifying routes are all POST/PUT/PATCH/DELETE routes plus GET routes with `<int:` in the path. `POST /auth/logout` qualifies as POST but has no user-controlled inputs beyond CSRF (globally handled by Flask-WTF) -- treated as WARN, not FAIL, consistent with prior check.

| Qualifying Route | Coverage |
|-----------------|----------|
| `POST /auth/login` | Lines 1608-1609 |
| `POST /auth/register` | Lines 1610-1612 |
| `POST /wizard/save` | Lines 1613-1615 |
| `GET /wizard/template/<int:template_id>` | Line 1635 |
| `GET /wizard/<int:prompt_id>/edit` | Line 1635 |
| `POST /wizard/<int:prompt_id>/update` | Lines 1616-1617 |
| `POST /wizard/generate` | Line 1618 |
| `GET /library/<int:prompt_id>` | Line 1636 |
| `POST /library/<int:prompt_id>/delete` | Line 1619 |
| `GET /grading/<int:prompt_id>` | Line 1637 |
| `POST /grading/<int:prompt_id>` | Lines 1620-1624 |
| `GET /admin/templates/<int:id>/edit` | Line 1638 |
| `POST /admin/templates` | Lines 1627-1628 |
| `POST /admin/templates/<int:id>` | Lines 1639-1641 (NEW) |
| `POST /admin/templates/<int:id>/delete` | Line 1642 (NEW) |
| `POST /admin/guidance/<int:industry_id>/<int:component_id>` | Line 1629 |
| `POST /admin/tokens/generate` | Line 1630 |
| `POST /admin/tokens/<int:id>/revoke` | Line 1631 |
| `POST /admin/export` | Line 1632 |
| `POST /auth/logout` | WARN: no user-controlled inputs; CSRF handled globally |

---

## Warnings

| Surface | Warning |
|---------|---------|
| Input Validation (FC4) | `POST /auth/logout` qualifies as POST but has no user-controlled form inputs (CSRF only, handled globally by Flask-WTF). Not a FAIL. Authors may add a row noting "CSRF-only" for completeness. |

## Summary

- **Total checks:** 6
- **PASS:** 5
- **FAIL:** 1
- **WARN:** 1
- **N/A:** 0
- **BLOCKED:** 0

STATUS: FAIL -- 36 omissions found across 1 surface
