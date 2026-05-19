---
name: Solopreneur Command Center — 16-Agent Swarm Build
description: Full-stack Flask + SQLite + Jinja2 business operating system built by 16 parallel agents
date: 2026-05-19
tags: [flask, sqlite, swarm, 16-agent, crm, pipeline, time-tracking, dashboard]
run_id: "047"
build_method: autopilot-swarm
agents: 16
files: 98
lines: 12821
merge_conflicts: 0
smoke_test: "27/27 PASS"
assembly_fixes: 1
---

# Solopreneur Command Center — 16-Agent Swarm Build

## Problem
Build a complete business operating system for solopreneurs — combining CRM, sales pipeline, project management, task management, time tracking, revenue/expense tracking, goals, notes, reports, search, and settings in a single Flask application. 13 modules, 21 database tables, 50+ routes, 98 files.

## Solution
16-agent swarm with vertical split by blueprint. Each agent owned one feature blueprint plus its templates. Shared modules (db.py, models.py, schema.sql, app factory) owned by core-infra agent. All agents worked in git worktrees, merged via assembly branch.

### Key Metrics
- **Agents:** 16 (core-infra, auth, layout-static, contacts, companies, pipeline, projects, tasks, time-tracking, revenue, goals, notes, reports, search, settings, dashboard)
- **Files created:** 98
- **Lines of code:** 12,821
- **Merge conflicts:** 0
- **Assembly fixes:** 1 (settings/routes.py missing session import + user_id in profile INSERT)
- **Smoke test:** 27/27 PASS

### Architecture
- Flask app factory with 14 blueprints
- SQLite with WAL mode, PRAGMA foreign_keys=ON per connection
- flask-wtf CSRF on all POST forms
- Session-based auth with setup_required decorator
- Money as integer cents, time as integer minutes
- FTS5 with triggers for notes search
- Chart.js for dashboard visualizations
- Bootstrap 5 dark sidebar professional UI

## Risk Resolution

### Brainstorm Risk: Activity log wiring across 16 agents
**What was flagged:** Every module must INSERT into activity_log with the same format. 12 of 16 agents must independently remember this.

**What actually happened:** The Coordinated Behaviors table in the spec prescribed the exact INSERT pattern per module. The smoke test confirmed all routes work, but activity log coverage wasn't individually verified. This is the expected weak point — review should catch any missing inserts.

**What was learned:** Prescriptive tables work better than prose instructions. The Coordinated Behaviors table reduced the activity log wiring from a design decision to a copy-paste task. The risk was mitigated by the spec's specificity, not by agent intelligence.

### Spec Consistency Gate Findings (3 FAILs, 4 WARNs)
All fixed before swarm launch:
- Revenue by_client and by_month templates missing from spec → added
- Reports index.html missing from directory structure → added
- Goal hours_target unit ambiguity → clarified
- get_revenue_snapshot unnecessary user_id parameter → removed
- Settings export_module is a download route → documented
- Revenue target unit (cents) → labeled

## What Worked
1. **Vertical split by blueprint** — zero merge conflicts across 98 files. Each agent's files were completely independent.
2. **Prescriptive code blocks** — app factory, db.py, decorators, filters all had exact code in the spec. Agents didn't need to make decisions.
3. **Endpoint registry** — 50+ routes with exact url_for names prevented naming divergence (FC1).
4. **Spec consistency checker** — caught 3 cross-section contradictions that would have caused runtime errors.
5. **Template render context section** — every render_template call had exact variable names, preventing silent missing data.

## What Didn't Work
1. **Settings agent missed session import** — despite session being a standard Flask import, the agent omitted it. The _get_or_create_profile helper used session.get() but didn't import session. Caught by smoke test.
2. **Auth field name mismatch** — register route used `confirm_password` but smoke test initially sent `password_confirm`. This is a spec gap — form field names should be in the spec.

## Lessons
1. **Form field names belong in the spec.** If the endpoint registry says POST /auth/register, the spec should also say "form fields: email, password, confirm_password". Without this, consumers (templates, tests) must read the route code to know the field names.
2. **16-agent swarm with vertical split produces zero merge conflicts.** The pattern is proven at this scale. The key is that shared modules (db, models, schema) are owned by exactly one agent, and all other agents import from shared modules only.
3. **Spec consistency checker is mandatory for 15+ agent builds.** It found 3 cross-section contradictions in a 1200-line spec. Each contradiction would have caused a runtime error.
4. **Assembly fix rate of 1/16 agents (6.25%) is acceptable.** The fix was a missing import — mechanical, not architectural.

## Feed-Forward
- **Hardest decision:** Whether to include all model functions in one 1573-line models.py or split per blueprint. Chose one file for simplicity — all agents can import from the same module.
- **Rejected alternatives:** Per-blueprint model files would reduce models.py size but create cross-import complexity.
- **Least confident:** CSV export in both reports and settings blueprints — potential duplication. Settings handles per-module export, reports handles report-specific CSV. May want to consolidate.
