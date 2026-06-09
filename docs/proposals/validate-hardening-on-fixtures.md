# Proposal: Validate Orchestration Hardening on Fixtures, Not Real Builds (M4/M5/M13)

**Status:** PLANNED (2026-06-08) — gate-ready plan drafted at
`docs/plans/2026-06-08-feat-hardening-fixture-suite-plan.md` (awaiting plan review +
operator go for the build). Original proposal below unchanged.
**Owner decision required:** adopt as the standard validation path for hardening changes.

## Problem

Run 070 was a "validate-on-real-build" of orchestration-hardening Tracks A/B/C. It
exposed three validity holes:

- **M4 — the vehicle didn't exercise the thing under test.** Film PM's cross-boundary
  calls are all model-layer (already pinned), so the FC50 failure mode (unpinned
  route→orchestration divergence) *could not occur*. The build would have assembled
  cleanly with NO FC50 fix. Track B was unexercised; we'd have stamped it "validated."
- **M5 — self-validation circularity.** The hardening was validated *using* the
  hardening. A latent FC51 bug would have looked like a build problem.
- **M13 — cost.** ~2.5M tokens / ~70 min for weak Track-B evidence + an accidental
  bug discovery. A targeted fixture exercises each track *decisively* for a fraction.

Real builds are necessary for ecological validity but are a *poor instrument* for
proving a specific guard works: their failure modes are incidental, not designed.

## Proposal: a deterministic fixture suite, one fixture per failure mode

A tiny synthetic spec (`FixtureApp`, ~3 workers) with **deliberately engineered
triggers**, run whenever hardening changes — *before* (or instead of) a full
validate-on-real-build. Each fixture is a negative test: it asserts the guard FIRES.

| Fixture | Track | Engineered trigger | Pass condition |
|---|---|---|---|
| F-A1 | A (FC51 cherry-pick) | Feature branch with an orphan commit on the default branch (divergent base) | swarm-runner cherry-picks `merge-base..branch` per worker; assembly clean; per-worker base recorded |
| F-A2 | A (FC51 hidden dep) | TWO workers deliberately assigned the SAME file | Assembly ABORTS with `assembly-ownership-conflict:` (proves the conflict-escape, not silent merge) |
| F-B1 | B (FC50 guard) | ONE genuine route→orchestration call pinned only in prose, absent from Export Names | 9w.6 Check 1b FAILS (or the call is flagged) — guard fires, not N/A |
| F-B2 | B (FC50 false-N/A) | Zero orchestration-entrypoint rows declared but a real route→module call exists | Documents the known N/A blind spot; asserts the assembly contract-check backstops it |
| F-C1 | C (spec-eval advisory) | A deliberately vague claim ("validate the input") | spec-eval flags advisory, does NOT block, pipeline proceeds |
| F-D1 | FC52 (provenance) | Worktree-base spec deliberately diverged from gated spec | Step 9w.9.5 provenance gate detects the diff and repairs/records before spawn |

## Properties

- **Deterministic & cheap:** ~3 workers, minutes, binary pass/fail per track. No
  2.5M-token real build needed to learn whether a guard works.
- **Breaks circularity (M5):** fixtures are designed to trigger the failure, so a
  PASS means the guard caught a real instance, not "the bug happened not to fire."
- **Regression suite:** re-run on every hardening edit. Real builds then only need
  to *not regress*, and serve ecological validity, not guard-proof.
- **Epistemic honesty (M6):** the validation report states which tracks were
  *exercised* (fixture fired) vs merely *present* (gate ran but no trigger).

## Adoption

1. Build `eval-harness/fixtures/` with the 6 fixtures above (specs + expected verdicts).
2. Add a `validate-hardening` entry point that runs the suite and emits a per-track
   EXERCISED/PASSED matrix.
3. Gate the orchestration-hardening merge on the fixture matrix, not on a real build.
4. Keep validate-on-real-build for ecological signal (does a real app still ship?),
   reported separately from guard-proof.

## Run-070 retro applied

Had this existed, the "cleared to merge" call would read: **A and C field-proven AND
fixture-proven; B fixture-proven but not field-exercised (Film PM had no unpinned
route→orchestration surface).** That is the honest statement run 070 could not make.
