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

## PARKED — drain these (recommended order: instruments first = nearly free, then planning, then governance, then small)

### Bucket 1 — Instruments / observability (cheapest, data already exists)
- **M29** — Instrument the orchestrator's own context (context_proxy_chars is a never-filled placeholder; the orchestrator is the only actor that can die and the only un-instrumented one). Wire a real proxy at each phase boundary; warn >~70% before Step 17w.
- **M34** — Surface three continuous instruments already in the telemetry: (a) tools-per-assigned-file as a spec-gap early-warning (070: search 9.5, tests 10 vs median ~3-5 = the two that hit real spec issues); (b) spec-eval pass-RATE as a spec-quality gradient (not just the binary verdict); (c) judgment-call count as an incompleteness metric. Likely a self-audit / BUILD_TRACKING addition.
- **M23** — Retire "0 merge conflicts" as a reported quality signal (tautology under disjoint ownership); replace with an integration-health metric (contract-check + import-resolution at boot). Edit wherever runs report "0 conflicts" as success.

### Bucket 2 — Spec-template / planning
- **M20/M21** — Coupling-aware decomposition: swarm-planner should read the Cross-Boundary Wiring density and choose cut-points that minimize cross-agent edges; "16 verticals" should be an OUTPUT, not a fixed template input. (swarm-planner agent + planning docs.)
- **M24** — Make model-layer ownership enforcement the DEFAULT for multi-role apps (get_X(conn,id,user) refuses un-owned rows) → IDOR impossible-by-construction. (spec-template + Authorization Matrix guidance.)
- **M11** — Feed-Forward calibration: divergence-risk ≠ coupling-density (a dense but model-pinned surface is low-risk). Fix how "least confident" items are chosen.
- **M16** — Convergence value audit: for each added section, did it change a worker decision? (a third of 070's convergence delta was restatement.)
- **M22** — Add "Schema-Behavior Contracts" surface to the spec template (cross-agent dependencies on cascade/constraint behavior, e.g., callsheets idempotency ← ON DELETE CASCADE). Between FC46 and FC50.

### Bucket 3 — Validation method / governance
- **M6** — Add an epistemic-quality axis to the Run Quality grade ("how strong is the evidence for the claim this run exists to support?") distinct from execution quality. (self-audit rubric + verify-self-audit.)
- **M7/M33** — Frozen-branch governance fixes: (a) assert validated-copy == merged-copy; (b) add a feedback edge (validation surfaced a hardening-adjacent issue → amend before merge); (c) freeze can't assume a stationary master. (governance doc.)
- **M10** — Re-promote / fix the feasibility gate: spec-eval is the ONLY gate covering the semantic-feasibility layer, which is where 070's real gaps lived (contentless-FTS impossibility, 8 judgment calls). Fix the harness (the demotion reason was ~0% failure-precision), don't abandon the layer.
- **M18** — Thin-brief validation mode: during VALIDATION runs, deliberately use minimal briefs so systemic bugs fail loudly instead of being masked by defensive briefing.

### Bucket 4 — Smaller pitfalls / skill
- **M27** — agent-pitfalls: cross-domain read aggregator (FTS workaround → 4-domain leak surface).
- **M26** — agent-pitfalls/security: prose→code authz translation is higher-risk; the highest-effort hardening (F-H6 exact-code) is exactly what the stale channel dropped.
- **M37** — agent-pitfalls: model-homogeneity correlated blind spots; deliberate model heterogeneity on high-risk slices + different-model review (decorrelation — the unstated reason for the Codex-binding-review preference).
- **M35** — SKILL: decision-log artifact (capture orchestrator pivot REASONING, not just outcomes; ~7 load-bearing deviations in 070).
- **M-meta** — make post-run meta-analysis a standard budgeted phase (this whole exercise only happened because it was requested).

## OPEN OPERATOR DECISIONS (NOT mine to execute — leave for the human)
1. **Merge** orchestration-hardening branch (feat/cpaa-event-replay-simulator) to master. Recommendation: GO for Tracks A & C (field-proven); Track B is fixture-worthy first (see M4 proposal) before claiming it field-proven.
2. **Push** either branch to remote (still local-only).

## Kickoff for the new session
Read docs/handoffs/run-070-meta-triage-continuation.md and docs/reports/070/meta-analysis.md.
Continue draining the PARKED meta-analysis patterns into their owning artifacts,
starting with Bucket 1 (instruments — nearly free). One bucket at a time; commit per
bucket. Do NOT touch the open operator decisions (branch merge / push).
