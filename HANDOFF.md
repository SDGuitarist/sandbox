# HANDOFF — Sandbox · G1 + G3 CONSOLIDATED ON MASTER (live-validation pending)

**Date:** 2026-06-26
**Branch:** `master` (G1 firebreak **and** G3 disconfirmer merged + **pushed to origin**, `c81486c`). Working tree clean.
**Phase:** **Step 1 (consolidate) DONE. NEXT = Step 2: one live autopilot run to validate the firebreak (G1) + Gate 8 (G3) — BLOCKED on the `dangerouslySkipPermissions` launch env. Do NOT start a new gate (G2/G4/G5) until that live run happens.**

## Recommended Next Move (start here)

**Step 1 is complete — both gates are merged to master and pushed.** G1 firebreak and G3
disconfirmer no longer live on separate unmerged branches; `master` (`c81486c`) carries both.
The shared residual is now narrowed to its second half: **"harness-green ≠ live."** One thing
stands between here and a clean base for G2/G4/G5:

1. ~~Merge G1 → master, then G3 → master.~~ **DONE** (2026-06-26). G1 fast-forwarded; G3 was a
   3-way merge (`autopilot/SKILL.md` auto-merged cleanly — firebreak wiring + disconfirmer
   section coexist, gate count = 8; `HANDOFF.md` + `compound-engineering.local.md` conflicts
   resolved to the G3 version). Merge commit `c81486c`, pushed to `origin/master`.
2. **Run ONE live autopilot build** that exercises the firebreak (G1) AND Gate 8 (G3) in a real
   tail — the positive-control / first-live-run validation both backlogs demand. **GATE: blocked
   on the `dangerouslySkipPermissions` launch env** (same blocker as Film-Production-PM). The
   working-tree `.claude/settings.local.json` has the flag, but the run needs a dedicated
   *unattended autopilot launch* — it cannot be fired from inside a normal interactive session.
   **Validation target:** (a) the firebreak positive-control probe trips, AND (b) a *planted*
   self-audit violation actually halts via Gate 8 (does the fail-closed gate really fire live?).
3. **Then** pick G2 (in-flight AI monitor) / G4 (per-run-nonce ledger) / G5 (delegation-as-authority)
   from the now-clean, merged base — via `/workflows:brainstorm`, seeding from the governance
   scorecard. **Still gated on Step 2 finishing first** — don't stack a third unvalidated gate.

**Why this order:** the base is now consolidated and durable, but neither gate has fired in a
real run. Live-validate before extending; a planted-violation positive-control is worth more than
any further bench-green.

## Current State

Both governance hardening features are **merged to `master` and pushed** (`c81486c`):

- **G1 firebreak** (was `feat/g1-risk-tiered-firebreak`) — risk-tiered PreToolUse classifier +
  sentinel lifecycle + orchestrator wiring + positive-control probe. ~17 convergence passes +
  activation. DONE/live-wired, not yet fired in a real swarm.
- **G3 disconfirmer** (was `feat/g3-verification-diversity`) — an Opus `self-audit-disconfirmer`
  runs once, BEFORE the Sonnet `self-audit-reviewer`, in both solo and swarm tails; its grounded
  `D#` findings become mandatory WARNs the self-audit disposes, enforced by deterministic
  fail-closed **Gate 8**. Efficacy cleared cross-family (Opus generates → Codex judges:
  novel-valid 4/4, overcall 0/25). Codex code review NO-GO (3 findings) → fixed (`65954b4`) →
  re-review GO.

The feature branches still exist (local + origin) but are now fully contained in master; they can
be deleted once Step 2 confirms the merged base is sound. **Do NOT reopen either's design.**

## Key Artifacts

| Phase | Location |
|-------|----------|
| G1 plan | docs/plans/2026-06-21-feat-g1-risk-tiered-firebreak-plan.md |
| G1 solution (activation arc) | docs/solutions/2026-06-25-g1-firebreak-activation-arc.md |
| G1 solution (denylist vs backstop) | docs/solutions/2026-06-24-enumerated-denylist-vs-structural-backstop.md |
| G3 brainstorm | docs/brainstorms/2026-06-25-g3-verification-diversity-brainstorm.md |
| G3 plan (completed) | docs/plans/2026-06-25-feat-g3-self-audit-disconfirmer-plan.md |
| G3 efficacy probe (PASS) | docs/spikes/2026-06-25-g3-disconfirmer-efficacy-probe.md |
| G3 solution | docs/solutions/2026-06-26-g3-self-audit-disconfirmer.md |
| Governance scorecard (G1+G3 rows closed) | docs/governance/2026-06-21-autopilot-vs-three-layers-agent-security.md |

Merged components: `.claude/hooks/firebreak-*.py` + tests (G1), `.claude/agents/self-audit-disconfirmer.md` (new, G3), `.claude/agents/self-audit-reviewer.md`, `.claude/agents/tail-runner.md`, `.claude/skills/autopilot/SKILL.md`, `.claude/skills/verify-self-audit/SKILL.md`, `tools/verify_delegated_status.py`.

## Review Fixes Pending

None. G1 review-clean (~17 passes + Codex GO); G3 all 3 Codex code-review findings fixed in `65954b4`, re-review GO. Merge itself: `autopilot/SKILL.md` auto-merge verified semantically correct (both feature surfaces present, gate count 8, no conflict markers).

## Deferred Items

- **[STEP 2 — top priority] Live-validate G1 + G3 in one real tail** (harness-green ≠ live). A real autopilot run, or a positive-control probe (does a *planted* self-audit violation actually halt via Gate 8? does the firebreak probe trip?), is the next validation. Blocked on the `dangerouslySkipPermissions` unattended-launch env.
- **[G3 PRIMARY RESIDUAL] Disposition monoculture** — the lone Sonnet confirmer still *disposes* the disconfirmer's findings; nothing verifies a disposition is *correct*. Diversifying disposition without a binding LLM verdict or a loop = a candidate future G-gate. (Prefer Step 2 before opening this.)
- **Branch cleanup** — `feat/g1-risk-tiered-firebreak` and `feat/g3-verification-diversity` (local + origin) are fully merged into master; safe to delete after Step 2 confirms the base is sound.
- **[G1 backlog] FC51 orchestrator rule** — ensure the converged spec is at the worktree base before swarm spawn (cherry-pick the spec-update commit, OR inline-inject spec sections). The `check_spec_provenance.py` BASEREF-FRESH change is the *detection* half; the orchestrator *repair* rule remains.
- **Track A `P-extract`** — refactor `swarm-runner.md` cherry-pick prose into a shared callable so Track A earns a real EXERCISED fixture row. Overlaps the FC51 item.
- **Suite adoption decision** — wire `validate_hardening.py` in as a blocking gate (docs/proposals/validate-hardening-on-fixtures.md).
- **Eval-harness ↔ catalog FC drift** — harness covers 47 FCs; catalog is at FC1–FC57. Add scenarios/judges for FC48–FC57.
- **[070-W4] Todo #070 (P2, LOW)** — double `get_schedule_entries` in `callsheets.generate` (todos/070-pending-p2-...md).
- **Governance G2 / G4 / G5** — in-flight AI monitor (G2), per-run-nonce ledger hardening (G4), delegation-as-authority-transfer (G5). Gated on Step 2.

## Three Questions

1. **Hardest decision?** Resolving the G3 merge conflicts — confirmed both `HANDOFF.md` and `compound-engineering.local.md` are "last-compound-wins" files (G1 and G3 each rewrote them wholesale), so taking the G3 version was correct, not a loss of G1 content. Verified the auto-merged `autopilot/SKILL.md` kept both surfaces.
2. **What was rejected?** Deleting the feature branches immediately post-merge (kept them until Step 2 proves the merged base); running the live validation from this interactive session (not possible — needs an unattended launch).
3. **Least confident about?** Whether Gate 8 and the firebreak actually fire in a real live tail — neither has run outside the bench. That is exactly what Step 2's planted-violation positive-control is for.

## Prompt for Next Session

```
Read HANDOFF.md, "Recommended Next Move" first. This is sandbox. G1 (firebreak) and G3
(self-audit disconfirmer) are now BOTH MERGED to master and pushed (c81486c). Step 1
(consolidate) is DONE. Do NOT reopen either's design, and do NOT start a new gate yet.

NEXT = Step 2: one live autopilot build that validates the merged base —
  (a) the firebreak positive-control probe trips, AND
  (b) a PLANTED self-audit violation actually halts via the fail-closed Gate 8.
This is the first-live-run / positive-control both backlogs demand. BLOCKED on the
dangerouslySkipPermissions unattended-launch env (same blocker as Film-Production-PM).
If the env is ready, run that build. If not, the cleanest available work is branch
cleanup (delete the two fully-merged feature branches) or teeing up the Step 2 plan.

ONLY after Step 2: start G2/G4/G5 from the clean validated base via /workflows:brainstorm,
seeding from docs/governance/2026-06-21-autopilot-vs-three-layers-agent-security.md.

If extending instead: the G3 PRIMARY RESIDUAL is diversifying self-audit DISPOSITION (not
just detection) without a binding LLM verdict or a loop — but prefer Step 2 first.

G1/G3 invariants if anything touches them: self-audit-reviewer stays model: sonnet; Gate 8
fail-closed + literal-token; no loop; no binding LLM verdict; enum ACCEPTED/PROMOTED/DEFERRED;
firebreak classifier is deny-known-bad with a STRUCTURAL backstop (no enumerated exemptions).
Solution docs: docs/solutions/2026-06-26-g3-self-audit-disconfirmer.md,
docs/solutions/2026-06-25-g1-firebreak-activation-arc.md.
```
