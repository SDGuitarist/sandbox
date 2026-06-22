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
`bypassPermissions` into every agent — a **blanket** bypass that overrides the
risk-tiering already in the user's global CLAUDE.md Safety Rule (ask before
destructive/irreversible actions) and permissions matrix.

The firebreak restores *oversight proportionate to risk* without sacrificing
unattended runs: it classifies each action, lets the safe majority run untouched,
and **defers** the binding/irreversible tail to an async human-approval queue.

**In scope:** classifying actions, intercepting the risky tier, deferring them to
a queue, async human approval. **Out of scope (this doc):** the in-flight AI
monitor (G2), monoculture mitigation (G3), ledger hardening (G4) — separate items.

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
| **GREEN** | Auto-run (unchanged) | file writes inside the worktree; local commits; running tests; reads; local-only git ops |

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
