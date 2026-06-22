---
title: "G1: Risk-Tiered Firebreak for Unattended Autopilot Swarm"
date: 2026-06-21
type: brainstorm
phase: brainstorm
status: ready-for-plan
traces_to:
  - docs/governance/2026-06-21-autopilot-vs-three-layers-agent-security.md (item G1)
  - docs/solutions/2026-06-21-unattended-swarm-autopilot-master-extraction.md
feed_forward:
  risk: "A PreToolUse hook may NOT actually fire when dangerouslySkipPermissions is true — the entire firebreak depends on intercepting above the bypass."
  verify_first: true
---

# G1: Risk-Tiered Firebreak for Unattended Autopilot Swarm

## What We're Building

A **risk-tiered firebreak** that reconciles zero-prompt autopilot throughput with
the "human controllers" principle (Google DeepMind, *Three Layers of Agent
Security*). Today autopilot sets `dangerouslySkipPermissions: true` and injects
`bypassPermissions` into every agent — a **blanket** bypass.

**The key reframe:** this isn't *overriding* safety — it's the missing
**enforcement engine** for a contract that already exists. The sandbox's own
`CLAUDE.md` "Forbidden Actions" section already enumerates most of the RED tier in
prose (no prod-DB access; no `git push --force`/`reset --hard` without
confirmation; no destructive history rewrites; no external API calls without
declaration; no edits outside `~/Projects/sandbox/`). Under
`dangerouslySkipPermissions`, that contract is currently **unenforced**. The
firebreak makes it executable. (It also restores the risk-tiering in the global
CLAUDE.md Safety Rule + permissions matrix that the blanket bypass overrides.)

The firebreak restores *oversight proportionate to risk* without sacrificing
unattended runs: it classifies each action, lets the safe majority run untouched,
and **defers** the binding/irreversible tail to an async human-approval queue.

**In scope:** classifying actions, intercepting the risky tier, deferring them to
a queue, async human approval. **Out of scope (this doc):** the in-flight AI
monitor (G2), monoculture mitigation (G3), ledger hardening (G4) — separate items.

### What success looks like (seeds the plan's EARS tests)

- A run that hits a RED action **completes unattended**: the action is deferred to
  a `NNN-pending-approval-*.md` todo, GREEN actions are unaffected, and the run
  still produces all required tail artifacts.
- **No RED action ever executes without explicit human approval.** Fail-closed:
  an unknown or ambiguous action defers rather than runs.
- The **sanctioned learnings-propagation writes are NOT deferred** (the carve-out
  holds — the compound tail still writes).
- A deferred item is **resolvable later** (approve → the action executes / the
  merge lands) without re-running the build.

## Why This Approach

Grounded in the repo scan: the building blocks already exist, so G1 is mostly
**composition**, not new infrastructure.

- **Escalation = defer-and-continue**, reusing the existing `todos/` +
  `resolve-todos` queue. A risky action is skipped, written as a
  `NNN-pending-approval-*.md` todo, and the run continues unattended to
  completion. The human becomes an **async batch reviewer**, not a 2am babysitter.
  (Rejected: *block-and-wait* breaks unattended; *checkpoint-and-halt* stalls the
  whole build on the first risky action.)
- **Classifier = deterministic denylist now, hybrid later.** A PreToolUse hook
  pattern-matches a small set of known-irreversible actions (fail-closed,
  auditable, zero-latency, no adjudication risk) — matching the user's "AI
  proposes, deterministic controls dispose" principle. A later Phase 2 adds an
  **AI advisory pass** that only *flags novel/unlisted* actions for the human to
  add to the denylist — never decides. (Rejected: an AI *judge* as the decider —
  the spec-eval gate already proved an AI judge hits ~0% field precision and was
  demoted to advisory; putting a non-deterministic judge in charge of irreversible
  actions repeats a documented mistake.)

## Key Decisions

1. **Escalation model:** Defer-and-continue via the `todos/` queue. ✅ decided
2. **Classifier mechanism:** Deterministic denylist (v1) → hybrid with AI advisory
   (Phase 2). ✅ decided
3. **Authority placement:** Deterministic layer is always dispositive; AI is only
   ever a blind-spot finder. ✅ decided

### Risk taxonomy (the denylist — finalized for v1)

| Tier | Disposition | Actions |
|------|-------------|---------|
| **RED** | Defer to approval queue | **Git:** force-push; push to `main`/`master`/shared branches; amend/rewrite of pushed commits. **Merge:** the swarm-runner's final merge-to-`main` (the finished build waits on its assembly branch for approval). **Data:** destructive ops on a real `*.db` (DROP/DELETE/rm) outside `/tmp`; **deletes targeting any path outside the repo worktree** (e.g. `~/Data`, home, other projects) and not `/tmp`. **Outward-facing:** external sends (curl/email/webhook to a non-localhost host); **deploy/promote** commands (vercel / railway / fly / netlify); **external-service MCP writes** (default-deny — any `mcp__*` send/create/publish/update/delete to a non-local service). **Packages:** removal (`pip/npm uninstall\|remove`). |
| **GREEN** | Auto-run (unchanged) | file writes inside the worktree; local commits; running tests; reads; local-only git ops; **sanctioned learnings-propagation out-of-repo writes** (see carve-out below) |

> **Carve-out (must-fix for the plan):** CLAUDE.md sanctions specific out-of-repo
> writes during the compound-phase tail — `~/.claude/docs/agent-pitfalls.md`,
> `~/Documents/dev-notes/` (LESSONS_LEARNED + daily journal), and
> `~/.claude/projects/[key]/memory/`. These are **append/write, not delete**, and
> are legitimate. The RED "out-of-repo" rule must GREEN-list these exact paths, or
> the firebreak will block the learnings propagation that every run requires.

> **Scope guardrail:** v1 only *defers* the merge-to-`main`; it does **not**
> redesign the assembly/tail flow. The build still assembles onto its
> `swarm-<id>-assembly` branch as today — only the final land-on-`main` step waits
> for approval.

**Detection confidence varies by category** (drives the Phase-2 advisory priority):

- **High / clean deterministic detection:** force-push, push-to-shared, merge-to-main, out-of-repo deletes, prod-DB destructive ops, deploy commands, package removal. (Path checks + tight command patterns.)
- **Coarse / default-deny in v1:** external-service MCP writes. The read/write
  distinction across MCP namespaces is imperfect deterministically, so v1 uses a
  conservative default-deny posture (errs toward defer, never toward run). This is
  the primary surface the Phase-2 AI advisory will refine.

Rationale for viability: in a swarm run, workers overwhelmingly do GREEN actions
(local file writes + local commits). The genuinely irreversible actions cluster
into the RED list above — which is what makes a deterministic denylist tractable.
A code-build swarm has **no legitimate reason** to deploy, send email, or delete
outside its worktree, so default-deny on those costs almost no false positives.

## Resolved Questions

1. **Final assembly merge-to-`main` = RED.** ✅ The merge is the single most
   binding action of a run, so a completed, verified build waits on its assembly
   branch for human approval before landing. We trade "lands on main unattended"
   for a strong human-controller checkpoint; everything up to the merge stays
   unattended. (Decided 2026-06-21.)
2. **RED list additions = Deploy + External-MCP-writes + Out-of-repo-deletes.** ✅
   All three folded into the taxonomy above. Deploy and out-of-repo deletes are
   high-blast-radius / low-false-positive / cleanly detectable; external-MCP-writes
   included as conservative default-deny (detection refined later by Phase 2).
   "Seed list only" was rejected — it would have left the highest-blast-radius
   actions uncovered. (Decided 2026-06-21.)

## Open Questions (deferred to plan phase)

1. **How does approval resolve?** Extend `resolve-todos` with an
   "approve-and-execute pending-approval" mode, or a dedicated `/approve` skill?
   And for a deferred *merge*, does approval trigger the merge automatically or
   just unblock it? (Design detail for the plan phase.)
2. **Deferred-merge × Required Artifacts ordering.** CLAUDE.md says every
   *completed* run must produce the tail artifacts (solution doc, learnings,
   HANDOFF, self-audit). Confirm the phase order: review/compound/tail run on the
   `swarm-<id>-assembly` branch and the run reports `PIPELINE_PASS` with the merge
   **pending in the queue** (run "complete" but unlanded). The plan must ensure a
   deferred merge does not trip the "run completes" / Required-Artifacts contract
   or the self-audit gate.

## Feed-Forward

- **Hardest decision:** Defer-and-continue vs. checkpoint-and-halt. Chose defer
  because it is the only model that preserves true unattended throughput while
  still removing the irreversible-action autonomy — the queue carries the human
  controller asynchronously.
- **Rejected alternatives:** AI-judge-as-decider (refuted by our own spec-eval
  ~0% precision demotion); block-and-wait (breaks unattended); checkpoint-and-halt
  (one risky action stalls the whole build).
- **Least confident:** Whether a **PreToolUse hook actually fires when
  `dangerouslySkipPermissions` is true.** The entire firebreak depends on
  intercepting *above* the bypass. If the bypass also short-circuits hooks, the
  mechanism must move (e.g., into the agent brief contract or a wrapper around the
  risky tools). **This must be verified first in the plan phase** before any other
  work.
