---
title: "Project Tracker -- 5+ Agent Swarm Scale Test"
date: 2026-04-12
status: complete
type: brainstorm
---

# Project Tracker

## What We're Building

A web-based project tracker with tasks, categories, team members, activity logging, and a dashboard. Built with Flask + SQLite + Jinja2, the sandbox standard stack. The primary goal is to test the swarm build pattern at 5+ agent scale -- all prior builds used 3 agents (except task-tracker at 4).

## Why This Approach

- **Flask + Jinja2** -- proven stack with 6 successful swarm builds in this repo
- **5 natural domains** -- tasks, categories, members, activity log, dashboard each map cleanly to an agent
- **Cross-module reads** -- dashboard reads from all tables, activity log writes from multiple routes. This stresses the data ownership pattern beyond what 3-agent builds tested.
- **Template Render Context** -- 5 blueprints with templates will push spec size past 600 lines, testing spec readability at scale

## Key Decisions

1. **5 agents, not 6** -- core (app factory, schema, models) + tasks + categories + members + dashboard-activity. Combining dashboard and activity log avoids a 6th agent that only reads. The dashboard agent owns templates + routes for both dashboard and activity display, plus the activity_log model (write-only).
2. **Activity log is automatic** -- routes that create/update/delete entities insert a row into `activity_log`. The activity model function is called directly from task/category/member routes, but the activity_log table is OWNED by the dashboard-activity agent's model file. Other routes call the function but don't write SQL directly. This is a controlled cross-module write -- the first in any sandbox swarm build.
3. **Single-user, no auth** -- consistent with all sandbox apps
4. **Categories are flat** -- no hierarchy, no nesting. A task belongs to one category (FK).
5. **Team members are assigned to tasks** -- many-to-many via junction table (composite PK). A task can have multiple assignees.
6. **Dashboard shows aggregates** -- task counts by status, tasks by category, recent activity, overdue tasks. All read-only queries.
7. **Status is an enum** -- todo/in_progress/done, stored as TEXT with CHECK constraint
8. **Due dates are optional** -- TEXT field, ISO 8601 format, nullable

## Scope

### In Scope
- CRUD tasks (title, description, status, due_date, category_id)
- CRUD categories (name, color)
- CRUD team members (name, role)
- Task-member assignments (add/remove assignees)
- Activity log (auto-recorded: entity_type, entity_id, action, description, timestamp)
- Dashboard (task counts by status, by category, recent activity, overdue tasks)
- CSRF protection on all POST forms
- SECRET_KEY from environment variable
- Input validation on all forms

### Out of Scope
- Authentication / authorization
- File attachments
- Comments on tasks
- Notifications / email
- Calendar or Gantt view
- Search / filtering beyond dashboard
- Task priorities / ordering
- Subtasks

## Data Model Sketch

- **tasks**: id, title, description, status (todo/in_progress/done), due_date, category_id (FK), created_at, updated_at
- **categories**: id, name (UNIQUE), color (hex), created_at
- **members**: id, name, role, created_at
- **task_members**: task_id, member_id (composite PK, FKs with CASCADE)
- **activity_log**: id, entity_type, entity_id, action (created/updated/deleted), description, created_at

## Agent Split Sketch (5 agents)

| Agent | Files | Writes To | Reads From |
|-------|-------|-----------|------------|
| core | app.py, schema.sql, requirements.txt | schema (DDL only) | — |
| tasks | models/tasks.py, routes/tasks.py, templates/tasks/* | tasks, task_members | categories, members (read), activity_log (via function call) |
| categories | models/categories.py, routes/categories.py, templates/categories/* | categories | tasks (read count), activity_log (via function call) |
| members | models/members.py, routes/members.py, templates/members/* | members | task_members (read), activity_log (via function call) |
| dashboard-activity | models/activity.py, routes/dashboard.py, templates/dashboard/*, templates/activity/* | activity_log | tasks, categories, members, task_members (all read-only) |

## Scale Test Hypotheses

1. **Spec size:** Will the spec remain readable at 600+ lines? Prior: 584 lines at 4 agents.
2. **Cross-module writes:** Activity log requires task/category/member routes to call `log_activity()` from the dashboard-activity agent's model. Does data ownership hold when multiple agents call a write function they don't own?
3. **Template complexity:** 5 sets of templates with shared base.html. Will CSS class conflicts emerge?
4. **Assembly merge:** More agents = more merge opportunities. Will merge conflicts increase?

## Prior Art (from solution docs)

- Scalar returns need usage examples (task-tracker-categories)
- Context manager usage mandatory in spec (flask-swarm-acid-test)
- Route prefix doubling common bug -- spec must show relative paths (personal-finance-tracker)
- Composite PK on junction tables (recipe-organizer, bookmark-manager)
- CSRF + SECRET_KEY from env required (autopilot-swarm-orchestration)
- Template Render Context is 20% of Flask spec (flask-swarm-acid-test)
- Deepening catches YAGNI before code (bookmark-manager -- saved ~165 LOC)

## Open Questions

None -- all key decisions resolved. The scale test hypotheses are the open research questions, not blockers.

## Feed-Forward

- **Hardest decision:** Whether to have 5 or 6 agents. Chose 5 by combining dashboard + activity log into one agent. A 6th agent that only reads (dashboard) would have minimal files and create an unbalanced split. The combined agent owns the activity_log model (writes) and dashboard routes/templates (reads).
- **Rejected alternatives:** (1) 4 agents with tasks+categories combined -- too few to test scale. (2) 6 agents with separate dashboard and activity agents -- unbalanced, dashboard would have 2-3 files vs 5-6 for others. (3) Activity log as middleware -- too magical, harder to spec for agents.
- **Least confident:** Whether the cross-module write pattern (tasks/categories/members routes calling `log_activity()` from dashboard-activity's model) will work cleanly. This is the first time multiple agents need to call a write function owned by another agent. The spec must define `log_activity()` with exact signature and usage example, and the data ownership table must clearly show activity_log is written by models/activity.py even though it's called from other routes.

## Refinement Findings

**Gaps found:** 4 (all to address in plan phase)

1. **Endpoint Registry** -- Spec must include exact `url_for()` names for all 5 blueprints. Dashboard templates reference routes across all blueprints. Without registry, BuildError at runtime. (from: bookmark-manager-swarm-build)

2. **Transaction boundary for log_activity()** -- Must specify whether log_activity() runs inside or outside the entity write transaction. Same transaction = atomic (both succeed or both roll back). Separate = risk of orphaned entity with no log. (from: event-sourced-audit-log)

3. **TOCTOU in cross-module writes** -- Routes that read entity → write entity → log activity in separate get_db() blocks expose a gap. Spec must prescribe single transaction or accept the risk. (from: recipe-organizer-swarm-build)

4. **log_activity() return type** -- Must specify: returns None (fire-and-forget) or int (new log ID). Without this, 3 different agents will handle the return value inconsistently. (from: chain-reaction-inter-service-contracts)
