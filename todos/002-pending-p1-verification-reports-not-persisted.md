---
status: resolved
priority: p1
issue_id: "002"
tags: [code-review, architecture, audit-trail]
dependencies: ["001"]
unblocks: ["006"]
sub_priority: 2
---

# Verification Reports Not Persisted -- No Audit Trail

## Problem Statement

`docs/reports/` is empty. Step 9w clears the reports directory at the start
of each run, and the final run's reports were either cleared or never written
through the skill pipeline. Without persisted reports, there is no proof that
verification agents (contract check, smoke test, test suite) actually ran.

Additionally, the ownership gate (Step 10.5w) writes a report only on
FAILURE. Successful ownership checks leave no audit trail.

**Impact:** The entire swarm architecture depends on verification-as-safety-net,
but there is no evidence the safety net was deployed.

## Findings

- **Architecture Strategist:** "Without persisted reports, there is no audit
  trail proving that verification actually ran."
- **Agent-Native Reviewer:** "The ownership gate writes a violation report
  on failure, but on success there is no explicit STATUS: PASS output."

## Proposed Solutions

### Option A: Namespace Reports by Run ID
Use `docs/reports/<run-id>/` instead of `docs/reports/`. Each run preserves
its full verification history.
- Pros: Full audit trail, easy to compare runs
- Cons: Directory accumulation over time
- Effort: Small
- Risk: None

### Option B: Keep Latest Only
Continue clearing, but ensure reports persist after the final verification
pass. Add an ownership-gate report on success.
- Pros: Simpler, no directory growth
- Cons: Only latest run visible
- Effort: Small
- Risk: None

## Recommended Action

Option A. Run-id namespacing aligns with the branch naming convention already
in use (`swarm-<run-id>-*`).

## Technical Details

**Affected files:**
- `.claude/skills/autopilot/SKILL.md` (Steps 9w, 10.5w, 12w, 13w, 14w)

## Acceptance Criteria

- [ ] After a swarm run, `docs/reports/<run-id>/` contains contract-check,
      smoke-test, test-results, and ownership-gate reports
- [ ] Ownership gate writes STATUS: PASS on success
- [ ] Prior run reports are not deleted

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-04-09 | Found during review | Reports dir was empty post-run |
