---
date: 2026-07-20
topic: dynamic-workflows-scale-test
---

# Biggest-Ever Autopilot Run — Dynamic Workflows Scale Test

## What We're Building

A **throwaway, deployable multi-resource CRUD app** whose only purpose is to be the vehicle
for validating **Dynamic Workflows** (the JS `Workflow` orchestration engine) as the successor
to manual autopilot at maximum scale.

The app is a single service with **~12–14 independent API-only resources** (users, orders,
invoices, etc. — no per-resource UI), each flowing the identical pipeline
**{scaffold → implement → verify}**, all sharing one auth/schema/router surface. That gives
**~36–42 resource agent-runs**, plus shared-surface (auth/schema/router) + integration + smoke
agents → **~45–55 total orchestrated agent-runs**, with *every* agent doing distinct work.

This clears the current **31-agent record** (GigSheet Run 050) on *total orchestrated
invocations*. Note the unit differs: Workflow agent-runs are ephemeral pipeline-stage calls,
not persistent named agents — so we also report **distinct-work units** (~12–14 resources +
shared-surface modules) as the apples-to-apples comparison. Resources are **API-only** on
purpose: identically-shaped pipeline items keep the per-resource baseline (B1) clean and
comparable; a per-resource UI would add variance for no test value.

"Biggest" is deliberately **reframed away from a vanity agent count**. The test is: can the
JS engine run itself at scale, beat manual autopilot on the same work, and do it without
bypassing the governance stack. The app is disposable; the engine validation is the deliverable.

## Why This Approach

Manual autopilot is already proven at 30–31 agents (lesson-studio Run 081, GigSheet Run 050).
Adding 10 more agents to the *same* machinery teaches nothing and makes the manual-launch toil
worse — a vanity number that compounds nothing.

Dynamic Workflows is the parked ceiling-breaker ("JS orchestration replacing manual autopilot
when scaling past ~15 agents — parked until the current system hits ceiling"). The pain of
hand-launching 30 agents *is* the ceiling signal, and the engine now exists as a **first-class
tool in this environment** (`pipeline()`/`parallel()`, deterministic control flow, real
`budget.spent()` token accounting). Shipping it makes *every* future big build deterministic,
cheaper, and less babysat — leverage a vanity count can't touch.

The multi-resource CRUD shape was chosen because **no agent is wasted**: each builds a distinct
resource (real, non-redundant work), all flow identical stages (clean `pipeline()` stress at
`items.length` scale), and the shared auth/schema/router is exactly the cross-section-contradiction
surface the governance stack exists to catch. It's also trivially manual-baselineable.

## Key Decisions

- **Engine = Dynamic Workflows (`Workflow` tool), not manual autopilot.** Manual is proven;
  the ceiling is manual toil, and the engine is the parked breaker, now natively runnable.
- **Throwaway spec = wide multi-resource CRUD platform**, ~12–14 **API-only** resources ×
  {scaffold → implement → verify}. Lands ~45–55 total orchestrated agent-runs (~36–42 resource
  runs + shared-surface/integration/smoke). Chosen over connector-hub (wastes agents —
  homogeneous, governance idle) and microservice-mesh (can't cleanly baseline; changes two
  variables at once). API-only keeps every pipeline item identically-shaped for a clean baseline.
- **Success = engine proven, not app quality.** Hard pass/fail gate: **A1** zero-touch
  orchestration (0 human interventions), **B1** beats a manual baseline (wall-clock, token
  cost, structural failures, human touches), **C2** dynamic smoke GREEN (app actually boots,
  shared surface works end-to-end — the surface-diversity lesson).
- **Captured-but-not-gating instrumentation:** **A2** ≥35 total orchestrated agent-runs
  (clears the 31 record); **B2**
  `budget.spent()` matches independent token count within ±10% (closes Run 081's char-vs-token
  miscalibration that faked "212% / context death"); **C1** governance ran *inside* the
  workflow (pitfalls injected per agent, G1/G3-equiv verify stage, zero P0 cross-section
  contradictions survive to final).
- **Baseline method = small same-spec slice.** Run 3–4 resources **both** manually and via
  Workflow, compare per-resource cost/time/touches, then run the *full* build only via Workflow
  and extrapolate. Cheap, honest, isolates the engine as the single variable under test.
- **Governance stays live inside the workflow** — the engine replaces the *launch/orchestration*
  layer, not the safety layer.

## Open Questions

*(For the plan phase — these are HOW, not WHAT)*

1. **Governance mapping (the hard one).** The sandbox's mandatory gates are wired into the
   *existing autopilot skill's* pipeline — the `Workflow` engine runs none of them natively. The
   plan must decide, concretely, how each rides inside (or bridges to) Workflow stages:
   - **Required Artifacts** (missing any = failed run): BUILD_TRACKING.md, solution doc,
     self-audit report at `docs/reports/<run-id>/`, HANDOFF, learnings propagation.
   - **Mandatory Spec Coverage** — the 6 sections validated by the spec-completeness-checker
     (Step **9w.6**).
   - **Pipeline gates** — the **9w.9 ghost-file/namespace** gate, ownership gates, and the
     self-audit-reviewer (WARN disposition + quality grade).
   - **Spec-convergence** — up front (manual, per the Spec Convergence Loop) or inside the workflow?
   - **Autonomy-class amendment** — the contract sanctions only manual / autopilot-solo /
     autopilot-swarm. Dynamic Workflows is an **unrecognized fourth mode**: does it inherit
     `autopilot-swarm`'s prerequisites (`swarm: true`, `dangerouslySkipPermissions`), or does
     `CLAUDE.md` need amending *before* launch to keep the run contract-compliant?
   *(This is the least-confident assumption — see Feed-Forward.)*
2. **The frozen spec itself.** The exact resource list still needs authoring + convergence
   (Claude Code → Codex → human) before launch, per the mandatory hardening loop.
3. **Baseline slice mechanics.** Which 3–4 resources, and how to run the manual arm without
   contaminating the Workflow arm (separate branch/worktree?).
4. **Token budget target.** What `budget.total` do we set — and do we want to *deliberately*
   probe real context-death this time (the one Run 081 never actually reproduced)?
   *Lean: yes — set a tight `budget.total` and probe it. It's the highest-value unknown, and the
   engine's real `budget.spent()` is exactly the instrument that closes the char-vs-token gap.*
5. **Deploy target for C2.** Local dynamic smoke only, or actually deploy somewhere disposable
   so "boots end-to-end" is real?
   *Lean: local smoke only. Real deploy is throwaway-infra scope creep; a local boot + end-to-end
   shared-surface exercise satisfies C2 without standing up disposable infrastructure.*
6. **No padding rule.** Confirm the spec genuinely *needs* ~12–14 resources — if we pad to hit
   the number, we've reintroduced wasted agents.

## Feed-Forward

- **Hardest decision:** Choosing Dynamic Workflows over a clean manual agent-count record —
  betting on infrastructure leverage (compounds every future build) over a legible vanity metric
  (compounds nothing). The record gets broken as a *byproduct*, not the goal.
- **Rejected alternatives:** (1) 40+ manual agents — vanity, no compounding, worsens the toil
  that *is* the ceiling. (2) Multi-connector hub — maximal fan-out but wastes agents
  (homogeneous; adapters 6–25 prove nothing new; governance stack idle). (3) Microservice mesh —
  highest correctness stress but un-baselineable and changes two variables at once (new engine +
  incomparable spec).
- **Least confident:** Whether the sandbox's **mandatory governance apparatus — which is coupled
  to the autopilot skill's pipeline, not the JS engine** — can ride inside the Workflow run
  without being bypassed. This is concrete, not abstract: Required Artifacts (BUILD_TRACKING,
  self-audit report, solution doc, HANDOFF, learnings), the 6 Mandatory Spec Coverage sections
  (checker Step 9w.6), the 9w.9 ghost-file/namespace gate, ownership gates, and the
  self-audit-reviewer all run *outside* `Workflow` today. Two failure modes: (1) porting/bridging
  them is the real, under-estimated work of this build; (2) Dynamic Workflows is an unrecognized
  autonomy class, so the run may be **contract-non-compliant before it starts** unless `CLAUDE.md`
  is amended. The entire "didn't cheat to win" tier (C1/C2) depends on this — if governance can't
  ride inside the workflow, a green run is a false positive, the most dangerous failure mode of
  the whole test.

## Next Steps
→ `/workflows:plan` for implementation details (author + converge the frozen spec, map governance
onto Workflow stages, define the baseline slice).
