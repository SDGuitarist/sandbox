---
title: "Dynamic Workflows can't carry firebreak identity — Run 082 governance gate"
date: 2026-07-21
type: solution
category: governance
run_id: "082"
status: resolved-negative
outcome: UNLAUNCHABLE
tags:
  - dynamic-workflows
  - firebreak
  - autopilot-swarm
  - governance
  - identity
  - verify-first
  - negative-result
related:
  - docs/plans/2026-07-20-feat-dynamic-workflows-max-scale-swarm-test-plan.md
  - docs/reports/082/identity-spike.md
  - docs/solutions/2026-04-30-spec-convergence-loop.md
---

# Dynamic Workflows can't carry firebreak identity (Run 082)

## Problem
Run 082 aimed to validate the JS `Workflow` engine (`pipeline()`/`parallel()`/`agent()`/`budget`)
as a **governance-faithful successor** to the manual autopilot skill, using a throwaway ~12-resource
Flask/SQLite swarm build as the vehicle. The app was disposable; **the engine validation was the
deliverable.** The whole run hinged on one unproven engine fact (the plan's *Load-Bearing Unknown*):
can the Workflow engine present a governed **worker** identity — and a TRUSTED control-plane identity —
to the sandbox's PreToolUse firebreak?

## Root cause (the negative result)
The sandbox firebreak governs by **identity only**. `classify_identity(env)` reads `env["agent_type"]`:
empty ⇒ `orchestrator` = fully control-plane-**TRUSTED**; `swarm-runner`/`tail-runner` ⇒ TRUSTED; any
other non-empty value ⇒ `worker` (governed). The `phase` field is inert. The **real autopilot** sets
each worker's identity through the **Agent tool's `name`** parameter (`name: "swarm-<run>-<role>"`,
SKILL.md:808-811) — that string lands in the hook envelope as `agent_type` (cf. fixture `swarm-072-api`).

The JS `Workflow` `agent()` exposes only `{label, agentType, model, isolation, schema}`:
- `agentType` → **spawnable-registry selection** (rejects `worker`/`swarm-runner`/`tail-runner`; a valid
  type like `general-purpose` still yields an **empty** hook identity).
- `label` → **display-only** (empirically inert to identity — a non-TRUSTED label, no label, and a
  `swarm-runner` spoof label all produced identical results; no spoof vector, but also no control).
- **No `name`/identity field** → nothing reaches the hook envelope's `agent_type`.

**Therefore every Workflow-spawned agent arrives with an empty `agent_type` → `orchestrator` → TRUSTED
→ ungoverned.** Every identity-based gate passes green because no worker is ever a "worker" — the exact
catastrophic false-positive the plan named. Governance cannot ride *inside* the engine, because identity
is the firebreak's only real axis and the engine won't let the script set it.

## How it was proven (Phase-0 spike, ~5 throwaway agents)
1. Hook-wiring pre-check: `firebreak-gate.sh` present + registered under PreToolUse `Bash|mcp__.*|Write|Edit`;
   `classify_identity` ground truth confirmed; `docs/reports/082/` absent. Gate is live.
2. `agent({agentType:'worker'|'swarm-runner'|'tail-runner'})` → rejected at spawn (not registry types).
3. `agentType:'general-purpose'` agents wrote the repo-root `.claude/` control plane **while the firebreak
   was armed**, no block, regardless of `label` (3 label variants identical) → classified TRUSTED (empty id).
4. Positive control: armed firebreak actively deferred the orchestrator's own indirection commands (not
   inert); `test_firebreak_superset.py` = 297/297 confirms a real worker identity **is** denied for
   control-plane actions. So worker→deny, empty→allow both proven; Workflow agents fall on the allow side.

## Secondary findings
- **`args` does not propagate** to a `scriptPath`+background Workflow (`typeof args === "undefined"`).
  Breaks the plan's freshness plumbing (run_start_ts-nonce was to arrive via `args`). Inject externally-
  captured values another way (hardcode at author time / a committed params file a pre-flight agent reads).
- **Worktree isolation works**, but via the **engine's own shared-checkout guard**, not the firebreak — a
  different, non-identity protection layer. It blocks a worktree agent from touching the main-repo control
  plane, but produces no RED approval record.
- **`parallel()` barrier**: all thunks awaited/returned. A thunk that throws **synchronously** rejects the
  whole run; only **async agent errors** resolve to `null`. Teardown-in-`finally` must not assume synchronous
  thunk throws are swallowed.

## Resolution
**Run 082 (Workflow engine) is UNLAUNCHABLE.** The plan is internally sound; its load-bearing premise is
refuted by the substrate. Marked `status: unlaunchable` in the plan frontmatter.

**The unblock is an engine capability**, not plan work: a Workflow `agent()` option that writes the spawned
agent's PreToolUse `agent_type` (mirroring the Agent tool's `name`). When it ships, re-run the exact Phase-0
spike; Q1a/Q2 become answerable and the plan proceeds unchanged.

## Lessons (compounding)
- **`verify_first` earned its keep.** A binary, load-bearing engine assumption was killed with ~5 throwaway
  agents *before* a 34–38-agent build spent tokens on a guaranteed false-green. Cost of the gate ≪ cost of
  the false positive. Keep pre-registering these as hard Phase-0 gates whenever a run depends on an unproven
  substrate fact.
- **Distinguish "orchestration engine" from "governance substrate."** The Workflow engine is a fine control-
  flow layer; it is not a governance-faithful *replacement* for autopilot as long as the safety layer keys on
  an identity the engine can't emit. Any future "replace autopilot with X" must first prove X can carry the
  firebreak identity axis end-to-end.
- **A negative result is a deliverable.** The goal was engine validation; the answer is "no, not yet, here's
  the precise reason and the exact capability that unblocks it." That is a successful run, not a failed one.

## Reproduction
`wfscale-identity-spike.mjs` (repo root; final = v4) + `docs/reports/082/identity-spike.md`.
