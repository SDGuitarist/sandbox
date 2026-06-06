---
title: "Gig Outcome Tracker: First Real Build Validating 3-Stage Context-Death Architecture"
date: 2026-06-06
run_id: "068"
category: swarm-build
severity: none
problem_type: feature-build / architecture-validation
tags:
  - swarm-build
  - 12-agent
  - flask
  - sqlite3
  - jinja2
  - context-death
  - delegation-architecture
  - spec-eval-gate
  - dashboard-aggregation
  - architecture-validation
components:
  - app/__init__.py
  - app/venue_models.py
  - app/venue_routes.py
  - app/gig_models.py
  - app/gig_routes.py
  - app/outcome_models.py
  - app/outcome_routes.py
  - app/contact_models.py
  - app/contact_routes.py
  - app/debrief_models.py
  - app/debrief_routes.py
  - app/dashboard_routes.py
root_cause: >
  Primary goal: build a single-user gig intelligence tracker (Flask + SQLite
  + Jinja2, 12 agents, 33 files, ~3076 LOC) and simultaneously validate the
  3-stage context-death delegation architecture introduced in run 065 under
  realistic 12-agent coordination load. Secondary goal: verify the
  deterministic dashboard aggregation fixture (3 played gigs, $880 paid-only
  revenue, 4.5 avg energy, 8000 tips, Grand Ballroom above Sunset Lounge).
resolution: >
  All 12 agents completed without merge conflicts (disjoint file sets).
  Contract check PASS with 1 inline fix (contact_models executescript→execute).
  Smoke test 54/54 PASS including full dashboard fixture verification.
  Architecture validated: spec-eval gate WAIVED_BY_HUMAN after harness fix;
  two binding structural gates PASSED. Tail phase (review + P2 fixes + compound)
  completed by tail-runner agent.
review_findings:
  p1_count: 0
  p2_count: 2
  all_fixed: true
  fix_commit: 89c2148
related_runs:
  - "065"
  - "067"
failure_class: none
recurrence_risk: low
predecessor: docs/solutions/2026-06-05-autopilot-context-death-delegation-architecture.md
---

# Gig Outcome Tracker: First Real Build Validating 3-Stage Context-Death Architecture

## Problem / Goal

Build a single-user gig intelligence tracker from scratch as a 12-agent
swarm, and use it to validate the 3-stage context-death delegation
architecture introduced in run 065. The app needed to be genuinely useful,
but the primary objective was proving that 12 isolated agents could
implement against a shared spec with zero merge conflicts and zero
cross-section contradictions, completing fully unattended.

The Feed-Forward risk from the plan: dashboard aggregation query correctness —
no prior solution doc covered paid-only revenue / GROUP BY / COALESCE logic.

## What Was Built

Flask app-factory + SQLite (stdlib `sqlite3`) + Jinja2, single-user gig
intelligence tracker. CSRF via Flask-WTF. 33 files, ~3076 LOC.

### Domain Model

- **Venues** — hotel/restaurant/corporate/festival/other with analytics
- **Gigs** — scheduled/played/cancelled with payment tracking (integer cents)
- **Outcomes** — 1:1 per gig, audience energy (1-5), tips, leads, rating
- **Contacts** — met at gig / venue, follow-up tracking
- **Debriefs** — raw text + takeaways + lessons, keyword search (LIKE, no FTS5)
- **Dashboard** — aggregation view (paid-only revenue, avg energy, top venues, monthly trend)

### Agent Assignment (12 agents, disjoint file sets)

| Agent | Files | Status |
|-------|-------|--------|
| scaffold | `run.py`, `app/__init__.py`, base templates, auth | COMPLETED |
| venue_models | `app/venue_models.py` | COMPLETED |
| venue_routes | `app/venue_routes.py` + venues templates | COMPLETED |
| gig_models | `app/gig_models.py` | COMPLETED |
| gig_routes | `app/gig_routes.py` + gigs templates | COMPLETED |
| outcome_models | `app/outcome_models.py` | COMPLETED |
| outcome_routes | `app/outcome_routes.py` + outcomes templates | COMPLETED |
| contact_models | `app/contact_models.py` | COMPLETED |
| contact_routes | `app/contact_routes.py` + contacts templates | COMPLETED |
| debrief_models | `app/debrief_models.py` | COMPLETED |
| debrief_routes | `app/debrief_routes.py` + debriefs templates | COMPLETED |
| dashboard | `app/dashboard_routes.py` + dashboard template | COMPLETED |

## Key Technical Decisions

### 1. Dashboard Aggregation (the Feed-Forward risk)

The critical queries: paid-only revenue uses LEFT JOIN to outcomes (so paid
gigs without outcome rows still contribute their pay), COALESCE on both sides
(so NULL pay or NULL tips don't zero out the sum), and `payment_status = 'paid'`
filter to exclude Gig 3's unpaid $450.

```sql
-- total_revenue_cents: COALESCE on both arms, payment_status filter
SELECT COALESCE(SUM(g.actual_pay_cents), 0) + COALESCE(SUM(o.tips_cents), 0)
FROM gigs g
LEFT JOIN outcomes o ON o.gig_id = g.id
WHERE g.status = 'played' AND g.payment_status = 'paid';

-- avg_audience_energy: averages over outcome rows (not gig rows)
SELECT AVG(audience_energy) FROM outcomes;
-- Returns 4.5 for the fixture (Gig1=4, Gig2=5; Gig3 played but no outcome)
```

Fixture verification (smoke test 54/54 PASS):
- 3 played gigs
- $880 (88000 cents) total revenue — Gig1 50000 + Gig2 30000 + tips 5000+3000;
  Gig3's 45000 unpaid excluded
- 4.5 avg energy — 2 outcome rows (Gig1=4, Gig2=5)
- 8000 total tips
- Grand Ballroom (2 played) above Sunset Lounge (1 played)

### 2. Spec-Eval Gate Waiver

The pre-swarm spec-eval gate (Step 9w.8) returned FAIL on a now-credible
harness (fixed in commit 6e3bf80 — stack detection, judge routing,
self-contained scenarios). Analysis of 20 residual failures found them to be
single-shot-agent artifacts, not spec defects:
- ~5 cosmetic type hints (`-> list` vs `-> list[Row]`, runtime-identical)
- ~6 auth-matrix rows → output truncation at 1024 tokens
- ~9 prose failures (wrong stack, truncated before templates)

The spec itself PASSED both binding structural gates:
- spec-consistency-check: PASS (45 checks, full Export↔Wiring bidirectional)
- spec-completeness-check: PASS (all 6 mandatory surfaces, 47 wiring rows)

**Gate was WAIVED_BY_HUMAN on 2026-06-06 (operator: Alex Guillen).** See
`docs/reports/068/spec-eval-waiver.md`.

### 3. Contact Models Inline Fix

`init_contact_schema` used `conn.executescript(CONTACT_SCHEMA)` (implicit
commit) instead of `conn.execute(CONTACT_SCHEMA)`. The `executescript()` call
issued an implicit `COMMIT` that disrupted the scaffold's outer `with conn:`
init_db block. Fixed by swarm-runner before contract check (commit 5742bc9).

**Pattern:** `executescript()` is for multi-statement scripts only. DDL strings
that are a single statement must use `conn.execute()`.

### 4. Blueprint Routing Order Constraint

The spec required static literal paths declared before `<converter>` paths
within each blueprint to prevent Flask from matching `<id>='new'` or
`<gig_id>='search'`:

```python
# contact_routes — MUST be in this order:
@contacts_bp.route('/follow-ups')   # static, before /<id>
@contacts_bp.route('/new')          # static, before /<id>
@contacts_bp.route('/<id>')         # dynamic, must be last

# debrief_routes — MUST be in this order:
@debriefs_bp.route('/search')       # static, before /<gig_id>
@debriefs_bp.route('/<gig_id>')     # dynamic, must be last
```

Both agents implemented this correctly.

### 5. Transaction Pattern

All model write functions use `with conn:` (no `conn.commit()`, no bare
`BEGIN`). `init_db` owns the outer `with conn:` block; all `init_*_schema`
functions call `conn.execute(DDL)` directly and delegate commit ownership to
the caller.

Exception caught during review: `init_debrief_schema` had a nested `with conn:`
(inconsistent with other 4 init functions). Fixed in commit 89c2148.

## Architecture Validation: 3-Stage Delegation

This was the first real build (not a harness test) of the 3-stage
context-death delegation architecture:

1. **No-read discipline** — swarm-runner reads gate reports at `limit:1`
   (reads only STATUS line), not full content. Prevents context saturation
   from large gate reports.
2. **deepen-merge-runner** — plan deepening + merge delegated to fresh context
   (new subagent), not inline in orchestrator.
3. **swarm-runner** — assembly + verification (Steps 11w-16w) delegated to
   fresh context, not inline in orchestrator.

**Result:** Orchestrator survived 12-agent spawn + assembly without context
death. Build completed with `final_status: ASSEMBLY_PASS` and
`manual_resume: false` (fully unattended). Tail phase handed off to
tail-runner agent.

**Limitation confirmed:** Deepening + worker spawn (Steps 7w-10.5w) remain
inline. The architecture is not yet proven for 20+ agent builds where those
phases may saturate context.

## Review Findings (Run 068)

P1: 0, P2: 2, P3: 2

| Finding | Severity | Status |
|---------|----------|--------|
| `monthly_revenue` ignores `months` param (hardcoded `-6 months`) | P2 | Fixed (89c2148) |
| `init_debrief_schema` nested `with conn:` inside `init_db` outer block | P2 | Fixed (89c2148) |
| `outcome_routes` view GET flashes 'error' for "no outcome yet" (informational) | P3 | Deferred |
| `list_contacts` has no ORDER BY (non-deterministic order) | P3 | Deferred |

## Risk Resolution

**What was flagged as risk (Feed-Forward):** Dashboard aggregation query
correctness — paid-only revenue / GROUP BY / COALESCE logic; specifically the
LEFT JOIN to outcomes (so paid gigs without outcomes still count their pay),
the `payment_status='paid'` filter (so Gig 3's unpaid 45000 is excluded), and
`AVG(audience_energy)` averaging over outcome rows (2), not gig rows (3).

**What actually happened:** The dashboard agent implemented the queries
correctly, matching the spec's prescriptive SQL in Section 12 exactly. The
smoke test seeded the full 4-gig deterministic fixture via POST routes and
verified all 5 dashboard assertions (3 played, 88000 revenue, 4.5 energy,
8000 tips, Grand Ballroom > Sunset Lounge) — all PASS. The spec-level
prescriptions (exact SQL) were load-bearing: having the spec dictate the
exact query prevented any agent-level guessing about the aggregation logic.

**Delta between expectation and reality:** The risk did NOT materialize
during implementation — it was fully prevented by the prescriptive SQL in the
spec. The review still scrutinized the queries, confirmed the LEFT JOIN is
correct (not INNER JOIN, which would drop paid gigs without outcomes), and
confirmed the COALESCE handles NULL tips correctly. No query corrections
were needed.

**Lesson:** For aggregation logic where correctness is non-obvious and the
failure mode is a silently wrong number (not an exception), prescribing the
exact SQL in the spec is a more reliable mitigation than asking agents to
derive the correct query from requirements. The deterministic fixture as a
verification anchor is equally important — it makes "silently wrong" visible.

## Prevention / Patterns

### For future swarm builds with dashboard aggregation:

1. **Prescribe exact SQL** for any aggregation involving COALESCE + LEFT JOIN
   + multiple filters. Don't write "calculate paid-only revenue" — write the
   exact query. Agents implement exact SQL reliably; they derive complex
   aggregations less reliably.

2. **Deterministic fixture as acceptance test anchor.** A fixture with known
   expected values (e.g., 88000 cents, 4.5 avg energy) catches silently
   wrong aggregations that don't raise exceptions.

3. **Route ordering in blueprints.** Static literal paths (`/follow-ups`,
   `/search`) MUST be declared before dynamic `<converter>` paths in the same
   blueprint. Enforce this as a spec constraint, not a review finding.

4. **`executescript()` vs `execute()` for DDL.** DDL strings with a single
   statement MUST use `conn.execute()`. `executescript()` triggers an
   implicit commit — incompatible with `with conn:` transaction blocks.

5. **`init_*_schema` functions call `conn.execute(DDL)` directly** — they do
   NOT wrap in `with conn:`. Transaction ownership belongs to the caller
   (`init_db`'s outer `with conn:`).

6. **`monthly_revenue(months=N)` anti-pattern.** If a function accepts a
   window parameter, the SQL must use it. Hardcoded literals that shadow
   a parameter create a misleading contract that smoke tests won't catch if
   the default matches the literal.

### For spec-eval gate:

1. The spec-eval harness fails on single-shot agents generating partial
   implementations (1024-token output truncation, wrong stack). This is a
   harness limitation, not a spec-followability defect.
2. The two binding structural gates (spec-consistency, spec-completeness)
   are more reliable signals of spec quality than the spec-eval gate.
3. A WAIVED_BY_HUMAN disposition is appropriate when: harness is credible,
   residual failures are all artifact/truncation classes, and structural
   gates PASS. Document the waiver explicitly in spec-eval-waiver.md.

## Artifacts

| Artifact | Path |
|----------|------|
| Plan | `docs/plans/2026-06-05-gig-outcome-tracker-plan.md` |
| Spec eval waiver | `docs/reports/068/spec-eval-waiver.md` |
| Smoke test report | `docs/reports/068/smoke-test.md` |
| Assembly summary | `docs/reports/068/assembly-summary.md` |
| Contract check | `docs/reports/068/contract-check.md` |

## Cross-References

- **3-Stage Architecture:** `docs/solutions/2026-06-05-autopilot-context-death-delegation-architecture.md`
- **Tail Delegation:** `docs/solutions/2026-06-01-tail-delegation-context-resilience.md`
- **Spec Convergence Loop:** `docs/solutions/2026-04-30-spec-convergence-loop.md`
- **Spec Completeness Checker:** `docs/solutions/2026-05-21-spec-completeness-checker-pre-swarm-gate.md`
- **Spec Eval Gate:** `docs/solutions/2026-06-01-spec-eval-gate-pre-swarm-validation.md`
- **Flask Swarm ACID Test:** `docs/solutions/2026-04-07-flask-swarm-acid-test.md`

## Feed-Forward

- **Hardest decision:** Whether the spec-eval FAIL warranted stopping the build
  or proceeding with a human-authorized waiver. Chose waiver because (1)
  harness was fixed and credible, (2) all residual failures were classified as
  single-shot-agent artifacts, (3) both binding structural gates PASSED.
  The waiver is the right call when gate infrastructure is imperfect but spec
  quality is high — stopping a credible build because of harness artifacts
  wastes build effort for zero safety gain.
- **Rejected alternatives:** Running the spec-eval gate in multi-shot mode
  (would require rewriting the harness); accepting the FAIL without waiver
  documentation (would silently lower the gate's apparent value).
- **Least confident:** Whether the 3-stage architecture survives 20+ agent
  builds. The 12-agent case passed, but deepening + worker spawn are still
  inline. The next validation step is a 20-25 agent build (CPAA shadow lab
  event-replay simulator) to test the inline-phase context limit.
