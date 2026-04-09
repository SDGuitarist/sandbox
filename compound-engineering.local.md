# Review Context -- Sandbox (Finance Tracker Swarm Build)

## Risk Chain

**Brainstorm risk:** "Cents conversion layer -- every form input must multiply
by 100, every display must divide by 100. A missed conversion shows $4599
instead of $45.99."

**Plan mitigation:** Extracted `dollars_to_cents` and `format_dollars` to
`app/utils.py`. Registered `|dollars` Jinja2 filter. Anti-patterns documented
in shared spec. Deepening added NaN/Inf/zero-cents guards.

**Work risks (from Feed-Forward):**
1. ON DELETE SET DEFAULT -- uncommon SQLite feature, verified working in smoke test.
2. Route prefix doubling -- new swarm-specific bug, caught by contract checker.

**Review resolution:** 1 P1, 4 P2, 2 P3 across 4 review agents.
- P1: transaction_date not validated (fixed)
- P2: year_month unbounded range (fixed), description length (fixed),
  lazy import re (fixed), duplicated WHERE builder (fixed)
- P3: color hex not validated (fixed), repeated render blocks (deferred)

## Files to Scrutinize

| File | What changed | Risk area |
|------|-------------|-----------|
| finance-tracker/app/utils.py | dollars_to_cents, validate_date, validate_year_month | Cents conversion, input validation |
| finance-tracker/app/models.py | 17 model functions, dashboard aggregate | SQL construction, _build_transaction_where |
| finance-tracker/app/blueprints/transactions/routes.py | 4 routes, validation, form handling | Date validation, amount conversion |
| finance-tracker/app/blueprints/views/routes.py | Dashboard + budget batch form | Aggregate math, batch upsert |
| finance-tracker/app/schema.sql | ON DELETE SET DEFAULT, CHECK constraints | Category deletion cascade |

## Plan Reference

`docs/plans/2026-04-09-feat-personal-finance-tracker-plan.md`
