---
review_agents:
  - codex (manual, binding — 3 rounds R1/R2/R3)
---

# Review Context — Orchestration-Hardening Fixture Suite (compound 2026-06-09)

## Risk Chain

**Brainstorm/Plan risk:** The drift trap — a fixture that silently tests a Python *reimplementation* of a guard rather than the guard the pipeline runs. That is FC52/M1 (gate-vs-use artifact drift) reborn *inside the validator*: a fixture passing against a reimplementation proves nothing about the shipped gate.

**Plan mitigation:** Phase-0 deepen pass established a callability matrix per guard; the fidelity column labels any non-ship invocation honestly (`MIRRORED`/`SPIKE-VALIDATED`/`PROSE-ASSERTED`), never rounding up to `EXERCISED`. Only guards drivable as-shipped earn `EXERCISED`.

**Work risk (from Feed-Forward):** The live SKILL.md Step 9w.9.5 rewire (gate now CALLS `tools/check_spec_provenance.py`) is proven by F-D1 in isolation but never exercised inside a real swarm — the agent→CLI wiring is deterministic on the bench, un-exercised end-to-end.

**Review resolution:** 3 Codex rounds applied. R1 — F-C1 surfaces scorer defects (no longer hidden as INCONCLUSIVE), Track A pulled out of the fidelity column. R2 — validate scorer JSON status against the shipped `GateStatus` enum; crash-proof the schema defense. R3 — timeout is its own FAILING class (hang ≠ env); removed the silent enum fallback (fail-closed + visible). R3 (`1d6ac07..8dca4b5`) not yet re-reviewed — operator opted to proceed. No new failure class.

## Files to Scrutinize

| File | What changed | Risk area |
|------|-------------|-----------|
| eval-harness/validate_hardening.py | runner + all fixture logic; fidelity matrix; scorer classification | honesty-label correctness; fail-closed enum validation; timeout-as-failure |
| tools/check_spec_provenance.py | NEW shared FC52 detector (SHA-blob compare, exit codes 0/2/3/5) | share-not-fork: must stay the SINGLE impl both gate and F-D1 call |
| .claude/skills/autopilot/SKILL.md | Step 9w.9.5 rewired to CALL the detector (was inline git rev-parse) | un-exercised end-to-end under a real swarm (the residual risk) |
| eval-harness/fixtures/ | F-B1/F-B2/F-C1/F-D1 crafted broken inputs + README fidelity contract | each fixture must trigger the ACTUAL guard surface, not any incidental FAIL |

## Plan Reference

`docs/plans/2026-06-08-feat-hardening-fixture-suite-plan.md`
