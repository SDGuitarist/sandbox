# Latent Risks & Working Mitigations (the inverse registry) (M36)

**Why this exists.** `agent-pitfalls.md` grows by exactly one mechanism: something
breaks → a new FC. It is a graveyard of failure modes. It cannot capture (a) what
*prevented* failure and why, or (b) risks that were *present but did not fire*.
Run 070 had **0 P1s** — by the failure-triggered loop it "taught nothing," yet it
surfaced 38 system-level patterns. The most valuable was a *masked near-miss*
(spec-provenance), which is exactly the class the failure loop is worst at: success
masks the lesson. This file is the counter-registry — fed by clean-run meta-analysis,
not by breakage.

**Process (proposed).** After every run — *especially* 0-P1 runs — a meta-analysis
pass (a budgeted phase, distinct from self-audit "did we execute correctly?" and
compound "what's the reusable solution?") asks **"what did this run teach about the
system?"** and writes: new FCs → agent-pitfalls; working mitigations + latent risks →
here. Before a build, a **pre-mortem** consults the Latent Risks below for trigger
conditions matching this build's shape.

---

## Working Mitigations (what prevented failure — with evidence)

| Mitigation | Evidence | Caveat / failure mode |
|---|---|---|
| **Model-layer pinning** of cross-boundary fns prevents FC50-class divergence | Run 070 callsheet 6-import all model-layer → 0 integration P1; Run 069 route→orchestration unpinned → 4 P1 | Holds only while coupling stays model-layer (M11) |
| **Independent re-validation before spawn** (re-run 9w.5 even on a "converged" spec) | 070: 9w.5 found 3 fresh cross-section issues post-Codex+human-gate (M12) | "Converged" decays per edit — must re-run as last step |
| **Disk-verify over wire STATUS** for delegated artifacts | 070: kept orchestrator lean across 16 workers + 3 delegations; context held | Only as good as the artifact freshness check (run_start_ts) |
| **Pre-flight merge to restore O3 invariant** (worktree-root == merge-base) | 070: enabled clean per-worker cherry-pick, 0 conflicts | Fixes CODE assembly, NOT the spec channel (FC52 still applied) |
| **Watch-item priming** of gate agents with known false-positives | 070: GET `<int:>` warning → 9w.6 did not false-FAIL (M36b) | Manual today; should be systematized |
| **Contract-rich defensive briefs** backfilled a stale spec file | 070: workers spec-compliant despite reading the stale plan | DOUBLE-EDGED — also *masks* divergence (see Latent: FC52). A mitigation that hides the bug it mitigates. |

## Latent Risks (present in run 070 but did NOT fire — with trigger conditions)

| Risk | Why it didn't fire in 070 | Trigger that WILL fire it |
|---|---|---|
| **FC52 provenance drift → silent stale-spec build** | Defensive briefs happened to carry the convergence fixes | Thin "read the spec" briefs + worktree-base spec divergence → silent catastrophe (M18) |
| **Model-homogeneity correlated blind spots** | No genuine spec ambiguity hit a shared wrong default | A real ambiguity → 16 identical wrong defaults → passes contract-check (internal consistency ≠ correctness) (M37) |
| **Non-reproducibility from judgment DOF** | ~8 independent gap-fills happened to be mutually compatible | Re-run with different fills → cross-boundary collision at contract-check (M9) |
| **Cross-domain read aggregator (search)** | search scoping was correct | One scoping gap in `search()` → simultaneous 4-domain data leak (M27) |
| **F-H6 prose→code authz translation** | crew/expenses translated dept-head scope correctly | A subtle own-dept/created_by mistranslation → IDOR; likeliest authz bug site (M26) |
| **Schema-behavior cross-agent contract** | database shipped `ON DELETE CASCADE` as callsheets assumed | database changes a cascade to RESTRICT → callsheet idempotency breaks silently (M22) |
| **Serial-tail Amdahl ceiling** | 16 agents stayed under budget | Scaling agent count yields ~no speedup; tail (≈92% of wall-clock) dominates (M31) |
| **Un-instrumented orchestrator context** | held at 16 agents | 20+ agent run → orchestrator context death with no warning instrument (M29) |
| **Feasibility layer ungated** (spec-eval demoted) | Film PM's feasibility gaps were caught by implementers post-spawn | A feasibility impossibility no implementer notices → ships (M10) |

---

## Pre-mortem actions for the security-shaped latent risks (Bucket 4 enrichment, 2026-06-08)

These three did NOT fire in 070, so they are NOT failure classes (no FC ID minted —
the registry is for observed breakage). But their mitigations are already known, so a
pre-mortem whose build matches the trigger should apply them:

- **M27 — Cross-domain read aggregator** (e.g. an FTS/search workaround that reads
  several ownership domains' source tables directly). When one function must read
  across N domains because a constraint forces it to bypass each domain's accessor
  (070: contentless FTS5 made `search()` read scenes/cast/crew/locations directly),
  that function becomes the single place where ALL N domains' authorization must be
  re-enforced — one scoping gap = N-domain leak. **Mitigation:** (a) route the
  aggregator's reads through the same ownership-scoped accessors as M24 (model-layer
  enforcement) instead of raw table reads, so per-domain scoping can't be forgotten;
  (b) if raw reads are unavoidable, add an explicit N-way scope assertion with one
  test per domain. Treat the aggregator as the build's highest-leverage security
  target. Generalizes the FC23 enumeration shape; neighbor of FC35/FC36.

- **M26 — prose→code authorization translation is the higher-risk path.** The hardest
  authz rules (070: F-H6 dept-head ownership) are exactly the ones a stale or thin
  spec channel is most likely to drop to *prose*, forcing each agent to re-derive the
  code — the likeliest hiding spot for a subtle authz bug. **Mitigation:** any authz
  rule above a trivial role-check must be pinned as EXACT CODE in the spec (not
  prose), and is a mandatory review-scrutiny target. Cross-ref M24 — model-layer
  enforcement removes the per-route translation entirely for ownership.

- **M37 — model-homogeneity correlated blind spots.** N same-model workers share blind
  spots: a real spec ambiguity gets the SAME wrong default N times, looks
  "consistent," and passes contract-check (internal consistency ≠ correctness).
  Same-model REVIEW is least able to catch same-model BUILDER errors. **Mitigation:**
  (a) deliberate model heterogeneity on the highest-risk slices (search, callsheets)
  so a shared wrong default is less likely; (b) different-engine binding review — this
  is the previously-unnamed reason the Codex-manual-review preference works
  ([[feedback_codex_manual_review]]): it is error DECORRELATION, not just a second
  opinion. Tension: same-model correlation HELPS assembly (compatible gap-fills, M9)
  but HURTS detection — so apply heterogeneity surgically on high-risk slices, not
  everywhere.

---

Full derivation: `docs/reports/070/meta-analysis.md` (patterns M1-M38).
First population: Run 070 (2026-06-08). Append after each run's meta-analysis pass.
