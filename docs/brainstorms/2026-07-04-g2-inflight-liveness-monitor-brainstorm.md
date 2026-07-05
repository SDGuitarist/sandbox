---
title: "G2: In-Flight Liveness Monitor for Unattended Autopilot Swarm"
date: 2026-07-04
type: brainstorm
phase: brainstorm
status: shelved-evidence-invalidated-premise
decision: "SHELVED 2026-07-04 — evidence check (OQ#2) found zero observed worker stalls; the real liveness failure is orchestrator context death (runs 050, 061), which a worker-monitor does not catch. Not worth building now (YAGNI). Session redirected to [080-W2]. If revisited, start from the Fork section: pivot #1 (context-death watchdog) or #2 (cross-worker semantic divergence), not the worker-liveness design."
traces_to:
  - docs/governance/2026-06-21-autopilot-vs-three-layers-agent-security.md (item G2)
  - docs/solutions/2026-06-30-shelftrack-run-080-g1-g3-coexistence-revalidation.md
  - docs/brainstorms/2026-06-21-g1-risk-tiered-firebreak-brainstorm.md (sibling)
  - docs/brainstorms/2026-06-25-g3-verification-diversity-brainstorm.md (sibling)
feed_forward:
  risk: "The monitor's headline value is EARLY action, but the orchestrator's blocking parallel-wait may only let it consume observations AFTER workers finish/timeout — degrading v1 to post-hoc diagnosis, not early-abort."
  verify_first: true
---

# G2: In-Flight Liveness Monitor for Unattended Autopilot Swarm

## ⚠️ Evidence Check (2026-07-04): Premise Challenged — Decision Needed

Before committing to a plan, OQ#2 ("do workers actually stall?") was resolved with
evidence from prior run reports, solution docs, and `agent-pitfalls.md`. **The
evidence contradicts the design premise below.**

- **Worker mid-flight stalls have never been observed.** Zero failure classes in
  `agent-pitfalls.md` about worker stalls / loops / silent-hangs / the 10-min
  spawn timeout firing. The "empirical-wall" reports (runs 070, 079, 080) are
  workers **self-reporting** a spec/env wall — a report, not silence. A liveness
  monitor adds nothing there; the worker already tells you.
- **The real, recurring in-flight liveness failure is ORCHESTRATOR context
  death** — documented twice (runs **050**, **061**), which a "monitor watching
  workers" does **not** catch. It hits the orchestrator at the tail, not workers
  mid-execution, and already owns an architecture line (`context-window-
  optimization`, `tail-delegation-context-resilience`, `context-death-delegation-
  architecture`; ~16 reports/docs). Run 061's self-audit names the unbuilt next
  step: the **"Tier 2 Pre-Review Resume checkpoint."**

**Implication:** the worker-liveness monitor (Decisions 1–3 below) addresses a
failure with **no observed occurrences**, while the genuine liveness pain sits
elsewhere with an already-identified, unbuilt fix. Building it now risks the
simulation-vs-building trap. **The decisions below are preserved as the pre-
evidence design, but the session should FORK here** (see "Fork" at the bottom)
rather than proceed straight to plan.

## What We're Building

An **in-flight liveness monitor** — the missing Layer-I "AI monitor" from Google
DeepMind's *Three Layers of Agent Security* (item G2, the only ❌ at Layer I after
G1 and G3 closed). It watches worker agents **during** execution, covering the one
failure class the other two layers structurally cannot:

- **G1 (firebreak)** is a deterministic hook that classifies each *tool call*
  (deny-known-bad). It cannot see that a worker is making perfectly-allowed calls
  while making **no progress** — and a stall is the *absence* of a call, which a
  PreToolUse hook (fires only *on* a call) can never detect by itself.
- **G3 (self-audit + disconfirmer)** is a **post-hoc** tail pass. It diagnoses a
  wasted run only after all workers have finished or hit the 10-min timeout.

**The gap G2 fills:** a worker silently spinning, looping the same failed action,
or dying to context death — caught at minute 3, not at the minute-10 timeout.

**The key reframe:** this is *liveness*, not *judgment*. It is deliberately the
**cheapest and most deterministic** monitor possible — progress heuristics over
worktree state and worker activity, with light AI reasoning only on ambiguous
cases, on a **non-Opus** model. That keeps cost low and, critically, **avoids the
monoculture blindness G3 exists to fight** (Opus watching Opus workers).

**In scope:** detecting stalled / looping / context-dead workers in-flight, and
recording structured liveness observations. **Out of scope (this doc):** semantic
drift / off-spec judgment, novel-rogue-action detection (that would reopen the
enumerated-denylist-vs-structural-backstop tar pit — deliberately avoided), and
emergent cross-worker conflict (post-completion cross-worker scan already covers
it). **Explicitly NOT built:** any authority for the monitor to kill a worker,
escalate to a human, or own a PASS/FAIL decision.

### What success looks like (seeds the plan's EARS tests)

- A worker that stops making progress is **flagged in `liveness.md` while the run
  is still in-flight**, with a timestamp and the stall signal — not discovered only
  at the 10-min timeout.
- The monitor **owns no control decision**: it writes observations only. G1 and G3
  behave identically whether the monitor is present or absent (coexistence
  preserved — zero regression to run-080 invariants).
- The monitor's own cost is **bounded and non-Opus**, and it adds **no** new
  outward/control-plane authority to the swarm.
- A false "stall" on a worker that was merely slow does **not** cause any action
  (alert-only → a false positive is a harmless ledger line, not a killed worker).

## Why This Approach

Three decisions, each chosen for lowest blast radius on the proven run-080
pipeline:

- **Job = liveness, not judgment.** Semantic-drift detection is the highest value
  *if it worked*, but it is the most expensive and least reliable AI task and
  duplicates the G3 disconfirmer + assembly contract-check. Liveness is a real,
  currently-uncaught failure that is *mostly deterministic* to detect — the best
  cost/coverage ratio and the natural first payload. (Rejected: novel-rogue
  detection — reopens the denylist tar pit our own notes flag at ~17 churn passes;
  fix the class structurally, don't chase variants with a fuzzy detector.)

- **Authority = alert-only, orchestrator consumes.** The monitor writes
  `liveness.md`; the orchestrator (the existing consumer that already waits on
  workers) decides whether to act. Authority-free → it **cannot** regress G1/G3.
  (Rejected: firebreak-to-human — a stall is wasteful-not-dangerous, so waking a
  human is noise; monitor-kills-worker — grants control authority the identity
  model doesn't allow and could kill mid-cherry-pick.)

- **Vehicle = hybrid heartbeat log + non-Opus sidecar.** The G1 hook (already
  firing on every worker call) emits a per-worker **activity heartbeat** to an
  append-only log — a near-free data spine. A cheap **sidecar agent**, spawned in
  the same parallel message as the workers, **ticks** over the log + worktree state
  and writes `liveness.md`. The sidecar solves "who detects silence"; the heartbeat
  makes observation cheap. (Rejected: sidecar reading worktrees directly every tick
  — costlier, coarser signal; orchestrator-polling — most invasive to the proven
  blocking-wait and carries a feasibility unknown.)

## Key Decisions

1. **Monitor's job:** in-flight **liveness/progress** (stalls, loops, context
   death). NOT semantic drift, NOT novel-rogue, NOT cross-worker conflict.
   ✅ decided
2. **Authority:** **alert-only**, orchestrator consumes; no kill, no human
   escalation, no PASS/FAIL ownership in v1. ✅ decided
3. **Observation vehicle:** **hybrid** — G1 hook emits per-worker heartbeat log +
   **non-Opus** sidecar poller writes `docs/reports/<run-id>/liveness.md`.
   ✅ decided

### Must-not-regress invariants (run-080 coexistence)

The monitor is additive and must leave every G1/G3 invariant untouched:

- Firebreak classifier stays **deny-known-bad** and **identity-based** — no
  worker-monitoring exception weakens it.
- `TRUSTED_PIPELINE_SCRIPTS` stays a **narrow basename-match allowlist** (currently
  `verify_delegated_status.py`, `check_spec_provenance.py`,
  `firebreak-activate.py`). Any liveness helper script that must run under the
  firebreak is a **deliberate, reviewed** addition — not a blanket "monitor may run
  code" carve-out.
- `self-audit-reviewer` stays **model: sonnet**; Gate 8 stays **fail-closed +
  literal-token**, no binding LLM verdict.
- **Single-command Bash** rule holds (no `&&`/`;`/loops) — the sidecar's tick uses
  individual Bash calls.
- **Phase-report STATUS-on-line-1** contract holds; `liveness.md` is an
  *observation* artifact, not a STATUS-gated report.
- **Build namespace convention** (FC59) — the monitor writes only under
  `docs/reports/<run-id>/`, never a shared app namespace.

## Resolved Questions

1. **Should the monitor judge correctness (semantic drift)?** ✅ **No — v1 is
   liveness only.** Semantic judgment is deferred as a *possible later layer on the
   same vehicle*, gated on evidence it pays for its cost. (Decided 2026-07-04.)
2. **Should the monitor be able to act on a worker?** ✅ **No.** Alert-only; the
   orchestrator is the sole actor. This is what guarantees zero G1/G3 regression.
   (Decided 2026-07-04.)
3. **Extra sidecar agent vs. no new agent?** ✅ **Sidecar** — it cleanly solves the
   "who detects silence" tick problem without restructuring the proven orchestrator
   wait. (Decided 2026-07-04.)

## Open Questions (deferred to plan phase)

1. **[VERIFY FIRST] Does the orchestrator's blocking parallel-wait allow mid-flight
   consumption + early abort?** The monitor's headline value is *early* action. If
   the orchestrator can only read `liveness.md` **after** its blocking wait returns
   (workers finished/timed-out), v1 degrades to **post-hoc diagnosis** — still
   useful as observability, but it does NOT save the wasted time. The plan must
   establish the Agent-tool wait semantics before promising early-abort. See
   Feed-Forward.
2. ~~**[VERIFY FIRST] Do workers actually stall often enough to justify G2 now?**~~
   **✅ RESOLVED 2026-07-04 — NO (see Evidence Check at top).** No observed worker
   stalls in any run; the real liveness failure is orchestrator context death,
   which this design does not catch. This is the fork trigger.
3. **Sidecar identity under the firebreak.** Is the sidecar a governed "worker"
   (writes `liveness.md` = an in-repo report write = GREEN; git-status reads =
   GREEN — likely fits with no carve-out) or does it need a narrow trusted
   identity like `swarm-runner`/`tail-runner`? Prefer *no* carve-out if governance
   already permits its actions.
4. **Heartbeat emission mechanism.** Can the G1 hook append a per-worker activity
   line to a log as a side-effect of classification without itself becoming a
   governed/deferred action, and without violating single-command Bash? Confirm the
   hook (harness-level infra, not a worker) can write the log directly.
5. **Stall heuristic + thresholds.** What deterministic signals define a stall
   (no new commit in N min? no heartbeat in N sec? same failed Bash ≥K times?) and
   what are the thresholds — tuned to avoid false positives on legitimately slow
   workers. Where does the light AI pass enter (ambiguous cases only)?
6. **Sidecar model + cost ceiling.** Haiku vs. Sonnet for the tick loop, and a
   hard cost/tick-count ceiling so the monitor can't itself become the expensive
   thing it's guarding against.

## Fork (post-evidence, 2026-07-04)

The Evidence Check invalidated the worker-liveness premise. Four honest paths:

1. **Pivot G2 → orchestrator context-budget watchdog / "Tier 2 Pre-Review Resume
   checkpoint."** Targets the *evidenced* liveness failure (runs 050, 061). Caveat:
   overlaps the existing context-death architecture line and is arguably a
   self-monitoring/checkpoint problem, not a DeepMind-style "AI monitor watching an
   agent" — so it partly drifts from the G2 governance framing. Likely a
   continuation of that line, not a fresh G2.
2. **Re-aim G2 at the failure workers DO have: cross-worker semantic/contract
   divergence** (FC1 name divergence et al. — `agent-pitfalls.md` is full of these;
   the cross-worker-scan exists *because* this is real). This was scoped out of v1
   as expensive/duplicative of G3 + assembly, but it is the real worker-level
   failure. Reopening it means confronting the cost/monoculture concerns head-on.
3. **Shelve G2, redirect the session** to a higher-leverage item the handoff already
   names: `[080-W2, HIGH]` (artifact-back the "0 P1" review verdict) or the master
   declutter. Respects YAGNI — don't build a monitor for a never-observed failure.
4. **Build G2 anyway as thin defense-in-depth** (heartbeat log only, no sidecar),
   accepting it guards a rare failure, purely to close the last Layer-I ❌ on the
   governance scorecard. Lowest value; only justified if scorecard completeness is
   itself the goal.

**Recommendation:** #3 or #1. #3 if the goal is shipping value this session (the
evidenced pain isn't what G2-as-scoped builds); #1 if you want to actually attack
the real liveness failure and are willing to treat it as a context-death-line
continuation rather than a clean G2. Avoid #4 (simulation-vs-building trap) and
defer #2 until there's appetite for the cost/monoculture fight.

## Feed-Forward

- **Hardest decision:** liveness vs. semantic-drift as the monitor's job. Semantic
  drift is the higher-ceiling capability, but it is expensive, unreliable, and
  duplicates G3 + assembly checks. Chose liveness because it is a *real,
  currently-uncaught* failure that is cheap and mostly-deterministic to detect —
  the best cost/coverage ratio and the vehicle that later semantic checks can build
  on. (Confidence ~70%; the gating unknown is stall frequency — OQ #2.)
- **Rejected alternatives:** novel-rogue detection (reopens the
  enumerated-denylist-vs-structural-backstop tar pit — ~85% confidence this is the
  right avoid); monitor-kills-worker (grants control authority the identity model
  forbids); orchestrator-polling vehicle (most invasive to the proven wait);
  Opus sidecar (reintroduces the exact monoculture G3 fights).
- **Least confident:** Whether the orchestrator's **blocking parallel-wait can
  consume liveness observations and abort a stalled worker mid-flight** (OQ #1). If
  it cannot, the monitor's headline "early action" value collapses to post-hoc
  diagnosis. **This must be verified first in the plan phase** — it determines
  whether G2 delivers early-abort or only observability, and therefore whether it's
  worth building over the other deferred items.
