# HANDOFF — Sandbox · G1+G3 LIVE VALIDATED + P1 (FC58) · MERGED TO MASTER

**Date:** 2026-06-29
**Branch:** `master` @ `fed9644` — **run 079 merged (`--no-ff`) and pushed to origin.** Working tree clean.
**Phase:** **Run 079 COMPLETE + merged. G1 live PASS. G3 live PASS (firebreak-OFF — coexistence still unverified, `[079-W3]`). NEW P1 (FC58). NEXT = FC58 fix cycle (fresh session), then hook-repoint, then a coexistence re-validation run. G2/G4/G5 are NOT yet truly unblocked — FC58 sits in front.**

## Honest validation status (read this before claiming "done")

- **G1 — clean PASS.** The live firebreak denied a real worktree worker's three control-plane writes; the deterministic no-canary verdict holds, and the false-GREEN concern was closed *empirically* (the deferred-action queue recorded the main-repo absolute path — the write would have landed where the verdict checked had the firebreak been inert). Strongest evidence type available.
- **G3 — PASS with an asterisk.** Gate 8 passed all 8 on real artifacts in the live tail (disconfirmer D1–D4 → bijected WARNs W1–W4). BUT the tail ran **firebreak-OFF** (FC58 forced an early teardown). So **G1+G3 simultaneous coexistence under production conditions was never tested** — `[079-W3]`, severity HIGH. Even "Gate-8 logic isn't python-blocked" is a *code-trace inference*, not empirically confirmed this run. The self-audit graded itself honestly: G1 individual **A**, G3 individual **B**, G1+G3 simultaneous **D (ABSENT)**.
- **Run status:** `PIPELINE_PASS_WITH_DEFERRED_RISK` (honest — FC58 deferred).

## What Was Accomplished (this arc)

1. **Consolidated** G1 firebreak + G3 disconfirmer onto master (`c81486c`, earlier this session) — clean merges, pushed.
2. **Pre-flight GREEN** — cleared the `sandbox-g1` hook-path false-GREEN concern by code analysis (sentinel is cwd/git-toplevel-anchored, code byte-identical to master).
3. **Gate-8 logic probe-validated** (the brief's Phase C) — a blind subagent ran `/verify-self-audit` against a planted fixture: DROP→FAIL (Gate 8c), CORRECTED→PASS. Deterministic, both directions.
4. **Live run 079** (unattended autopilot swarm, throwaway "Snippets" Flask CRUD, 3 workers) — both gates fired live; **FC58 discovered**.
5. **Verified + merged** run 079 to master (`fed9644`, `--no-ff`, pushed) after an independent check of the headline claims. The throwaway `validation-notes/` app rode along (isolated, deletable later).

## Recommended Next Move (start here — fresh session)

**Do NOT start G2/G4/G5 or branch cleanup yet.** The sequence is:

**Step 1 — FC58 fix cycle (proper compound cycle: brainstorm/plan → review → work → review).** FC58 = the firebreak's identity-agnostic `bash_indirection` defers ALL Bash-python (incl. the orchestrator's own pipeline tools and the firebreak's own python lifecycle/teardown). Three fixes (todos 071–073):
1. **Trusted-tool indirection allowlist** (todo 071, P1) — pre-check in `classify_simple_command` before line 2070: when `identity in TRUSTED` AND `os.path.basename(script)` ∈ allowlist (`firebreak-activate.py`, `verify_delegated_status.py`, `check_spec_provenance.py`) → skip `bash_indirection`. **SECURITY-SENSITIVE: basename-match only, never a broad interpreter bypass for TRUSTED** (the run's own least-confident item; architecture-reviewer-confirmed). Workers stay fully governed.
2. **SKILL.md lifecycle hotfix** (todo 072, P1) — Step 17w `set-phase tail` → Write-tool sentinel edit; Step 18w `deactivate` → `rm .claude/firebreak-active.json`. Both confirmed GREEN for TRUSTED orchestrator.
3. **Live-lifecycle integration test** (todo 073, P2) — add a sentinel-aware group to `test_firebreak_classify.py`: orchestrator python3 GREEN under active sentinel; worker python3 DEFERRED; orchestrator `rm` GREEN.

**Step 2 — Repoint the global firebreak hook → main repo. THIS IS A PREREQUISITE for re-validation, not just cleanup.** The global PreToolUse hook in `~/.claude/settings.json` execs `sandbox-g1`'s `firebreak-gate.sh` → `sandbox-g1`'s `firebreak-classify.py`, which is on `feat/g1` (stale, has the SAME FC58 bug and WON'T have your fix). So **your FC58 classifier fix will not run live until the hook points at the main repo.** Repoint via `update-config` (global settings — confirm with Alex), then reconcile the sentinel write/read paths.

**Step 3 — Coexistence re-validation run** — a new live autopilot run with the firebreak **active through the tail**, to actually close `[079-W3]` (G1+G3 simultaneous). This is the real "Step 2 done."

**Step 4 — `sandbox-g1` worktree teardown + branch cleanup** (deferred all session). Order: hook already repointed (Step 2) → `git worktree remove sandbox-g1` → delete `feat/g1-risk-tiered-firebreak`, `feat/g3-verification-diversity`, `feat/g1-g3-live-validation` (local + remote; all merged).

**Step 5 — THEN G2/G4/G5** (in-flight AI monitor / per-run-nonce ledger / delegation-as-authority) via `/workflows:brainstorm`, seeding from the governance scorecard.

## Current State

- **master @ `fed9644`** (pushed) carries: G1 firebreak + G3 disconfirmer (live-validated), the full run-079 record, the FC58 finding + 3 fix todos, and the throwaway `validation-notes/` app.
- **`sandbox-g1` worktree** (on `feat/g1-risk-tiered-firebreak`, `6dd621a`) is STILL load-bearing — the global firebreak hook execs its `firebreak-gate.sh`. Do not remove it before the Step-2 hook repoint.
- **Global propagation done by run 079's tail:** `~/.claude/docs/agent-pitfalls.md` (FC58 entry, 2026-06-29) and the auto-MEMORY. No need to re-propagate.
- Feature branches `feat/g1-risk-tiered-firebreak`, `feat/g3-verification-diversity`, `feat/g1-g3-live-validation` all merged into master, unpushed-deletion pending Step 4.

## FC58 — the finding, precisely (do NOT overclaim)

The G1 firebreak's `bash_indirection` check is **identity-agnostic**. Under an active sentinel it deferred: (a) `python3 tools/verify_delegated_status.py` (Steps 11w–18w disk-verify — **no non-python fallback**; done manually this run); (b) `python3 .claude/hooks/firebreak-activate.py set-phase tail` (17w); (c) `python3 .claude/hooks/firebreak-activate.py deactivate` (18w teardown). Working non-python fallback: `rm .claude/firebreak-active.json` (TRUSTED orchestrator bypasses the control-plane delete check; `rm` is not an interpreter so indirection never fires) — CONFIRMED GREEN. **Scope = Bash-invoked python (orchestrator pipeline tooling + firebreak lifecycle), NOT Gate-8 logic** (`verify-self-audit` is Read/Grep/Glob; disconfirmer/self-audit agents Write to `docs/reports/` = not control-plane). Cross-project lesson: *harness-green ≠ live is bi-directional — an inert gate AND a too-broad gate are both invisible to unit tests.*

## Key Artifacts

| Item | Location |
|------|----------|
| **Solution doc (run 079)** | **docs/solutions/2026-06-26-g1-g3-live-validation.md** |
| Live-validation brief/plan | docs/plans/2026-06-26-g1-g3-live-validation-run-brief.md |
| Firebreak probe (G1 PASS) | docs/reports/079/firebreak-probe.md |
| FC58 deadlock finding (P1) | docs/reports/079/firebreak-deadlock-finding.md |
| Disconfirmer (G3) / Self-audit | docs/reports/079/disconfirmer.md · docs/reports/079/self-audit.md |
| FC58 fix todos | todos/071-…, todos/072-…, todos/073-… (firebreak) |
| G1 solution (activation arc) | docs/solutions/2026-06-25-g1-firebreak-activation-arc.md |
| G3 solution | docs/solutions/2026-06-26-g3-self-audit-disconfirmer.md |
| Governance scorecard | docs/governance/2026-06-21-autopilot-vs-three-layers-agent-security.md |
| FC58 in registry | ~/.claude/docs/agent-pitfalls.md (FC58) |

## Deferred Items

- **[079-W3, HIGH] G1+G3 coexistence empirically unverified** — G3 tail ran firebreak-OFF; production condition (firebreak active through the tail) never tested. Two run-079 artifacts disagree on whether Gate-8 python can run under an active sentinel (BUILD_TRACKING vs firebreak-deadlock-finding). Resolution: FC58 fixes → hook repoint → re-validation run (Steps 1–3 above).
- **[FC58-DISKVERIFY-079, P1]** Trusted-tool indirection allowlist (todo 071).
- **[FC58-LIFECYCLE-079, P1]** SKILL.md 17w/18w lifecycle hotfix (todo 072).
- **[FC58-LIVETEST-079, P2]** Live-lifecycle integration test (todo 073).
- **[HOOK-PATH-REPOINT — now a PREREQ]** Repoint global firebreak hook off the `sandbox-g1` worktree to the main repo BEFORE any FC58 re-validation (else the fixed classifier never runs live). Pair with worktree+branch teardown (Step 4).
- **[G3-RESIDUAL-DISPOSITION]** Disposition monoculture — the lone Sonnet confirmer disposes disconfirmer D# findings; nothing verifies a disposition is *correct*. Candidate future G-gate. Prefer after FC58 + coexistence.
- **[070-W4] Todo #070 (P2, LOW)** — double `get_schedule_entries` in `callsheets.generate`.
- **[G2/G4/G5]** Governance gates — **gated behind FC58 fixes + the coexistence re-validation.** Then `/workflows:brainstorm` from the scorecard.

## Three Questions

1. **Hardest decision?** Whether G3 counts as "live validated" with the firebreak torn down before the tail. Answer: partial — the plan's Phase B criterion ("Gate 8 passes on real run artifacts") was met, but production coexistence was not. Honest framing: each gate fires live *individually*; together is unverified (`[079-W3]`).
2. **What was rejected?** Implementing FC58 fixes inside the validation run (per operator direction); starting the fix cycle in the long validation session (deferred to fresh context for the security-sensitive classifier change).
3. **Least confident about?** Whether FC58 fix A (trusted-tool allowlist) stays narrow enough to not open a python-exec hole. Must basename-match specific scripts only — never a broad TRUSTED interpreter bypass.

## Prompt for Next Session

```
Read HANDOFF.md, "Recommended Next Move" first. This is sandbox, on master (fed9644, pushed).
Run 079 (G1+G3 live validation) is COMPLETE and MERGED. Status:
  - G1 PASS (clean): live firebreak denied a real worktree worker's control-plane writes.
  - G3 PASS (asterisk): Gate-8 chain ran in the live tail, but firebreak-OFF — G1+G3
    SIMULTANEOUS coexistence is UNVERIFIED ([079-W3], HIGH). Don't claim "fully done."
  - NEW P1 (FC58): firebreak's identity-agnostic bash_indirection defers all Bash-python,
    incl. the orchestrator's own pipeline tools + the firebreak's python lifecycle/teardown.
    Recoverable via trusted `rm .claude/firebreak-active.json`. Scope = Bash-python tooling,
    NOT Gate-8 logic (Read/Grep-based). Do not overclaim.

NEXT, in order (do NOT jump to G2/G4/G5):
  1. FC58 fix cycle (compound cycle) — todos 071 (trusted-tool allowlist; SECURITY-SENSITIVE,
     basename-match only), 072 (SKILL.md 17w/18w lifecycle hotfix), 073 (live-lifecycle test).
  2. Repoint global firebreak hook ~/.claude/settings.json off the sandbox-g1 worktree to the
     main repo — PREREQUISITE: the live hook execs sandbox-g1's stale classifier, so the FC58
     fix won't run live otherwise (update-config; confirm with Alex).
  3. Coexistence re-validation run (firebreak ACTIVE through the tail) → closes [079-W3].
  4. sandbox-g1 worktree teardown + delete the 3 merged feature branches (local+remote).
  5. THEN G2/G4/G5 via /workflows:brainstorm from the governance scorecard.

Invariants (don't touch designs): self-audit-reviewer stays model: sonnet; Gate 8 fail-closed +
literal-token, no loop, no binding LLM verdict; firebreak classifier = deny-known-bad with a
STRUCTURAL backstop (no enumerated exemptions); FC58 allowlist matches script basenames ONLY.

Solution doc: docs/solutions/2026-06-26-g1-g3-live-validation.md
Self-audit (honest grades): docs/reports/079/self-audit.md
FC58 finding: docs/reports/079/firebreak-deadlock-finding.md
```
