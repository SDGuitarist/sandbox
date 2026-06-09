# Orchestration-Hardening Fixture Suite

Negative-test fixtures that prove each shipped orchestration-hardening guard
**fires** on an engineered trigger — a deterministic regression net re-run on
every future hardening edit. Driven by `../validate_hardening.py`.

Source plan: `docs/plans/2026-06-08-feat-hardening-fixture-suite-plan.md`.
Source proposal: `docs/proposals/validate-hardening-on-fixtures.md`.

## Why this exists

Run 070 spent ~2.5M tokens validating Tracks A/B/C on a real app and **never
exercised Track B** (Film PM's cross-boundary calls were all model-layer, already
pinned, so the FC50 failure mode could not occur). Track B is the only track still
unproven and it gates a confident merge of the hardening to master. F-B1 turns
Track B from "present but unexercised" into "fixture-proven" for a fraction of the
cost, and breaks the self-validation circularity.

## Fidelity label vocabulary (the honesty contract, M6)

A fixture's matrix row carries TWO axes. The fidelity axis must report the label
the invocation actually earned — never rounding up:

| Label | Meaning |
|-------|---------|
| `EXERCISED` | Drove the shipped artifact itself (e.g. invoked the real agent). |
| `SPIKE-VALIDATED` | Ran an existing spike *copy* of the recipe, not the ship. |
| `PROSE-ASSERTED` | Checked an orchestrator-prose contract; no executable guard. |
| `MIRRORED` | Ran a Python *reimplementation* — a last resort, never `EXERCISED`. |

Second axis: `PASSED` (the guard produced the expected verdict) | `FAILED`.

These four are the ONLY values the matrix's fidelity column may hold. A track
with no fixture earned no fidelity, so its fidelity cell is `—` (a no-result
sentinel, alongside `PENDING` / `NOT RUN`) and its coverage provenance lives in
the evidence column. `FIELD+SPIKE` is such a provenance note, **not** a fifth
fidelity label — it never appears in the fidelity column.

## Phase status

| Fixture | Track | Fidelity | Status |
|---------|-------|----------|--------|
| **F-B1** | B (FC50) | `EXERCISED` | Built. Real `spec-completeness-checker` agent; FAILs on an unpinned entrypoint. The merge-blocking proof. |
| **F-B2** | B (FC50 false-N/A) | `EXERCISED` | Built. Real agent returns `N/A` on a wholly-omitted entrypoint — the honest blind spot, not a false PASS. Backstop (assembly contract-check) is `PROSE-ASSERTED`. |
| **F-D1** | FC52 | `EXERCISED` | Built. Shipped `tools/check_spec_provenance.py` (detection only; repair is out of scope). |
| **F-C1** | C | `PROSE-ASSERTED` (L2) / `EXERCISED` (L1, opt-in) | Built. Advisory contract always; real scorer via `--with-api` (a scorer defect FAILs; only genuine environment unavailability is non-failing). |
| **Track A** | A (FC51) | `—` (not fixtured) | **P-accept.** Coverage = `FIELD+SPIKE` (field-proven runs 069/070 + spikes); cherry-pick assembly is agent-prose, so no fixture exists and no fidelity is claimed — pending a deliberate `P-extract` refactor (its own real-build validation). F-A1/F-A2 intentionally not built. |

All planned fixtures are now built except F-A1/F-A2 (intentionally `P-accept`'d).
Track B carries two fixtures (FAIL-on-unpinned + N/A-on-omitted); the matrix
aggregates them — the track PASSES only if both pass.

### The operator decision (resolved)

Track A + FC52-detection were offered as **P-extract / P-promote / P-accept**.
Chosen: a **split** — `P-extract` the cheap, deterministic FC52 SHA-compare (now a
shared callable both the gate and F-D1 invoke); `P-accept` Track A's cherry-pick
assembly (agent-prose; exercising it as-shipped needs a larger share-not-fork
refactor + real-build validation, so it stays honestly field+spike-validated, not
a hollow `SPIKE-VALIDATED` row). `P-promote` was rejected: a spike is a copy of the
recipe, so a green spike row would not catch ship-prose drift — the very thing this
suite exists to catch.

### Cost / hermeticity

The default `validate_hardening.py` run is **not fully hermetic**: **F-B1 and
F-B2** each invoke the real `spec-completeness-checker` agent (two bounded agent
calls — network + tokens). F-D1 and F-C1 layer 2 are free and deterministic
(git + file reads). F-C1 layer 1 (the spec-eval scorer, real bounded LLM calls)
is the only **opt-in** cost, via `--with-api`; without it the suite asserts only
the deterministic advisory contract. So "default" ≈ two agent calls; truly
zero-cost subsets are `--fixture F-D1` and `--fixture F-C1` (without `--with-api`).
