---
status: resolved
priority: p2
issue_id: "005"
tags: [code-review, simplicity, maintenance]
dependencies: ["001"]
unblocks: []
sub_priority: 1
---

# Duplicated Solo/Swarm Tail in SKILL.md

## Problem Statement

Steps 8s-11s (solo tail) and Steps 17w-20w (swarm tail) are identical:
Review, Resolve TODOs, Compound + Learnings, Done. This is copy-paste
duplication. If a step is added to one tail, the other will be missed.

**Impact:** Maintenance trap -- ~14 duplicated lines, single point of
divergence risk.

## Findings

- **Code Simplicity Reviewer (P2-5):** "If the shared tail changes, you
  need to update both places."

## Proposed Solutions

Extract a "Shared Tail" section referenced by both paths:
```markdown
## Shared Tail (both paths)
### Review ...
### Resolve TODOs ...
### Compound + Learnings ...
### Done ...
```

- Effort: Small
- Risk: None

## Acceptance Criteria

- [ ] One shared tail section exists
- [ ] Both paths reference it
- [ ] No duplicated steps
