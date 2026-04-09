---
status: resolved
priority: p1
issue_id: "004"
tags: [code-review, learnings, spec-template, feed-forward-risk]
dependencies: []
unblocks: ["003"]
sub_priority: 4
---

# Scalar Return Usage Examples Missing from Spec Template

## Problem Statement

The one real post-assembly bug (create_project returns int, not Row) was
caused by spec ambiguity. The spec said the function returns int, but had
no usage example showing the correct variable naming pattern. Agent 2
wrote `project = create_project(...)` and accessed `project.id`.

This bug class will recur in every Flask swarm build unless the shared-spec
template is updated. The learnings researcher confirmed this is documented
in the task-tracker solution doc but not yet propagated to the template.

**Impact:** Recurring swarm build failures on scalar-returning functions.

## Findings

- **Learnings Researcher (P1):** "The spec should include a usage example
  for every model function that returns a scalar (not a Row). Template
  location not yet created."
- **Architecture Strategist (P2-002):** "The verification layer is blind
  to the most common bug class in swarm builds: correct API, incorrect usage."
- **Feed-Forward risk confirmed:** Spec ambiguity on scalar returns caused
  1 post-assembly fix.

## Proposed Solutions

### Option A: Create Flask Shared-Spec Template
Create `docs/templates/shared-spec-flask.md` with:
1. Scalar-return usage examples section
2. Context manager usage examples (`with ... as ...:`)
3. Template Render Context section (pre-filled stub)
4. CSRF setup section
5. Data ownership table
- Pros: Prevents recurrence across all future Flask swarms
- Cons: Template maintenance overhead
- Effort: Medium
- Risk: None

## Technical Details

**Example spec addition:**
```python
# Usage: create_project returns an int, not a Row
project_id = create_project(conn, name, color)
redirect(url_for('projects.show_project', project_id=project_id))
```

**Affected files:**
- `docs/templates/shared-spec-flask.md` (create new)

## Acceptance Criteria

- [ ] Template exists with scalar-return usage examples section
- [ ] Template includes context manager examples
- [ ] Next Flask swarm build uses the template
- [ ] No scalar-return bugs in the next swarm build

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-04-09 | Bug found in Phase 5 integration | create_project int vs Row |
| 2026-04-09 | Learnings researcher confirmed pattern | 7 solution docs reference this |
