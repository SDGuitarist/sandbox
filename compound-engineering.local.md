---
review_agents:
  - codex (manual, binding — for future G1/G3 fix implementation cycles)
---

# Review Context — G1+G3 Live Validation Run 079 (2026-06-29)

## Risk Chain

**Brainstorm/Plan risk (Feed-Forward, verify_first):** "harness-green ≠ live. Both G1 (firebreak) and G3 (Gate 8 disconfirmer) pass on the bench but have NEVER fired in a real autopilot tail. A gate that is silently inert (fail-open) passes every bench test and protects nothing."

**Plan mitigation:** Run the smallest possible real swarm (3 workers, throwaway Flask CRUD) to force the full swarm + tail path. G1 validated via positive-control probe (canary-file deterministic verdict). G3 validated via disconfirmer→self-audit→Gate-8 chain in a live tail.

**Work outcome:** G1 PASS — firebreak denied a real worktree worker's control-plane writes (no canary, deterministic verdict). G3 PASS (with caveat) — disconfirmer + Gate-8 chain ran in a live tail, but with the firebreak torn down first due to the P1 deadlock.

**P1 finding (new FC58 — Pipeline Self-Strangulation):** The G1 firebreak's `bash_indirection` check in `firebreak-classify.py` is identity-agnostic (no TRUSTED bypass). It deferred the orchestrator's own python tools: `python3 tools/verify_delegated_status.py` (disk-verify gates), `python3 .claude/hooks/firebreak-activate.py set-phase tail` (lifecycle), `python3 .claude/hooks/firebreak-activate.py deactivate` (teardown). Working fallback: `rm .claude/firebreak-active.json` from TRUSTED orchestrator is GREEN. Disk-verify gates have no non-python equivalent (manual workaround this run). Fix deferred to G1 backlog.

**Review resolution:** 2 P1, 2 P2 from architecture-strategist + learnings-researcher agents. No fix commits (all findings deferred to G1 backlog per operator direction). Findings confirm P1 classification for disk-verify deferral and set-phase deferral; P2 for deactivate (rm fallback) and live-lifecycle test missing.

## Files to Scrutinize (for next G1 fix cycle)

| File | What needs changing | Risk area |
|------|---------------------|-----------|
| .claude/hooks/firebreak-classify.py | Add trusted-tool indirection allowlist before line 2070 | Narrow scope to specific pipeline script basenames; workers stay fully governed |
| .claude/skills/autopilot/SKILL.md | Step 17w/18w: replace python lifecycle cmds with Write-tool/rm alternatives | Non-python fallback must be documented and tested |
| .claude/hooks/test_firebreak_classify.py | Add live-lifecycle integration test group | Trusted orchestrator python GREEN + worker python DEFERRED under active sentinel |

## Plan Reference

`docs/plans/2026-06-26-g1-g3-live-validation-run-brief.md`
