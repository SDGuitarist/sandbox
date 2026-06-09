# Proposal: Retroactive Corpus Meta-Analysis (mine all prior builds) (extends M36/M34)

**Status:** PROPOSED (operator idea, 2026-06-08). Own context window — this is a
~45-build read-only fan-out + synthesis, not a quick task.

## Thesis

We only ever extracted *failure-mode* lessons (FCs) from prior builds. The META layer
— working mitigations, unfired latent risks, and the process/architecture/governance
patterns like the 38 mined from run 070 (`docs/reports/070/meta-analysis.md`) — was
never extracted from runs 024–069 + named builds. This is M36 (failure-triggered loop
is blind to clean-run lessons) applied to the whole corpus.

## Why it's more than "070's analysis ×45"

1. **Cross-build aggregate signal > per-build anecdote.** Design for patterns visible
   only in aggregate: mitigations that worked N/N builds; latent risks present in X,
   fired in Y (calibration); instrument time-series (spec-eval pass-rate, P1-rate,
   tools/file, agent-count vs P1-count) per M34.
2. **Calibrates the 38.** History is the test set: which of M1–M38 RECUR (real →
   promote) vs were 070 one-offs (demote). We mined the 38 on a training set of one.
3. **Empirically proves/kills the M36 thesis.** If the corpus is full of un-captured
   working-mitigations, "the failure loop is blind to clean-run lessons" becomes a
   measured fact, not an assertion.

## Method (read-only location-sliced fan-out — fittingly, a swarm)

- **Phase 0 — inventory.** Enumerate every prior build and which artifacts it has
  (docs/solutions/*, docs/reports/<run>/self-audit.md, BUILD_TRACKING archives,
  agent-pitfalls Update Log rows). One cheap pass. Expect richer yield from ~run 050+.
- **Phase 1 — parallel extraction.** One agent per build (or small cluster), read-only,
  conclusions-only. Emit a structured meta-record per build:
  `{ run_id, date, n_agents, p1, p2, spec_eval_pass_rate?, tools_per_file_outliers?,
     m1_m38_scored: {id: present|fired|mitigated|n/a + 1-line evidence},
     novel_patterns: [...], confidence }`.
  Discipline: extract ONLY what artifacts evidence (guard against hindsight retrofit);
  tag confidence; note when a field is absent (thin early-build artifacts).
- **Phase 2 — synthesis.** Aggregate into:
  - instrument time-series → feeds M34 instruments
  - high-confidence working mitigations (worked N/N) → `docs/latent-risks-and-mitigations.md`
  - calibrated latent risks (present X / fired Y) → same registry
  - net-new patterns → candidate FCs (M39+) and a `docs/reports/corpus-meta/` dataset
  - 38-pattern calibration table (recur vs one-off)

## Caveats (scope the run)

- **Artifact thinness over time** — Run Quality Grading (~05-15), self-audit layer
  (later), BUILD_TRACKING phases (later) didn't exist early; schema won't fully
  populate for runs ~024–045.
- **Hindsight/retrofit bias** — only extract evidenced patterns; tag confidence.
- **Diminishing returns** — novel-pattern rate decays fast; budget-bound and
  loop-until-dry on NOVEL patterns, not a fixed build count.
- **Cost** — read-only so cheaper than a build swarm, but ~45 agents + synthesis;
  run it as its own context with a token budget.

## Output targets
- `docs/latent-risks-and-mitigations.md` (mitigations + calibrated risks)
- `docs/reports/corpus-meta/` (per-build meta-records + cross-build trends + 38-pattern calibration)
- agent-pitfalls.md (any net-new FCs surfaced)

## Risk
Pure analysis on existing artifacts; changes no code; does not touch the open operator
decisions. Low risk. The only failure mode is wasted tokens on redundancy — bounded by
loop-until-dry + budget.
