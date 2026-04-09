---
title: Swarm-Enabled Autopilot with Assembly Verification
date: 2026-04-08
status: brainstorm
tags: [autopilot, swarm, agents, assembly-verification, quality-gates]
prior_solutions:
  - 2026-04-07-flask-swarm-acid-test.md
  - 2026-03-30-swarm-build-alignment.md
  - 2026-03-30-swarm-scale-shared-spec.md
  - 2026-03-30-chain-reaction-inter-service-contracts.md
  - 2026-03-30-uptime-pulse-multi-service-automation.md
---

# Swarm-Enabled Autopilot with Assembly Verification

## What We're Building

Evolve the `/autopilot` command from a linear solo-build pipeline into a smart
command that detects swarm builds and branches accordingly. Add six new
specialized agents and additional quality gates so the entire loop - including
parallel multi-agent builds - runs fully unattended without Codex handoffs.

### Constraint: Static Markdown Cannot Branch

The current `/autopilot` command is static markdown - it chains slash commands
in a fixed order with no conditional logic. Swarm detection requires runtime
branching (read the plan, check for assignment table, choose a path). This means
the command format itself must change. Options for the plan phase to evaluate:
a skill with logic, a wrapper script, or a new command format that supports
conditionals.

### New Agents (one job each)

1. **Brainstorm Refinement Agent** - Runs after the initial brainstorm. Fills
   gaps by cross-referencing prior solution docs. Identifies missing edge cases,
   missing requirements, and patterns from prior builds that the brainstorm
   didn't consider. Additive, not adversarial.

2. **Swarm Planner Agent** - Reads the completed plan and generates the Swarm
   Agent Assignment table. Decides file splits (vertical by feature/blueprint).
   Keeps the planning agent focused on architecture, not logistics.

3. **Spec Contract Checker** - Static analysis after swarm assembly. Greps the
   assembled code for every contract point in the shared interface spec: imports,
   route signatures, CSS classes, function signatures, data ownership. Auto-fixes
   mismatches and reports every change.

4. **Smoke Test Runner** - Starts the assembled app, hits key routes, verifies
   responses match expected behavior. Catches runtime issues that static analysis
   misses (like the context manager gap in the Flask Acid Test).

5. **Test Suite Runner** - Runs any test suite generated during the work phase.
   Reports pass/fail with details.

6. **Assembly Fix Agent** - Activated when the smoke test runner reports a
   failure. Reads the error output and the spec, makes targeted fixes, then
   the smoke test re-runs. One job: fix startup/runtime failures.

All verification agents auto-fix what they can and report changes. The pipeline
continues unattended.

### Updated Autopilot Sequence

**Solo builds** (no Swarm Agent Assignment table in plan):
Current flow unchanged - linear single-agent implementation.

**Swarm builds** (plan contains Swarm Agent Assignment table):

| Step | Phase | Agent(s) | Job |
|------|-------|----------|-----|
| 1 | Init | Ralph Loop + compound-start | Load context, surface prior lessons |
| 2 | Brainstorm | Solo | Generate initial brainstorm with solution-doc-searcher |
| 3 | Brainstorm Refinement | Refinement Agent (parallel) | Fill gaps from prior solution docs |
| 4 | Plan + Spec | Solo + research agents | Full plan with shared interface spec |
| 5 | Deepen Plan | Research agents | Refine spec, auto-generate prescriptive code blocks, quality gate |
| 6 | Swarm Planning | Swarm Planner Agent | Generate agent assignment table from plan |
| 7 | Swarm Work | N parallel agents (git worktrees) | Each agent works in isolated worktree with spec + file assignments |
| 8 | Assembly | Git merge of worktree branches | Merge all agent branches into one codebase |
| 9 | Contract Check | Spec Contract Checker | Static verification of spec contracts, auto-fix |
| 10 | Smoke Test | Smoke Test Runner | Start app, hit routes, verify responses |
| 10a | Fix (if needed) | Assembly Fix Agent | Read errors + spec, make targeted fixes, re-test |
| 11 | Test Suite | Test Suite Runner | Run generated tests |
| 12 | Review | /workflows:review (multi-agent) | Full review of assembled + verified code |
| 13 | Resolve TODOs | resolve_todo_parallel | Fix review findings |
| 14 | Compound | compound + update-learnings | Solution doc + propagate lessons |

### Detection Logic

The plan phase makes the architectural decision: is this a swarm build or solo?
It sets `swarm: true` in the plan's YAML frontmatter. After step 5 (Deepen
Plan), the autopilot checks the frontmatter. If `swarm: true`, it branches to
step 6 (Swarm Planner Agent generates the assignment table). Otherwise, it
follows the current solo work path. The plan decides, the planner executes.

## Why This Approach

### Prescriptive specs stay, but get cheaper to write

The 0-mismatch track record comes from prescriptive code blocks in the spec.
Relaxing spec quality and relying on verification would move from prevention to
detection - always more expensive. Instead, we keep prescriptive specs and invest
in automating their generation during plan deepening. The verification agents are
a safety net, not a replacement for spec quality. Belt AND suspenders.

### One agent, one job

Agents with multiple responsibilities get off task. Each verification agent does
exactly one thing: contract checking, smoke testing, or test running. This keeps
each focused and makes failures easy to diagnose.

### Brainstorm refinement catches what solo brainstorms miss

The brainstorm is where unverified assumptions sneak through. A refinement agent
that cross-references solution docs fills gaps before they reach the plan. This
is especially valuable as the solution doc library grows - more prior knowledge
to leverage.

### No Codex handoffs

This is an experimental sandbox. Codex review breaks the unattended flow.
Instead, we compensate with deeper planning (brainstorm refinement + plan
deepening) and post-build verification (4 specialized agents + full review).
More review surface total, just distributed differently.

## Key Decisions

1. **Auto-fix + report on mismatches** - Verification agents fix what they find
   and document changes. Keeps the loop unattended. Review phase verifies the
   fixes were correct.

2. **Six specialized agents, one job each** - Brainstorm refinement, swarm
   planner, spec contract checker, smoke test runner, test suite runner,
   assembly fix agent. Never overload an agent with multiple responsibilities.

3. **Prescriptive specs stay** - Don't shrink specs. Keep prescriptive code
   blocks. Future improvement: automate spec generation during plan deepening
   (out of scope for this build).

4. **One smart /autopilot command** - Detects swarm builds from plan frontmatter
   (`swarm: true`) and branches. No separate /swarm-autopilot command. No
   heuristics, no file count thresholds. Plan decides, planner executes.

5. **Brainstorm refinement is additive** - Fills gaps from prior solution docs.
   Not adversarial (challenging assumptions) or Feed-Forward-only. Adds missing
   edge cases, requirements, and patterns.

6. **Git worktrees for swarm isolation** - Each parallel agent works in an
   isolated git worktree. Assembly is a git merge of worktree branches. Claude
   Code already supports `isolation: "worktree"` on agent spawning.

7. **Dedicated swarm planner agent** - A separate agent reads the plan and
   generates the agent assignment table. Keeps the planning agent focused on
   architecture, not logistics.

8. **Dedicated assembly fix agent** - When smoke test fails, a fix agent reads
   errors + spec and makes targeted repairs. Then smoke test re-runs. Max one
   retry - if the fix agent's changes don't resolve the failure, escalate to
   the review phase with full error context.

9. **Spec auto-generation is out of scope** - Auto-generating prescriptive code
   blocks during plan deepening is a future improvement. This build focuses on
   the pipeline and agents, not spec tooling.

## Feed-Forward

- **Hardest decision:** Whether to relax spec prescriptiveness now that
  verification agents exist. Decided to keep prescriptive specs and automate
  their generation instead. Prevention over detection.
- **Rejected alternatives:** Lean specs with verification-as-primary-defense
  (Chain Reaction proved ambiguity causes bugs). Two separate commands for
  solo/swarm (maintenance burden, unclear intent at invocation time).
  Adversarial brainstorm refinement (additive gap-filling is higher value
  when the solution doc library is the primary knowledge source).
- **Least confident:** Whether git worktree merges will be clean when swarm
  agents touch shared files (e.g., `__init__.py`, `layout.html`). The spec
  assigns these to one agent, but if prescriptive code blocks are identical
  across agents, accidental touches could cause merge conflicts. Need to
  validate with a real swarm build using worktrees.

## Refinement Findings

**Gaps found:** 5

1. **Chain Reaction Inter-Service Contracts -- Spec Contract Checker missing data ownership verification** -- The Spec Contract Checker (step 9) checks imports, route signatures, CSS classes, and function signatures, but does not mention verifying data ownership assignments. The Chain Reaction build showed that data ownership ambiguity (two services writing to the same table) was the #1 source of bugs at inter-service boundaries. The checker should grep for data ownership table entries in the spec and verify each table has exactly one writer in the assembled code.
   - Source: `docs/solutions/2026-03-30-chain-reaction-inter-service-contracts.md`
   - Relevance: Without data ownership checks, the contract checker has a blind spot for the most common swarm assembly bug class. The brainstorm lists what the checker verifies but omits the pattern that caused the most bugs in prior builds.

2. **Flask Swarm Acid Test -- Spec ambiguity produces identical mistakes that verification cannot catch** -- The brainstorm positions verification agents as a safety net for spec gaps, but the acid test revealed that when the spec is ambiguous (e.g., context manager usage), ALL agents make the identical wrong choice. A Spec Contract Checker comparing code against spec finds 0 mismatches because every agent matched the ambiguous spec perfectly. The real gap was in the spec, not the code. The brainstorm refinement agent or plan deepening step should include a check for ambiguous spec patterns (functions without usage examples, return types without consumption patterns).
   - Source: `docs/solutions/2026-04-07-flask-swarm-acid-test.md`
   - Relevance: The brainstorm says "verification agents are a safety net, not a replacement for spec quality" but does not address the case where verification passes AND the spec is wrong. This is a blind spot in the pipeline between steps 5 (Deepen Plan) and 9 (Contract Check).

3. **Swarm Scale Shared Spec -- Security risks are found in review, not verification** -- Across all prior swarm builds, security issues (XSS, SSRF) were consistently found during review, never during planning or static verification. The brainstorm removes the Codex review layer (key decision: "No Codex handoffs") and compensates with deeper planning and post-build verification agents. But none of the 4 verification agents (steps 9-11) are designed to catch security issues. The review at step 12 is the only security checkpoint, and it runs later in the pipeline than Codex would have. The brainstorm should acknowledge this gap and consider whether the Spec Contract Checker or Smoke Test Runner should include a basic security checklist (innerHTML usage, allow_redirects, SSRF patterns).
   - Source: `docs/solutions/2026-03-30-swarm-scale-shared-spec.md`
   - Relevance: The brainstorm claims "more review surface total, just distributed differently" but the distribution has no security-focused agent before step 12. Every prior swarm build found its security bugs in review. Pushing security checks earlier (into verification agents) would match the "prevention over detection" philosophy the brainstorm already endorses.

4. **Cross-Project Knowledge Merge -- Validate infrastructure assumptions before planning** -- The brainstorm assumes git worktrees work for swarm isolation (key decision 6) and that Claude Code supports `isolation: "worktree"` on agent spawning, but the Feed-Forward flags worktree merges as the least confident area. The cross-project knowledge merge solution doc learned that verifying infrastructure assumptions BEFORE planning (the 5-minute check of autopilot.md) saved a plan rewrite. The brainstorm should note whether worktree-based swarm isolation has been tested at all, or whether this is an unverified assumption entering the plan phase.
   - Source: `docs/solutions/2026-04-05-cross-project-knowledge-merge.md`
   - Relevance: The brainstorm states "Claude Code already supports isolation: worktree" but this has never been used in a sandbox build. If this assumption is wrong, the entire swarm work phase (step 7) and assembly phase (step 8) need redesign. A 5-minute verification before planning would confirm or kill this assumption.

5. **Flask Swarm Acid Test -- Python specs are 3x larger and may exceed context windows** -- The acid test found Python/Flask specs are 584 lines for 4 agents (vs ~190 lines for 6 JS agents). The brainstorm's plan deepening step (step 5) aims to "auto-generate prescriptive code blocks," which would increase spec size further. If a 6-agent Python swarm build produces a ~900-line spec, the spec itself may exceed agent context budget, causing agents to skip sections. The brainstorm does not address spec size limits or how the autopilot handles specs that approach context pressure.
   - Source: `docs/solutions/2026-04-07-flask-swarm-acid-test.md`
   - Relevance: The autopilot pipeline targets fully unattended builds. If a spec grows past agent context limits during plan deepening, agents will silently drop contract points. The brainstorm should set a spec size budget or define a fallback (sub-specs, per-agent spec slices) for the plan phase.

STATUS: PASS
