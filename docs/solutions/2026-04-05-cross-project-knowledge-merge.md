---
tags: [knowledge-merge, documentation, cross-project, compound-engineering, swarm, shared-spec]
module: sandbox
problem: Two sandbox repos testing the same hypothesis had siloed learnings that didn't compound into each other
severity: N/A (process improvement, not a bug)
lesson: When two projects share a goal, merge their knowledge docs early — duplicate discoveries (like SSRF) are the signal that silos are costing you
origin_plan: docs/plans/2026-04-05-sandbox-merge-swarm-integration-plan.md
origin_brainstorm: docs/brainstorms/2026-04-05-sandbox-merge-swarm-integration.md
---

# Cross-Project Knowledge Merge — Sandbox + Sandbox-Auto

## Problem

Two sandbox projects tested Claude Code automation from opposite directions:
- **sandbox:** solo unattended automation (Docker + `/autopilot`, 13 apps, 18 test files, 14 solution docs)
- **sandbox-auto:** parallel swarm coordination (shared specs, 3-6 agents, 0 mismatches at 6-agent scale, 4 solution docs)

Both independently discovered the same SSRF defense pattern. Both documented it in their own solution docs. Neither repo could reference the other's learnings. Every new cycle in one repo risked rediscovering what the other already knew.

## Solution

Ported 8 knowledge docs from sandbox-auto into sandbox:
- 4 solution docs (swarm alignment, multi-service automation, swarm scaling, chain reaction contracts)
- 2 review summaries (health journal, uptime pulse)
- 2 brainstorm docs (swarm scale experiment, marketing funnel architecture)

Each ported doc received two annotations:
1. **YAML frontmatter:** `origin_repo: sandbox-auto` + `origin_context: "Built with [stack]. See sandbox-auto repo for source code."`
2. **Body-level note** (solution docs only): "File paths reference the sandbox-auto repo (archived). Pattern applies to any stack."

Did NOT port: 5 plan docs (60%+ dead file path references), app source code (different stack), HANDOFF/config files (sandbox has its own).

## Patterns

1. **Duplicate discoveries are the merge signal.** Both repos independently found SSRF as the default risk for URL-fetching services. When two projects learn the same lesson independently, their knowledge docs should be consolidated — the duplication cost is already being paid.

2. **Port patterns, not implementations.** Solution docs and brainstorms transfer across stacks because they describe patterns. Plan docs don't transfer because they reference specific file paths, schemas, and implementation details. The rule: if >50% of a doc's content is stack-specific, leave it in the source repo.

3. **Annotate origin, don't rewrite.** Adding `origin_repo` + `origin_context` to frontmatter is sufficient. Rewriting ported docs to match the target repo's stack would destroy the original context without adding value. The pattern is stack-agnostic; the examples are historical evidence.

4. **Separate cycle artifacts from ported docs.** The brainstorm and plan that drove the merge are NOT ported docs — they were written in sandbox for sandbox. HANDOFF must distinguish these clearly, or doc counts become confusing.

5. **Static commands can't branch.** `/autopilot` is a static markdown file with `disable-model-invocation: true`. It can't read other files or conditionally switch behavior. Any plan-driven branching (solo vs swarm) must happen downstream in the work skill, not in the command. This is actually cleaner — the command stays simple, the intelligence is in the phase that reads the plan.

6. **Shared interface specs transfer to Python.** Investigation found 8 integration surfaces in Python/Flask (function signatures, DB schema, status enums, shared constants, import paths, Flask routes, config/env vars, implicit contracts) that are more structured than JS equivalents (CSS classes, DOM IDs). A Python shared spec is more precise and easier to verify than a JS one.

## Key Decisions

| Decision | Chosen | Rejected | Why |
|----------|--------|----------|-----|
| Which repo absorbs? | sandbox (has Docker, tests, quality gates) | sandbox-auto (has deployment) or fresh repo | Compounding requires building on the largest knowledge base |
| What to port? | Solution docs + reviews + brainstorms | Also plan docs and source code | Plans have too many dead references; code is wrong stack |
| One command or two? | One `/autopilot`, branching in work phase | Separate `/swarm-autopilot` | Less maintenance; command stays simple |
| Annotation style? | Frontmatter fields + body note | Rewrite docs for Python context | Preserves original evidence; patterns are stack-agnostic |

## Risk Resolution

| Flagged Risk | What Actually Happened | Lesson |
|---|---|---|
| Dead references — ported docs may cite sandbox-auto file paths that don't exist in sandbox | All 4 solution docs cite sandbox-auto paths. Body-level notes added to all 4. Review confirmed coverage. | Always add a path-origin note when porting docs with code references. Check is fast (grep for file extensions) and catches 100% of cases. |
| Implied capability — ported docs describe swarm workflows sandbox doesn't support yet | Mitigated by HANDOFF's "Not Yet Validated" section listing swarm detection as next-cycle. Review confirmed accuracy. | When porting capability-describing docs into a repo that doesn't have those capabilities yet, add a "not yet validated" section to HANDOFF. Readers who skip HANDOFF may still be misled — acceptable for a sandbox, not for production docs. |
| `/autopilot` can't branch — plan-driven solo vs swarm detection assumed command could read files | Investigation before planning confirmed it can't. Plan scoped correctly as a result. | Verify infrastructure assumptions BEFORE planning, not during work. The 5-minute check of `autopilot.md` saved a plan rewrite. |

## Feed-Forward

- **Hardest decision:** Whether to port plan docs or leave them behind. Plans have the richest context (shared specs, agent assignments, quality gates) but 60%+ of their content is sandbox-auto file paths. Chose to leave them — the patterns they contain are already captured in the solution docs, which are more portable.
- **Rejected alternatives:** Rewriting plan docs to replace sandbox-auto paths with generic examples (too much work for a sandbox). Symlinking docs between repos (breaks in Docker). Creating a shared docs repo (over-engineering for 2 sandbox projects).
- **Least confident:** Whether the "Not Yet Validated" section in HANDOFF is enough to prevent the implied-capability risk. A reader who goes straight to solution docs (skipping HANDOFF) will see swarm patterns described as proven, with no indication that sandbox can't actually run swarm builds yet. For a sandbox this is fine. For a production knowledge base, ported docs would need an inline status badge or similar.
