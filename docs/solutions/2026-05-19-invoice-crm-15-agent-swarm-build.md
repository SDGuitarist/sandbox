---
title: Invoice & CRM 15-Agent Swarm Build
date: 2026-05-19
type: solution
project: invoice-crm
build_method: swarm
agents: 15
total_files: 80
total_lines: ~6000
tests: 37
merge_conflicts: 0
assembly_fixes: 2
review_findings: TBD
run_id: "046"
tags: [flask, sqlite, jinja2, swarm, crm, invoicing, 15-agent]
---

# Invoice & CRM 15-Agent Swarm Build

## Problem

Build a full-stack Invoice & CRM application (Freshbooks/Wave competitor) for freelancers and small businesses. Flask + SQLite + Jinja2. 12 tables, 12 blueprints, 40+ routes. The largest swarm build attempted: 15 parallel agents.

## Solution

Vertical split by Flask blueprint. Each agent owns one blueprint package (routes, forms, templates). Shared modules (db.py, helpers.py, app factory) owned by scaffold agent. Two spec-prescribed cross-agent imports (dashboard imports generate_due_invoices from recurring).

### Architecture
- 12 Flask blueprints: auth, clients, activities, pipeline, catalog, invoices, recurring, payments, dashboard, reports, settings_bp, search
- 12 SQLite tables with foreign keys and cascading deletes
- Integer cents for all money (|dollars Jinja2 filter for display, manual conversion for form prefill)
- Session-based auth with bcrypt password hashing
- Bootstrap 5 UI with Chart.js, 647-line custom CSS, 141-line vanilla JS
- 37 pytest tests covering all cross-boundary flows

### Agent Split (15 agents)
| Agent | Files | Lines | Role |
|-------|-------|-------|------|
| scaffold | 8 | 390 | App factory, db, helpers, base template |
| auth | 6 | 235 | Login, register, profile |
| clients | 6 | 751 | Client CRUD, tags, search/filter |
| activities | 5 | 210 | Activity log CRUD |
| pipeline | 7 | 546 | Deals, kanban, stage transitions |
| catalog | 5 | 238 | Product/service catalog |
| invoices | 7 | 1134 | Invoice CRUD, line items, numbering |
| recurring | 4 | 259 | Recurring settings, generation |
| payments | 5 | 303 | Payment recording, auto-status |
| dashboard | 3 | 379 | Revenue summary, overdue, recurring trigger |
| reports | 7 | 350 | Revenue, aging, forecast, CSV export |
| settings | 4 | 199 | Business profile, invoice defaults |
| search | 3 | 136 | Global search across entities |
| static | 2 | 788 | CSS + vanilla JS |
| tests | 8 | 899 | Full pytest suite |

## Key Decisions

1. **Vertical split by blueprint works at 15 agents.** Zero merge conflicts across all 15 branches. Each agent's template directory is isolated (blueprint-scoped `template_folder`). This scales linearly.

2. **Cross-boundary wiring table prevents dead exports.** The spec explicitly defined two cross-boundary flows (deal-won -> invoice creation, dashboard -> recurring generation) with exact code blocks. Both worked on first assembly. Compare to Ethics Toolkit where 3 functions were dead exports.

3. **Coordinated behaviors table prevents inconsistency.** Flash message patterns and activity logging rules were prescribed for all 15 agents. No inconsistency found in review.

4. **Form field naming is the #1 test-vs-route mismatch.** 4 of 4 test failures were tests sending `field` when routes expected `field_name` (WTForms field names) or `field[]` (getlist keys). This is FC9 at scale.

5. **Missing dependency (email_validator) is easy to miss.** WTForms Email() validator silently requires email_validator package. requirements.txt didn't list it. Fixed in assembly.

## Assembly Fixes

1. **Missing email-validator dependency** -- WTForms Email() needs it. Added to requirements.txt.
2. **4 test field name mismatches** -- Tests used `stage` instead of `new_stage`, `status` instead of `new_status`, `descriptions` instead of `descriptions[]`. All FC9 instances.

## Risk Resolution

### From Brainstorm Feed-Forward
**Risk flagged:** "cross-blueprint data flows (deal-to-invoice, payment-to-invoice-status, recurring generation from dashboard)"

**What actually happened:** All three cross-boundary flows worked correctly after assembly:
- Deal-won redirects to invoice creation with `from_deal` param (verified by test)
- Payment recording updates invoice status to 'paid' on full payment (verified by test)
- Dashboard triggers recurring generation on load (verified by test)

**What was learned:** The Cross-Boundary Wiring Table with exact code blocks is the solution. When the spec prescribes the exact import statement and function signature, there's no room for naming divergence. This is the 15-agent validation of the pattern introduced in the 8-agent Workshop Registration Hub build.

### From Plan Feed-Forward
**Risk flagged:** "invoice line items form with parallel arrays and JS to add/remove rows"

**What actually happened:** The invoices agent implemented the parallel array pattern correctly with length-check before zip() per the recipe-organizer lesson. The static agent's JS correctly clones template rows and handles catalog autofill. The test that exercises line item creation passed after the `[]` suffix fix.

**What was learned:** Prescribing the exact array key names in the spec (`descriptions[]`, `quantities[]`, etc.) and requiring length-check before zip() prevented the desync bug found in the recipe-organizer build.

## Metrics

| Metric | Value |
|--------|-------|
| Total agents | 15 |
| Total files | 80 |
| Total lines | ~6,000 |
| Total tests | 37 |
| Tests passing | 37/37 |
| Merge conflicts | 0 |
| Assembly fixes | 2 (1 dep, 1 test fix batch) |
| Ownership violations | 0 |
| Smoke test | 20/20 PASS |
| Agent completion time | 45s - 198s |
| Slowest agent | invoices (198s, 1134 lines) |
| Fastest agent | search (45s, 136 lines) |

## Feed-Forward

- **Hardest decision:** Whether to have 15 thin agents or 10 merged agents. 15 thin agents proved correct -- zero merge conflicts.
- **Rejected alternatives:** Merging blueprints would have created shared template directories causing merge conflicts. The thin-agent approach scales better.
- **Least confident:** Whether the test suite (written by a separate agent) would correctly match the routes (written by 12 other agents). 4/37 failures were naming mismatches. For future builds, the test agent's brief should include the exact form field names from each route's spec section.
