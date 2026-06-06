# Codex Handoff — Work-Phase Code Review (Plan A Implementation)

**Branch:** `feat/orchestration-hardening-A-reliability`
**Created:** 2026-06-06
**Type:** code review of the implemented diff vs. the plan (mandatory pre-merge gate)

---

## Copy-paste prompt for Codex

```
Read these files first for project context:
  - CLAUDE.md
  - docs/plans/2026-06-06-autopilot-orchestration-hardening-A-reliability-plan.md
  - .claude/agents/self-audit-reviewer.md   (real self-audit.md format the script parses)
  - .claude/agents/swarm-runner.md          (real assembly-summary.md format + blocking aborts)

Review branch feat/orchestration-hardening-A-reliability against the plan above.
Diff it with: git diff master...feat/orchestration-hardening-A-reliability

This change moves the autopilot run's TERMINAL pass/fail authority from each delegated
agent's echoed wire STATUS to the on-disk artifact, via a new shared verifier script. It
is the highest-consequence surface in the pipeline: a bug here silently flips a run's
verdict (false-PASS ships a broken run; false-FAIL kills a good one). Review accordingly.

Files changed:
  - tools/verify_delegated_status.py            (NEW — the deterministic gate)
  - tests/test_verify_delegated_status.py       (NEW — 9-case harness, currently 9/9)
  - .claude/skills/autopilot/SKILL.md           (Steps 1, 5.5, 10w, 11w-16w handler, 18w,
                                                 solo TAIL_SYNC_POINT comment)
  - .claude/agents/tail-runner.md               (Output Contract note + TAIL_SYNC_POINT)

Focus on:

1. Script correctness (tools/verify_delegated_status.py):
   - Does it stay FAIL-CLOSED on every ambiguous path (unreadable file, missing run-id,
     missing status token, malformed args, unexpected exception)? Any path that could
     return exit 0 incorrectly?
   - Exit codes: all in 1-255 (256 wraps to 0)? Does the argparse-error override to 5
     actually avoid the collision with EXIT_MISSING=2?
   - Freshness: st_mtime_ns >= run_start_ts*1e9 — is `>=` correct, and is the
     seconds->ns conversion safe? Any off-by-one or float issue?
   - STATUS/run-id parsing: are the regexes correctly ANCHORED so prose can't false-match
     (e.g. "BYPASS" vs "PASS", a "**Final Status:**" header line vs the section
     "**Status:**" line)? Verify the self-audit parser reads the line UNDER
     "## Final Run Status", not the header.
   - Accept-sets: self-audit {PIPELINE_PASS, PIPELINE_PASS_WITH_DEFERRED_RISK}, assembly
     {PASS} — correct and complete against the producer agents?

2. Does the diff match the plan? Flag anything added or missing vs. the plan's
   "Files in Scope" and the item-1 change list. Confirm the three Invariants hold in the
   code: (a) script checks only status/freshness/run-id, (b) /verify-self-audit still owns
   deferred-risk adjudication, (c) wire STATUS never vetoes a fresh matching disk artifact.

3. The Feed-Forward "least confident" risk: the gate logic now lives in PROSE that an LLM
   orchestrator must execute. Are the SKILL.md Step 18w and 11w-16w instructions
   unambiguous enough that the orchestrator will INVOKE the script and TRUST its exit code
   rather than re-deciding from the wire STATUS? Flag any wording that invites second-
   guessing.

4. Escalation safety: confirm the blocking-FAIL classes (contract-check / merge-conflict)
   short-circuit BEFORE any disk-verify in the 11w-16w handler (a stale prior-run
   assembly-summary.md must never mask a current abort). Is the ordering correct as
   written?

5. Bugs, regressions, missing edge cases in the script or the harness. Is the harness
   deterministic (os.utime, no sleeps) and does it actually exercise the false-PASS hole
   rather than passing trivially?

6. Files that should NOT have changed but did. (Plan A must not edit the artifact
   producers self-audit-reviewer.md / swarm-runner.md — confirm they are untouched.)

Output: findings ordered by severity (P0/P1/P2) + a Claude Code fix prompt that MUST
instruct Claude Code to:
1. Apply the requested fixes
2. Run a second review of its own changes after the fixes
3. Report any remaining risks before the task is considered complete
```

---

## Notes for the human routing this

- Highest-value targets: the script's fail-closed behavior and whether the SKILL.md prose
  reliably makes the orchestrator trust the exit code (the plan's least-confident item).
- Producers (`self-audit-reviewer.md`, `swarm-runner.md`) are read-only reference — Codex
  is asked to confirm they were NOT edited.
- After Codex returns: apply fixes → Claude Code second review → push + PR → compound.
