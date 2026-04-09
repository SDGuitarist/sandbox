---
status: resolved
priority: p3
issue_id: "012"
tags: [code-review, agent-native, reliability]
dependencies: []
unblocks: []
sub_priority: 2
---

# No Timeout on Swarm Agents

## Problem Statement

Step 10w waits for all swarm agents with no maximum wait time. A hung
agent blocks the entire pipeline indefinitely.

## Findings

- **Agent-Native Reviewer (P2):** "Add a maximum wait time (e.g., 5 minutes
  per agent). If not completed, abort its worktree and mark as FAIL."

## Acceptance Criteria

- [ ] Timeout mechanism documented in SKILL.md
- [ ] Pipeline continues or aborts gracefully on timeout
