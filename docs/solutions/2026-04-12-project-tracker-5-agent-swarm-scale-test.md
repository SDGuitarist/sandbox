---
title: "Project Tracker -- 5-Agent Swarm Scale Test"
date: 2026-04-12
category: integration-issues
tags: [flask, swarm, scale-test, cross-module-writes, activity-log, 5-agents]
module: project-tracker
symptom: "Untested assumption: swarm pattern works at 5+ agent scale"
root_cause: "Prior builds maxed at 4 agents. Cross-module writes and 700+ line specs were untested."
---

# Project Tracker -- 5-Agent Swarm Scale Test

## Problem

All prior swarm builds used 3-4 agents. The HANDOFF.md flagged "5+ agent swarm" as a deferred scale test. Two novel risks: (1) cross-module writes where 3 agents call log_activity() owned by a 4th agent, and (2) spec readability at 700+ lines.

## What Worked

5-agent swarm produced 25 files. All 24 routes passed smoke test. Cross-module writes worked atomically. 1 minor fix needed (missing c.id in a SELECT).

### Scale Results

| Metric | Build #7 (3 agents) | Build #8 (5 agents) | Delta |
|--------|---------------------|---------------------|-------|
| Agents | 3 | 5 | +67% |
| Files | 11 | 25 | +127% |
| Spec lines | 728 | 728 | Same plan |
| Merge conflicts | 0 | 0 | Same |
| Post-assembly fixes | 2 | 1 | Better |
| Routes | 13 | 24 | +85% |

### Cross-Module Write Pattern (Validated)

The key innovation: `log_activity()` owned by dashboard-activity agent but called from task, category, and member routes. Pattern:

```python
db = get_db()
task_id = create_task(db, ...)
log_activity(db, 'task', task_id, 'created', f"Created task '{title}'")
db.commit()  # Atomic -- both succeed or both roll back
```

All 3 calling agents followed this pattern correctly because:
1. The spec included an explicit usage example with the exact call pattern
2. Each agent's assignment included a "Cross-module write note" with the pattern
3. The data ownership table clearly showed activity_log owned by models/activity.py

## Risk Resolution

**Flagged risk:** Whether cross-module writes work and whether 700+ line specs remain readable.

**What happened:** Both worked. The cross-module write pattern is clean because log_activity() takes the caller's db connection (no separate get_db call). The 728-line spec was readable -- agents followed it correctly with only 1 minor oversight (missing column in a query).

**Lesson:** Cross-module writes work when the spec clearly defines: (1) who owns the table, (2) the exact function signature with usage example, (3) who calls it and how, (4) the transaction pattern (caller commits). The spec length was not a problem at 728 lines.

## Prevention / Best Practices

1. Cross-module write functions MUST take the caller's db connection as first arg -- never call get_db() internally
2. The caller commits once after both the entity write and the cross-module write
3. Each calling agent's assignment must include the exact call pattern (not just "calls log_activity")
4. Python packages need __init__.py files -- add them to the core agent's file list
5. SELECT queries used by other agents' templates must include all columns needed for url_for links

## Stats

- **Agents:** 5 (core, tasks, categories, members, dashboard-activity)
- **Files:** 25
- **Routes:** 24
- **Spec lines:** 728
- **Post-assembly fixes:** 1 (c.id in count query)
- **Cross-module writes:** 3 agents calling log_activity() -- all correct
