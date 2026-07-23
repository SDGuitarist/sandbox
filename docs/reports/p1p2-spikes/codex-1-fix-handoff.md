Work in /Users/alejandroguillen/Projects/sandbox
Branch: feat/p1p2-unattended-swarm-wave-barrier
Review target / base: the current TIP of that branch — run `git rev-parse feat/p1p2-unattended-swarm-wave-barrier`
and work on THAT commit (it carries all of §1 plus this handoff; Codex reviewed d346dd7 and only
this record/handoff was added on top). Do not hunt for "the right commit" — it is the branch tip.

Read first: HANDOFF.md, CLAUDE.md, and docs/plans/2026-07-22-p1p2-unattended-swarm-wave-barrier-plan.md
(revision 5 — §7 is the verifier spec). Prior review: docs/reports/p1p2-spikes/codex-1-code-review-result.md.

OBJECTIVE: Codex's §1 CODE review returned NO-GO on TWO real gaps — the wave verifier is not yet
authoritative because it under-implements the plan §7 reject-set. Close both gaps in
tools/verify_wave.py (both --wave K and --reconcile) and add regression tests, WITHOUT changing
single-wave behavior or any fixed constraint. This is a focused work phase, not a redesign.

FIXED CONSTRAINTS (do NOT change):
  - Do NOT touch .claude/hooks/firebreak-classify.py logic (data-only allowlist stays; 284/284).
  - Do NOT change single-wave behavior — verify_wave is only invoked in wave mode; leave the
    tools/agents/SKILL single-wave paths byte-for-byte unchanged.
  - Truth stays DERIVED from --plan / --spec-path / live git / re-read evidence — never a
    caller-supplied roster. No new caller-trusting inputs.

FIX THESE FINDINGS IN ORDER (file, exact change, why):

1. tools/verify_wave.py — reject a non-PASS-EMITTED or count-mismatched artifact.
   In `verify_wave()` (the shared §7 reject-set), add near the top (right after the run-identity
   checks):
     - FAIL unless `art.get("status") == "PASS-EMITTED"` (a forged/ABORT artifact must not pass).
     - FAIL unless `int(art.get("wave_count"))` equals the plan's declared `waves`
       (`parse_waves_frontmatter(plan_text)` → int). Pass the declared wave-count into
       `verify_wave()` (add a param) so BOTH `cmd_wave` and `cmd_reconcile` enforce it.
   Why: plan §7 `--wave` rejects "a wave-count mismatch"; an artifact must represent a
   PASS-EMITTED wave. Today an artifact with `status:"ABORT"` and otherwise-valid fields PASSES.

2. tools/verify_wave.py — recompute and enforce prev_wave_artifact_sha (plan §7 tamper-evidence).
   For every wave k > 1, recompute sha256 over the raw bytes of `w<k-1>/wave.md` and require it
   equals the artifact's `prev_wave_artifact_sha`; FAIL on mismatch or if the prior file is
   missing. Enforce in BOTH modes:
     - `--wave K`: derive the prior dir as the sibling `w<k-1>/` of `--reports-dir` (which ends
       `/w<K>/`); recompute and compare.
     - `--reconcile`: you already iterate waves and track `prev_artifact_path` (currently UNUSED —
       Codex flagged it) — use it: hash the prior `w<k-1>/wave.md` and compare to
       `art["prev_wave_artifact_sha"]`.
   Reuse a small `sha256_file(path)` helper (wave_artifact.py has the same computation — mirror it,
   do not import across tools). Why: plan §7 lists "`prev_wave_artifact_sha` ≠ recomputed sha256 of
   `w<k-1>/wave.md`" as a reject; the chain is currently un-verified.

3. tools/test_verify_wave.py — add regression cases (keep all 32 existing green):
   - `test_wave_status_abort_rejected` — an artifact with `status:"ABORT"` (+ abort_reason) FAILs `--wave`.
   - `test_wave_wrong_wave_count_rejected` — artifact `wave_count` ≠ plan declared waves FAILs `--wave`.
   - `test_wave_forged_prev_artifact_sha_rejected` — a 2-wave fixture where w2's
     `prev_wave_artifact_sha` ≠ sha256(w1/wave.md) FAILs `--wave 2` (and `--reconcile`).
   - `test_reconcile_prev_artifact_sha_enforced` — the happy 2-wave chain PASSes only when the
     recomputed prior-artifact sha matches.
   (A 2-wave git fixture is needed for the prev-sha cases — extend build_wave_repo, or add a
   second wave dir w2 with its own wave.md whose prev_wave_output_sha/expected_base_sha chain to w1.)

DEFINITION OF DONE (each fix proven, not asserted):
  - `python3 tools/test_verify_wave.py | tail -1` → all pass, count > 32 (new cases added).
  - The three forged cases (ABORT status, wrong wave_count, forged prev_wave_artifact_sha) each FAIL
    verify_wave with a specific STATUS reason.
  - `--reconcile` recomputes and enforces the prior-artifact sha (prev_artifact_path is now USED).
  - `python3 .claude/hooks/test_firebreak_classify.py | tail -1` → 284/284 (unchanged).
  - `python3 tools/test_wave_artifact.py | tail -1` → 15/15 (unchanged).
  - Single-wave paths in SKILL.md / swarm-runner.md / swarm-planner.md are untouched (git diff shows
    only tools/verify_wave.py + tools/test_verify_wave.py changed).
  - Commit in small checkpoints; update HANDOFF.md; leave the worktree clean.

After fixing: run all three suites, do a SECOND self-review of your own diff, report residual
risks, then produce a fresh Codex re-review handoff using the template at
docs/codex-review-request-template.md (lead with "Work in …", reference the tip by name — never a
pinned/stale SHA). Do NOT launch any autopilot run (P4 stays gated).
