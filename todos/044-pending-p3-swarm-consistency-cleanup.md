---
status: pending
priority: p3
issue_id: "044"
tags: [code-review, consistency, brewops]
---

# Swarm Agent Consistency Cleanup (Batch)

## Problem Statement
21 parallel agents produced minor inconsistencies across the codebase:

1. **Flash messages:** auth_routes uses trailing periods, staff omits "successfully", sale has mixed period usage
2. **Doc style:** 4 model files use comment-block headers, 4 use docstrings
3. **Import ordering:** tank/staff routes swap app.db/app.auth order, alphabetize Flask imports differently
4. **Name length:** batches/ingredients/recipes/staff use 200, tanks/taps use 100
5. **`list` shadows built-in:** 7 route files define `def list():`
6. **Taps template:** uses attribute access (tap.name) vs bracket notation (tank['name'])
7. **Taps new route:** doesn't pass `tap=None` to template (relies on Jinja undefined-is-falsy)
8. **Validation duplication:** create/update handlers repeat identical validation (~40 lines each in ingredient, tank, recipe routes)

## Findings
- Pattern reviewer: 12 low-severity findings
- Python reviewer: P2-1, P2-2
- Architecture reviewer: L2-L5
- Simplicity reviewer: ~40 lines duplicated validation

## Proposed Solution
Batch fix in one commit: standardize flash format, pick docstring style, fix import order, normalize template access, pass entity=None on new routes.

## Affected Files
- All route files in app/routes/
- All model files in app/models/
- app/templates/taps/form.html

## Acceptance Criteria
- [ ] Consistent flash message format (no trailing periods, include "successfully")
- [ ] Consistent template property access (bracket notation)
- [ ] tap new route passes tap=None
