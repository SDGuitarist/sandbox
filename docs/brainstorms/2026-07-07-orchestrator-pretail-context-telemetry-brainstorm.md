---
title: "Orchestrator Pre-Tail Context Saturation — Measure Before Building"
date: 2026-07-07
type: brainstorm
phase: brainstorm
status: planned-instrument-already-exists
decision: "PLANNED 2026-07-07. verify-first found the proposed telemetry ALREADY EXISTS (SKILL.md Step 1.52 / M29, since 2026-06-08). Not rebuilt. Outcome = minimal validate-at-scale plan (docs/plans/2026-07-07-chore-validate-orchestrator-context-telemetry-at-scale-plan.md): next >=20-agent build validates the existing instrument; missing boundary row = failure trigger; >70% WARN = size-a-fix trigger. One clarifying note added to Step 1.52."
traces_to:
  - docs/brainstorms/2026-07-04-g2-inflight-liveness-monitor-brainstorm.md (G2 shelved → pivot #1 was context-death)
  - docs/solutions/2026-05-20-autopilot-context-window-optimization.md (Tier 1 checkpoint)
  - docs/solutions/2026-06-01-tail-delegation-context-resilience.md (tail-runner delegation)
  - docs/solutions/2026-06-05-autopilot-context-death-delegation-architecture.md (3-stage delegation — the fix that shipped)
  - docs/reports/050/self-audit.md (context death, 31 agents)
  - docs/reports/061/self-audit.md (context death, 10 agents, pre-tail)
feed_forward:
  risk: "The remaining pre-tail context-death risk is UNMEASURED, not proven. Building a fix now risks solving a non-problem (the delegation architecture may already hold at 30 agents); NOT measuring risks a silent death on the first big build."
  verify_first: true
---

# Orchestrator Pre-Tail Context Saturation — Measure Before Building

## Origin (why we're here)

Step 5's G2 brainstorm shelved the worker-liveness monitor (zero observed worker
stalls); its Fork named the *evidenced* liveness failure as **orchestrator context
death** (runs 050, 061). This doc scopes that pivot. G4 (per-run nonce) was found to
be a consciously-deferred residual whose revisit trigger has not fired. This is the
one Step-5-adjacent item local evidence still supports — but only narrowly.

## What We Learned (the evidence check — done first, per the G2/G4 lesson)

**The original pain is SOLVED.** The June 1–5 delegation architecture closed
tail-phase context death:

- **Live stack:** (a) no-read discipline — orchestrator reads PASS reports `limit:1`
  (status line only), full read only on FAIL; (b) `swarm-runner` delegates Steps
  11w–16w (assembly, contract-check, smoke, tests, cleanup) to a fresh context;
  (c) `tail-runner` delegates the whole tail (review → compound → learnings →
  self-audit) to another fresh context.
- **Post-June-5 evidence:** no `PAUSED_FOR_CONTEXT` exits in any run; run **069**
  survived **24 agents** inline with no context death; runs **079/080** hit 91%/63%
  pre-tail then delegated cleanly.
- The "Tier 2 Pre-Review Resume checkpoint" (run 061's named unbuilt fix) was not
  merely unbuilt — it was **consciously superseded** by delegation (2026-06-05 doc:
  prevent the pre-review pressure entirely rather than checkpoint-and-resume).

**What is NOT solved is also not proven — it is UNMEASURED.** The failure mode
structurally shifted from "dies during tail" → "*might* die during inline work
phases (Steps 6–10w)":

- Deepening (Step 6) + worker spawn (Steps 7w–10w) **must run inline** — the Agent
  tool can't delegate them. Delegation savings are all post-spawn.
- **The critical boundaries were never instrumented.** Runs 068/069/070 (12–24
  agents) carry `context_proxy_chars: 0` — orchestrator context % at Step 7w
  (post-deepening) and Step 10w (post-spawn) was not captured. Only tiny runs
  (079/080, 3–4 agents) have telemetry, and only at the pre-tail point.
- So for a 20–30 agent build, **nobody knows the orchestrator's pre-tail headroom.**
  Run 069's 24-agent survival is real but blind.

## What We're Building (proposed)

**Measurement-first, not a speculative re-architecture.** Two boundaries of the
inline work phase get a context-telemetry capture so the *next* real 20+ agent build
converts the unknown into evidence:

- Capture `context_proxy_chars` (or the existing proxy) at **Step 7w (post-deepening)**
  and **Step 10w (post-spawn)** — the two points delegation cannot protect — and
  record them in BUILD_TRACKING / `context-telemetry.md` alongside the existing
  pre-tail capture.
- Define a **soft threshold** (candidate: >75% at Step 10w) that, if crossed, prints
  a WARN and recommends splitting the build — an *advisory* signal, not a hard gate
  (no new abort path, no G1/G3 interaction).

**Deliberately NOT in v1:** re-architecting inline spawn into a proxy agent (high
cost, unproven need); any hard checkpoint/abort; touching the delegation stack that
already works.

### What success looks like (seeds the plan's EARS tests)

- After the next 20+ agent build, BUILD_TRACKING shows a **non-zero** orchestrator
  context % at Step 7w and Step 10w — the measurement gap is closed.
- If the orchestrator stays comfortably below threshold at Step 10w, the delegation
  architecture is **proven** sufficient at that scale and no deeper fix is built.
- If it crosses threshold, we now have the **evidence** that justifies (and sizes) a
  real Gap-1 fix — instead of guessing.
- Zero change to the tail-delegation behavior, G1 firebreak, or G3 self-audit.

## Why This Approach

- **The pain is real but its size is unknown.** Two prior Step-5 items evaporated
  under evidence (G2 non-problem; G4 non-triggered residual). The disciplined read
  here is not "build a watchdog" but "measure the one thing we're blind to." A cheap
  instrument that could kill or size the problem beats a speculative build.
- **This is the opposite of the simulation-loop trap.** It is not simulating to feel
  safe; it is adding two telemetry points to a real pipeline so the *next real run*
  yields ground truth. (Alex's rule: "simulating to validate is the loop in disguise"
  — this is real instrumentation on the real path, not a simulator.)
- **Lowest blast radius.** Advisory WARN + two captures. No new abort, no delegation
  change, no G1/G3 surface touched.

## Key Decisions

1. **Posture: measurement-first.** Instrument Steps 7w + 10w before building any
   Gap-1 fix. ✅ proposed
2. **Threshold is advisory, not a gate.** WARN + recommend-split; no hard abort. ✅ proposed
3. **Delegation stack is invariant.** Do not touch the shipped tail-runner /
   swarm-runner / no-read discipline. ✅ proposed

## Open Questions (for the plan phase)

1. **Where exactly is `context_proxy_chars` captured today, and what proxy is it?**
   The plan must find the existing capture site and reuse the same proxy at Steps
   7w/10w for comparability. (Verify: it's currently only pre-tail.)
2. **Is the ~100K-char agent-pitfalls.md full read carried by the ORCHESTRATOR
   inline?** If so, trimming it (grep-by-role vs full read) is a cheap, safe ~50K-char
   context win — but agent-pitfalls injection is MANDATORY per CLAUDE.md, so any trim
   must preserve the full injection into worker briefs; only the orchestrator's own
   inline read (if any) is the candidate. Verify ownership before touching.
3. **Threshold value + which step.** 75% at Step 10w is a guess; the first
   instrumented big build should set it empirically.
4. **Gap 2 (tail-runner capacity at 20+ agents) — separate item?** The tail-runner
   itself has no auto-checkpoint; a 30-agent `/workflows:review` could saturate *it*.
   Same measurement logic applies (instrument tail-runner peak). Likely a sibling
   deliverable, not v1.

## Feed-Forward

- **Hardest decision:** measure vs. build. Building a pre-tail context fix now would
  be the third speculative Step-5 build against an unproven need. Chose measurement
  because it is cheap, converts the one genuine unknown into evidence, and can *size
  or kill* the problem before any expensive re-architecture.
- **Rejected alternatives:** re-architect inline spawn into a proxy agent (high cost,
  unproven need); resurrect the Tier-2 pre-review checkpoint (already consciously
  superseded by delegation); a hard context gate (new abort path, risks false-pause
  like run 048's score-40.5 false positive).
- **Least confident:** whether the delegation architecture already holds at 30 agents.
  Run 069 (24) survived but blind. The instrument is precisely what resolves this —
  which is why measurement must come first. **Verify at the next 20+ agent build.**
