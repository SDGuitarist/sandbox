---
title: "Orchestration-Hardening Fixture Suite: a guard-firing regression net that refuses to test a copy"
date: 2026-06-09
type: solution
project: sandbox
phase: compound
tags: [autopilot, swarm, fixtures, regression-net, eval-harness, FC50, FC52, spec-completeness, spec-eval, share-not-fork, honesty-contract, fail-closed, verify-first-spike]
related_plan: docs/plans/2026-06-08-feat-hardening-fixture-suite-plan.md
related_proposal: docs/proposals/validate-hardening-on-fixtures.md
builds_on:
  - docs/solutions/2026-06-07-autopilot-orchestration-hardening.md
  - docs/solutions/2026-06-08-film-production-pm-run-070-swarm-build.md
failure_classes: [FC50, FC51, FC52]
commits: "feat/film-production-pm 787f2fb..8dca4b5 (15 commits)"
feed_forward:
  risk: "The live SKILL.md Step 9w.9.5 rewire (gate now CALLS tools/check_spec_provenance.py) is proven by F-D1 in isolation but has NEVER run inside a real swarm — the agent→CLI wiring is deterministic on the bench but un-exercised end-to-end."
  verify_first: true
---

# Orchestration-Hardening Fixture Suite

## Problem

The autopilot orchestration hardening (Tracks A/B/C, post-Run-069) was
**reviewed but not field-proven on a live build**. Run 070 then spent ~2.5M
tokens / ~70 min trying to validate all three tracks on a real app — and
**never exercised Track B (FC50)**: Film PM's cross-boundary calls were all
model-layer and already pinned, so the unpinned-orchestration-entrypoint failure
mode could not even occur. Track B stayed the one unproven track, and it gates a
confident merge of the hardening to master.

Worse, "validate on a real build" is the wrong instrument: it relies on an app
*incidentally* tripping a guard rather than *deliberately* triggering it (the M4
finding). The fix is a **negative-test fixture suite** — each fixture engineers a
broken input and asserts the corresponding shipped guard FIRES — for a fraction
of the cost, breaking the self-validation circularity and leaving a regression
net re-run on every future hardening edit.

The deepest trap, flagged in the plan's Feed-Forward and confirmed real by the
deepen pass: **a fixture that tests a Python *reimplementation* of a guard proves
nothing about the guard the pipeline runs.** That is FC52/M1 (gate-vs-use
artifact drift) reborn *inside the validator*. So the design problem was not
"write fixtures" — it was "drive the SAME artifact the autopilot invokes, in
isolation, against a crafted input, and label honestly when you can't."

## Solution

`eval-harness/validate_hardening.py` (a runner) + `eval-harness/fixtures/`
(crafted broken inputs) + one shared shipped detector extracted from the gate.
Five fixtures across four tracks, each labelled by the fidelity its invocation
actually earned.

### The fidelity vocabulary (the honesty contract, M6)

The matrix carries two axes. The fidelity axis may hold **only** these four
values, and a row never rounds up to a stronger one:

| Label | Meaning |
|-------|---------|
| `EXERCISED` | Drove the shipped artifact itself (e.g. invoked the real agent / shipped script). |
| `SPIKE-VALIDATED` | Ran an existing spike *copy* of the recipe, not the ship. |
| `PROSE-ASSERTED` | Checked an orchestrator-prose contract; no executable guard exists. |
| `MIRRORED` | Ran a Python *reimplementation* — last resort, NEVER conflated with `EXERCISED`. |

Second axis: `PASSED | FAILED`. A track with no fixture earns no fidelity — its
cell is `—` (a no-result sentinel) and its coverage provenance (`FIELD+SPIKE`)
lives in the evidence column. **`FIELD+SPIKE` is provenance, not a fifth fidelity
label — it never appears in the fidelity column.**

### What got built

| Fixture | Track | Fidelity | What it proves |
|---------|-------|----------|----------------|
| **F-B1** | B (FC50) | `EXERCISED` | Real `spec-completeness-checker` agent FAILs on an unpinned orchestration entrypoint, naming the symbol. **The merge-blocking proof.** |
| **F-B2** | B (FC50 false-N/A) | `EXERCISED` | Real agent returns `N/A` on a *wholly-omitted* entrypoint — the honest blind spot, not a false PASS. Backstop is `PROSE-ASSERTED`. |
| **F-D1** | FC52 | `EXERCISED` | Shipped `tools/check_spec_provenance.py` detects spec drift (exit 3) + identical-spec control (exit 0). Detection only; repair is out of scope. |
| **F-C1** | C | `PROSE-ASSERTED` (L2) / `EXERCISED` (L1, opt-in) | Advisory-demotion contract (always) + real spec-eval scorer (`--with-api`). |
| **Track A** | A (FC51) | `—` (not fixtured) | **P-accept.** Cherry-pick assembly is agent-prose; coverage = `FIELD+SPIKE` (runs 069/070 + spikes). |

### Share-not-fork extraction (the FC52 detector)

The one live shipped change. Step 9w.9.5 previously *inlined* the spec-provenance
SHA compare as `git rev-parse` prose. To let F-D1 exercise it for real without
forking, the compare was extracted into `tools/check_spec_provenance.py` — a
single ~120-line script with documented exit codes — and **SKILL.md Step 9w.9.5
was rewired to CALL it.** Now there is exactly ONE implementation of the compare:
the gate calls it, the fixture calls it. There is no second copy that can drift.
Behavior is identical (detection only; the inline-injection *repair* stays agent
judgment). This is the literal antidote to the drift trap — the suite would have
reproduced FC52 had it tested a reimplementation.

### Opt-in API fixtures (hermetic by default)

The default run is honestly **not fully hermetic** — F-B1 and F-B2 each invoke
the real checker agent (two bounded network/token calls), because the *only*
faithful way to exercise an agent-prose guard is to run the agent. But the
expensive, less-deterministic layer is gated: F-C1 layer 1 (the spec-eval LLM
scorer) runs ONLY under `--with-api`. Without it, F-C1 asserts just the
deterministic advisory contract. Truly zero-cost subsets exist (`--fixture F-D1`,
`--fixture F-C1` without `--with-api`). Cost is disclosed in the README, not
hidden.

### Fail-closed over silent fallback (Codex R2/R3)

F-C1 validates the scorer's JSON `status` against the shipped `GateStatus` enum —
itself a share-not-fork read (`from models import GateStatus`), so the valid set
can't drift from the scorer. Three rounds hardened the failure semantics:

- **R1** — a scorer that runs but produces no verdict is surfaced as a
  `SCORER_DEFECT` that FAILS the fixture, no longer hidden as `INCONCLUSIVE`.
- **R2** — an unrecognized/non-string status is schema drift (a defect), and the
  schema-drift *defense must not itself crash* on drifted data.
- **R3** — two fail-closed moves: (a) a scorer **TIMEOUT is its own FAILING
  class** (a hang ≠ an environment miss; it can no longer pass under `--with-api`
  as "environment"); (b) `_valid_gate_statuses()` **dropped its silent fallback**
  to a hardcoded copy — if the shipped enum can't be imported it RAISES and the
  caller fails closed visibly, rather than quietly validating against a stale set.
  The valid set is now resolved *before* spending an API call.

## Key Lessons

1. **Fixturing agent-prose guards means making them callable first — or labelling
   honestly that you didn't.** The deepen pass found that most hardening guards
   are LLM-orchestration prose, not callable code. Only Track B (invoke the real
   agent), the FC52 SHA-detection (extractable), and the spec-eval scorer were
   exercisable-as-shipped. "Fixture the guards" partly meant "make the guards
   callable." The honest resolution per guard: **invoke the real agent (FC50),
   share-not-fork extract (FC52), or admit field+spike coverage with no fidelity
   claim (Track A)** — never a Python mirror.

2. **The honesty label is the product, not a footnote.** A green suite that
   rounds a spike/prose/mirror up to `EXERCISED` is *worse* than no suite — it
   manufactures false confidence in exactly the place the hardening exists to
   protect. The four-value vocabulary with a no-rounding rule, and the `—`
   sentinel + `FIELD+SPIKE` provenance note for unfixtured tracks, is what keeps
   the matrix trustworthy. A coverage note is not a fidelity label; conflating
   them is the same category error as testing a copy.

3. **Share-not-fork is the only extraction that's allowed to touch a live gate.**
   When a guard must become callable to be testable, the refactor must keep the
   agent as the SINGLE caller of one shared function — the fixture calls the same
   function. The moment the fixture gets its *own* copy (a fork, a mirror, a
   spike), it can pass while the ship drifts. FC52's extraction (one detector,
   two callers) is the pattern; `P-promote` (promote the spike) was rejected
   precisely because a spike is a second copy.

4. **Fail-closed beats silent fallback when validating against a shipped
   artifact.** Every place the suite reads a shipped contract (the `GateStatus`
   enum) it now refuses to substitute a hardcoded copy on import failure — it
   raises and surfaces. A silent fallback would let the validator drift from the
   thing it validates, recreating the bug class. A hang, likewise, is a failure,
   not an environment excuse. "Visible defect" always beats "quiet pass."

5. **A negative-test fixture is the right instrument when a real build won't
   reliably trip the guard.** Run 070's ~2.5M-token real-build "validation"
   never exercised Track B because the app happened not to contain the failure
   shape. An engineered trigger proves the guard fires deterministically, for two
   agent calls instead of a full swarm, and keeps proving it on every future
   edit. Reserve validate-on-real-build for *integration* questions a fixture
   can't reach (e.g. the agent→CLI wiring under a live swarm — see Remaining gate).

## Validation

- Full default run: **A** `—`/NOT FIXTURED, **B** `EXERCISED`/PASSED, **C**
  `PROSE-ASSERTED`/PASSED, **FC52** `EXERCISED`/PASSED. Exit 0.
- F-B1: real `spec-completeness-checker` report line-1 `STATUS: FAIL` naming the
  unpinned symbol (the assertion targets the FC50 surface, not any FAIL — `ce99187`).
- F-B2: real agent `N/A` on the omitted entrypoint (honest blind spot).
- F-D1: shipped `tools/check_spec_provenance.py` exit 3 on drift, exit 0 on the
  identical-spec control.
- F-C1: advisory prose asserted always; real `--with-api` scorer run still
  `EXERCISED` (verdict FAIL). Unit-tested: valid set == shipped enum; status
  valid/invalid/non-string; run policy (EXERCISED/ENV pass, SCORER_DEFECT/TIMEOUT
  fail); enum-unavailable → fail-closed.
- Codex binding review: **3 rounds applied** (R1 scorer-defect surfacing + Track
  A out of the fidelity column; R2 enum validation + crash-proofing; R3 timeout
  fails + no silent fallback). R3 (`1d6ac07..8dca4b5`) not yet re-reviewed —
  operator opted to proceed.

## Remaining gate

**The live SKILL.md Step 9w.9.5 rewire is un-exercised end-to-end.** F-D1 proves
`tools/check_spec_provenance.py` detects drift in isolation, but no real swarm has
run with the gate CALLING it. The agent→CLI wiring is deterministic on the bench;
its first real-swarm invocation is the proof. This is the highest residual risk —
see Feed-Forward.

## Feed-Forward

- **Hardest decision:** per guard, invoke the real shipped artifact vs. extract a
  shared callable. Resolved by fidelity: invoke the real agent for FC50
  (F-B1/F-B2); share-not-fork extract for FC52 (F-D1); decline to fixture Track A
  (agent-prose, field+spike-covered) rather than ship a hollow `SPIKE-VALIDATED`
  row. Never a Python mirror.
- **Rejected alternatives:** (a) another validate-on-real-build (the M4 instrument
  failure — incidental triggers, ~2.5M tokens for weak evidence); (b)
  reimplementing each gate in Python for clean determinism (the drift trap —
  validates a copy); (c) `P-promote` for Track A (a spike is a copy of the recipe;
  a green spike row wouldn't catch ship-prose drift, the very thing the suite
  exists to catch); (d) hiding API cost / silent enum fallback (fail-closed +
  disclosed instead).
- **Least confident:** the live SKILL 9w.9.5 agent→CLI wiring under a real swarm.
  Deterministic in isolation (F-D1), un-exercised end-to-end. First real swarm on
  this branch is the proof.

## Follow-ups

- **Deferred — Track A `P-extract`:** refactor `swarm-runner.md:76-138`
  cherry-pick prose into a shared callable so Track A earns a real `EXERCISED`
  row; its own real-build validation required. (Carried in HANDOFF.md.)
- **Deferred — real-swarm check of the 9w.9.5 rewire** (the Remaining gate).
- **Deferred — Codex pass on R3** (`1d6ac07..8dca4b5`), optional pre-merge.
- **Adoption decision (operator):** wiring the suite into the autopilot pipeline
  as a blocking gate is proposal step 3, out of this scope.
