# Run 070 — Deep Meta-Analysis (pattern mine)

Status: RAW CAPTURE for triage. These are insights mined from run 070 (Film
Production PM, 16-agent swarm, validate-on-real-build for orchestration-hardening
Tracks A/B/C). Most are NOT 070-specific — they are system-level patterns the run
surfaced. Each has a stable ID (M1..M38) for triage routing. Triage will assign
each to an owning artifact (agent-pitfalls / autopilot skill / spec-template /
governance / instruments / architecture) — see "Finding routing" (M30).

NOTE: run 070 had 0 P1s and graded A (4.7/5). By the current learning loop it
"taught nothing" (no new FC). This document is the counter-evidence: a clean run
surfaced 38 patterns. That gap is itself M36.

---

## A. Provenance & artifact-identity (the run's deepest theme)

- **M1 — Gate/use artifact-identity drift.** Every pre-swarm gate validated the
  converged feat spec (2295 lines); all 16 workers built against the stale
  master-base spec (2010 lines). No check links gate-time artifact to use-time
  artifact. Generalizes FC34 (cross-project) to cross-branch. *The single most
  important systemic finding.*
- **M2 — Detection was luck, not a check.** The divergence was caught only because
  the callsheets agent's summary happened to say "no sections literally named…".
  No systematic provenance check exists; a differently-phrased summary = silent
  ship of a build certified against a spec it didn't use.
- **M7 — Validated copy ≠ merged copy (governance-level identity drift).** We
  validated the hardening as inherited into feat/film; we will merge it from
  feat/cpaa. Nothing checks the two copies are identical.
- **M14 — Briefs are the operative spec channel and are unvalidated.** The spec
  file went through Codex + human + 3 machine gates; the briefs (which workers act
  on) went through nothing. Hand-transcribed contract content into 16 briefs with
  no provenance check back to the gated spec.

## B. Validation validity / epistemics

- **M3 — Proof-of-firing ≠ proof-of-benefit.** Track B's proof was "9w.6 PASS +
  Check 1b fired." It fired, but its downstream purpose (workers using pinned
  sigs) never happened. A validation that checks "did the guard fire" is weaker
  than "did the guard's outcome occur."
- **M4 — The vehicle didn't exercise the thing under test.** Film PM's
  cross-boundary calls are all model-layer (already pinned in Model Functions), so
  the FC50 failure mode (unpinned route→orchestration divergence) could not occur.
  The build would have assembled cleanly with NO FC50 fix. Track B is unexercised;
  A and C are genuinely exercised.
- **M5 — Self-validating infrastructure can't separate "correct" from "didn't
  trigger."** The hardening was validated using the hardening. A latent FC51 bug
  would have looked like a build problem. Needs failure-mode fixtures, not a real
  app.
- **M6 — Run Quality grade measures execution quality, not epistemic quality.**
  A (4.7/5) honestly scores process/artifacts; it does NOT score "did the run
  produce the knowledge it claimed?" By that axis 070 is ~C+ (B barely proven,
  near-miss on silent-invalid).
- **M13 — Validate-on-real-build is expensive and diffuse.** ~2.5M tokens / ~70min
  for weak Track-B evidence + accidental bug discovery. A targeted fixture (3
  workers, deliberate route→orchestration divergence, divergent base) exercises
  A/B far more cheaply and decisively.
- **M15 — All-green is auto-correlated; signal came from reality-collisions.**
  Workers, tests, smoke, contract-check all derive from one source (the spec), so
  "everything agrees" proves common provenance, not correctness. The ~8 moments an
  implementer hit an empirical wall (search/FTS, budget/render-context,
  tests/amount) are where new information entered. We have the S/N backwards:
  green checks are loud, reality-collisions are buried in prose.

## C. Spec completeness, feasibility & calibration

- **M8 — Structural completeness ≠ implementation completeness.** 9w.6 passed
  (6 sections present) yet workers made ≥8 judgment calls filling real gaps. The
  count of worker judgment-calls is the true incompleteness measure; no gate
  measures it.
- **M9 — Non-reproducibility from judgment DOF.** Build success depended on ~8
  independent gap-fills happening to be mutually compatible (same-model
  correlation helped — see M37). Re-run could collide. n=1 success on high-DOF
  build is weak evidence.
- **M10 — We demoted the only feasibility-layer gate.** Detector map:
  structural=9w.5/9w.6, feasibility=9w.8 (spec-eval, DEMOTED), integration=
  contract-check/review. This build's real gaps (contentless-FTS impossibility,
  8 judgment calls) were ALL feasibility-layer — the only layer now ungated.
  Fix the spec-eval harness; don't abandon the layer.
- **M11 — FC50 risk ∝ non-model-layer share of coupling.** Dense coupling ≠ high
  divergence risk when the dense surface is model-pinned. Feed-Forward flagged the
  callsheet 6-import seam as top risk; it was actually low risk. Feed-Forward
  conflated coupling-density with divergence-risk.
- **M12 — "Converged/frozen" is a point-in-time claim, not a distribution
  guarantee, and decays per edit.** 9w.5 found 3 fresh cross-section issues on a
  spec that passed Codex + human gate — because edits happened after the human
  gate. No re-verify-after-edit invariant. 9w.5-as-last-step-before-spawn is
  load-bearing.
- **M16 — Convergence ROI is lossy / diminishing.** Big chunks of convergence
  (Orchestration Entrypoints table redundant with Model Functions; Call Sheet
  Algorithm reconstructable from Wiring) produced low marginal behavior change =
  restatement, not addition. And its value reached workers only via manual
  re-encoding into briefs (M14). A "convergence value audit" (did each added
  section change a worker decision?) would quantify.

## D. Spec-delivery channels

- **M17 — Dual-channel spec delivery (file + brief); redundancy masked the
  divergence.** Workers got contract content from both the worktree file and the
  brief. Defensive briefs backfilled the stale file. The "mitigation" was luck.
- **M18 — Defensive briefing converts loud failures into silent ones.** Minimal
  "read the spec" briefs would have failed loudly and surfaced the
  worktree-base-spec bug cleanly on run 1. Over-defensiveness is camouflage during
  VALIDATION runs specifically. Consider a deliberate thin-brief validation mode.
- **M19 — 16× redundant spec ingestion.** Each worker re-reads the full ~2300-line
  spec (~dominant worker token sink). Pre-digested per-role spec slices would cut
  cost and shrink the stale-spec surface.

## E. Decomposition & architecture

- **M20 — Vertical-slice decomposition is coupling-blind.** swarm-planner cuts a
  fixed 16-vertical template with zero coupling-graph analysis, slicing the dense
  core (callsheets/schedule/scenes/cast/crew/locations) along its thickest edges →
  maximizes cross-agent contracts. The decomposition CHOICE created the
  Feed-Forward #1 risk.
- **M21 — Vertical trades assembly-time safety for spec-time burden.** Disjoint
  files → 0 conflicts + clean ownership gate, paid for by having to pin every
  cross-vertical contract (convergence/FC50/contract-check). Burden scales with
  coupling density; at Film PM's density it may exceed the benefit. Decomposition
  should follow the coupling graph (cut thin edges); "16 verticals" should be an
  OUTPUT, not an input.
- **M22 — Schema-behavior is an uncovered cross-agent contract class.** callsheets'
  idempotency depends on database's `ON DELETE CASCADE` — a behavioral dependency
  on another agent's schema, not covered by FC46 (phantom FK) or FC50 (signatures).
  Needs pinning ("this cascade exists BECAUSE callsheets regeneration needs it").
- **M23 — "0 merge conflicts" is a tautology / vanity metric.** Disjoint ownership
  makes 0 conflicts guaranteed by construction; it measures the ownership gate, not
  integration health. The real risk (semantic import mismatch) produces 0 conflicts
  and surfaces at runtime (run 069: 0 conflicts + 4 integration P1s). Retire it as
  a quality claim.
- **M24 — Model-layer ownership enforcement should be the default for multi-role
  apps.** Vertical slices push IDOR enforcement to N route leaves (N failure
  points). Enforcing ownership in the model layer (get_X(conn,id,user) refuses
  un-owned rows) makes IDOR impossible-by-construction.

## F. Security

- **M25 — Security = N independent implementations of a centralized policy.** Auth
  Matrix centralizes policy; 16 verticals hand-roll enforcement. require_role
  centralizes the role check; ownership is per-route (why FC35/IDOR recurs).
- **M26 — The highest-effort security hardening was exactly what the stale channel
  dropped.** F-H6 (dept-head ownership) was the one policy convergence promoted to
  "exact code"; it was one of the 4 sections missing from the stale plan. crew/
  expenses implemented it from prose+brief — the higher-risk path. Likeliest hiding
  spot for a subtle authz bug.
- **M27 — The FTS workaround created an unguarded cross-domain read aggregator.**
  Contentless FTS5 forced search() to read scenes/cast/crew/locations source tables
  directly, bypassing each vertical's access control and requiring 4-way scoping in
  one place. One scoping gap → 4-domain leak (FC23 enumeration shape via an FTS
  workaround). Highest-leverage security target, created accidentally by a schema
  constraint.
- **M28 — Centralized security = one agent's unreviewed judgment.** scaffold
  unilaterally made SESSION_COOKIE_SECURE conditional (correct, but no peer review
  on the security chokepoint).

## G. Cost / parallelism / scaling

- **M31 — Amdahl inversion: we parallelized ~8%.** Parallel workers ≈6 min of a
  ~70-min agent-time run; the serial tail (swarm-planner 26.8m, gates ~7m,
  spec-eval 6.3m, swarm-runner 12.3m, tail 17.6m) dominates. To speed autonomy,
  parallelize the TAIL, not add workers.
- **M32 — swarm-planner was 26.8 min of redundant critical-path work.** It
  re-derived an assignment the plan already contained + a patch script I discarded.
  Detect "assignment present in plan" → validate-only (30s), don't regenerate.

## H. Governance (frozen-branch model)

- **M33 — The freeze→validate→merge model has four cracks:** (a) circular
  validation (M5); (b) validated-copy ≠ merged-copy (M7); (c) no feedback edge —
  validation surfaced a hardening-adjacent issue with no path back to amend before
  merge; (d) freeze assumed a stationary master (it gained orphan f90aed8; required
  a pre-flight merge).
- **M30 — Findings land in a different artifact than the one under governance.**
  The run's key finding (spec-provenance) is an autopilot-SKILL bug, but the
  governance decision is "merge the hardening BRANCH." Correct merge + orphaned
  finding. Need a finding-routing step: every run-surfaced issue assigned an owning
  artifact before run close.

## I. Instrumentation & observability

- **M29 — The orchestrator is the only un-instrumented actor — and the only one
  that can die.** Delegates run in fresh contexts (can't die) and report
  tokens/duration; the orchestrator accumulates across 16 workers + delegations and
  reports nothing (context_proxy_chars stayed 0, a never-filled placeholder). We
  instrument the safe actors and fly blind on the fragile one.
- **M34 — Three continuous instruments already in the data, unused:** (a)
  tools-per-assigned-file as a spec-gap early-warning (search 9.5, tests 10 vs pack
  median ~3-5 — both hit real spec issues); (b) spec-eval pass-RATE as a spec-quality
  gradient (070: 262/277 = 5.4% fail) vs its binary verdict; (c) judgment-call count
  (M8) as incompleteness metric. None need new agents.

## J. Learning-loop / process

- **M6b — Missing escalation tier.** "Proceed vs abort" on the stale spec was a
  validity-affecting (not execution-blocking) judgment. The autonomy contract has
  only "handle silently" and "hard abort" — no middle tier for "anomaly that
  compromises the meaning of the result," exactly where an unattended run should
  surface to the operator.
- **M35 — Skill describes ~70%; the rest is orchestrator judgment, unspecified and
  unlogged.** ~7 load-bearing deviations this run (entry-point skip, run-id
  override, 9w.5 fix-and-retry vs abort, pre-flight master merge, keep-5/delete-28
  ghost nuance, split spawn, mid-swarm stale-spec decision). "Autopilot" is a
  capable agent following a thick checklist + improvising the rest. Needs a
  decision-log artifact (reasoning, not just outcomes).
- **M38 — Workers act as a distributed spec-review pass with no collection
  channel.** search/budget/tests caught real spec issues the gates can't (semantic
  feasibility). Surfaced only because the orchestrator read summaries closely. Add a
  required `SPEC_ISSUES:` field in worker output, aggregated pre-assembly.

## K. Positive patterns to harvest

- **M36b — Watch-item priming works.** Pre-loading a gate agent with known prior
  false-positives (the GET `<int:>` warning → 9w.6 didn't false-FAIL) is a cheap,
  high-yield steering mechanism. Inverse of pitfalls injection: tell GATES what GATES
  tend to get wrong. Systematize.
- **M-meta — Post-run meta-analysis is the highest-ROI artifact and isn't a phase.**
  This document only exists because it was requested. Self-audit asks "did we execute
  correctly?"; compound asks "what's the reusable solution?"; neither asks "what did
  this run teach about the system itself?" That's where compounding happens.

---

## Last three veins (mined after M1–M35) — see narrative for detail

- **M36 — Failure-triggered learning loop is blind to clean-run lessons &
  near-misses.** agent-pitfalls grows only on breakage. 070 (0 P1) "taught nothing"
  by that logic, yet surfaced 38 patterns. Success masks lessons; masked near-misses
  (the highest-value lessons, e.g. spec-provenance) are systematically
  under-captured. The registry is a graveyard (failure modes only), not a map (no
  mitigations-that-worked, no present-but-unfired risks). The loop is reactive
  (post-mortem); there is no pre-mortem / latent-risk capture.
- **M37 — 16 same-model workers: integration-consistency bought at the cost of
  error-decorrelation.** Homogeneous workers share blind spots → a real spec
  ambiguity gets the SAME wrong default 16×, looks "consistent," passes
  contract-check. Same-model correlation HELPED assembly (compatible gap-fills, M9)
  but HURTS detection. Same-model review is least able to catch same-model builder
  errors → the Codex-different-engine binding-review preference is error-
  decorrelation we hadn't named. Lever: deliberate model heterogeneity on high-risk
  slices (callsheets/search) and for review.
- **M38b — Completion ORDER determined detection latency and recovery cost.** The
  spec-divergence tell arrived at the 12th completion (callsheets) → caught at 12/16
  (recovery options already collapsed). Had callsheets finished first, catch at 1/16
  (cheap abort). Arrival order is duration-driven ≈ random. Compounding hazards:
  (a) anchoring — 11 confident successes before the worrying signal lowered
  vigilance; (b) the highest-signal workers (search/tests, high tool-use discovery
  agents) finish LAST, reporting when orchestrator context is fullest and the
  "build's done" anchor is set; (c) incremental completion-processing optimizes
  liveness but misses cross-cutting signals visible only in aggregate. Mitigation: a
  post-completion BATCH scan for cross-worker anomalies (e.g., spec-version
  agreement) would have caught the staleness systematically.
