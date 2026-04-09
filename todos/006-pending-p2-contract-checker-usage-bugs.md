---
status: resolved
priority: p2
issue_id: "006"
tags: [code-review, architecture, verification]
dependencies: ["002"]
unblocks: []
sub_priority: 2
---

# Spec Contract Checker Blind to Usage Bugs + Does Two Jobs

## Problem Statement

Two related issues with the spec-contract-checker agent:

1. **Blind spot:** It greps for function names and signatures but cannot
   detect incorrect usage of return values (the exact bug that occurred).
2. **Two jobs:** It both checks contracts AND auto-fixes mismatches,
   violating the one-agent-one-job principle.

## Findings

- **Architecture Strategist (P2-002):** "The contract checker gives false
  confidence. The most common bug class is: correct API, incorrect usage."
- **Agent-Native Reviewer (P1):** "A verification step should not modify
  source code. Conflates detection and remediation."

## Proposed Solutions

### Option A: Add Usage Contract Checks
Extend rules to include: for scalar-returning functions, grep for
`variable = function_name(` and verify variable is not accessed with `.attr`.
- Effort: Small (add 1-2 rules to agent prompt)
- Risk: Low

### Option B: Split Into Checker + Fixer
Make spec-contract-checker read-only. Let assembly-fix handle all repairs.
- Effort: Medium (rewire skill pipeline)
- Risk: Low

## Acceptance Criteria

- [ ] Contract checker can detect scalar return type misuse
- [ ] Either: checker is read-only, OR: SKILL.md re-runs checker after fixes
