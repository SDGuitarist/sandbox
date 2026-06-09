---
title: "Orchestration-Hardening Fixture Suite (decisive Track-B proof + regression net)"
type: feat
status: active
date: 2026-06-08
swarm: false
autonomy_class: manual
tech_stack: Python (eval-harness/) + git scenarios; exercises .claude/ gates & assembly
origin: docs/proposals/validate-hardening-on-fixtures.md (M4/M5/M13); run-070 meta-analysis
feed_forward:
  risk: "The whole point is to exercise the REAL guard, not a copy. The deepest trap is re-implementing a gate's logic in the fixture (e.g. rewriting Check 1b in Python) — that creates a SECOND implementation that can drift from the agent the pipeline actually runs, which is FC52/M1 (gate/use artifact-identity drift) reborn inside the validator itself. A fixture that passes against a reimplementation proves nothing about the shipped gate. The ONE unknown gating any code: can each guard be driven against a crafted fixture input IN ISOLATION while still being the SAME artifact the autopilot invokes? Resolve in a Phase-0 spike per guard BEFORE building fixtures. Secondary: F-A1/F-A2/F-D1 are git-mechanics and genuinely deterministic; F-B1/F-B2 invoke the structural Check 1b; F-C1 invokes an LLM judge — the suite must report EXERCISED-vs-PASSED per track honestly (M6) and never claim determinism it doesn't have."
  verify_first: true
---

# Orchestration-Hardening Fixture Suite

## Why this exists (the one-paragraph case)

Run 070 spent ~2.5M tokens / ~70 min to "validate" orchestration-hardening Tracks
A/B/C on a real app — and **never exercised Track B** (Film PM's cross-boundary
calls were all model-layer, already pinned, so the FC50 failure mode could not
occur; M4). Track B is the only track still unproven, and it gates a confident
merge of the hardening to master. A deterministic fixture suite with *engineered*
triggers proves each guard FIRES for a fraction of the cost, breaks the
self-validation circularity (M5), and becomes a regression net re-run on every
future hardening edit. Source proposal: `docs/proposals/validate-hardening-on-fixtures.md`.

## The four-question quality gate

**1. What exactly is changing?**
A new `eval-harness/fixtures/` package plus a `validate_hardening.py` entry point.
It adds *negative-test fixtures* — each sets up a deliberately broken input and
asserts the corresponding shipped guard catches it — and emits a per-track
`EXERCISED / PASSED` matrix. Six fixtures (proposal table): F-A1, F-A2, F-B1,
F-B2, F-C1, F-D1. Nothing in the autopilot pipeline's behavior changes.

**2. What must NOT change?**
- The shipped guards themselves (`spec-completeness-checker` Check 1b,
  `swarm-runner` cherry-pick assembly + ownership gate, Step 9w.9.5 provenance
  gate, `spec_eval_gate.py`, CLAUDE.md). Fixtures EXERCISE them read-only; they do
  not edit gate logic. (One *permitted* exception, gated on the Phase-0 spike: if a
  guard cannot be invoked in isolation, refactor it so the agent and the fixture
  call ONE shared function — see Risk. This is the only change to a live gate, and
  it must keep the agent as the single caller, not a fork.)
- The validated hardening on `0d36a24` (the merge source). This plan adds a
  validator; it does not touch what is being validated.
- No real swarm build is run. Fixtures are git + parser mechanics + at most one
  agent/LLM call each.

**3. How will we know it worked?** → see `## Acceptance Tests` (EARS). Headline:
F-B1 makes the spec-completeness gate FAIL on an unpinned orchestration entrypoint,
turning Track B from "present but unexercised" into "fixture-proven."

**4. What is the most likely way this plan is wrong?**
That a fixture silently tests a *reimplementation* of a guard rather than the guard
the pipeline runs (the Feed-Forward risk). Mitigation is structural: Phase 0 proves
each guard is invoked as the same artifact, and the matrix labels any fixture whose
guard is a Python mirror (not the shipped agent) as `MIRRORED` — never `EXERCISED`.

## Grounding (verified against the repo, not assumed)

- `eval-harness/` is a real Python package (`parser.py`, `scorer.py`,
  `spec_eval_gate.py`, `runner.py`, `reporter.py`, `requirements.txt`, `.venv`
  convention). The fixture suite lives here.
- `spec-completeness-checker.md` **Check 1b is deterministic structural logic**
  (`spec-completeness-checker.md:85-106`): parse the Export Names Table; for each
  row whose Type is exactly `orchestration entrypoint` (case-insensitive, trimmed),
  the `Full Signature` cell must be non-empty/non-placeholder, else **FAIL naming
  the symbol**; zero such rows ⇒ **N/A**. This is implementable as a pure function —
  which is exactly why the drift trap is real (don't fork it; share it).
- `tools/verify_delegated_status.py` exists — precedent for standalone Python that
  drives a pipeline mechanic.
- Track A assembly recipe (per-COMPLETED-worker `git cherry-pick $(git merge-base
  <original_branch> <branch>)..<branch>`; conflict ⇒ `assembly-ownership-conflict:`
  abort) is **agent-prose inside `swarm-runner.md` Step 3 (lines 76-138)** — executed
  by the swarm-runner LLM, NOT callable infrastructure (corrected by the deepen pass;
  see below). The three-dot ownership gate (`git diff --name-only
  <original_branch>...<branch>`, `SKILL.md` Step 10.5w:773) is orchestrator-inline
  Bash — callable but not a reusable function.

## Deepening findings (2026-06-08, plan-flow deepen pass — 3 parallel code-grounded agents)

The plan's central assumption ("each guard can be driven against a fixture as the
SHIPPED artifact") was tested against the real code. **Result: only Track B is cleanly
exercisable-as-shipped today.** Most hardening guards are LLM-orchestration prose, not
callable code — which means the Feed-Forward "least confident" risk is CONFIRMED REAL
for Tracks A, C, and the FC52 repair. Callability matrix:

| Guard (fixture) | What's shipped | Exercisable as-shipped? | Path |
|---|---|---|---|
| **Check 1b / FC50 (F-B1, F-B2)** | agent-prose in `spec-completeness-checker.md:85-109`; STATUS on line 1 of its report | **YES — invoke the real agent** on a tiny fixture spec, read the STATUS line (~60s, 1 agent call). Proven in prod (runs 069/070). `extractor.py:_parse_markdown_table` exists but a Python reimpl of 1b = a FORK (drift) — rejected. | invoke real agent |
| **spec_eval scorer / Track C (F-C1)** | `spec_eval_gate.py` real CLI: `python -m eval_harness.spec_eval_gate <spec> [opts]` | **PARTIAL.** The SCRIPT blocks (exit 1 on FAIL/WARN_UNSCORABLE). Its "advisory/non-blocking" property lives in the SKILL **Step 9w.8 wrapper**, not the script. So a fixture can exercise the scorer (verdict + exit code) but the *non-blocking* behavior under test is orchestrator-prose. | scorer: callable; non-block: prose |
| **FC52 provenance (F-D1)** | `SKILL.md` Step 9w.9.5: SHA-blob compare (`git rev-parse <branch>:<spec>` both sides) + LLM repair (inline-inject spec into briefs). No `tools/check_spec_provenance.py`. | **DETECTION yes** (the SHA compare is ~3 callable lines, trivially extractable); **REPAIR no** (agent judgment). Fixture exercises detection only. | extract detection (small) |
| **Track A assembly + conflict (F-A1, F-A2)** | agent-prose in `swarm-runner.md:76-138`; executed by swarm-runner LLM | **NO** — not callable. BUT spike scripts already exist and demonstrate the behavior: `docs/reports/orchestration-hardening/spike-worktree-base.sh` and `spike-conflict.sh`. | extract OR promote spikes |

**The meta-finding (surface to operator).** "Fixture the guards" turns out to partly
mean "make the guards callable first." The hardening is mostly agent instructions, so
genuine ship-exercising fixtures for Track A require a **share-not-fork extraction**
(pull the cherry-pick/abort flow into e.g. `tools/assembly_worker.py` that the
swarm-runner agent then CALLS, and the fixture calls too) — a real refactor of shipped
hardening, larger than "write a fixture." Three honest paths for the non-Track-B
guards, for the operator to choose (does NOT block Track B):
- **(P-extract)** Refactor Track A + FC52-detection into shared callable functions →
  agents call them, fixtures call them. Zero drift, fully testable, biggest scope.
- **(P-promote)** Promote the EXISTING spike scripts into a maintained regression
  fixture for Track A, labelled `SPIKE-VALIDATED` (honestly NOT `EXERCISED`, since a
  spike is a copy of the recipe, not the ship). Cheapest; accepts mild drift risk.
- **(P-accept)** Leave Track A/C as one-time spike-validated + field-proven (runs
  069/070); fixture only the cleanly-testable slices (B, FC52-detection, scorer).

## Build sequence (phased; each phase ships independently)

### Phase 0 — Verify-first spike (LARGELY PRE-RESOLVED by the deepen pass)
The deepen pass already answered "invoked-as-shipped: yes/no" per guard (see the
callability matrix above). Phase 0 now reduces to one operator decision plus two small
confirmations:
- **Operator decision (gates Phase 2 only):** choose **P-extract / P-promote / P-accept**
  for Track A + FC52-repair (see meta-finding above). This does NOT gate Track B.
- **Confirm (small):** (a) the real `spec-completeness-checker` agent returns
  `STATUS: FAIL` on the F-B1 fixture spec and `N/A`/PASS on F-B2 (one agent call each);
  (b) the FC52 SHA-compare extracts cleanly into a ~3-line callable.
- Output: the one-page note at `docs/reports/hardening-fixtures/spike.md` recording the
  matrix (done above) + the chosen Phase-2 path. The Feed-Forward risk is now RESOLVED,
  not open.

### Phase 1 — MVP: Track-B proof + runner (unblocks the merge)
- `eval-harness/fixtures/` scaffold + `validate_hardening.py` runner that discovers
  fixtures, runs each, and prints the per-track matrix. Fidelity label vocabulary
  (honesty contract, M6): `EXERCISED` (drove the shipped artifact) | `SPIKE-VALIDATED`
  (ran an existing spike copy) | `PROSE-ASSERTED` (checked an orchestrator-prose
  contract, no executable guard) | `MIRRORED` (ran a Python reimplementation — a
  last resort, never conflated with EXERCISED). Second axis: `PASSED | FAILED`.
- **F-B1** (Track B FC50 guard): a ~30-line fixture spec with one genuine
  route→orchestration call declared as an `orchestration entrypoint` row with an
  EMPTY `Full Signature`. The runner **invokes the real `spec-completeness-checker`
  agent** on this spec and asserts its report STATUS line is `FAIL` naming the symbol
  (exercises the ship, no reimplementation). ← the decisive Track-B evidence.
- Matrix output for Track B: `EXERCISED ✓ / PASSED ✓` (real agent, not a mirror).

### Phase 2 — Track A + FC52 (GATED on the Phase-0 P-extract/P-promote/P-accept choice)
Per the deepen pass, Track A is agent-prose, so these fixtures' fidelity depends on the
chosen path. Build accordingly:
- **F-A1** (FC51 cherry-pick): temp repo, feature branch + orphan commit on default
  branch (divergent base), 1–2 worker branches. Run the merge-base cherry-pick recipe;
  assert assembly clean, per-worker base == `merge-base`, no commit dropped. Under
  **P-extract** this calls the extracted `tools/assembly_worker.py` (labelled
  `EXERCISED`); under **P-promote** it wraps the existing `spike-worktree-base.sh`
  (labelled `SPIKE-VALIDATED`).
- **F-A2** (FC51 hidden dep): two worker branches touching the SAME file → assert abort
  with `assembly-ownership-conflict:`. Same P-extract/P-promote labelling; the existing
  `spike-conflict.sh` is the P-promote source.
- **F-D1** (FC52 provenance — DETECTION only): worktree-base spec deliberately diverged
  from the gated spec. Run the extracted SHA-blob compare; assert it reports divergence
  before "spawn." The LLM **repair** (inline-inject) is agent judgment and is OUT of
  fixture scope — the fixture asserts detection fires, not that repair is correct.

### Phase 3 — Completeness (blind-spot + advisory documentation)
- **F-B2** (FC50 false-N/A): a spec with ZERO orchestration-entrypoint rows but a
  real route→module call in fixture code. Assert gate returns N/A AND the assembly
  contract-check backstops it. Documents the known blind spot honestly.
- **F-C1** (Track C advisory) — TWO-LAYER, per the deepen pass: (layer 1, callable)
  invoke `python -m eval_harness.spec_eval_gate <vague-spec>` and assert it produces a
  verdict + JSON report (the scorer runs). (layer 2, the actual demotion) assert the
  SKILL **Step 9w.8 wrapper** treats a non-PASS exit as advisory and proceeds — note
  this property is orchestrator-prose, so the fixture can only assert it by checking the
  Step 9w.8 contract text / a wrapper shim, NOT the `spec_eval_gate.py` exit code (which
  still blocks). Label Track C `EXERCISED` for layer 1, `PROSE-ASSERTED` for layer 2.

## Acceptance Tests (EARS)

### Happy path
- WHEN F-B1 runs against the spec with an unpinned orchestration entrypoint THE
  SYSTEM SHALL report Track B `EXERCISED` and the gate verdict `FAIL` naming the
  symbol.
  - Verify: `eval-harness/.venv/bin/python eval-harness/validate_hardening.py --fixture F-B1` — the spec-completeness-checker report's line-1 STATUS is `FAIL` naming the symbol; runner matrix row `B | EXERCISED | PASSED`.
- WHEN F-A1 runs with a divergent-base scenario THE SYSTEM SHALL assemble cleanly
  with each worker's cherry-pick base equal to `merge-base(original_branch, branch)`.
  - Verify: `... validate_hardening.py --fixture F-A1` — matrix row `A | EXERCISED|SPIKE-VALIDATED | PASSED` (label per the chosen Phase-2 path); log shows per-worker base == merge-base.
- WHEN F-A2 runs with two workers owning the same file THE SYSTEM SHALL abort
  assembly with `assembly-ownership-conflict:`.
  - Verify: `... --fixture F-A2` — output contains `assembly-ownership-conflict:`.
- WHEN F-D1 runs with a diverged worktree spec THE SYSTEM SHALL detect the
  divergence before spawn.
  - Verify: `... --fixture F-D1` — provenance check reports the diff; matrix `FC52 | EXERCISED | PASSED`.
- WHEN the full suite runs THE SYSTEM SHALL emit a per-track EXERCISED/PASSED matrix
  distinguishing exercised guards from mirrored ones.
  - Verify: `... validate_hardening.py` — prints a 4-row (A/B/C/FC52) matrix.

### Error / honesty cases
- WHEN a fixture's guard is a Python mirror rather than the shipped artifact THE
  SYSTEM SHALL label that track `MIRRORED`, never `EXERCISED`.
  - Verify: grep the matrix output for `MIRRORED` when invocation method (ii) is used.
- WHEN F-B2 runs (zero entrypoint rows, real call exists) THE SYSTEM SHALL return
  gate verdict `N/A` and assert the contract-check backstop, NOT a false PASS.
  - Verify: `... --fixture F-B2` — verdict `N/A`; matrix notes the backstop.
- WHEN F-C1 runs a vague claim THE SYSTEM SHALL produce a scorer verdict (layer 1) AND
  assert the Step 9w.8 wrapper's non-blocking contract (layer 2).
  - Verify: `... --fixture F-C1` — `spec_eval_gate.py` emits a JSON report + verdict (note: the SCRIPT exits non-zero on non-PASS — that is expected; the demotion is in the 9w.8 wrapper, which the fixture asserts via the wrapper contract/shim, labelled `PROSE-ASSERTED`).
- WHEN any fixture's expected verdict does not occur THE SYSTEM SHALL exit non-zero
  and name the failing fixture.
  - Verify: temporarily pin F-B1's signature → suite reports `B | EXERCISED | FAILED`.

## Scope fence
- IN: the six fixtures, the runner, the EXERCISED/PASSED matrix, the Phase-0 spike note.
- OUT: changing any shipped guard's behavior (except the single permitted
  share-not-fork refactor if Phase 0 requires it); running a real swarm build;
  wiring the suite into the autopilot pipeline as a blocking gate (that is a
  follow-on adoption decision — proposal step 3 — and an operator call).

## Feed-Forward
- **Hardest decision:** whether to invoke the real shipped gate (true guard-proof,
  but LLM for Check 1b) or extract a shared deterministic function (zero drift, but
  one live-gate refactor). Resolved by deferring to a Phase-0 spike per guard, with
  the default being "invoke the real artifact" and extraction allowed only as a
  share-not-fork refactor — because a fixture that tests a copy reproduces the exact
  FC52/M1 drift the hardening exists to kill.
- **Rejected alternatives:** (a) another validate-on-real-build — rejected as the M4
  instrument failure (incidental, not designed, triggers; ~2.5M tokens for weak
  evidence); (b) reimplementing each gate in Python for clean determinism — rejected
  as the drift trap (validates a copy, not the ship); (c) MVP = all six fixtures —
  descoped to F-B1-first because Track B is the only merge-blocking gap.
- **Least confident → NOW RESOLVED by the deepen pass.** The open question was whether
  F-A1/F-A2/F-D1 could drive the *actual* code paths. Answer: **no** — Track A assembly
  + conflict are agent-prose (`swarm-runner.md:76-138`), the FC52 repair is agent
  judgment, and even Track C's "advisory" property is orchestrator-prose (the
  `spec_eval_gate.py` script itself blocks). Only Track B (via invoking the real agent),
  the FC52 SHA-detection, and the spec-eval scorer are exercisable-as-shipped. So the
  residual uncertainty is no longer technical — it is the operator's **P-extract /
  P-promote / P-accept** choice for Track A (refactor for true fidelity vs promote the
  existing spikes vs accept field+spike validation). Track B (the merge-blocker) is
  unaffected and clean.

## Codex handoff prompt

> Review `docs/plans/2026-06-08-feat-hardening-fixture-suite-plan.md` against
> `docs/proposals/validate-hardening-on-fixtures.md` and the shipped guards
> (`.claude/agents/spec-completeness-checker.md` Check 1b:85-109;
> `.claude/agents/swarm-runner.md:76-138` cherry-pick assembly + `assembly-ownership-conflict`;
> autopilot `SKILL.md` Step 9w.9.5 provenance gate + Step 9w.8 spec-eval wrapper;
> `eval-harness/spec_eval_gate.py`). A plan-flow deepen pass already established the
> "Deepening findings" callability matrix (most guards are agent-prose, only Track B is
> cleanly exercisable-as-shipped). **Pressure-test two things specifically:**
> (1) Is the deepen matrix CORRECT? Verify each row against the cited lines — especially
> the claim that Track A assembly/abort is agent-prose-only and that Track C's advisory
> property lives in the 9w.8 wrapper not `spec_eval_gate.py`. Flag any miscategorization.
> (2) Is the **P-extract / P-promote / P-accept** framing for Track A sound, and is the
> EXERCISED / SPIKE-VALIDATED / PROSE-ASSERTED labelling honest (does it ever let a
> mirror or spike be reported as EXERCISED)? Then confirm the Phase-1 MVP (F-B1 via the
> real agent) is genuinely decisive Track-B evidence and the EARS tests are individually
> runnable.
