# HANDOFF — Run 070 Meta-Analysis Triage (continuation)

**Date:** 2026-06-08
**Branch:** feat/film-production-pm
**Context:** Run 070 (Film Production PM, 16-agent swarm) is COMPLETE and was the
validate-on-real-build vehicle for the orchestration-hardening branch. A deep
post-run meta-analysis mined **38 system-level patterns** (IDs M1–M38). We are
draining them into their owning artifacts (triage). The top 4 are DONE; ~31 remain.

## Canonical artifacts (READ THESE FIRST — they are self-contained)
- **`docs/reports/070/meta-analysis.md`** — all 38 patterns, stable IDs M1–M38, grouped by theme. The source of truth.
- **`docs/latent-risks-and-mitigations.md`** — the inverse registry (M36), seeded from 070.
- **`docs/proposals/validate-hardening-on-fixtures.md`** — M4 fixture-validation proposal.
- `~/.claude/docs/agent-pitfalls.md` — FC52 added (global file; outside repo).
- `.claude/skills/autopilot/SKILL.md` — Step 9w.9.5 (spec-provenance) + post-completion batch-scan added.

## DONE (committed 5af6f4d)
- **M1** → agent-pitfalls FC52 "Gate/Use Artifact-Identity Drift" (unifies FC34 + FC51 spec-facet).
- **M2** → SKILL Step 9w.9.5 pre-spawn spec-provenance gate (brief = authoritative channel; worktree base is harness-opaque).
- **M38** → SKILL post-completion cross-worker batch-scan.
- **M4** → fixture-validation proposal doc.
- **M36** → latent-risks-and-mitigations.md inverse registry + process change (meta-analysis as a budgeted phase).

## DONE — Bucket 1 (Instruments / observability), committed this session
- **M29** → SKILL **Step 1.52 Orchestrator Context Instrumentation** (wires `context_proxy_chars` updates at every phase boundary + a `context-telemetry.md` log) and a pre-delegation hook in **Step 17w** (>70% warning as a recorded, non-blocking finding). Framed observability-only per the context-death plan's "not a gate" rule.
- **M34** → tail-runner **Step 6 RUN_METRICS** "Run Health Instruments" block (tools-per-assigned-file outliers, spec-eval pass-RATE, judgment-call count) + self-audit "What Was Missed" now uses those outliers as its search heuristic.
- **M23** → tail-runner **Step 6 RUN_METRICS** retires "0 merge conflicts" as a quality signal; replaced with an **Integration Health** row (contract-check + import-resolution at boot). If a conflict count is kept it must be labeled tautological. (Historical run reports left untouched per CLAUDE.md; swarm-planner's "zero merge conflicts" objective line left as-is — it describes the planner's design goal, not a reported run-quality claim.)

## DONE — Bucket 2 (light, calibration-aware only), committed this session
After reading `docs/proposals/retroactive-corpus-meta-analysis.md`, Bucket 2 was
split: the heavy structural patterns are n=1 (run 070 only) and would be premature
to harden into live files, so only the two corpus-safe items were drained. The
heavy three are parked as the corpus mine's first calibration targets (below).
- **M24** → agent-pitfalls **FC35** "Stronger fix" block: model-layer ownership-enforcement DEFAULT (`get_X(conn, id, user)` refuses un-owned rows), framed corpus-proven defense-in-depth (FC35 recurs: VenueConnect/GigSheet/BrewOps/SlateFund), additive to the per-route 403 check — explicitly NOT n=1. (Did not edit the live spec-template; agent-pitfalls is the registry home for a recurring class's mitigation.)
- **M11** → agent-pitfalls **FC50** risk-calibration note: divergence-risk ∝ non-model-layer share of coupling, NOT raw import density; steers Feed-Forward "least confident" toward unpinned Tier 2/3 entrypoints. Tagged n=1 (run 070) pending corpus confirmation. Reversible reasoning fix, so safe to write.

### Bucket 2 (PARKED — blocked on corpus calibration; first targets of the corpus mine)
These are heavy and structural — they change live `swarm-planner.md` / the spec
template, which future builds read. A flagged-but-written change to a live file is
riskier than parking, and each rests on a single run. Do NOT write them until the
retroactive corpus mine (`docs/proposals/retroactive-corpus-meta-analysis.md`)
confirms they recur. Make these the mine's FIRST calibration targets.
- **M20/M21** — Coupling-aware decomposition: swarm-planner should read the Cross-Boundary Wiring density and choose cut-points that minimize cross-agent edges; "16 verticals" should be an OUTPUT, not a fixed template input. (swarm-planner agent + planning docs.) **Corpus test:** does agent-count-vs-P1-count / cross-agent-edge density predict integration P1s across builds?
- **M16** — Convergence value audit: for each added section, did it change a worker decision? (a third of 070's convergence delta was restatement.) **Corpus test:** is restatement-heavy convergence common across builds?
- **M22** — Add "Schema-Behavior Contracts" surface to the spec template (cross-agent dependencies on cascade/constraint behavior, e.g., callsheets idempotency ← ON DELETE CASCADE). Between FC46 and FC50. **Corpus test:** how many prior builds had a cross-agent schema-behavior dependency that bit? (n=1 today.)

## DONE — Bucket 3 (governance), committed this session
New owning artifact: **`docs/governance/validation-validity-governance.md`** — the
"is our green actually meaningful?" axis (distinct from the roadmap's
verification-touch axis). Same calibration discipline as Bucket 2: principle +
actionable change captured; invasive live-gate changes on n=1 evidence PARKED.
- **M6** → governance doc + **safe non-breaking** edit to `self-audit-reviewer` skeptical-questions (a 6th focus: "how strong is the evidence for the claim this run exists to support, distinct from clean execution?"). **PARKED:** a 7th *gated* Run Quality dimension — `verify-self-audit` Gate 7b hard-requires exactly 6 rows; needs an atomic rubric+gate change + corpus calibration.
- **M7/M33** → governance doc: the freeze→validate→merge model + its four cracks (circular validation, validated-copy ≠ merged-copy, no feedback edge, non-stationary master). Crack #2 turned into a concrete **operator pre-merge diff check** (validated branch vs merge-source). The merge/push themselves untouched (operator authority).
- **M10** → governance doc + **safe non-breaking** note in `[[spec-eval-gate-behavior]]` memory: the demotion left the FEASIBILITY layer ungated (070's real gaps were all feasibility-layer); structural gates ≠ feasibility coverage; precision-fix-then-re-promote is an open roadmap improvement, not optional cleanup. **PARKED:** the `spec_eval_gate.py` precision fix + 9w.8 re-promotion (real engineering, a build).
- **M18** → governance doc: thin-brief validation mode documented as an **opt-in mode for validation runs** (declare in the plan), NOT a SKILL default — defensive briefing stays correct for production builds.

## DONE — Bucket 4 (smaller pitfalls / skill), committed this session
Calibration discipline: M26/M27/M37 did NOT fire in 070 → they are latent risks, not
failure classes, so NO new FC IDs were minted (the registry is for observed breakage).
They were already listed in `latent-risks-and-mitigations.md`; this session adds their
actionable mitigations for pre-mortems.
- **M27** → `latent-risks-and-mitigations.md` "Pre-mortem actions" — cross-domain read aggregator: route reads through M24 ownership-scoped accessors, or add N-way scope assertion + per-domain test; treat as highest-leverage security target. (No FC minted; generalizes FC23, neighbor of FC35/FC36.)
- **M26** → same section — prose→code authz translation: any non-trivial authz rule must be pinned as EXACT CODE in spec (not prose) + mandatory review-scrutiny target; M24 removes the per-route translation for ownership.
- **M37** → same section — model-homogeneity: deliberate model heterogeneity on high-risk slices + different-engine binding review = the previously-unnamed error-DECORRELATION rationale for the Codex-review preference ([[feedback_codex_manual_review]]). Applied surgically (same-model correlation helps assembly per M9 but hurts detection).
- **M35** → **`docs/proposals/orchestrator-decision-log.md`** (parked proposal): a `decision-log.md` capturing orchestrator pivot REASONING not just outcomes (~7 load-bearing deviations in 070). NOT drained into the live SKILL — a mandatory artifact needs a tail gate on n=1; proposed as opt-in trial first. Serves M6b (missing escalation tier) + feeds the meta-analysis phase.
- **M-meta** → already DONE as **M36** (prior session): "meta-analysis as a budgeted phase" is live in `latent-risks-and-mitigations.md` Process section. No separate artifact needed; noted here for completeness.

---

## TRIAGE COMPLETE — all four PARKED buckets drained (2026-06-08)
Every M-pattern is now in an owning artifact. What remains is **operator-gated**, not
triage work:
- **PARKED-for-corpus (heavy, n=1):** M20/M21, M22, M16 (Bucket 2) — first calibration
  targets of the corpus mine. M6 7th gated dimension (Bucket 3). These need the corpus
  to confirm recurrence before hardening live files.
- **PARKED-for-engineering:** M10 spec-eval precision fix + 9w.8 re-promotion (Bucket 3);
  M35 decision-log opt-in trial (Bucket 4). Real builds, not doc edits.
- **OPEN OPERATOR DECISIONS** (unchanged, untouched): branch merge / push (below).

## BIG PARALLEL EFFORT (own context window) — Retroactive Corpus Meta-Analysis
**`docs/proposals/retroactive-corpus-meta-analysis.md`** — operator idea (2026-06-08):
apply the run-070 meta-analysis lens to ALL prior builds (024–069 + named). It's M36
at corpus scale AND the validation set for the 38 patterns (which recur = real, which
were 070 flukes) AND the empirical proof of the M36 thesis. Read-only location-sliced
fan-out (one agent per build) → synthesis into cross-build trends, calibrated latent
risks/mitigations, instrument time-series (M34), and candidate net-new FCs. Run as its
OWN context with a token budget + loop-until-dry on novel patterns. Caveats: thin
early-build artifacts (~024–045), hindsight-retrofit bias, diminishing returns.
Distinct from (and larger than) the parked-bucket drain below — sequence it separately.

## OPEN OPERATOR DECISIONS (NOT mine to execute — leave for the human)
1. **Merge** orchestration-hardening branch (feat/cpaa-event-replay-simulator) to master. Recommendation: GO for Tracks A & C (field-proven); Track B is fixture-worthy first (see M4 proposal) before claiming it field-proven.
2. **Push** either branch to remote (still local-only).

## Kickoff for the new session
Read docs/handoffs/run-070-meta-triage-continuation.md and docs/reports/070/meta-analysis.md.
Continue draining the PARKED meta-analysis patterns into their owning artifacts,
starting with Bucket 1 (instruments — nearly free). One bucket at a time; commit per
bucket. Do NOT touch the open operator decisions (branch merge / push).
