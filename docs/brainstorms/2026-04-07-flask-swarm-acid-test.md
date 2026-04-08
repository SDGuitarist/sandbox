---
title: Flask Swarm Acid Test
date: 2026-04-07
type: brainstorm
status: complete
tags: [swarm, flask, python, shared-spec, parallel-agents, acid-test]
origin: sandbox-auto archive decision (2026-04-05 merge cycle)
---

# Flask Swarm Acid Test

## Context

The sandbox-auto repo was knowledge-merged into sandbox on April 5, 2026.
sandbox-auto remains read-only, pending archival. The archival condition:
**prove the shared interface spec pattern works for Python/Flask, not just
JS/static.** This brainstorm defines that validation.

Three prior JS swarm builds established the pattern:
- Health Journal (3 agents, 3 files): 7 mismatches without spec, 0 with spec
- Uptime Pulse (3 services, 5 files): 0 mismatches, discovered SSRF risk
- DevDash (6 agents, 13 files): 0 mismatches, spec grew to ~190 lines

## What We're Building

A **Task Tracker** Flask app built by 4 parallel agents using only a shared
interface spec as their coordination mechanism.

Features:
- Projects with CRUD operations
- Tasks within projects (create, assign, update status, comment via Tasks blueprint)
- Dashboard with project summaries and task counts
- Shared SQLite database with foreign key relationships
- Jinja2 templates with shared layout/inheritance

## Why This Approach

The Task Tracker exercises every Python-specific integration surface that
JS builds didn't test:
- **Python imports** between blueprints and shared models
- **Blueprint registration** in the app factory
- **SQLite model definitions** shared across modules
- **Jinja2 template inheritance** (layout -> page templates)
- **Flask config** (current_app.config, app context)

Vertical slicing (by feature blueprint) mirrors the DevDash pattern while
keeping each agent's scope self-contained.

## Key Decisions

| Decision | Chosen | Rejected | Why |
|----------|--------|----------|-----|
| App type | Task Tracker | Inventory, Events, Incidents | Natural 4-agent split, exercises all Python surfaces |
| Agent count | 4 | 3 (too simple), 6 (adds scale risk on top of stack risk) | Sweet spot: proves parallelism without conflating variables |
| Agent split | Vertical (feature blueprints) | Horizontal (by layer) | Fewer integration surfaces, matches DevDash pattern |
| Parallelism | All 4 parallel, spec-only deps | Agent 1 first then 3 | True acid test -- no agent depends on another's code |
| Pass/fail criteria | Match JS DevDash criteria | Stricter Python-specific checks | Keeps comparison clean; Python import issues will surface as mismatches anyway |

## Agent Assignment

| # | Agent | Output Files | Depends On |
|---|-------|-------------|------------|
| 1 | Core + Models | `app/__init__.py`, `app/models.py`, `app/db.py`, `run.py` | Spec only |
| 2 | Projects | `app/blueprints/projects/__init__.py`, `app/blueprints/projects/routes.py`, `app/templates/projects/*.html` | Spec only |
| 3 | Tasks | `app/blueprints/tasks/__init__.py`, `app/blueprints/tasks/routes.py`, `app/templates/tasks/*.html` | Spec only |
| 4 | Dashboard + Layout | `app/blueprints/dashboard/__init__.py`, `app/blueprints/dashboard/routes.py`, `app/templates/layout.html`, `app/templates/dashboard/*.html`, `app/static/style.css` | Spec only |

**Collision points (spec must resolve these):**
- Agent 1's `app/__init__.py` must import and register blueprints created by
  Agents 2-4. Spec MUST define exact blueprint variable names, import paths,
  and url_prefixes.
- Agent 4's `layout.html` defines `{% block %}` tags that Agents 2-3 extend.
  Spec MUST list exact block names (e.g., `title`, `content`). Mismatched
  block names fail silently (blank sections, no error).

All agents depend ONLY on the shared spec. No agent depends on another agent's
output. This enables true parallel execution.

## Acceptance Criteria (Pass/Fail)

Adapted from DevDash's 6 checkpoints:

1. **Mismatch count = 0** -- all function signatures, model fields, template
   blocks, blueprint names, and route paths match across all files.
   Verification: `flask run` + hit all routes catches import/route mismatches;
   manual spec-vs-code audit catches silent mismatches (wrong block names,
   unused function signatures)
2. **All routes respond** -- `flask run`, hit every endpoint, no 500 errors
3. **Shared DB state works** -- create a project via Projects blueprint, see it
   in Dashboard blueprint (proves cross-blueprint DB access works)
4. **Navigation works** -- links between views resolve correctly, no broken hrefs
5. **Invalid routes return 404** -- unknown paths handled gracefully
6. **Spec line count documented** -- record actual spec size for the 4-agent
   Python build (compare to JS: ~60 lines at 3 agents, ~190 at 6)

**Overall pass:** All 6 checkpoints green = pattern is stack-agnostic.
sandbox-auto can be archived.

**Overall fail:** Any mismatch > 0 = investigate root cause. Is it a spec
gap (fixable) or a fundamental Python limitation (pattern needs adaptation)?

## Shared Spec Structure (Python Convention)

The spec must include these 7 subsections (6 from the merge plan + Jinja blocks):

1. **Public Function Signatures** -- Module, Function, Parameters, Returns, Called by
2. **Database Schema** -- CREATE TABLE with constraints, FK semantics, status enums
3. **Shared Constants** -- Constant, Value, Defined in, Used by, Purpose
4. **Flask Routes** -- Method, Path, Auth, Body, Returns
5. **Data Ownership** -- Table, Writer (single owner), Readers
6. **Jinja Template Blocks** -- block names in layout.html, which templates extend it
7. **Implicit Contracts** -- timestamp format, transaction semantics, JSON conventions

## Open Questions

None -- all questions resolved during brainstorm dialogue.

## Feed-Forward

- **Hardest decision:** Whether to run all 4 agents in parallel or let the
  Core agent run first. Chose full parallelism because the whole point is
  testing spec-only coordination. If we let Agent 1 run first, we're testing
  "can agents read code" not "can agents coordinate via spec."

- **Rejected alternatives:** Horizontal layer split (models/routes/templates/
  static as separate agents) would have created more integration surfaces but
  conflated "does the pattern work in Python" with "does horizontal splitting
  work" -- two untested variables at once. 6-agent count rejected for the same
  reason: don't add scale risk on top of stack-transfer risk.

- **Least confident:** Whether Python imports between blueprints will cause
  mismatches that CSS class/ID matching in JS didn't. In JS, agents just
  need to agree on string names. In Python, agents need to agree on import
  paths, function signatures, AND the app factory's blueprint registration
  order. The spec template has subsections for all of these, but it's
  untested. This is the #1 thing to watch during the build.
