# HANDOFF — Sandbox

**Date:** 2026-06-09
**Branch:** feat/film-production-pm
**Phase:** Orchestration-hardening FIXTURE SUITE — **COMPOUND COMPLETE** + 9w.9.5 rewire **VALIDATED** (scoped real-swarm check). NEXT: Codex R3 pass → then merge in a new session.

## Current State

The orchestration-hardening fixture suite is built, green, reviewed (3 Codex
rounds), and now **compounded**: solution doc written + learnings propagated. It
is a negative-test regression net proving each shipped hardening guard FIRES (or
honestly reports its blind spot), with no reimplementations. Driven by
`eval-harness/validate_hardening.py`; emits a per-track fidelity matrix using the
honest vocabulary (EXERCISED / SPIKE-VALIDATED / PROSE-ASSERTED / MIRRORED).

Full default run (2 real agent calls; not fully hermetic): **A** `—`/NOT FIXTURED,
**B** EXERCISED/PASSED, **C** PROSE-ASSERTED/PASSED, **FC52** EXERCISED/PASSED. Exit 0.

| Fixture | Track | Fidelity | What it proves |
|---------|-------|----------|----------------|
| F-B1 | B (FC50) | EXERCISED | Real `spec-completeness-checker` FAILs on an unpinned orchestration entrypoint (merge-blocking proof). |
| F-B2 | B (FC50 false-N/A) | EXERCISED | Real agent returns N/A on a wholly-omitted entrypoint — honest blind spot, not a false PASS. |
| F-D1 | FC52 | EXERCISED | Shipped `tools/check_spec_provenance.py` detects spec drift (exit 3) + identical-spec control (exit 0). |
| F-C1 | C | PROSE-ASSERTED (L2) / EXERCISED (L1, `--with-api`) | Advisory demotion in SKILL 9w.8 + real scorer run. |
| Track A | A (FC51) | — (not fixtured) | P-accept: cherry-pick assembly is agent-prose; field-proven 069/070 + spikes. |

**One live shipped change:** `SKILL.md` Step 9w.9.5 was rewired (share-not-fork) to
CALL `tools/check_spec_provenance.py` instead of inlining `git rev-parse`. Behavior
identical (detection only; repair stays agent-prose). **This is the highest residual
risk — NOT validated by a real swarm run, only by F-D1 in isolation.**

## Key Artifacts

| Phase | Location |
|-------|----------|
| Plan | docs/plans/2026-06-08-feat-hardening-fixture-suite-plan.md |
| Review | 3 Codex rounds (manual): R1 `0433cf1`/`a64e48d`/`19e89ce`, R2 `9b17c1a`/`1d6ac07`, R3 `8dca4b5` |
| Solution | docs/solutions/2026-06-09-orchestration-hardening-fixture-suite.md |
| Runner + all fixture logic | eval-harness/validate_hardening.py |
| Fixtures + README (fidelity contract) | eval-harness/fixtures/ |
| Shipped FC52 detector (new) | tools/check_spec_provenance.py |
| Live gate rewire | .claude/skills/autopilot/SKILL.md (Step 9w.9.5) |
| Commits | feat/film-production-pm `787f2fb..8dca4b5` (15) + compound doc `81a36c8` |

## THE MERGE DECISION (gated — do NOT merge without explicit go-ahead)

`feat/film-production-pm` is **~108 commits / 245 files ahead of master** — merging
ships the ENTIRE Run 070 build + hardening + meta-analysis + the fixture suite, not
just the fixtures. This is a large, deliberate call. **Operator plan: do the Codex R3
pass, then merge in a NEW session.**

1. **Codex R3 pass (REMAINING pre-merge step)** — final binding Codex review of
   `1d6ac07..8dca4b5` (the round-3 scorer hardening: timeout-as-failure, no silent
   enum fallback). Handoff prompt is in HANDOFF (see "Codex R3 Handoff Prompt" below).
   Use the manual human-driven Codex, not headless `codex exec`.
2. ~~Real-swarm check of the SKILL 9w.9.5 FC52 rewire~~ — **DONE (2026-06-09).** A
   scoped real-orchestrator run on branch `test/fc52-9w95-rewire-real-swarm`
   (commit `998854e`) drove Step 9w.9.5 to completion and STOPPED before spawn:
   the step invoked `tools/check_spec_provenance.py` with real branch args →
   `PROVENANCE_DRIFT`/exit 3 (the agent→CLI wiring works); the 9w.6 completeness
   gate FAIL→fix→PASS proved the run legitimately reaches 9w.9.5. Repair was
   identified but NOT executed (pre-spawn halt) — recorded honestly, not as
   `PROVENANCE_REPAIRED`. Evidence: `docs/reports/fc52-9w95-val/{spec-provenance.md,
   spec-completeness-check.md}` on the test branch. **Scope boundary:** proved the
   DETECT wiring (the new/risky part); did NOT exercise live brief-injection at
   Step 10w or the OK-path (lower risk; OK-path covered by F-D1 in isolation).
   Keep the `test/` branch until merge as the audit trail.

## Codex R3 Handoff Prompt (run before merge)

> Binding review. Scope: commits `1d6ac07..8dca4b5` on `feat/film-production-pm`
> (round-3 fixes to `eval-harness/validate_hardening.py`). Context: this is the
> orchestration-hardening fixture suite's F-C1 scorer-validation layer. The R3
> changes: (1) a scorer TIMEOUT is now its own FAILING class `L1_TIMEOUT` (a hang
> must not pass under `--with-api` as "environment"); (2) `_valid_gate_statuses()`
> dropped its silent fallback — it reads `from models import GateStatus` and RAISES
> if unimportable, and `_run_scorer` resolves the valid set BEFORE spending an API
> call, returning a visible fail-closed `SCORER_DEFECT` on failure. Pressure-test:
> (a) Is the EXERCISED/ENV/DEFECT/TIMEOUT classification airtight — can any genuine
> scorer defect still masquerade as a non-failing environment miss, or vice-versa?
> (b) Is the fail-closed enum read correct (no path where a drifted/absent enum
> silently validates)? (c) Does the timeout bound risk a false TIMEOUT on a slow-but-
> healthy scorer? Confirm GO or list blocking findings.

## Deferred Items

1. **Track A `P-extract` (follow-on):** refactor `swarm-runner.md:76-138` cherry-pick
   prose into a shared callable so Track A earns a real EXERCISED row — its own
   real-build validation required.
2. **Real-swarm validation of the 9w.9.5 rewire** (the merge gate above).
3. **Suite adoption decision (operator):** wiring `validate_hardening.py` into the
   autopilot pipeline as a blocking gate — proposal step 3, out of this scope.
4. **[070-W4] Todo #070 (P2, LOW):** double `get_schedule_entries` in
   `callsheets.generate` — pass pre-fetched entries as optional param.
5. **FC51 orchestrator rule:** ensure converged spec is at the worktree base before
   spawn (cherry-pick the spec-update commit, OR inline-inject sections into briefs).

## Three Questions

1. **Hardest decision?** Per guard, invoke the real shipped artifact vs. extract a
   shared callable. Resolved by fidelity: real agent for FC50; share-not-fork extract
   for FC52; decline to fixture agent-prose Track A rather than ship a hollow
   `SPIKE-VALIDATED` row. Never a Python mirror.
2. **What was rejected?** Another validate-on-real-build (M4 instrument failure);
   reimplementing guards in Python (the drift trap); `P-promote` for Track A (a spike
   is a copy that can't catch ship-prose drift); hiding API cost / silent enum fallback.
3. **Least confident about?** The live SKILL 9w.9.5 agent→CLI wiring under a real
   swarm — deterministic in isolation, un-exercised end-to-end.

## Prompt for Next Session

```
Read HANDOFF.md. This is Sandbox, branch feat/film-production-pm. The orchestration-
hardening fixture suite is COMPOUND COMPLETE and the SKILL 9w.9.5 FC52 rewire is
VALIDATED (scoped real-swarm check, evidence on branch test/fc52-9w95-rewire-real-swarm
commit 998854e). Solution: docs/solutions/2026-06-09-orchestration-hardening-fixture-suite.md.

This session = the MERGE. Two steps, in order:
1. Codex R3 pass — run the "Codex R3 Handoff Prompt" in HANDOFF.md against
   1d6ac07..8dca4b5 (manual human-driven Codex). Bring findings back; if any
   blocking, fix before merging.
2. If Codex says GO: merge feat/film-production-pm -> master. This is a ~108-commit
   merge shipping the WHOLE Run 070 build + hardening + meta-analysis + fixtures.
   Confirm with the operator ("are you sure") before executing; it is hard to reverse.
   After merge, delete the throwaway test/fc52-9w95-rewire-real-swarm branch.
```
