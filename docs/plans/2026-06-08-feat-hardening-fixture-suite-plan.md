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
- Track A assembly recipe (verified in FC51 fix-status / swarm-runner): per-COMPLETED-worker
  `git cherry-pick $(git merge-base <original_branch> <branch>)..<branch>`; a
  cherry-pick conflict ⇒ abort with blocking class `assembly-ownership-conflict:`.
- Ownership gate is three-dot `git diff --name-only <original_branch>...<branch>`.

## Build sequence (phased; each phase ships independently)

### Phase 0 — Verify-first spike (NO fixture code until this passes)
For each of the three guard *families*, prove it can be driven in isolation against
a crafted input while remaining the artifact the autopilot runs:
- **Check 1b (B):** Can its structural logic run against a fixture spec file and
  return FAIL/N/A deterministically? Decide ONE of: (i) invoke the real
  `spec-completeness-checker` agent on the fixture and assert its verdict (true
  guard-proof, one agent call), or (ii) extract Check 1b into a shared
  `eval-harness` function that the agent is refactored to call (single source of
  truth, zero drift) and test the function. Recommend (ii) ONLY if the agent proves
  unreliable/expensive; default (i).
- **Assembly/ownership/provenance (A, FC52):** Can a temp git repo reproduce the
  divergent-base / same-file / diverged-spec scenarios and run the *actual* recipe
  (merge-base cherry-pick; three-dot ownership diff; provenance diff) as Python
  subprocess calls? (Expected yes — pure git.)
- **Spec-eval (C):** Can `spec_eval_gate.py` run on a one-claim fixture and return
  an advisory verdict without blocking? (Expected yes — it's already advisory.)
Output: a one-page spike note in `docs/reports/hardening-fixtures/spike.md` recording,
per guard, "invoked-as-shipped: yes/no" and the chosen invocation method. This
resolves the Feed-Forward risk before any fixture is written.

### Phase 1 — MVP: Track-B proof + runner (unblocks the merge)
- `eval-harness/fixtures/` scaffold + `validate_hardening.py` runner that discovers
  fixtures, runs each, and prints the per-track `EXERCISED|MIRRORED / PASSED|FAILED`
  matrix.
- **F-B1** (Track B FC50 guard): a ~30-line fixture spec with one genuine
  route→orchestration call declared as an `orchestration entrypoint` row with an
  EMPTY `Full Signature`. Assert the gate FAILS naming the symbol. ← the decisive
  Track-B evidence.
- Matrix output for Track B: `EXERCISED ✓ / PASSED ✓`.

### Phase 2 — Track A + FC52 (deterministic git fixtures)
- **F-A1** (FC51 cherry-pick): temp repo, feature branch + orphan commit on default
  branch (divergent base), 1–2 worker branches. Run the merge-base cherry-pick
  recipe. Assert: assembly clean, per-worker base == `merge-base`, no commit dropped.
- **F-A2** (FC51 hidden dep): two worker branches touching the SAME file. Run
  ownership gate + assembly. Assert abort with `assembly-ownership-conflict:` (proves
  the escape is caught, not silently merged).
- **F-D1** (FC52 provenance): worktree-base spec deliberately diverged from the gated
  spec. Run the Step 9w.9.5 provenance check. Assert it detects the diff and
  records/repairs before "spawn."

### Phase 3 — Completeness (blind-spot + advisory documentation)
- **F-B2** (FC50 false-N/A): a spec with ZERO orchestration-entrypoint rows but a
  real route→module call in fixture code. Assert gate returns N/A AND the assembly
  contract-check backstops it. Documents the known blind spot honestly.
- **F-C1** (Track C advisory): a deliberately vague claim ("validate the input").
  Assert spec-eval flags it advisory and the pipeline does NOT block.

## Acceptance Tests (EARS)

### Happy path
- WHEN F-B1 runs against the spec with an unpinned orchestration entrypoint THE
  SYSTEM SHALL report Track B `EXERCISED` and the gate verdict `FAIL` naming the
  symbol.
  - Verify: `eval-harness/.venv/bin/python eval-harness/validate_hardening.py --fixture F-B1` — exit non-zero from the gate, matrix row `B | EXERCISED | PASSED`.
- WHEN F-A1 runs with a divergent-base scenario THE SYSTEM SHALL assemble cleanly
  with each worker's cherry-pick base equal to `merge-base(original_branch, branch)`.
  - Verify: `... validate_hardening.py --fixture F-A1` — matrix row `A | EXERCISED | PASSED`; spike/fixture log shows per-worker base == merge-base.
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
- WHEN F-C1 runs a vague claim THE SYSTEM SHALL record an advisory result and the
  pipeline SHALL proceed (no block).
  - Verify: `... --fixture F-C1` — advisory verdict present, exit code 0 (non-blocking).
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
- **Least confident:** that all three git-mechanics fixtures (F-A1/F-A2/F-D1) can
  drive the *actual* assembly/ownership/provenance code paths via subprocess without
  re-encoding their logic. If the recipes live only inside agent prose (not callable
  code), F-A* may require the same share-not-fork refactor as Check 1b — Phase 0
  determines this and it is the gate on Phase 2.

## Codex handoff prompt

> Review `docs/plans/2026-06-08-feat-hardening-fixture-suite-plan.md` against
> `docs/proposals/validate-hardening-on-fixtures.md` and the shipped guards it
> exercises (`.claude/agents/spec-completeness-checker.md` Check 1b lines 85-106;
> `.claude/agents/swarm-runner.md` cherry-pick assembly + `assembly-ownership-conflict`;
> autopilot `SKILL.md` Step 9w.9.5 provenance gate; `eval-harness/spec_eval_gate.py`).
> Focus your review on ONE question above all: **does any fixture risk validating a
> reimplementation of a guard rather than the guard the autopilot actually runs?**
> For each of the six fixtures, state whether the plan's invocation method exercises
> the shipped artifact or a mirror, and whether the Phase-0 spike adequately gates
> that distinction. Then check the EARS tests are individually runnable and the
> EXERCISED-vs-MIRRORED honesty distinction (M6) is preserved end to end. Flag any
> fixture whose "deterministic" claim is overstated (LLM in the loop).
