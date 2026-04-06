---
title: "Sandbox Merge — Swarm + Solo Automation Integration"
date: 2026-04-05
status: ready
origin: docs/brainstorms/2026-04-05-sandbox-merge-swarm-integration.md
feed_forward:
  risk: "Whether /workflows:work can detect a Swarm Agent Assignment table in the plan and switch to parallel builds — unverified, but a next-cycle concern, not a blocker for this docs merge"
  verify_first: false
---

# Sandbox Merge — Swarm + Solo Automation Integration Plan

## Plan Quality Gate

### 1. What exactly is changing?

Four things:

1. **Port 8 knowledge docs** from sandbox-auto into sandbox's `docs/` directories
2. **Add a `docs/reviews/` directory** to sandbox (doesn't exist yet)
3. **Define the Python Shared Interface Spec template** as a convention for multi-module plans
4. **Update HANDOFF.md** to reflect the merge, verified assumptions, and next-cycle validation plan

### 2. What must NOT change?

- The existing 13 apps and their source code
- The existing 14 solution docs, 14 brainstorm docs, 14 plan docs
- The Dockerfile, run-autopilot.sh, or Docker automation infrastructure
- The `.claude/commands/autopilot.md` file (investigation confirmed it can't branch)
- The 18 test files
- The plan quality gate agent memory (11 files in `.claude/agent-memory/`)

### 3. How will we know it worked?

- sandbox's `docs/solutions/` contains 18 solution docs (14 original + 4 ported)
- sandbox's `docs/reviews/` contains 2 review summaries from sandbox-auto
- sandbox's `docs/brainstorms/` contains 16 brainstorm docs (14 original + 2 ported)
- All ported docs have `origin_repo: sandbox-auto` in their YAML frontmatter
- HANDOFF.md is updated to reflect the merge and point to the next cycle (Python swarm validation)

### 4. What is the most likely way this plan is wrong?

Two risks:

1. **Dead references.** The ported solution docs may reference sandbox-auto file paths (e.g., `pulse-api/server.js:45`) that don't exist in sandbox. Without enough surrounding context, these become dead references. Mitigation: during porting, add an `origin_context:` note to any doc that references sandbox-auto-specific paths.

2. **Implied capability.** The ported docs describe swarm workflows (shared specs, parallel agent builds, spec verification) that sandbox does not yet support. A reader may assume sandbox can do swarm builds today. Mitigation: HANDOFF.md explicitly lists swarm routing and spec verification as unvalidated next-cycle items, not current capabilities.

---

## Phase 1: Port Knowledge Docs (copy + annotate)

### What to port

**4 solution docs** → `docs/solutions/`

| Source file | Lesson |
|---|---|
| `2026-03-30-swarm-build-alignment.md` | Shared spec prevents mismatches (origin story) |
| `2026-03-30-uptime-pulse-multi-service-automation.md` | Spec scales to multi-service; SSRF default risk |
| `2026-03-30-swarm-scale-shared-spec.md` | Spec scales to 6 agents; prescriptive > descriptive |
| `2026-03-30-chain-reaction-inter-service-contracts.md` | Data ownership is #1 gap |

**2 review summaries** → `docs/reviews/` (new directory)

| Source file | Content |
|---|---|
| `2026-03-30-health-journal-review-summary.md` | 10 findings, XSS fixes |
| `2026-03-30-uptime-pulse-review-summary.md` | 23 findings, SSRF critical |

**2 brainstorm docs** → `docs/brainstorms/`

| Source file | Content |
|---|---|
| `2026-03-30-swarm-scale-brainstorm.md` | 6-agent experiment design |
| `2026-03-30-marketing-funnel-brainstorm.md` | Chain-reaction architecture |

### Annotation rules

For each ported doc, add to YAML frontmatter:
```yaml
origin_repo: sandbox-auto
origin_context: "Built with [stack]. See sandbox-auto repo for source code."
```

If the doc body references sandbox-auto file paths, add a one-line note:
```
> **Note:** File paths reference the sandbox-auto repo (archived). Pattern applies to any stack.
```

### What NOT to port

- 5 plan docs (reference sandbox-auto file paths and app-specific schemas too heavily)
- App source code (different stack, different purpose)
- HANDOFF.md or compound-engineering.local.md (sandbox has its own)

## Phase 2: Define Python Shared Interface Spec Convention

This is a documentation convention, not code. Add a template section to this plan doc that future plans can copy.

### Python Shared Interface Spec Template

When a plan has 2+ independent modules that will be built by separate agents (or in separate work phases), include a `## Shared Interface Spec` section with these subsections:

```markdown
## Shared Interface Spec

### Public Function Signatures
| Module | Function | Parameters | Returns | Called by |
|--------|----------|------------|---------|----------|
| services.py | create_service | (conn, name: str, url: str) | dict | routes.py |

### Database Schema
- Full CREATE TABLE statements with constraints
- FK semantics explicitly stated (CASCADE vs SET NULL) with reasoning
- Status enum values listed: `status IN ('pending', 'running', 'done', 'failed')`

### Shared Constants
| Constant | Value | Defined in | Used by | Purpose |
|----------|-------|-----------|---------|---------|
| _KEY_PREFIX_LEN | 8 | keys.py | keys.py, routes.py | Display prefix length |

### Flask Routes
| Method | Path | Auth | Body | Returns |
|--------|------|------|------|---------|
| POST | /services | Bearer token | {name, url} | 201 + service dict |

### Data Ownership
| Table | Writer (single owner) | Readers |
|-------|----------------------|---------|
| events | events.py only | routes.py, dashboard |

### Implicit Contracts
- Timestamp format: `YYYY-MM-DD HH:MM:SS` (SQLite datetime() compatible)
- All multi-step operations in same `BEGIN IMMEDIATE` transaction
- Compute time-dependent values INSIDE the transaction lock
- JSON payloads use shallow merge semantics
```

### When to use this template

- Plan has 2+ modules that could be built independently → MUST include spec
- Plan has 1 module → skip spec
- Solo build but multiple files with shared state (e.g., routes.py + db.py + worker.py) → SHOULD include spec

### When NOT to use

- Single-file apps (CLI tools, scripts)
- Refactors that don't change integration surfaces

## Phase 3: Update HANDOFF.md

Update sandbox's HANDOFF.md to reflect:
- Merge is complete (docs ported)
- Python Shared Interface Spec convention is defined
- Next cycle: validate with a Python swarm build
- sandbox-auto status: read-only, archive after validation

```markdown
# HANDOFF — Sandbox Merge Complete

**Date:** 2026-04-05
**Branch:** main
**Phase:** Plan complete — ready for work phase (doc porting)

## Current State

Brainstorm and plan complete for merging sandbox-auto's swarm coordination
patterns into sandbox. No code changes — this is a knowledge consolidation.

## Key Artifacts

| Phase | Location |
|-------|----------|
| Brainstorm | docs/brainstorms/2026-04-05-sandbox-merge-swarm-integration.md |
| Plan | docs/plans/2026-04-05-sandbox-merge-swarm-integration-plan.md |

## What Was Ported

- 4 solution docs (swarm alignment, multi-service automation, swarm scaling, chain reaction contracts)
- 2 review summaries (health journal, uptime pulse)
- 2 brainstorm docs (swarm scale experiment, marketing funnel architecture)
- All ported docs have `origin_repo: sandbox-auto` in frontmatter

## Assumptions Verified

1. `/autopilot` command CANNOT branch — it's a static markdown file. Branching
   happens in /workflows:work when it reads the plan.
2. Shared interface spec DOES transfer to Python/Flask — 8 integration surfaces
   identified (function signatures, DB schema, status enums, shared constants,
   import paths, Flask routes, config/env vars, implicit contracts).

## Next Cycle

Validate the merge with a Python swarm build: multi-module Flask app, shared
interface spec in the plan, parallel agents in the work phase. This is the acid
test before archiving sandbox-auto.

## Deferred Items

- Test agent that auto-generates tests from shared spec (validate pattern first)
- Archive sandbox-auto (after Python swarm validation succeeds)
- Investigate whether /workflows:work can detect Swarm Agent Assignment tables
  and launch parallel agents automatically

## Three Questions

1. Hardest decision: [to be filled after work phase]
2. What was rejected: [to be filled after work phase]
3. Least confident about: [to be filled after work phase]
```

## Execution Order

| Step | Phase | Files touched | Depends on |
|------|-------|--------------|------------|
| 1 | Phase 1 | Create `docs/reviews/` directory | Nothing |
| 2 | Phase 1 | Copy + annotate 4 solution docs | Nothing |
| 3 | Phase 1 | Copy + annotate 2 review summaries | Step 1 |
| 4 | Phase 1 | Copy + annotate 2 brainstorm docs | Nothing |
| 5 | Phase 3 | Update HANDOFF.md | Steps 2-4 |

Steps 1-4 are independent and can run in parallel. Step 5 depends on all ports being complete.

**Total new files:** 8 (ported docs)
**Total new directories:** 1 (`docs/reviews/`)
**Total modified files:** 1 (HANDOFF.md)
**Total deleted files:** 0

## Feed-Forward

- **Hardest decision:** Whether to change `/autopilot` or leave it static. Investigation showed it CAN'T branch (static markdown, `disable-model-invocation: true`). This means the swarm detection must happen downstream in `/workflows:work`. This is actually cleaner — the command stays simple, the intelligence is in the work skill that reads the plan.
- **Rejected alternatives:** Rewriting `/autopilot` as a dynamic skill (breaks the `disable-model-invocation` safety property). Creating a separate `/swarm-autopilot` command (maintenance burden of two commands). Porting plan docs from sandbox-auto (too many dead file path references).
- **Least confident:** Whether `/workflows:work` can detect a "Swarm Agent Assignment" table in the plan and switch to parallel builds. This is compound-engineering plugin behavior, not something we control. The next cycle (Python swarm validation) will test this. If `/workflows:work` doesn't support it, the fallback is manual: user reads the plan, launches parallel agents via the Agent tool, then continues the compound loop.
