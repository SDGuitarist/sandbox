---
title: "VenueConnect: 25-Agent Swarm Build (Run 049)"
category: swarm-build
tags: [flask, sqlite, swarm, 25-agent, rbac, booking, settlement, pdf, fts5, notifications, chart-js, state-machine]
module: venueconnect
date: 2026-05-20
run_id: "049"
agents: 25
files: 90
lines: 5750
grade: pending
symptom: "Largest swarm build to date -- 25 agents, 3-role RBAC, 8-state booking lifecycle, settlement engine with PDF, FTS5 search, Chart.js analytics"
root_cause: "N/A (greenfield build)"
---

# VenueConnect: 25-Agent Swarm Build (Run 049)

## Problem / Goal

Build a three-sided venue booking and settlement platform for the live music
industry. Venues list rooms and availability, musicians search and request
bookings, promoters create events. After shows, settlement sheets calculate
payouts (guarantee vs door split vs hybrid). This was designed as the largest
and most complex sandbox swarm build to date, targeting 25 agents (run 048
was 20).

## Solution Summary

**90 files, 5,750 LOC, 25 agents, zero merge conflicts, 18/18 smoke tests pass.**

Vertical blueprint split with strict file ownership. Each agent owns a Flask
blueprint (routes + templates) or a shared module. No two agents write to the
same file. The shared interface spec (2,620 lines) prescribed every function
signature, form field name, template render context variable, and cross-boundary
import.

### Architecture

- **Stack:** Flask 3.1 + SQLite + Jinja2 + Bootstrap 5 + ReportLab + Chart.js 4.x
- **Auth:** Session-based, single role per user (venue_manager, musician, promoter)
- **Decorators:** `@login_required` (sets g.user) + `@role_required(role)` (403)
- **State machine:** Dict-based with guard functions in `booking_lifecycle.py`
- **Money:** Integer cents everywhere, `|dollars` Jinja filter, `round(float(...)*100)` for form parsing
- **Search:** FTS5 virtual table with INSERT/UPDATE/DELETE triggers
- **PDF:** ReportLab SimpleDocTemplate with BytesIO buffer
- **Charts:** Chart.js CDN, data via `{{ data|tojson }}` in inline scripts
- **Notifications:** Table + helper + navbar badge polled via JS fetch

### Agent Split (25 Agents)

| # | Agent | Files | Lines | Status |
|---|-------|-------|-------|--------|
| 1 | scaffold | 11 | 282 | Clean |
| 2 | auth | 6 | 285 | Clean |
| 3 | models | 3 | 900 | Clean |
| 4 | venue-crud | 5 | 304 | Clean |
| 5 | room-crud | 5 | 264 | Clean |
| 6 | availability | 4 | 250 | Clean |
| 7 | booking-create | 7 | 595 | Clean |
| 8 | booking-manage | 5 | 550 | Clean |
| 9 | booking-lifecycle | 1 | 164 | Clean |
| 10 | promoter-events | 5 | 285 | Clean |
| 11 | ticket-tiers | 4 | 360 | Clean |
| 12 | settlement-engine | 1 | 51 | Clean |
| 13 | settlement-views | 5 | 307 | Clean |
| 14 | settlement-pdf | 1 | 88 | Clean |
| 15 | search | 3 | 74 | Clean |
| 16 | notifications | 1 | 39 | Clean |
| 17 | notification-views | 3 | 85 | Clean |
| 18 | analytics-venue | 3 | 113 | Clean |
| 19 | analytics-musician | 3 | 117 | Clean |
| 20 | analytics-promoter | 3 | 110 | Clean |
| 21 | dashboard-venue | 3 | 118 | Clean |
| 22 | dashboard-musician | 3 | 125 | Clean |
| 23 | dashboard-promoter | 3 | 72 | Clean |
| 24 | seed | 1 | 83 | Clean |
| 25 | tests | 1 | 117 | Clean |

### Assembly Results

- **Merge conflicts:** 0 (all agents created new files, no overlapping edits)
- **Assembly fixes needed:** 2 (role-to-dashboard mapping, trailing slash in tests)
- **Uncommitted worktrees:** 14 of 25 agents didn't auto-commit -- orchestrator committed manually
- **Smoke tests:** 18/18 pass after assembly fixes

## Review Findings

### P1s Fixed (8 total)

| # | Finding | Agent Source | Fix |
|---|---------|-------------|-----|
| 1 | IDOR on settlement detail | settlement-views (13) | Added `_check_settlement_access()` ownership check |
| 2 | IDOR on settlement PDF | settlement-views (13) | Same ownership check |
| 3 | IDOR on settlement approval | settlement-views (13) | Check `venue_manager_id` match |
| 4 | IDOR on musician booking detail | booking-create (7) | Check `musician_user_id` match |
| 5 | Promoter link_booking escalation | promoter-events (10) | Validate booking's venue matches event's venue |
| 6 | Unvalidated financial parsing | settlement-views (13), booking-create (7) | try/except on float conversion |
| 7 | FTS5 MATCH injection | models (3) | Sanitize query, quote as phrase |
| 8 | Inconsistent rounding | booking-manage (8) | Added `round()` to advance_dollars conversion |

### P2s Documented (9 total, deferred)

| # | Finding | Type | Effort |
|---|---------|------|--------|
| 1 | N+1 query in dashboard-venue | Performance | Medium |
| 2 | Unbounded list queries (no pagination) | Performance | Large |
| 3 | Analytics queries without date bounds | Performance | Medium |
| 4 | Missing WAL mode | Performance | Small |
| 5 | Missing composite index for conflict check | Performance | Small |
| 6 | Notification mark_read no ownership | Security | Small |
| 7 | Percentage field sum validation | Security | Small |
| 8 | Missing CSP header | Security | Small |
| 9 | Session cookie security attributes | Security | Small |

## Key Lessons

### 1. Worktree Agent Commit Reliability (NEW)

**14 of 25 agents failed to commit their changes** despite being instructed to
commit. The files were created correctly in the worktree directories but not
staged/committed to git. The orchestrator had to manually `git add` and `commit`
for each affected worktree.

**Root cause:** Uncertain -- possibly the agents' commit commands were blocked
by security heuristics or the agents ran out of context before reaching the
commit step.

**Prevention:** After all agents complete, the orchestrator must verify each
branch has commits beyond the base. Check with
`git log --oneline -1 <branch>` and compare to the base commit. If unchanged,
manually commit from the worktree.

### 2. Role-to-Blueprint Name Mapping (FC1 variant)

The root route and auth login used `url_for(f'dashboard_{role}.index')` where
`role` = `venue_manager`. This produced `dashboard_venue_manager.index` but
the blueprint is named `dashboard_venue`. The underscore in `venue_manager`
was not accounted for in the naming pattern.

**Prevention:** For multi-word role names, spec must prescribe a `DASHBOARD_MAP`
dict that maps role strings to blueprint names. Never use f-string interpolation
with user-controlled role values in `url_for()`.

### 3. Trailing Slashes on Blueprint Root Routes

Flask blueprints registered at `/dashboard/venue` with a route `@bp.route('/')`
serve at `/dashboard/venue/` (with trailing slash). Requests to `/dashboard/venue`
(without slash) get a 308 redirect. Smoke tests must use trailing slashes for
blueprint root routes.

**Prevention:** Add to coordinated behaviors table: "Blueprint root routes
require trailing slash in URLs and tests."

### 4. IDOR is the #1 Security Finding in Multi-Role Apps

5 of 8 P1 findings were IDOR (Insecure Direct Object Reference). Each route
checked the user's role via `@role_required()` but not whether the specific
resource belongs to that user. The booking lifecycle guards (in
`advance_booking_state`) correctly checked ownership, but CRUD routes did not.

**Prevention:** Add a mandatory coordinated behavior: "Every detail/edit/delete
route must verify `resource.owner_field == g.user['id']` after the 404 check."
This should be in the spec's coordinated behaviors table, not left to agents.

### 5. Spec Consistency Checker Caught Real Bugs Pre-Swarm

The pre-swarm spec consistency checker found 2 critical issues that would have
broken reject/cancel at the database level (missing CHECK constraint states)
and the notification badge JS (wrong URL). Both were fixed before agents launched,
preventing 25 agents from building against a broken spec.

**Lesson:** The spec consistency checker ROI is highest on large swarms. At 25
agents, a spec bug amplifies to 25 agents building wrong code.

## Risk Resolution (Feed-Forward Closure)

**Brainstorm risk:** "RBAC permission boundaries and booking state machine are
the two novel patterns most likely to produce cross-section contradictions."

**What actually happened:**
- RBAC permission boundaries: The spec prescribed decorators correctly, but
  IDOR ownership checks were missing from most routes. The guards in
  `advance_booking_state` were the only defense, and they worked. But CRUD
  routes had no ownership protection. 5 P1 IDOR findings.
- Booking state machine: Worked correctly across all 3 consuming agents (8, 13,
  and the booking-lifecycle agent 9). The prescriptive code block in the spec
  was followed exactly by all agents. Zero state machine bugs.

**Plan risk:** "Calendar conflict detection atomicity."

**What actually happened:** The BEGIN IMMEDIATE + check_room_available +
create_booking pattern was implemented correctly by the booking-create agent.
Flow-trace reviewer confirmed the TOCTOU prevention works. No bugs found.

**Delta:** The brainstorm correctly identified RBAC as the highest risk, but
underestimated HOW it would manifest. The risk wasn't in the decorator chain
(which worked) but in missing ownership checks on non-state-machine routes.
The state machine itself was the safest part because it was the most
prescriptively specified.

**Lesson:** Prescriptive code blocks in specs prevent bugs. Prose descriptions
of security requirements ("check ownership") get skipped. Future specs should
include exact ownership check code blocks in every agent's brief, not just
the state machine consumers.

## Prevention Strategies

1. **Add IDOR ownership check to coordinated behaviors** -- not just the role
   decorator, but the actual `resource.owner == g.user['id']` pattern
2. **Verify worktree commits after agent completion** -- automated check that
   each branch has commits beyond base
3. **DASHBOARD_MAP dict** for role-to-blueprint name translation
4. **Trailing slash in test URLs** for blueprint root routes
5. **FTS5 sanitization** as a standard pattern (strip operators, quote as phrase)

## Cross-References

- **Brainstorm:** docs/brainstorms/2026-05-19-venueconnect-brainstorm.md
- **Plan:** docs/plans/2026-05-19-venueconnect-plan.md
- **Prior art:** Run 048 (client-music-planner, 20 agents), Run 047 (solopreneur, 16 agents)
- **Agent pitfalls:** FC1 (naming), FC7 (prefix doubling), FC9 (form fields), FC29 (transaction boundaries)
- **New patterns:** IDOR as coordinated behavior, worktree commit verification, role-to-blueprint mapping
