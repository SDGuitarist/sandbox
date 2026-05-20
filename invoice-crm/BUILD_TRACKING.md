# BUILD_TRACKING.md

## Run Info

| Field | Value |
|-------|-------|
| Project | Invoice & CRM (InvoiceCRM) |
| Spec | docs/plans/invoice-crm-plan.md |
| Date | 2026-05-19 |
| Phases | 6 (brainstorm, plan, plan-review, work, review, compound) |
| Total Agents | 15 |
| Build Method | swarm |
| Run ID | 046 |
| Reports Dir | docs/reports/046/ |
| Self-Audit | docs/reports/046/self-audit.md |

---

## AGENT_STATUS

### scaffold -- Phase 1
- **Status:** COMPLETED
- **Files created:** 8 (run.py, requirements.txt, .gitignore, __init__.py, config.py, db.py, helpers.py, base.html)
- **Files modified:** 0
- **Duration:** ~100s
- **Issues encountered:** none
- **Commit:** a909f9c

### auth -- Phase 1
- **Status:** COMPLETED
- **Files created:** 6 (blueprint, routes, forms, 3 templates)
- **Duration:** ~73s
- **Issues encountered:** none
- **Commit:** c139d49

### clients -- Phase 1
- **Status:** COMPLETED
- **Files created:** 6 (blueprint, routes, forms, 3 templates)
- **Duration:** ~138s
- **Issues encountered:** none
- **Commit:** 69697d0

### activities -- Phase 1
- **Status:** COMPLETED
- **Files created:** 5 (blueprint, routes, forms, 2 templates)
- **Duration:** ~64s
- **Issues encountered:** none
- **Commit:** 4cdf56e

### pipeline -- Phase 1
- **Status:** COMPLETED
- **Files created:** 7 (blueprint, routes, forms, 4 templates)
- **Duration:** ~107s
- **Issues encountered:** none
- **Commit:** 0533ec5

### catalog -- Phase 1
- **Status:** COMPLETED
- **Files created:** 5 (blueprint, routes, forms, 2 templates)
- **Duration:** ~72s
- **Issues encountered:** none
- **Commit:** a43ae4b

### invoices -- Phase 1
- **Status:** COMPLETED
- **Files created:** 7 (blueprint, routes, forms, 4 templates)
- **Duration:** ~198s (slowest -- most complex agent, 1134 lines)
- **Issues encountered:** none
- **Commit:** fa7e1b2

### recurring -- Phase 1
- **Status:** COMPLETED
- **Files created:** 4 (blueprint, routes, 2 templates)
- **Duration:** ~72s
- **Issues encountered:** none
- **Commit:** 98a20cb

### payments -- Phase 1
- **Status:** COMPLETED
- **Files created:** 5 (blueprint, routes, forms, 2 templates)
- **Duration:** ~77s
- **Issues encountered:** none
- **Commit:** 7a77f90

### dashboard -- Phase 1
- **Status:** COMPLETED
- **Files created:** 3 (blueprint, routes, 1 template)
- **Duration:** ~92s
- **Issues encountered:** none
- **Cross-boundary imports used:** generate_due_invoices from app.recurring.routes
- **Commit:** 1cd2fff

### reports -- Phase 1
- **Status:** COMPLETED
- **Files created:** 7 (blueprint, routes, 5 templates)
- **Duration:** ~113s
- **Issues encountered:** none
- **Commit:** 2b54ef2

### settings -- Phase 1
- **Status:** COMPLETED
- **Files created:** 4 (blueprint, routes, forms, 1 template)
- **Duration:** ~65s
- **Issues encountered:** none
- **Commit:** 57f12e9

### search -- Phase 1
- **Status:** COMPLETED
- **Files created:** 3 (blueprint, routes, 1 template)
- **Duration:** ~45s (fastest)
- **Issues encountered:** none
- **Commit:** ebd1097

### static -- Phase 1
- **Status:** COMPLETED
- **Files created:** 2 (style.css, app.js)
- **Duration:** ~110s
- **Issues encountered:** none
- **Commit:** 175d2d1

### tests -- Phase 1
- **Status:** COMPLETED
- **Files created:** 8 (conftest, 6 test files, __init__)
- **Tests added:** 37
- **Duration:** ~159s
- **Issues encountered:** 4 field name mismatches (fixed in assembly)
- **Commit:** 05f401d

---

## FAILURES

### 2026-05-19 Assembly -- Missing email-validator Dependency

**Phase:** Assembly
**Severity:** LOW
**Location:** requirements.txt

**Error:**
```
ModuleNotFoundError: No module named 'email_validator'
```

**Root cause:** WTForms Email() validator requires email_validator package, which wasn't in requirements.txt. Auth agent used the validator correctly but didn't add the transitive dependency.
**Resolution:** Added `email-validator>=2.0` to requirements.txt
**Time to resolve:** <1 min
**Failure class:** New pattern -- transitive dependency not listed

### 2026-05-19 Assembly -- 4 Test Field Name Mismatches

**Phase:** Test Suite
**Severity:** LOW
**Location:** tests/test_invoices.py, tests/test_pipeline.py

**Error:**
Test sends `stage` but route expects `new_stage` (MoveDealForm field name).
Test sends `descriptions` but route expects `descriptions[]` (getlist key).
Test sends `status` but route expects `new_status` (StatusForm field name).

**Root cause:** Tests agent inferred form field names from feature descriptions instead of reading the exact WTForms class definitions or route code. Classic FC9 (Mock/Test Data Mismatches) at scale.
**Resolution:** Changed field names in test data to match route expectations
**Time to resolve:** <2 min
**Failure class:** FC9 (Mock/Test Data Mismatches)

---

## RUN_METRICS

### Final Build Metrics

| Metric | Value |
|--------|-------|
| Total agents | 15 |
| Total files | 80 |
| Total lines | ~6,000 |
| Total tests | 37 |
| Tests passing | 37/37 |
| Merge conflicts | 0 |
| Ownership violations | 0 |
| Smoke test | 20/20 PASS |
| Assembly fixes | 2 |
| P1 findings (review) | 8 (deduplicated across 4 reviewers) |
| P2 findings (review) | ~12 |
| P3 findings (review) | ~17 |
| All P1s fixed | yes (6 fixed in code, 2 documented as acceptable) |

### Agent Performance Summary

| Agent | Findings Caused | Failure Classes Hit | Notes |
|-------|----------------|--------------------|----|
| scaffold | 0 | -- | Clean build, all shared modules correct |
| auth | 1 | FC33 (transitive dep) | Missing email-validator in requirements |
| invoices | 3 | FC4, FC17, new | IDOR on client_id, duplicated line-item parsing, redundant DELETE |
| recurring | 1 | FC2 | Prefix[:3] slice in invoice number generation (crash bug) |
| payments | 2 | new, new | Status bypass (draft payments allowed), hardcoded revert to 'sent' |
| dashboard | 2 | new, new | Overdue skips 'viewed', 12 queries per load |
| tests | 4 | FC9 | Form field name mismatches |
| All others | 0 | -- | Clean builds |

### Lessons for Next Build

1. **FC9 update:** Test agent briefs should include exact form field names from each route's WTForms class or request.form.get() calls
2. **Transitive deps:** Spec should list ALL pip dependencies including transitive ones like email-validator
3. **15 agents scales linearly** with zero merge conflicts when using blueprint-scoped templates

---

## Template Version

v1.0 -- 2026-05-03 (created after WRC Build #7)
