---
title: "Project Tracker -- 5-Agent Swarm Scale Test (Complete)"
date: 2026-04-12
updated: 2026-04-12
category: integration-issues
tags: [flask, swarm, scale-test, cross-module-writes, activity-log, 5-agents, plan-deepening, code-review, parallel-fixes]
module: project-tracker
symptom: "Untested assumption: swarm pattern works at 5+ agent scale"
root_cause: "Prior builds maxed at 4 agents. Cross-module writes and 700+ line specs were untested. Post-build review found 9 issues from input validation gaps and swarm consistency gaps."
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

## Session 2: Retroactive Quality Phases (2026-04-12)

Build #8 completed the swarm build but skipped plan deepening, code review, and learnings propagation. This session ran them retroactively.

### Plan Deepening Results

7 parallel research agents analyzed the plan:
- kieran-python-reviewer, security-sentinel, architecture-strategist, performance-oracle, data-integrity-guardian, pattern-recognition-specialist, solutions-reader
- **28 findings total** across all agents
- Key insight: plan deepening identified all 9 code issues BEFORE code review confirmed them. Plan deepening is NOT redundant with code review -- it catches design-level gaps that manifest as implementation bugs.

### Code Review Results (6 agents)

| Severity | Count | Examples |
|----------|-------|---------|
| P1 | 2 | Due date not validated, missing composite index |
| P2 | 5 | Category ID unhandled, description unbounded, flash gaps, assign/unassign not logged, SECRET_KEY undocumented |
| P3 | 2 | Dead COLOR_RE, dead count_tasks_for_member |

**Two root cause themes:**
1. **Input validation gaps** -- Spec defined validation rules but agents didn't implement all of them (due date, description length, category existence check)
2. **Swarm consistency gaps** -- Different agents made different UX decisions (flash messages in categories but not tasks/members; assign/unassign not logged)

**What passed cleanly (zero issues):**
- Cross-module writes (log_activity) -- all 3 agents followed exact pattern
- Scalar return types -- all create_* returns used correctly
- Route prefix convention -- no doubling
- CSRF coverage -- every POST form has csrf_token
- Data ownership boundaries -- no violations
- PRAGMA foreign_keys=ON -- set correctly

### Fixes Applied (All 9 in Parallel)

All 9 fixes applied via parallel pr-comment-resolver agents with zero conflicts:

1. **Due date validation** -- Added `datetime.strptime` check in create/edit routes
2. **Composite index** -- Added `idx_tasks_due_date_status ON tasks(due_date, status)`
3. **Category existence check** -- Added `get_category(db, category_id)` before insert
4. **Description cap** -- Added `[:2000]` + `maxlength="2000"` on textarea
5. **Flash messages** -- Added success flashes to all task and member routes
6. **Activity log assign/unassign** -- Added log_activity calls to both routes
7. **SECRET_KEY comment** -- Documented dev-only fallback
8. **Dead COLOR_RE** -- Removed from models/categories.py (only used in routes/)
9. **Dead count_tasks_for_member** -- Removed (YAGNI, templates use tasks|length)

### New Prevention Strategies

**For input validation gaps (Problem 1):**
- Use validation tables in spec, not prose paragraphs (tables are harder to skip)
- Include per-agent validation checklists in agent assignments
- Post-assembly grep to verify pattern coverage

**For swarm consistency gaps (Problem 2):**
- Add "Coordinated Behaviors" section to spec with mandatory reference table
- Every write operation gets a row in the table showing expected flash + log_activity
- Post-assembly consistency audit (flash message coverage, activity log coverage)

**For dead code from overspecification (Problem 3):**
- Pre-swarm checklist: every spec function must be called by at least one route
- If a constant is used cross-agent, define it in models/ with explicit ownership
- Post-assembly dead code scanner (grep for defined but unused functions)

## Related Docs

- [flask-swarm-acid-test](2026-04-07-flask-swarm-acid-test.md) -- context manager lesson (this build chose simpler pattern instead)
- [task-tracker-categories-swarm](2026-04-09-task-tracker-categories-swarm.md) -- scalar return types, prescriptive code blocks
- [recipe-organizer-swarm-build](2026-04-09-recipe-organizer-swarm-build.md) -- junction tables, composite PK
- [personal-finance-tracker-swarm-build](2026-04-09-personal-finance-tracker-swarm-build.md) -- plan deepening catching issues pre-build
- [notes-api-node-express-swarm-build](2026-04-12-notes-api-node-express-swarm-build.md) -- stack-agnostic validation
- [autopilot-swarm-orchestration](2026-04-09-autopilot-swarm-orchestration.md) -- assembly verification pipeline

## Stats

- **Agents:** 5 (core, tasks, categories, members, dashboard-activity)
- **Files:** 25
- **Routes:** 24
- **Spec lines:** 728
- **Post-assembly fixes:** 1 (c.id in count query)
- **Cross-module writes:** 3 agents calling log_activity() -- all correct
- **Retroactive review findings:** 9 (2 P1, 5 P2, 2 P3)
- **Parallel fix agents:** 9 (zero conflicts)
- **Plan deepening agents:** 7
- **Code review agents:** 6
