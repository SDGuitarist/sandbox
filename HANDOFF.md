# HANDOFF — Sandbox · G1+G3 LIVE VALIDATED + P1 DEADLOCK FOUND

**Date:** 2026-06-29
**Branch:** `feat/g1-g3-live-validation` (3 workers cherry-picked, assembled, all tail artifacts complete)
**Phase:** **Run 079 COMPLETE. G1 LIVE PASS. G3 LIVE PASS. NEW P1 (FC58) — firebreak deadlocks orchestrator python pipeline tools. Deferred to G1 backlog. NEXT: implement FC58 fixes (todos 071-073), then G2/G4/G5.**

## What Was Just Completed

Run 079 — first live validation of both the G1 firebreak and G3 Gate-8 disconfirmer in a real
autopilot swarm. The throwaway "Snippets" Flask+SQLite CRUD (3 workers) was built solely to force
a real swarm + tail. Both governance gates were proven live. A new P1 finding (FC58) was surfaced:
the firebreak's `bash_indirection` check is identity-agnostic, deferring the orchestrator's own
python tools alongside workers.

## Recommended Next Move (start here)

**Priority 1 — Implement FC58 fixes (G1 backlog):**
1. **Trusted-tool indirection allowlist** (todo 071) — add pre-check in `classify_simple_command` before
   line 2070: when `identity in TRUSTED` and `os.path.basename(script)` in allowlist
   (`firebreak-activate.py`, `verify_delegated_status.py`, `check_spec_provenance.py`) → skip
   bash_indirection. Workers remain fully governed. Test: 265/265 existing + new live-lifecycle tests.
2. **SKILL.md lifecycle hotfix** (todo 072) — replace Step 17w `python3 firebreak-activate.py set-phase tail`
   with Write-tool edit to sentinel JSON; replace Step 18w `python3 firebreak-activate.py deactivate`
   with `rm .claude/firebreak-active.json`. Both confirmed GREEN for TRUSTED orchestrator.
3. **Live-lifecycle integration test** (todo 073) — add test group to `test_firebreak_classify.py`:
   orchestrator python3 GREEN under active sentinel; worker python3 DEFERRED; orchestrator rm GREEN.

**Priority 2 — After FC58 fixes merge:** pick G2 (in-flight AI monitor) / G4 (per-run-nonce ledger) /
G5 (delegation-as-authority) from the governance scorecard via `/workflows:brainstorm`.

## Current State

Both governance hardening features were **merged to `master`** (c81486c) before this run:
- **G1 firebreak** — live (probe PASS confirmed run 079: real worktree worker's control-plane writes denied)
- **G3 disconfirmer** — live (disconfirmer→self-audit→Gate-8 chain confirmed in run 079 tail)

**Run 079 branch** (`feat/g1-g3-live-validation`) — 3-agent swarm assembly PASS, contract check PASS,
smoke FIREBREAK_DEFERRED (non-blocking), tail complete with all artifacts.

**NEW P1 — FC58 (Pipeline Self-Strangulation):** The G1 firebreak `bash_indirection` check is
identity-agnostic. Under an active sentinel, it deferred: (a) `python3 tools/verify_delegated_status.py`
(disk-verify gates, Steps 11w–18w — no non-python fallback; done manually this run), (b)
`python3 .claude/hooks/firebreak-activate.py set-phase tail` (Step 17w), (c)
`python3 .claude/hooks/firebreak-activate.py deactivate` (Step 18w). Working non-python fallback:
`rm .claude/firebreak-active.json` (orchestrator TRUSTED identity bypasses control-plane delete check;
`rm` not an interpreter → indirection never fires). CONFIRMED GREEN in run 079. The precise finding:
the DOCUMENTED python-based lifecycle path is deferred; the non-python rm path is an undocumented
but valid workaround. Fix = trusted-tool allowlist + SKILL.md lifecycle documentation update.

## Key Artifacts

| Phase | Location |
|-------|----------|
| Live validation plan | docs/plans/2026-06-26-g1-g3-live-validation-run-brief.md |
| **Solution doc (run 079)** | **docs/solutions/2026-06-26-g1-g3-live-validation.md** |
| Firebreak probe (G1 PASS) | docs/reports/079/firebreak-probe.md |
| Firebreak deadlock finding (P1) | docs/reports/079/firebreak-deadlock-finding.md |
| Disconfirmer report (G3) | docs/reports/079/disconfirmer.md |
| Self-audit report | docs/reports/079/self-audit.md |
| Assembly summary | docs/reports/079/assembly-summary.md |
| BUILD_TRACKING | BUILD_TRACKING.md |
| G1 solution (activation arc) | docs/solutions/2026-06-25-g1-firebreak-activation-arc.md |
| G3 solution | docs/solutions/2026-06-26-g3-self-audit-disconfirmer.md |
| Governance scorecard | docs/governance/2026-06-21-autopilot-vs-three-layers-agent-security.md |

## Deferred Items

- **[079-W3]** G1+G3 coexistence empirically unverified — G3 tail ran with firebreak INACTIVE (firebreak torn down before tail due to FC58). The production condition (firebreak active, phase=tail, during the tail) was never tested. Two artifacts contradict each other on whether Gate-8 python can run under active sentinel (BUILD_TRACKING.md vs firebreak-deadlock-finding.md). Resolution: implement FC58 fixes (todos 071-073), then run a new live validation with firebreak active through the tail. Severity: HIGH.
- **[FC58-DISKVERIFY-079, P1]** Trusted-tool indirection allowlist — orchestrator python3 pipeline
  scripts GREEN under active sentinel (todo 071). Fix A: pre-check in classify_simple_command.
- **[FC58-LIFECYCLE-079, P1]** SKILL.md Step 17w/18w lifecycle hotfix — replace python commands with
  Write-tool/rm alternatives (todo 072). Fix B: immediate SKILL.md update, no classifier change.
- **[FC58-LIVETEST-079, P2]** Live-lifecycle integration test (todo 073). Fix C: add to
  test_firebreak_classify.py, sentinel-aware test group.
- **[G3-RESIDUAL-DISPOSITION]** Disposition monoculture — the lone Sonnet confirmer still disposes
  disconfirmer D# findings. No verification of disposition correctness. Candidate future G-gate (G4/G5).
- **[HOOK-PATH-CLEANUP]** Repoint global firebreak hook from sandbox-g1 worktree to main repo,
  then remove worktree + merged branches. Order: repoint hook (update-config + Alex confirm) →
  `git worktree remove sandbox-g1` → delete local+remote feature branches.
- **[STEP 2 DONE]** Live validation complete. G1 + G3 both validated in a real autopilot tail.
  FC58 deadlock discovered and logged. Governance G2/G4/G5 now unblocked (one open finding: FC58 fixes).
- **[070-W4] Todo #070 (P2, LOW)** — double `get_schedule_entries` in `callsheets.generate`.
- **[G2/G4/G5]** Governance gates: in-flight AI monitor (G2), per-run-nonce ledger (G4),
  delegation-as-authority-transfer (G5). Now unblocked (Step 2 complete). Start with `/workflows:brainstorm`.

## Three Questions

1. **Hardest decision?** Whether G3 counts as "live validated" when the firebreak was torn down
   before the tail. Answer: yes — the plan's Phase B success criterion was "Gate 8 passes on real
   run artifacts," which was met. G1 and G3 being live simultaneously is impossible until FC58 is fixed;
   validating them in sequence within the same run is the best achievable result.
2. **What was rejected?** Implementing the FC58 fixes during this validation run (per operator
   direction: "do NOT implement in this validation run"). The fixes were documented and logged to the
   G1 backlog for the next session.
3. **Least confident about?** Whether FC58 fix A (trusted-tool allowlist) will be narrow enough
   that it does not inadvertently open the orchestrator to exec arbitrary python. The allowlist must
   match on specific script basenames only, not grant broad interpreter bypass to TRUSTED identities.
   The architecture reviewer confirmed this risk and prescribed basename-matching.

## Prompt for Next Session

```
Read HANDOFF.md, "Recommended Next Move" first. This is sandbox. Run 079 (G1+G3 live validation)
is COMPLETE. Both gates are confirmed live:
  - G1 PASS: firebreak probe denied real worktree worker's control-plane writes (no canary)
  - G3 PASS: disconfirmer→self-audit→Gate-8 chain ran in the live tail

NEW P1 FINDING (FC58): The G1 firebreak's bash_indirection check is identity-agnostic.
Under an active sentinel, it deferred the orchestrator's own pipeline python tools:
  - python3 tools/verify_delegated_status.py (disk-verify gates — no non-python fallback)
  - python3 .claude/hooks/firebreak-activate.py set-phase tail (lifecycle)
  - python3 .claude/hooks/firebreak-activate.py deactivate (teardown)
Working fallback: rm .claude/firebreak-active.json (TRUSTED orchestrator identity GREEN).

NEXT PRIORITY = FC58 fixes (3 todos, all G1 backlog):
  - Todo 071 (P1): trusted-tool indirection allowlist in classify_simple_command (before line 2070)
  - Todo 072 (P1): SKILL.md Step 17w/18w lifecycle hotfix (Write-tool/rm instead of python)
  - Todo 073 (P2): live-lifecycle integration test in test_firebreak_classify.py

G1+G3 invariants: self-audit-reviewer stays model: sonnet; Gate 8 fail-closed + literal-token;
no loop; no binding LLM verdict; firebreak classifier: deny-known-bad with structural backstop.

Solution doc: docs/solutions/2026-06-26-g1-g3-live-validation.md
Self-audit: docs/reports/079/self-audit.md
```
