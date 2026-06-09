# HANDOFF — Sandbox

**Date:** 2026-06-09
**Branch:** feat/film-production-pm
**Phase:** Orchestration-hardening FIXTURE SUITE complete (Work + 3 Codex review rounds applied). NEXT: compound + merge decision.

## Current State

The orchestration-hardening **fixture suite** is built and green. It is a negative-test
regression net that proves each shipped hardening guard FIRES (or honestly reports its
blind spot), with no reimplementations. Driven by `eval-harness/validate_hardening.py`;
emits a per-track fidelity matrix using the honest vocabulary
(EXERCISED / SPIKE-VALIDATED / PROSE-ASSERTED / MIRRORED).

Full default run (2 real agent calls; not fully hermetic): **A** `—`/NOT FIXTURED,
**B** EXERCISED/PASSED, **C** PROSE-ASSERTED/PASSED, **FC52** EXERCISED/PASSED. Exit 0.

| Fixture | Track | Fidelity | What it proves |
|---------|-------|----------|----------------|
| F-B1 | B (FC50) | EXERCISED | Real `spec-completeness-checker` agent FAILs on an unpinned orchestration entrypoint (merge-blocking proof). |
| F-B2 | B (FC50 false-N/A) | EXERCISED | Real agent returns N/A on a wholly-omitted entrypoint — honest blind spot, not a false PASS. |
| F-D1 | FC52 | EXERCISED | Shipped `tools/check_spec_provenance.py` detects spec drift (exit 3) + identical-spec control OK (exit 0). |
| F-C1 | C | PROSE-ASSERTED (L2) / EXERCISED (L1, `--with-api`) | Advisory demotion in SKILL 9w.8 + real scorer run. |
| Track A | A (FC51) | — (not fixtured) | P-accept: cherry-pick assembly is agent-prose; field-proven 069/070 + spikes. |

**Operator decision resolved (split):** `P-extract` FC52-detection (now a shared callable
the gate AND F-D1 invoke); `P-accept` Track A; `P-promote` rejected. F-A1/F-A2 not built.

**One live shipped change:** `SKILL.md` Step 9w.9.5 was rewired (share-not-fork) to CALL
`tools/check_spec_provenance.py` instead of inlining `git rev-parse`. Behavior identical;
detection only (repair stays agent-prose). **This is the highest residual risk — it has
NOT been validated by a real swarm run, only by F-D1 in isolation.**

## Key Artifacts (this work)

| Item | Location |
|------|----------|
| Plan | docs/plans/2026-06-08-feat-hardening-fixture-suite-plan.md |
| Runner + all fixture logic | eval-harness/validate_hardening.py |
| Fixtures + README (fidelity contract) | eval-harness/fixtures/ |
| Shipped FC52 detector (new) | tools/check_spec_provenance.py |
| Live gate rewire | .claude/skills/autopilot/SKILL.md (Step 9w.9.5) |
| Commits | feat/film-production-pm `787f2fb..8dca4b5` (15 commits) |

## Review Rounds Applied (Codex, manual)

- **R1** → F-C1 scorer-defect surfacing (no longer hidden as INCONCLUSIVE); Track A out of the fidelity column. (`0433cf1`, `a64e48d`, `19e89ce`)
- **R2** → validate scorer JSON status against the shipped `GateStatus` enum; crash-proof the schema defense. (`9b17c1a`, `1d6ac07`)
- **R3** → timeout is a FAILING class (hang ≠ env); removed the silent enum fallback (fail-closed + visible). (`8dca4b5`)

## NEXT SESSION — two things

1. **Compound** (`/workflows:compound` or the compound skill): write `docs/solutions/` doc +
   run `/update-learnings`. Lessons worth capturing: share-not-fork extraction (FC52 detector
   called by both gate and fixture); the honesty-label discipline (never round spike/prose/mirror
   to EXERCISED; FIELD+SPIKE is coverage provenance, not a fidelity label); opt-in API fixtures
   (hermetic by default); fail-closed > silent fallback when validating against a shipped enum.
2. **Merge decision.** `feat/film-production-pm` is **108 commits / 245 files ahead of master** —
   merging ships the ENTIRE Run 070 build + hardening + meta-analysis + the 9 fixture commits, not
   just the fixtures. This is a large, deliberate call. Before merge: consider a final Codex pass on
   R3 (`1d6ac07..8dca4b5`, not yet reviewed — operator opted to proceed) and a real-swarm check of
   the SKILL 9w.9.5 rewire.

## Carried-Forward Deferred Items (from Run 070)

1. **[070-W4] Todo #070 (P2, LOW):** Double `get_schedule_entries` in `callsheets.generate`. Fix: pass pre-fetched entries as optional param to `generate_call_sheet`.
2. **FC51 orchestrator rule:** ensure converged spec is at the worktree base before spawn (cherry-pick the spec-update commit onto the default branch, OR inline-inject sections into briefs).
3. **Track A `P-extract` (follow-on):** refactor `swarm-runner.md:76-138` cherry-pick prose into a shared callable so Track A earns a real EXERCISED row — its own real-build validation required.

## Feed-Forward

- **Hardest decision:** invoke the real shipped guard vs. extract a shared function. Resolved per-guard: invoke the real agent for FC50 (F-B1/F-B2); share-not-fork extract for FC52 (F-D1). Never a Python mirror.
- **Rejected:** `P-promote` for Track A (a spike is a copy of the recipe — a green spike row wouldn't catch ship-prose drift, the very thing the suite exists to catch).
- **Least confident:** the live SKILL 9w.9.5 rewire's agent→CLI wiring under a real swarm (deterministic in isolation, but un-exercised end-to-end).

## Prompt for Next Session

```
Read HANDOFF.md. This is Sandbox, branch feat/film-production-pm. The orchestration-hardening
fixture suite is COMPLETE and green (F-B1, F-B2, F-D1, F-C1; Track A = P-accept), with 3 Codex
review rounds applied. Plan: docs/plans/2026-06-08-feat-hardening-fixture-suite-plan.md.

Do the COMPOUND phase for the fixture-suite work:
1. Write docs/solutions/ doc (frontmatter) — key lessons: share-not-fork extraction (FC52 detector
   called by both the gate and F-D1), honesty-label discipline (no spike/prose/mirror rounded to
   EXERCISED; FIELD+SPIKE = coverage note, not a fidelity label), opt-in API fixtures, fail-closed
   over silent fallback. Scope the solution doc to the fixture suite (commits 787f2fb..8dca4b5).
2. Run /update-learnings (or /update-learnings-noninteractive) and produce the Learnings Propagated table.

THEN surface the MERGE decision (do not merge without explicit go-ahead): feat/film-production-pm is
~108 commits ahead of master — merging ships the whole Run 070 build, not just the fixtures. Flag two
pre-merge gates: (a) optional final Codex pass on R3 (1d6ac07..8dca4b5); (b) the live SKILL.md Step
9w.9.5 FC52 rewire has no real-swarm validation yet.
```
