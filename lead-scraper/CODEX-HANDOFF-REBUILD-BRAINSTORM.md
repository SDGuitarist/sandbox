# CODEX HANDOFF: Save Rebuild-In-Place Brainstorm Only

## Instruction

Do **not** implement anything from this handoff.

Your job in this session is only to:
1. Save the brainstorm document.
2. Preserve the current state.
3. Make no architecture or behavior changes.
4. Do not begin Phase 0 work.

This is a documentation-only handoff.

## Context

The lead-scraper was stabilized after repeated production DB wipe incidents and now has new safety boundaries in place. The next step is **not** implementation. The next step is to save a new brainstorm for a phased rebuild-in-place epic using the full compound engineering cycle.

## Current State To Understand Before Saving The Brainstorm

### 1. Production DB safety hardening

The current codebase now includes:
- Tests blocked from touching production `leads.db`
- Explicit production migration guard
- Destructive migration removed from ordinary startup flow
- Explicit `migrate` command required for destructive production migration
- Safer `outreach_queue` migration behavior
- App tests moved to temp DBs only

### 2. Safe workflow path

The current codebase now includes:
- Global DB lock for write-heavy operations
- Automatic backup path for write-heavy commands
- Safe workflow commands:
  - `workflow daily`
  - `workflow scrape-only`
  - `workflow outreach-prep`
  - `workflow status`

### 3. Restricted natural-language interface

The current codebase now includes:
- A new `nl` command that translates only allowlisted intents
- No arbitrary NL execution path
- Safe NL support for:
  - status requests
  - scrape requests
  - outreach prep / daily workflow requests
  - source-list mutations for:
    - Eventbrite keywords
    - Instagram hashtags
    - Facebook groups
    - Meetup groups
    - LinkedIn queries

### 4. Config override layer

The current codebase now includes:
- Mutable scrape targeting persisted to `sources.overrides.json`
- Scrape reading source config dynamically at runtime
- No Python source edits needed for target additions
- Source-list validation for supported mutation types
- Eventbrite keyword cap enforced at 25 total

### 5. Preview and audit

The current codebase now includes:
- `nl --preview` to show translation without applying or running
- `nl_audit.jsonl` for preview / cancelled / executed NL requests

## Current Test State

Latest known results:
- Targeted NL/workflow/DB-safety tests passed
- Full suite: `239 passed, 1 failed`
- Remaining failure is the same unrelated pre-existing failure:

`tests/test_unhold.py::test_unhold_enables_campaign_assignment`

Do not treat that failure as caused by the new DB-safety, workflow, NL, or config changes.

## What Must Happen In This Session

Create a new brainstorm document in `docs/brainstorms/`.

Suggested filename:

`docs/brainstorms/2026-05-09-rebuild-in-place-epic-brainstorm.md`

This brainstorm is **not** a plan and **not** implementation-ready work.

## Core Decision To Preserve

Do **not** do a big-bang rewrite.  
Do **not** keep patching forever.  
Use a **multi-phase rebuild-in-place epic**, where each phase gets its own full compound cycle:

`Brainstorm -> Plan -> Plan Review -> Work -> Review -> Compound`

## Brainstorm Title

`Rebuild Lead Scraper In Place Without Stopping Feature Delivery`

## Rebuild Principle

**Production data is a protected asset, not a default file.**

## Phase Sequence To Preserve In The Brainstorm

- Phase 0 — Architecture Freeze / Safety Doctrine
- Phase 1 — Environment and DB Boundary
- Phase 2 — Migration Rebuild
- Phase 3 — Config and Targeting Rebuild
- Phase 4 — Natural Language Planner / Executor Split
- Phase 5 — Workflow and Operations Unification

## Important Constraint

This brainstorm should explicitly optimize for **keeping feature delivery moving** while rebuilding the foundation underneath.

New feature work is allowed only when it plugs into approved safe boundaries. The brainstorm should preserve that principle.

## What Claude Should Do

1. Save the brainstorm doc.
2. Use the brainstorm content created in the prior Codex session beginning with:

   `# Brainstorm: Rebuild Lead Scraper In Place Without Stopping Feature Delivery`

3. Preserve the structure and intent of that brainstorm, including:
   - why this exists
   - current problem
   - decision
   - rebuild principle
   - phase structure
   - what must not change
   - allowed vs forbidden feature work during the epic
   - main tradeoff
   - biggest risk
   - suggested compound sequence
   - go / no-go check
   - feed-forward

## What Claude Must Not Do

- Do not implement any phase.
- Do not begin Phase 0.
- Do not refactor code.
- Do not modify DB behavior.
- Do not modify NL behavior.
- Do not modify config behavior.
- Do not modify workflow behavior.
- Do not change tests.
- Do not treat this brainstorm like a plan.

## Done Condition

This handoff is complete only when:
- The brainstorm doc is saved
- No implementation work has started
- No code behavior has changed
- The repo remains functionally unchanged except for the new brainstorm doc
