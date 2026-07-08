---
title: "Validate Orchestrator Context Telemetry (Step 1.52 / M29) at 20+ Agent Scale"
type: chore
status: active
date: 2026-07-07
origin: docs/brainstorms/2026-07-07-orchestrator-pretail-context-telemetry-brainstorm.md
feed_forward:
  risk: "The Step 1.52 telemetry is model-followed prose; run 050 proves the orchestrator drops manual bookkeeping under context pressure — so the validation run may yield INCOMPLETE telemetry, and a naive reader could mis-read missing boundary rows as 'healthy' instead of 'instrument failed'."
  verify_first: true
---

# Validate Orchestrator Context Telemetry at 20+ Agent Scale

## Overview

**This is a validation plan, not a build plan.** The instrumentation the origin
brainstorm proposed (capture orchestrator `context_proxy_chars` at pre-tail
boundaries + advisory >70% WARN) **already exists** and has since 2026-06-08 —
`Step 1.52: Orchestrator Context Instrumentation (MANDATORY — observability)` in
`.claude/skills/autopilot/SKILL.md`, added in commit `06cefe4` (draining run-070's
M29 meta-analysis). Writing code to add it would be redundant.

What is genuinely unresolved is **whether that existing instrument works at scale**,
because it has only ever run on tiny builds (079 = 3 agents, 080 = 4 agents). This
plan designates the next ≥20-agent swarm build as the scale-validation run and
pre-registers the trigger that would justify hardening.

(See brainstorm: `docs/brainstorms/2026-07-07-orchestrator-pretail-context-telemetry-brainstorm.md` — posture "measure, don't speculatively build".)

## Current State (verified 2026-07-07)

- **Step 1.52 protocol (`.claude/skills/autopilot/SKILL.md:144-182`):** updates
  `context_proxy_chars` at every phase boundary — *end of Step 6 (deepen), Step 9w.6
  (gates done), Step 10w (all workers returned), each Steps 11w–16w return, and
  immediately before Step 17w* — and appends a row to
  `docs/reports/<run-id>/context-telemetry.md`. Explicitly **observability only,
  never a gate**.
- **>70% advisory WARN (`SKILL.md:174-182`):** if `context_proxy_chars` > ~140K at
  the pre-17w boundary, write a WARN to `context-telemetry.md` + BUILD_TRACKING
  FAILURES. Does NOT block (tail is delegated to a fresh context regardless).
- **Why runs 068/069/070 show `context_proxy_chars: 0`:** they predate the
  2026-06-08 instrumentation. Runs 079/080 (post-instrumentation) do capture it.
- **OQ#2 resolved (`SKILL.md:192-196`):** the orchestrator DOES read the full
  `~/.claude/docs/agent-pitfalls.md` inline (Step 1.6) and carries it to inject into
  worker briefs at Step 10w. A grep-by-role trim is therefore a real context-saver
  BUT touches the MANDATORY pitfalls injection (per `CLAUDE.md`) — **out of scope
  here**; noted for a future, separate, carefully-scoped item.

## The 4-Question Plan Quality Gate

1. **What exactly is changing?** Essentially **no production code**. We (a) designate
   the next ≥20-agent swarm build as the telemetry scale-validation run, (b)
   pre-register the harden trigger, and (c) add ONE clarifying sentence to Step 1.52
   stating that a *missing* boundary row on a ≥20-agent run is an instrument FAILURE
   (a fired trigger), not a pass. Nothing else in the skill changes.
2. **What must NOT change?** The Step 1.52 protocol logic; the delegation stack
   (`tail-runner`, `swarm-runner`, no-read discipline); the G1 firebreak and G3
   self-audit surfaces; the advisory-only nature of the WARN (never a gate); the
   MANDATORY `agent-pitfalls.md` injection.
3. **How will we know it worked?** The next ≥20-agent build produces a complete
   `context-telemetry.md` with non-zero values at every boundary — giving us, for the
   first time, the orchestrator's true pre-tail headroom at scale.
4. **Most likely way this plan is wrong?** The orchestrator **silently drops** Step
   1.52 updates under context pressure at scale (run 050 is direct evidence: it
   failed to fill BUILD_TRACKING during that run's context death). Then the validation
   run yields *incomplete* telemetry, and a naive reading mistakes "missing rows" for
   "healthy." **Mitigation (baked into acceptance tests below): missing boundary rows
   = FAILED validation = harden trigger, never a pass.**

## Acceptance Tests (EARS)

### Happy Path

- WHEN the next swarm build of ≥20 agents completes THE SYSTEM SHALL record a
  **non-zero** `context_proxy_chars` at each Step 1.52 boundary (end of Step 6, Step
  9w.6, Step 10w, each 11w–16w return, pre-17w) as rows in
  `docs/reports/<run-id>/context-telemetry.md`.
  - Verify: `grep -c '|' docs/reports/<run-id>/context-telemetry.md` — row count ≥ (boundaries reached).
- WHEN that build's orchestrator stays below ~140K (70%) at the pre-17w boundary THE
  SYSTEM SHALL complete with **no** >70% WARN — confirming the delegation architecture
  holds at that scale, and this item can be CLOSED.
  - Verify: `grep -ci 'WARN.*context proxy' docs/reports/<run-id>/context-telemetry.md BUILD_TRACKING.md` — returns `0`.

### Error / Trigger Cases

- WHEN a ≥20-agent build finishes with **any** Step 1.52 boundary row MISSING from
  `context-telemetry.md` THE SYSTEM SHALL treat it as a fired trigger to build the
  residual-#2 robustness backstop (dropped-update visibility) — it SHALL NOT be read
  as a healthy pass.
  - Verify: compare boundary rows present vs. the phases the run actually reached (from BUILD_TRACKING Phase Status).
- WHEN `context_proxy_chars` exceeds ~140K at the pre-17w boundary THE SYSTEM SHALL
  emit the existing advisory WARN AND continue without aborting (tail delegates to a
  fresh context) — and that WARN is the trigger to size a real Gap-1 fix.
  - Verify: `grep -i 'WARN.*context proxy' docs/reports/<run-id>/context-telemetry.md` — present, AND the run reached a terminal `final_status` (not aborted at that boundary).

### Verification Commands (run after the next ≥20-agent build)

- `grep 'context_proxy_chars' BUILD_TRACKING.md` — non-zero final value.
- `cat docs/reports/<run-id>/context-telemetry.md` — one row per boundary reached, monotonic non-zero values.
- `grep -i 'WARN.*context proxy' docs/reports/<run-id>/context-telemetry.md BUILD_TRACKING.md` — presence = harden/size trigger.

## Scope

**In scope:** the one clarifying sentence in Step 1.52 (missing-row = failure), and
designating + pre-registering the scale-validation run and its triggers.

**Out of scope:** any deterministic re-implementation of the char tally (residual #2
— only if a trigger fires); the `agent-pitfalls.md` inline-read trim (touches
mandatory injection); any change to the delegation stack or G1/G3 surfaces.

## Dependencies & Risks

- **Dependency:** requires a real ≥20-agent swarm build to occur. Until one runs, this
  item stays OPEN-pending-evidence (no synthetic/simulated run — that would be the
  simulation-loop trap; the value is a real build's real telemetry).
- **Risk:** the char-tally is inherently model-estimated (why Step 1.52 is prose, not
  a script). Full determinism may be infeasible; the realistic robustness win (if
  triggered) is making a *dropped* update VISIBLE, not making the count exact.

## Sources & References

- **Origin brainstorm:** `docs/brainstorms/2026-07-07-orchestrator-pretail-context-telemetry-brainstorm.md` — decisions carried forward: measure-first not build-first; advisory-only threshold; delegation stack invariant.
- `.claude/skills/autopilot/SKILL.md:144-196` — Step 1.52 (telemetry) + Step 1.6 (pitfalls read).
- Commit `06cefe4` (2026-06-08) — introduced Step 1.52 / M29 from run-070 meta-analysis.
- `docs/reports/050/self-audit.md` — context death dropped BUILD_TRACKING bookkeeping (the fragility evidence).
- `docs/reports/079/`, `docs/reports/080/context-telemetry.md` — the only two runs that exercised the instrument (3–4 agents).
- `docs/solutions/2026-06-05-autopilot-context-death-delegation-architecture.md` — the delegation stack this validates the sufficiency of.

## Feed-Forward

- **Hardest decision:** whether to plan a build at all. The brainstorm's proposal was
  already implemented (Step 1.52, 2026-06-08), so a build plan would be redundant.
  Chose a validation plan that closes the item on evidence from the next real big
  build, and only escalates to hardening if a trigger fires.
- **Rejected alternatives:** re-add telemetry (already exists); build the deterministic
  backstop now (residual #2 — unproven need + feasibility unknown; wait for a
  trigger); trim the pitfalls inline read (touches mandatory injection); a synthetic
  large run to force telemetry (simulation-loop trap — real build required).
- **Least confident:** whether the orchestrator reliably executes ~9 model-followed
  telemetry updates at 20–30 agents under rising context pressure. Run 050 says it may
  not. That is exactly why the acceptance tests treat a MISSING boundary row as a
  failed validation, not a pass — the one interpretive safeguard this plan cannot get
  wrong.
