# HANDOFF — Sandbox · G3 Disconfirmer COMPOUND COMPLETE

**Date:** 2026-06-26
**Branch:** `feat/g3-verification-diversity` (pushed to origin; UNMERGED; working tree clean after the compound commits)
**Phase:** **G3 DONE through Compound. RECOMMENDED NEXT = consolidate + live-validate G1 & G3 (merge both to master, then one live autopilot run) BEFORE starting any new gate.**

## Recommended Next Move (start here)

**Don't start a third gate yet — consolidate and live-validate what's built.** There are now
**two** completed governance hardening features — **G1 firebreak** (`feat/g1-risk-tiered-firebreak`)
and **G3 disconfirmer** (`feat/g3-verification-diversity`) — both review-clean but **unmerged on
separate branches and never fired in a real autopilot run.** Both backlogs carry the *same* residual:
**"harness-green ≠ live."** Starting G2/G4/G5 (or the G3 disposition residual) stacks a third
unvalidated gate on that pile. Retire the shared residual once, for both:

1. **Merge `feat/g1-risk-tiered-firebreak` → master, then `feat/g3-verification-diversity` → master.**
   Both are review-clean (G1: ~17 passes + activation; G3: plan-review + efficacy probe + code-review
   GO). **GATE: needs explicit human go-ahead** (merge-to-master). Show each merge's diff stat first;
   do NOT push master without confirmation. Manual merge is fine (G1's "merge-to-main = RED" applies to
   autopilot, not a human session).
2. **Run ONE live autopilot build** that exercises the firebreak (G1) AND Gate 8 (G3) in a real tail —
   the positive-control / first-live-run validation both backlogs demand. **GATE: blocked on the
   `dangerouslySkipPermissions` env** (same blocker as Film-Production-PM). If the env isn't ready, do
   step 1 now to consolidate the base and tee up step 2 for when it is.
3. **Then** pick G2 (in-flight AI monitor) / G4 (per-run-nonce ledger) / G5 (delegation-as-authority)
   from a clean, validated, merged base — via `/workflows:brainstorm`, seeding from the governance
   scorecard.

**Why this over the alternatives:** starting a new gate or the G3 disposition residual adds MORE
unvalidated gate logic on top of two features that are "done but unproven, unmerged." Validate + merge
first; extend from a proven base.

## Current State

G3 ("carry the disconfirmer antidote into autopilot BUILD-verification") is **complete through the full compound loop** and review-clean. An Opus `self-audit-disconfirmer` now runs once, BEFORE the Sonnet `self-audit-reviewer`, in both the solo and swarm tails; its grounded `D#` findings become mandatory WARNs the self-audit disposes, enforced by a new deterministic fail-closed **Gate 8**. The verify-first efficacy risk was cleared cross-family (Opus generates → Codex judges): **novel-valid 4/4, overcall 0/25**. Codex code review went NO-GO (3 findings) → fixed (`65954b4`) → re-review **GO**. **G1 remains DONE/live on `feat/g1-risk-tiered-firebreak` (unmerged); do NOT reopen it.**

## Key Artifacts

| Phase | Location |
|-------|----------|
| Brainstorm | docs/brainstorms/2026-06-25-g3-verification-diversity-brainstorm.md |
| Plan (completed) | docs/plans/2026-06-25-feat-g3-self-audit-disconfirmer-plan.md |
| Efficacy probe (PASS) | docs/spikes/2026-06-25-g3-disconfirmer-efficacy-probe.md |
| Code-review handoffs (Codex) | docs/handoffs/2026-06-26-g3-disconfirmer-{code-review,rereview}-codex-handoff.md |
| Solution | docs/solutions/2026-06-26-g3-self-audit-disconfirmer.md |
| Governance scorecard (G3 row closed) | docs/governance/2026-06-21-autopilot-vs-three-layers-agent-security.md |

Changed components: `.claude/agents/self-audit-disconfirmer.md` (new), `.claude/agents/self-audit-reviewer.md`, `.claude/agents/tail-runner.md`, `.claude/skills/autopilot/SKILL.md`, `.claude/skills/verify-self-audit/SKILL.md`, `tools/verify_delegated_status.py`.

## Review Fixes Pending

None. All 3 Codex code-review findings fixed in `65954b4`; re-review GO, no new findings.

## Deferred Items

- **[G3 PRIMARY RESIDUAL] Disposition monoculture** — the lone Sonnet confirmer still *disposes* the disconfirmer's findings; nothing verifies a disposition is *correct*. Diversifying disposition without a binding LLM verdict or a loop = a candidate future G-gate.
- **[G3] Gate 8 not yet fired in a live tail** (harness-green ≠ live). A real autopilot run, or a positive-control probe (does a planted self-audit violation actually halt?), is the next validation.
- **Merge decision: G3 → master** — pending explicit go-ahead (G3 sits done-on-branch like G1).
- **[G1 backlog] FC51 orchestrator rule** — ensure the converged spec is at the worktree base before swarm spawn (cherry-pick the spec-update commit, OR inline-inject spec sections). The `check_spec_provenance.py` BASEREF-FRESH change is the *detection* half; the orchestrator *repair* rule remains.
- **Track A `P-extract`** — refactor `swarm-runner.md` cherry-pick prose into a shared callable so Track A earns a real EXERCISED fixture row. Overlaps the FC51 item.
- **Suite adoption decision** — wire `validate_hardening.py` in as a blocking gate (docs/proposals/validate-hardening-on-fixtures.md).
- **Eval-harness ↔ catalog FC drift** — harness covers 47 FCs; catalog is at FC1–FC57. Add scenarios/judges for FC48–FC57.
- **[070-W4] Todo #070 (P2, LOW)** — double `get_schedule_entries` in `callsheets.generate` (todos/070-pending-p2-...md).
- **Governance G2 / G4 / G5** — in-flight AI monitor (G2), per-run-nonce ledger hardening (G4), delegation-as-authority-transfer (G5).

## Three Questions

1. **Hardest decision?** Whether the disconfirmer's meta-objection needed its own binding `disconfirmer_verdict` field. Cut it — cosmetic AND it violated no-LLM-in-dispose-path; intent preserved via the deterministic Gates 2/5/7f.
2. **What was rejected?** A re-run/convergence loop (re-entry into the G1 trap); a binding/unilateral-BLOCK disconfirmer; bumping the reviewer to Opus (scope creep); a weaker Sonnet/Haiku disconfirmer.
3. **Least confident about?** The PRIMARY RESIDUAL — disposition monoculture (detection is diversified, disposition is not) — and that Gate 8 has not yet fired in a real live tail.

## Prompt for Next Session

```
Read HANDOFF.md, "Recommended Next Move" first. This is sandbox. Both G1 (risk-tiered
firebreak, feat/g1-risk-tiered-firebreak) and G3 (self-audit disconfirmer,
feat/g3-verification-diversity) are DONE, review-clean, and COMPOUND COMPLETE but UNMERGED
and never run live. Do NOT reopen either's design.

RECOMMENDED PATH — consolidate + live-validate before any new gate:
1. Merge G1 -> master, then G3 -> master. Show me each merge's diff stat FIRST; do NOT push
   master without my explicit confirmation (merge-to-master needs go-ahead). Manual merge is
   fine — G1's "merge-to-main = RED" applies to autopilot, not a human session.
2. Run ONE live autopilot build that exercises the firebreak (G1) AND Gate 8 (G3) in a real
   tail = the first-live-run / positive-control validation both backlogs demand. BLOCKED on
   the dangerouslySkipPermissions env; if not ready, do step 1 now and tee up step 2.
3. THEN start G2/G4/G5 from a clean, validated, merged base via /workflows:brainstorm,
   seeding from docs/governance/2026-06-21-autopilot-vs-three-layers-agent-security.md.

If I instead want to extend now: the G3 PRIMARY RESIDUAL is diversifying self-audit
DISPOSITION (not just detection) without a binding LLM verdict or a loop — but prefer
validate+merge first (this is more unvalidated gate logic otherwise).

G3 invariants if anything touches it: self-audit-reviewer stays model: sonnet; Gate 8
fail-closed + literal-token; no loop; no binding LLM verdict; enum ACCEPTED/PROMOTED/DEFERRED.
Solution doc: docs/solutions/2026-06-26-g3-self-audit-disconfirmer.md.
```
