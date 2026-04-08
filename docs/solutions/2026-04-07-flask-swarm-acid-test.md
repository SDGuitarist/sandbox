---
tags: [swarm, parallel-agents, shared-spec, flask, python, acid-test, stack-transfer]
module: task-tracker
problem: Does the shared interface spec pattern produce 0 mismatches in Python/Flask, or is it JS-only?
severity: N/A (experiment, not a bug)
lesson: Shared spec produces 0 interface mismatches in Python/Flask with 4 parallel agents. Context manager usage examples are mandatory — @contextmanager alone is ambiguous. Spec size 3x larger for Python due to Template Render Context section.
---

# Flask Swarm Acid Test — Shared Spec Stack Transfer

## Problem

The shared interface spec pattern was validated in JavaScript (3 builds, 0
mismatches at 3-6 agents) but never tested with Python/Flask. Python adds
integration surfaces that JS doesn't have: import paths, blueprint registration
order, app factory pattern, context managers, Jinja2 template inheritance.

The question: is the pattern stack-agnostic, or did it only work because JS
has fewer integration surfaces?

## Context

- 3 prior JS builds established the pattern (Health Journal, Uptime Pulse, DevDash)
- 8 knowledge docs ported from sandbox-auto to sandbox (2026-04-05)
- sandbox-auto archived pending this validation
- Brainstorm: `docs/brainstorms/2026-04-07-flask-swarm-acid-test.md`
- Plan: `docs/plans/2026-04-07-feat-flask-swarm-acid-test-plan.md`

## What Was Built

A **Task Tracker** Flask app: projects with CRUD, tasks within projects, dashboard
with summaries. 4 parallel agents, vertical split by feature blueprint:

| Agent | Files | LOC |
|-------|-------|-----|
| 1: Core + Models | run.py, requirements.txt, app/__init__.py, db.py, models.py, schema.sql | ~250 |
| 2: Projects | blueprint, routes, 3 templates | ~200 |
| 3: Tasks | blueprint, routes, 2 templates | ~200 |
| 4: Dashboard + Layout | blueprint, routes, layout.html, index.html, style.css | ~328 |

Total: 20 files, ~978 LOC. Spec: 584 lines.

## Results

| Checkpoint | Result |
|-----------|--------|
| 1: App starts (no import errors) | PASS |
| 2: All 15 routes respond | PASS |
| 3: Cross-blueprint DB state | PASS |
| 4: Navigation links resolve | PASS |
| 5: Invalid routes return 404 | PASS |
| 6: Spec line count (584 lines) | PASS |
| 7: Spec-vs-code audit (0 mismatches) | PASS |

**Interface mismatch count: 0.**

The shared spec pattern is stack-agnostic. sandbox-auto can be archived.

## Spec Gap Found

All 3 blueprint agents used `db = get_db()` instead of `with get_db() as db:`.
The spec defined `get_db` as `@contextmanager` but did not include a usage
example showing `with ... as ...:` syntax.

This was a **spec ambiguity**, not agent divergence — all 3 agents made the
identical mistake, proving the spec was the single source of truth (agents
coordinated through it, not through each other's code).

**Root cause:** The function signature table said `@contextmanager` in the
return type column, but the implicit contracts section showed transaction
semantics without a code example. Agents inferred a plain function call.

**Fix applied:** Post-assembly, changed all `db = get_db()` to
`with get_db() as db:` across 3 route files. Zero-risk fix — only changes
how the connection is acquired, not what queries run.

## Key Lessons

### 1. Context manager usage examples are mandatory

When a shared spec defines a `@contextmanager` function, include an explicit
usage example:

```python
# READ operation
with get_db() as conn:
    project = get_project(conn, project_id)

# WRITE operation
with get_db(immediate=True) as conn:
    create_project(conn, name, description)
```

Don't assume agents will infer `with` syntax from `@contextmanager`. This was
added to the plan in revision 4 — future specs must include it from the start.

### 2. Python specs are 3x larger than JS specs

| Stack | Agents | Spec lines | Lines per agent |
|-------|--------|-----------|-----------------|
| JS (Health Journal) | 3 | ~60 | 20 |
| JS (DevDash) | 6 | ~190 | 32 |
| Python/Flask | 4 | 584 | 146 |

The jump is mostly Section 8 (Template Render Context) — 150+ lines defining
exact `render_template()` keyword arguments for every route/template pair. In
JS, templates are standalone HTML files with no server-side binding. In Flask,
every variable name must match between route and template.

**Open question:** Can Section 8 be auto-generated from route signatures and
model function returns? If yes, spec size drops to ~300 lines.

### 3. Prescriptive code blocks eliminate ambiguity

The plan included exact code for `app/__init__.py`, all 3 blueprint
`__init__.py` files, and `run.py`. These prescriptive blocks produced 0
mismatches in the highest-risk files (import ordering, blueprint registration).

**Rule:** For files that are integration surfaces (touched by multiple agents'
imports), include the exact code in the spec. Don't describe it — write it.

### 4. Vertical splitting works for Python blueprints

Each agent owned one Flask blueprint (feature slice). No agent's code imported
from another agent's code — all imports pointed to Agent 1's shared modules
(db.py, models.py). This made the dependency graph acyclic by construction.

## Spec Size Data

For the scaling analysis across builds:

| Build | Date | Stack | Agents | Files | Spec lines | Mismatches |
|-------|------|-------|--------|-------|-----------|------------|
| Health Journal | 2026-03-30 | JS/HTML/CSS | 3 | 3 | ~60 | 0 |
| Uptime Pulse | 2026-03-30 | JS/multi-service | 3 | 5 | ~80 | 0 |
| DevDash | 2026-03-30 | JS/Chart.js | 6 | 13 | ~190 | 0 |
| Task Tracker | 2026-04-07 | Python/Flask | 4 | 20 | 584 | 0 |

Spec growth is NOT linear with agent count — it's driven by integration surface
complexity. Python/Flask has more surfaces (imports, context managers, template
binding) than vanilla JS.

## Risk Resolution

**Flagged risk (brainstorm Feed-Forward):** "Whether Python imports between
blueprints will cause mismatches that CSS class/ID matching in JS didn't."

**Actual outcome:** Zero import mismatches. The prescriptive code blocks for
`__init__.py` files (exact import order, exact blueprint variable names)
eliminated the risk entirely. The circular import risk never materialized
because the dependency graph was acyclic by design (blueprints import from
db/models, never from each other or from `app/__init__`).

**What actually went wrong instead:** The context manager usage gap (see above).
This was NOT flagged as a risk — it was a blind spot. The brainstorm focused on
import paths and the plan focused on blueprint registration, but neither
considered that `@contextmanager` functions need usage examples.

**Lesson for risk tracking:** Blind spots cluster around "obvious" patterns
that the spec author knows but doesn't write down. The fix is prescriptive
examples for every cross-agent function call pattern, not just the signatures.

## Feed-Forward

- **Hardest decision:** Whether to fix the context manager gap by changing
  `get_db()` to a plain function or by fixing the usage in routes. Chose to
  fix the routes because `@contextmanager` is the established repo convention
  and ensures connections are always closed.

- **Rejected alternatives:** Auto-generating Section 8 from route signatures
  (would reduce spec size but adds a generation step that itself could
  introduce mismatches — validate the manual pattern first, automate later).

- **Least confident:** Whether the 584-line spec size is sustainable for
  larger Python builds (6+ agents). The JS spec grew sub-linearly
  (60 → 190 for 3 → 6 agents). If Python grows linearly from 584, a 6-agent
  build would need ~876 lines — approaching the point where the spec itself
  becomes an error source. Auto-generating Section 8 is the likely solution
  but is unvalidated.
