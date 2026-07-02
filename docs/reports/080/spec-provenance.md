STATUS: PROVENANCE_REPAIRED -- inline-injection-FALLBACK

# Spec Provenance Gate — run 080

## Pre-check (FC52-BASEREF-FRESH-071)
- `git rev-parse master` == `git rev-parse origin/master` == `85be609d50bf35b18df9ac4f9f16475f8adea7ba` (EQUAL — no local-ahead divergence, no push needed).

## Detect
- Detector: `tools/check_spec_provenance.py --default-branch master --original-branch feat/shelftrack-reading-list --spec-path docs/plans/2026-06-30-shelftrack-reading-list.md`
- Result: `STATUS: PROVENANCE_DRIFT` (exit 3)
- Pre-repair blob SHAs:
  - default (origin/master): **ABSENT** (the plan does not exist on master — it was authored on the feature branch)
  - original (feat/shelftrack-reading-list): `ae9f45c40c116323ef61da6e116e5ed68647db9e`

## Repair — FALLBACK: inline brief injection (NOT the cherry-pick channel)
The cherry-pick primary would commit the spec onto master, mutating the shared default
branch. The operator explicitly chose "master UNCHANGED" for this run (the base already
carries an unrelated prior `app/` build; ShelfTrack is namespaced under `shelftrack/` to
avoid touching it). Inline injection is the sanctioned fallback and is already the native
channel of this pipeline: Step 10w builds every worker prompt containing the FULL shared
interface spec, and each worker brief states the brief is AUTHORITATIVE over any worktree
spec file. Workers do NOT read `docs/plans/...md` from their worktree at all.

## Re-verify (audit, NOT equivalence proof)
Per the injection-fallback contract, the detector still reports `PROVENANCE_DRIFT` (the
file channel is unchanged — the spec remains absent on master). This is EXPECTED for the
fallback and is recorded as an audit step, explicitly **labeled: FALLBACK — not an
equivalence proof.**

### Injected-section manifest (full spec injected into every worker brief)
Because the spec is ABSENT on the worker base, the ENTIRE converged spec is injected inline.
Sections injected (all `##` headings of the plan):
Overview; 1. What exactly is changing?; 2. What must NOT change?; 3. How will we know it
worked?; 4. Most likely way this plan is wrong; Acceptance Tests (EARS); App Configuration;
Database Connection + Schema; login_required decorator; Model Functions; Route Table;
Template Render Context; Export Names Table; Cross-Boundary Wiring Table; Input Validation
Prescriptions; Coordinated Behaviors; Transaction Contracts; Authorization Matrix; Swarm
Agent Assignment; File Assignment Boundaries; Smoke Test; Deferred Hardening; Feed-Forward.

## Cleanup contract
N/A — the repair did NOT mutate master (no spec-only commit was cherry-picked). There is no
side effect on the default branch to revert or carry forward.

## Guarantee
Every worker receives the byte-identical converged spec inline (the gate-validated
feature-branch spec, blob `ae9f45c4...`), and is instructed the brief overrides any worktree
file. The gated spec == the used spec via the brief channel.
