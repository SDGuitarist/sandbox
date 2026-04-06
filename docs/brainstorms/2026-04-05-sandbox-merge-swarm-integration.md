---
title: "Sandbox Merge — Swarm + Solo Automation Integration"
date: 2026-04-05
status: complete
origin: "cross-project analysis of sandbox vs sandbox-auto"
---

# Sandbox Merge — Swarm + Solo Automation Integration

## Problem

Two sandbox projects test Claude Code automation from opposite directions:

- **sandbox** tests solo unattended automation: Docker container, `/autopilot` command, 13 apps built sequentially, 2,678 lines of tests, 14 solution docs, plan quality gate memory. But it builds everything sequentially with one agent — no parallelism.
- **sandbox-auto** tests parallel swarm coordination: shared interface specs, 3-6 agents building one app simultaneously, 0 mismatches at 6-agent scale. But it has zero automated tests, no Docker automation, no plan quality gate tracking, and its solution docs stay siloed.

Both repos solve the same question — "how far can compound engineering automate?" — but their learnings don't compound into each other. Sandbox rediscovered SSRF patterns that sandbox-auto had already documented. Sandbox-auto has no tests despite sandbox proving they're essential. Two repos means two HANDOFFs, two solution directories, and double the maintenance.

## Context

### What sandbox brings
- Docker container (`Dockerfile` + `run-autopilot.sh`) for fully unattended runs
- `/autopilot` command that chains the entire compound loop (11 steps)
- 18 test files (pytest, SQLite in-memory, verify-first gates)
- Plan quality gate agent memory (11 files tracking READY/NOT READY across apps)
- 14 solution docs with compounding cross-references
- `dangerouslySkipPermissions` in container for zero-human automation
- Python/Flask + SQLite stack (all apps)

### What sandbox-auto brings
- Shared interface spec pattern (validated at 3, 5, and 6 agents with 0 mismatches)
- Swarm agent assignment tables in plan docs
- Spec scaling research: ~100 lines interface + ~100 lines structural contracts
- Prescriptive lifecycle contracts (exact patterns > interface descriptions)
- Data ownership lesson: every table needs one declared writer
- GitHub Pages + Railway + Supabase deployment pipeline
- Review summary doc format (standalone files, not inline)
- Vanilla HTML/CSS/JS + Node/Express stack

### Why merge now?

The duplicate SSRF discovery is the clearest signal: both repos independently learned the same lesson because their solution docs don't cross-reference. Every cycle that runs in one repo without access to the other's learnings risks repeating this.

## What We're Building

A merged sandbox that combines solo automation + swarm coordination into one repo and one compound loop. The goal is NOT to rebuild existing apps — it's to create infrastructure that future cycles can use for either solo or swarm builds.

### Deliverables

1. **Port sandbox-auto's knowledge docs** — 4 solution docs, 2 review summaries, 2 brainstorm docs into sandbox's `docs/` (add `origin_repo: sandbox-auto` to frontmatter). Don't port plan docs or source code.
2. **Add shared interface spec as a plan convention** — every plan with 2+ independent modules gets a `## Shared Interface Spec` section. This is a documentation convention, not tooling enforcement.
3. **Update `/autopilot` to support a parallel work phase** — when the plan includes a "Swarm Agent Assignment" table, the work phase launches independent agents in parallel instead of building sequentially. One command, not two — the plan determines the build strategy.
4. **Add spec verification step** — after parallel builds complete, check that all agents' output matches the shared spec before proceeding to review
5. **Validate with a Python swarm build** — the next `/autopilot` cycle uses a multi-module Python app with a shared spec and parallel agents. This is the acid test for whether the pattern transfers from JS.

### What we're NOT building
- Deployment pipeline (sandbox is local-only by design)
- A "test agent" that auto-generates tests from specs (validate spec-in-Python first, then revisit)
- Merging git histories (sandbox-auto stays as archived reference)

## Options

### Option A: Merge repos — sandbox absorbs sandbox-auto's patterns (recommended)

Keep `sandbox` as the single repo. Port solution docs, review summaries, and the swarm pattern into sandbox's infrastructure. Archive sandbox-auto (read-only).

**Pros:**
- One HANDOFF, one solution doc directory, one set of learnings
- All future cycles compound in one place
- Docker automation + swarm + tests + quality gates in one loop
- Simplest to maintain

**Cons:**
- Two different stacks (Python vs Node/JS) coexist — acceptable for a sandbox

### Option B: Keep both repos (rejected)

Symlinks break in Docker, two HANDOFFs still diverge, learnings stay siloed. Defeats the purpose.

### Option C: Fresh "sandbox-v2" repo (rejected)

Loses 14 solution docs + 18 test files + plan quality gate memory. Anti-compounding.

## Key Design Decisions

### One command, plan-driven branching

No separate `/swarm-autopilot`. The existing `/autopilot` command gets a smarter work phase:
- If the plan has a "Swarm Agent Assignment" table → parallel build (launch independent agents, then dependent agents, then verify)
- If not → sequential build (current behavior)

The plan decides the build strategy. The command just executes it. Exact step sequence is a plan-phase concern.

### Shared spec is a plan section, not a separate file

Sandbox-auto kept the shared spec embedded in the plan doc. This worked because agents already read the plan. No reason to change it — the spec lives in the plan under a `## Shared Interface Spec` heading. The plan phase is responsible for writing it when needed (2+ independent modules).

### What to migrate

**Must port (learnings that compound):**
- 4 solution docs (swarm alignment, multi-service automation, swarm scaling, chain reaction contracts)
- 2 review summaries → new `docs/reviews/` directory
- 2 brainstorm docs (swarm scale brainstorm is the experiment design; marketing funnel brainstorm has the chain-reaction architecture)

**Don't port (implementation details tied to sandbox-auto's apps):**
- 5 plan docs (reference sandbox-auto file paths and app-specific schemas)
- App source code (different stack, different purpose)

### Unstated assumption to verify

The `/autopilot` command today is a static markdown file — a fixed sequence of slash commands. "Parse the plan and decide solo vs swarm" requires the command to read a file and branch. This may not be possible in a `.claude/commands/` markdown file. If not, the branching logic lives in the plan template instead (plan author includes the right work-phase instructions).

## Risks

1. **Shared spec may not transfer to Python/Flask.** All 4 solution docs validated the pattern with HTML/CSS/JS (class names, DOM IDs, data attributes). Python modules have different integration surfaces (imports, function signatures, DB schemas). The first swarm build in the merged repo must be a Python app to test this.
2. **`/autopilot` may not support plan-driven branching.** The command is a static markdown file today. If `.claude/commands/` can't do conditional logic, the fallback is two commands or plan-template-driven instructions. Needs investigation in the plan phase.
3. **Swarm failure recovery is undefined.** If one agent in a parallel wave fails, what happens to the others' output? Mitigation: git commit before each wave so there's a rollback point.
4. **Shared spec adds planning overhead for small apps.** Mitigation: spec only required when plan has 2+ independent modules. Single-module apps skip it.

## Open Questions

1. Can `.claude/commands/` markdown files read other files and branch? If not, the "one command" approach needs a different mechanism.

**Decided:** sandbox-auto stays alive (read-only, no new work) until the first swarm build in the merged repo succeeds. Then archive.

## Feed-Forward

- **Hardest decision:** Whether to merge into sandbox or create a fresh repo. Chose merge because the whole point of compound engineering is building on prior work. Starting fresh throws away 14 solution docs and 18 test files — that's anti-compounding.
- **Rejected alternatives:** Symlinked shared docs (breaks in Docker, diverges in practice). Fresh repo (loses institutional knowledge). Keeping both repos with manual cross-referencing (the status quo — already proven not to compound). Separate `/swarm-autopilot` command (adds maintenance burden — one command with plan-driven branching is simpler). Test agent in the swarm (premature — validate the spec pattern in Python first, then decide if auto-generated tests add value).
- **Least confident:** Two things tied. (1) Whether the shared interface spec pattern transfers from vanilla JS to Python/Flask — different integration surfaces (imports, function signatures, DB schemas vs CSS classes and DOM IDs). (2) Whether `/autopilot` can branch based on plan content — if `.claude/commands/` can't do conditional logic, the "one command" design needs a fallback. Both must be investigated before building anything.
