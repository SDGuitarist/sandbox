# Codex Review Handoff: Gig Outcome Tracker Autopilot Brief

## Context

Read these files first:
  - HANDOFF.md (project state)
  - CLAUDE.md (operating contract, mandatory spec sections, escalation rules)
  - docs/briefs/2026-06-05-gig-outcome-tracker-autopilot-brief.md (the brief)

## What This Is

An autopilot brief for a 12-agent Flask + SQLite swarm build. This brief
will be the sole input to `/autopilot` — the system brainstorms, plans, and
builds from it with zero human prompts. Everything an agent needs to build
the right thing must be in this document.

This is also the first build validating the 3-stage context-death delegation
architecture (no-read discipline + deepen-merge-runner + swarm-runner).

## Review This Brief For

### 1. Completeness — Can Agents Build From This Alone?

- Does the data model have enough detail for a model agent to write DDL +
  CRUD functions without inventing anything?
- Does the route table cover every user-facing action?
- Does the cross-boundary wiring table cover every cross-module import?
  Missing entries cause assembly failures.
- Are the dashboard SQL queries precise enough to implement identically
  across agents?
- Are validation rules complete? Check: can an agent build every POST route
  handler from the validation table alone?

### 2. Internal Consistency — Do All Sections Agree?

Check these specific known-risk areas:
- Feature Scope says "CRUD" for entities — do the routes table and smoke
  tests cover create, read, update, AND delete for each?
- The data model has paired CHECK on `actual_pay_cents` + `payment_status`.
  Do the validation rules match? Does the gig edit form enforce this?
- "Single-user focus, no user_id" — does this create any problem for the
  auth flow? Does session-based auth work without user_id on domain tables?
- Venue dedup is case-insensitive UNIQUE. Do the validation rules and the
  venue create route both handle this?
- Outcomes and debriefs are 1:1 with gigs. Do the routes, validation, and
  data model all enforce this consistently?

### 3. Agent Split Quality — Will This Cause Merge Conflicts?

- Are file ownership boundaries clean? No two agents should write the same
  file.
- Does the dashboard agent import from gig_models and outcome_models without
  owning those tables?
- Does the gig_routes agent import from 4 other model agents (venue, outcome,
  debrief, contact)? Is that manageable, or should the gig detail hub be
  simplified?
- The scaffold agent owns get_db(), base.html, auth, and static CSS. Is that
  too much for one agent?

### 4. Gaps — What Will Break During Implementation?

- Are there any routes that need data from a model agent but aren't listed
  in the cross-boundary wiring table?
- Is the debrief search implementation specified enough? (SQLite LIKE vs FTS5)
- Are the status transition rules (upcoming→played, upcoming→cancelled)
  complete? What about reversing a cancellation?
- Is the gig delete flow safe? Route checks status = 'upcoming', DB enforces
  no outcome/debrief via RESTRICT. Are both needed, or is there a gap?
- The acceptance criteria mention "Dashboard totals match prescribed SQL
  calculations" — is this testable in a smoke test, or does it need fixture
  data?

### 5. Swarm-Specific Risks

- Does this brief have enough information for the autopilot to generate a
  spec with all 6 mandatory sections (CLAUDE.md requirements): Export Names,
  Cross-Boundary Wiring, Input Validation, Coordinated Behaviors,
  Transaction Contracts, Authorization Matrix?
- Is the agent count (12) appropriate for the complexity? Too many agents
  for a simple app = unnecessary coordination overhead. Too few = doesn't
  stress-test the architecture.
- Any FC (failure class) risks from agent-pitfalls.md that this brief
  should preemptively address? Key ones to check: FC1 (naming divergence),
  FC4 (validation gap), FC5 (coordinated behaviors), FC29 (transaction
  boundaries).

## Rubric Used

This brief was graded against a 10-category rubric (see below). Pre-fix
score was 73 (marginal). Six targeted fixes were applied. Expected post-fix
score: 85-90 (good, ready for launch).

Categories: Build Objective Clarity (10%), Scope Specificity (15%),
Data Model Completeness (15%), Workflow Completeness (10%),
Route and UI Coverage (10%), Validation and Error Handling (10%),
Architecture and Team Split Readiness (10%), Testability (10%),
Context-Death Fit (5%), Consistency and Drift Control (5%).

## Output Format

Return:
1. **Re-score** — Grade the fixed brief against the same rubric categories.
   State the score per category (1-5) and the weighted total.
2. **Findings** — List any remaining gaps, contradictions, or risks. Use
   severity labels: P0 (blocks autopilot), P1 (likely causes agent churn),
   P2 (minor, acceptable risk).
3. **Fix prompt** — If P0 or P1 findings exist, write a Claude Code fix
   prompt that addresses each finding specifically. If the brief scores
   85+ with no P0/P1, write "READY FOR LAUNCH — no fixes needed."
