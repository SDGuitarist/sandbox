# Spec Contract Check — Run 061

**Checked:** 2026-06-01
**Total checks:** 83 | **PASS:** 80 | **FAIL:** 3

## FAIL Items

### FAIL #81 (LOW) — Delete confirmation event handler
- File: `app/templates/prompts/detail.html`
- Spec: `onclick="return confirm('Are you sure?')"` on button
- Code: `onsubmit="return confirm(...)"` on form
- Functionally equivalent, cosmetic mismatch

### FAIL #82 (FALSE POSITIVE) — test_smoke.py absent from git
- File exists on disk but is intentionally gitignored per spec
- Core agent created it correctly; .gitignore excludes it
- Not a real failure

### FAIL #83 (HIGH) — Dashboard template accesses non-existent `prompt['tags']`
- File: `app/templates/dashboard/index.html`, lines 109-111
- `prompt['tags']` accessed but `prompts` table has no `tags` column
- `get_all_prompts()` returns `SELECT p.*` with no tag join
- Will cause 500 IndexError on dashboard when prompts exist
- Fix: remove tags display from dashboard prompt cards, or modify get_all_prompts to include tags

STATUS: FAIL -- 2 real mismatches (1 false positive)
