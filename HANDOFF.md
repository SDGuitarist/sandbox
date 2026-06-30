# HANDOFF — Sandbox · FC58 FIXED + MERGED + HOOK REPOINTED · NEXT = COEXISTENCE RE-VALIDATION

**Date:** 2026-06-29
**Branch:** `master` @ `2c23724`+ (HANDOFF commits after) — **FC58 fix cycle merged (`--no-ff`) and pushed.** Working tree clean.
**Phase:** **FC58 (the run-079 P1) is FIXED + reviewed (security=SAFE, architecture=mergeable) + merged (279/279 tests). Step 2 hook repoint DONE + live-probe-verified — the FC58-fixed classifier is now what the global firebreak hook invokes (effective next session). NEXT = Step 3 (coexistence re-validation: a live autopilot run with the firebreak active THROUGH the tail, to close `[079-W3]`). G2/G4/G5 still gated behind the re-validation. `sandbox-g1` worktree is no longer load-bearing → can be torn down (Step 4).**

## Honest validation status (read this before claiming "done")

- **G1 — clean PASS.** The live firebreak denied a real worktree worker's three control-plane writes; the deterministic no-canary verdict holds, and the false-GREEN concern was closed *empirically* (the deferred-action queue recorded the main-repo absolute path — the write would have landed where the verdict checked had the firebreak been inert). Strongest evidence type available.
- **G3 — PASS with an asterisk.** Gate 8 passed all 8 on real artifacts in the live tail (disconfirmer D1–D4 → bijected WARNs W1–W4). BUT the tail ran **firebreak-OFF** (FC58 forced an early teardown). So **G1+G3 simultaneous coexistence under production conditions was never tested** — `[079-W3]`, severity HIGH. Even "Gate-8 logic isn't python-blocked" is a *code-trace inference*, not empirically confirmed this run. The self-audit graded itself honestly: G1 individual **A**, G3 individual **B**, G1+G3 simultaneous **D (ABSENT)**.
- **Run status:** `PIPELINE_PASS_WITH_DEFERRED_RISK` (honest — FC58 deferred).

## What Was Accomplished (latest — FC58 fix cycle, 2026-06-29)

The FC58 fix cycle (handoff Step 1) is **DONE + merged to master** (`2c23724`, pushed). 5 commits + merge on `feat/fc58-firebreak-trusted-indirection`:

1. **Todo 071 (P1)** — added `TRUSTED_PIPELINE_SCRIPTS` allowlist + `trusted_pipeline_indirection_ok()` pre-check before the `bash_indirection` call in `classify_simple_command`. **Narrow carve-out: TRUSTED identity + `python`/`python3` interpreter + allowlisted script BASENAME only.** Waives ONLY the indirection defer; control-plane/destructive/outward checks still run first. Workers stay fully governed; fails closed.
2. **Todo 072 (P1, HYBRID — operator-chosen)** — Step 18w `deactivate` → `rm .claude/firebreak-active.json` (independent teardown, does not depend on the carve-out). Step 17w `set-phase tail` **kept as python** (now GREEN via 071) because it is a field-preserving read-modify-write; a blind Write would clobber `run_id`/`repo_root`. Abort-path teardown (SKILL.md line ~947) also → `rm`. Maintainer note added so new python gate tools get added to the allowlist.
3. **Todo 073 (P2)** — 14 FC58 classifier tests (incl. the `python3 -c` inline-code DENY and command-sub DENY that pin the "any python" boundary). **279/279 pass** (was 265).
4. **Review** (separate context, two agents): security-sentinel = **SAFE-WITH-NOTES, no P0, no worker escape, fails closed**; architecture-strategist = **mergeable as-is**, structural-backstop concern cleared (carve-out is on the *governing* TRUSTED population + finite-frozen-allowlist = the non-looping case).
5. **Todo 074 (P2) created + deferred** — path-pin the allowlist to retire two trusted-only residuals (basename-no-path-pin; `first_verb` `-W` flag-value mis-pick). Both reviewers rated it optional hardening, not a blocker.

### Earlier this session (run 079 — G1+G3 live validation)
1. Consolidated G1 firebreak + G3 disconfirmer onto master; live run 079 fired both gates; **FC58 discovered** and merged with the run-079 record (`fed9644`). The throwaway `validation-notes/` app rode along (isolated, deletable later).

## Recommended Next Move (start here — fresh session)

**Steps 1 + 2 are COMPLETE.** Do NOT start G2/G4/G5 yet. Remaining sequence:

**Step 2 — Repoint the global firebreak hook → main repo. ✅ DONE (2026-06-29).** `~/.claude/settings.json` line 114 now execs `/Users/alejandroguillen/Projects/sandbox/.claude/hooks/firebreak-gate.sh` (was `sandbox-g1`). Verified: gate scripts byte-identical between trees; gate locates the classifier via `$HOOK_DIR` (so it now uses the main-repo FC58-fixed classifier); sentinel resolution is cwd-anchored (`find_sentinel` walks up from cwd / `FIREBREAK_SENTINEL`), independent of gate location — no path reconciliation needed. Live gate→classifier probe passed: orchestrator allowlisted python → ALLOW, `firebreak-activate.py set-phase` → ALLOW, worker python → DENY, orchestrator `python3 -c` → DENY. Backup at `~/.claude/settings.json.bak-fc58-repoint`. **Caveat:** Claude Code loads hooks at session start, so a session already running before the edit keeps the old path in memory — the repoint is effective for the NEXT session / autopilot run (which is what Step 3 needs anyway). The `sandbox-g1` worktree is now NO LONGER load-bearing → safe to tear down in Step 4.

**Step 3 — Coexistence re-validation run. ⬅ START HERE.** A new live autopilot run with the firebreak **active through the tail**, to actually close `[079-W3]` (G1+G3 simultaneous, never tested live together). With FC58 fixed + the hook repointed, the tail's `verify_delegated_status.py` disk-verify gates and `set-phase tail` now run GREEN under the active firebreak, so the firebreak no longer has to tear down before the tail. This is a full unattended autopilot run (needs a throwaway spec + `dangerouslySkipPermissions` env) — kick off deliberately.

**Step 4 — `sandbox-g1` worktree teardown + branch cleanup** (deferred all session). Order: hook already repointed (Step 2) → `git worktree remove sandbox-g1` → delete `feat/g1-risk-tiered-firebreak`, `feat/g3-verification-diversity`, `feat/g1-g3-live-validation`, **and `feat/fc58-firebreak-trusted-indirection`** (local + remote; all merged).

**Step 5 — THEN G2/G4/G5** (in-flight AI monitor / per-run-nonce ledger / delegation-as-authority) via `/workflows:brainstorm`, seeding from the governance scorecard.

**Also pending (low-priority, anytime):** the compound/solution-doc for the FC58 fix is best written AFTER Step 3 closes `[079-W3]` (so the "harness-green ≠ live, bi-directional" lesson lands with the coexistence proof). Todo 074 (path-pinning) is the one open FC58 follow-up.

## Current State

- **master @ `2c23724`** (pushed) carries everything from `fed9644` PLUS the merged FC58 fix cycle (classifier carve-out, hybrid lifecycle, 14 tests, todos 071–073 complete + 074 deferred).
- **FC58 is FIXED on master but NOT LIVE.** The global firebreak hook still execs the stale `sandbox-g1` worktree classifier — the merged fix runs live only after the Step-2 hook repoint.
- **`sandbox-g1` worktree** (on `feat/g1-risk-tiered-firebreak`, `6dd621a`) is STILL load-bearing — the global firebreak hook execs its `firebreak-gate.sh`. Do not remove it before the Step-2 hook repoint.
- **Global propagation done by run 079's tail:** `~/.claude/docs/agent-pitfalls.md` (FC58 entry, 2026-06-29) and the auto-MEMORY. No need to re-propagate. (The FC58 *fix* lesson is not yet propagated — pending the post-Step-3 compound doc.)
- Feature branches `feat/g1-risk-tiered-firebreak`, `feat/g3-verification-diversity`, `feat/g1-g3-live-validation`, `feat/fc58-firebreak-trusted-indirection` all merged into master, deletion pending Step 4.

## FC58 — the finding + the fix (do NOT overclaim)

**Finding:** the G1 firebreak's `bash_indirection` check was **identity-agnostic**. Under an active sentinel it deferred all Bash-python, incl. (a) `python3 tools/verify_delegated_status.py` (Steps 11w–18w disk-verify — no non-python fallback); (b) `python3 .claude/hooks/firebreak-activate.py set-phase tail` (17w); (c) `... deactivate` (18w teardown). **Scope = Bash-invoked python (orchestrator pipeline tooling + firebreak lifecycle), NOT Gate-8 logic** (`verify-self-audit` is Read/Grep/Glob).

**Fix (merged `2c23724`):** a narrow carve-out — a TRUSTED identity running `python`/`python3` on an allowlisted script BASENAME (`verify_delegated_status.py`, `check_spec_provenance.py`, `firebreak-activate.py`) skips ONLY the indirection defer. Plus `rm`-based independent teardown for `deactivate`. Reviewed SAFE (no worker escape, fails closed). **Accepted residuals (todo 074, P2):** basename-match has no path-pin, and `first_verb` doesn't model python's flag-value grammar — both trusted-only, low realistic exploitability. Cross-project lesson: *harness-green ≠ live is bi-directional — an inert gate AND a too-broad gate are both invisible to unit tests* (the FC58 lifecycle tests now exercise an active on-disk sentinel to catch exactly this).

## Key Artifacts

| Item | Location |
|------|----------|
| **Solution doc (run 079)** | **docs/solutions/2026-06-26-g1-g3-live-validation.md** |
| Live-validation brief/plan | docs/plans/2026-06-26-g1-g3-live-validation-run-brief.md |
| Firebreak probe (G1 PASS) | docs/reports/079/firebreak-probe.md |
| FC58 deadlock finding (P1) | docs/reports/079/firebreak-deadlock-finding.md |
| Disconfirmer (G3) / Self-audit | docs/reports/079/disconfirmer.md · docs/reports/079/self-audit.md |
| FC58 fix (classifier + helper) | .claude/hooks/firebreak-classify.py (`TRUSTED_PIPELINE_SCRIPTS`, `trusted_pipeline_indirection_ok`) |
| FC58 tests (14 cases) | .claude/hooks/test_firebreak_classify.py (FC58 block, 279/279) |
| FC58 fix todos | todos/071-complete-…, 072-complete-…, 073-complete-…; **074-pending** (path-pin, deferred) |
| G1 solution (activation arc) | docs/solutions/2026-06-25-g1-firebreak-activation-arc.md |
| G3 solution | docs/solutions/2026-06-26-g3-self-audit-disconfirmer.md |
| Governance scorecard | docs/governance/2026-06-21-autopilot-vs-three-layers-agent-security.md |
| FC58 in registry | ~/.claude/docs/agent-pitfalls.md (FC58) |

## Deferred Items

- **[079-W3, HIGH] G1+G3 coexistence empirically unverified** — G3 tail ran firebreak-OFF; production condition (firebreak active through the tail) never tested. FC58 fixes are now MERGED (the disagreement about whether Gate-8/pipeline python can run under an active sentinel is resolved in code + tests), so the remaining resolution is: hook repoint (Step 2) → re-validation run (Step 3).
- **[FC58-DISKVERIFY-079, P1] DONE** — trusted-tool indirection allowlist (todo 071, merged `2c23724`).
- **[FC58-LIFECYCLE-079, P1] DONE** — lifecycle teardown hotfix (todo 072, hybrid, merged).
- **[FC58-LIVETEST-079, P2] DONE** — 14 lifecycle/boundary tests (todo 073, merged, 279/279).
- **[FC58-PATHPIN, P2] NEW** — path-pin the allowlist to retire the two trusted-only residuals (todo 074, pending).
- **[HOOK-PATH-REPOINT] DONE (2026-06-29)** — `~/.claude/settings.json` line 114 repointed to the main-repo gate; live probe verified the FC58-fixed classifier runs. Effective next session (hooks load at session start). `sandbox-g1` worktree no longer load-bearing → tear down in Step 4. Rollback backup: `~/.claude/settings.json.bak-fc58-repoint`.
- **[G3-RESIDUAL-DISPOSITION]** Disposition monoculture — the lone Sonnet confirmer disposes disconfirmer D# findings; nothing verifies a disposition is *correct*. Candidate future G-gate. Prefer after FC58 + coexistence.
- **[070-W4] Todo #070 (P2, LOW)** — double `get_schedule_entries` in `callsheets.generate`.
- **[G2/G4/G5]** Governance gates — **gated behind FC58 fixes + the coexistence re-validation.** Then `/workflows:brainstorm` from the scorecard.

## Three Questions

1. **Hardest decision?** Todo 072's approach now that 071 already makes the python lifecycle commands GREEN. Chose **hybrid** (operator-confirmed): `deactivate` → independent `rm` (robust, doesn't depend on the carve-out), but `set-phase` kept as python (it's a field-preserving read-modify-write; a raw Write would clobber `run_id` and break the Step-18w disk-verify). Full Solution-A (convert both) was rejected as more fragile.
2. **What was rejected?** Path-pinning the allowlist now (deferred to todo 074 — the invariant says "basename-match only", and both reviewers rated path-pin optional). Also rejected: converting ALL deactivate calls to `rm` (only the live-under-active-firebreak ones — 18w + the 947 abort path — were switched; failure-path 729 is FAIL-OPEN, human-recovery 744 works via orchestrator identity).
3. **Least confident about?** Whether the Step-2 hook repoint cleanly reconciles the sentinel write/read paths once the live hook points at the main repo (the run-079 "harness-green ≠ live" lesson). Verify with a live probe right after repointing, before the Step-3 re-validation run.

## Prompt for Next Session

```
Read HANDOFF.md, "Recommended Next Move" first. This is sandbox, on master (2c23724, pushed).
The FC58 fix cycle (handoff Step 1) is COMPLETE + MERGED + reviewed (security=SAFE,
architecture=mergeable). 279/279 classifier tests pass. Status:
  - FC58 FIXED on master: narrow TRUSTED+python+allowlisted-basename indirection carve-out
    (todo 071) + hybrid lifecycle teardown (todo 072: deactivate→rm, set-phase kept python)
    + 14 boundary/lifecycle tests (todo 073). Todo 074 (path-pin hardening) deferred.
  - BUT NOT LIVE: the global firebreak hook still execs the STALE sandbox-g1 worktree
    classifier. The merged fix runs live only after Step 2.
  - [079-W3, HIGH] G1+G3 simultaneous coexistence is STILL UNVERIFIED (run 079's tail ran
    firebreak-OFF). Don't claim "fully done" until Step 3.

DONE this session: Step 1 (FC58 fix cycle, merged 2c23724) + Step 2 (hook repoint —
  ~/.claude/settings.json line 114 now points at the main-repo gate; live probe passed:
  orch allowlisted python GREEN, worker python DEFERRED, orch python3 -c DENY).

NEXT, in order (do NOT jump to G2/G4/G5):
  3. ⬅ Coexistence re-validation run (firebreak ACTIVE through the tail) → closes [079-W3].
     READY-TO-LAUNCH BRIEF: docs/plans/2026-06-30-step3-coexistence-revalidation-brief.md
     MUST launch in a FRESH session (hook-load certainty + autopilot loop/context budget).
     In a fresh session in ~/Projects/sandbox, verify settings.json:114 points at the MAIN
     repo gate, then run /autopilot with the ShelfTrack throwaway described in the brief.
     Close [079-W3] only if all 5 success criteria in the brief hold.
  4. sandbox-g1 worktree teardown (now safe — no longer load-bearing) + delete the 4 merged
     feature branches (incl. feat/fc58-firebreak-trusted-indirection), local+remote.
  5. THEN G2/G4/G5 via /workflows:brainstorm from the governance scorecard.
  Also: write the FC58 compound/solution-doc AFTER Step 3 (so the coexistence proof lands with it).

Invariants (don't touch designs): self-audit-reviewer stays model: sonnet; Gate 8 fail-closed +
literal-token, no loop, no binding LLM verdict; firebreak classifier = deny-known-bad; FC58
carve-out is TRUSTED-only + python-only + allowlist matches script BASENAMES ONLY (todo 074
may revisit to path-pin — a conscious change, not a silent one).

Solution doc (run 079): docs/solutions/2026-06-26-g1-g3-live-validation.md
FC58 fix: .claude/hooks/firebreak-classify.py + test_firebreak_classify.py (FC58 block)
FC58 finding: docs/reports/079/firebreak-deadlock-finding.md
```
