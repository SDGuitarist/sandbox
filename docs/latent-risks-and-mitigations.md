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

Full derivation: `docs/reports/070/meta-analysis.md` (patterns M1-M38).
First population: Run 070 (2026-06-08). Append after each run's meta-analysis pass.
