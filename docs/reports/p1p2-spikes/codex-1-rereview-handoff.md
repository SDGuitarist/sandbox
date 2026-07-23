# Codex §1 CODE re-review handoff (copy-paste to Codex, fresh context)

Your PRIOR §1 CODE review returned NO-GO on 2 gaps (`codex-1-code-review-result.md`).
Both are now fixed on the branch tip. This handoff asks you to re-review ONLY that the
two fixes are correct and complete, single-wave is untouched, and no new caller-trusting
input was added. Built with the hardened template (`docs/codex-review-request-template.md`).

```
Work in /Users/alejandroguillen/Projects/sandbox
Branch: feat/p1p2-unattended-swarm-wave-barrier
Review target: the current TIP of that branch. Run `git rev-parse feat/p1p2-unattended-swarm-wave-barrier`
and review THAT exact commit. Do NOT ask me which commit — the tip is the single
authoritative HEAD; everything to review is on it. If your checkout shows a different
tip, `git fetch` first.

ASK (one decision): GO / NO-GO on whether the TWO prior NO-GO findings are now correctly
and completely fixed in tools/verify_wave.py (both --wave K and --reconcile), with the
single-wave path and all fixed constraints preserved.
This is a CODE review. Do NOT write code. Do NOT ask for confirmation of the commit,
branch, or scope — everything you need is below.

READ THESE FILES FIRST (Codex has no other context):
  - HANDOFF.md
  - CLAUDE.md
  - AGENTS.md (if it exists)
  - docs/plans/2026-07-22-p1p2-unattended-swarm-wave-barrier-plan.md  (revision 5; §7 is the verifier spec)
  - docs/reports/p1p2-spikes/codex-1-code-review-result.md            (your prior NO-GO)
  - docs/reports/p1p2-spikes/codex-1-fix-result.md                    (what I changed + why)

WHAT THIS IS (3 lines max, self-contained):
  verify_wave.py is the authoritative wave verifier for an unattended multi-wave swarm
  barrier loop; its truth is DERIVED from --plan / --spec-path / live git / re-read
  evidence, never a caller-supplied roster. "Correct" = the two prior gaps are closed
  exactly per plan §7 and nothing else (single-wave, firebreak logic, constraints) moved.

REVIEW THIS FOR (numbered, specific — not "is it good"):
  1. Fix 1 authoritative-status/count: verify_wave() FAILs unless status == PASS-EMITTED
     AND int(wave_count) == the plan's declared `waves`. Confirm BOTH cmd_wave (parses
     declared waves from --plan) and cmd_reconcile (passes N) enforce it, and that an
     ABORT artifact with otherwise-valid fields now FAILs --wave K.
  2. Fix 2 prev_wave_artifact_sha: for k>1, verify_wave() recomputes sha256 of
     w<k-1>/wave.md and FAILs on mismatch/missing, in BOTH modes. Confirm cmd_wave derives
     the sibling w<K-1>/ of --reports-dir correctly, and cmd_reconcile now USES the
     previously-dead prev_artifact_path (no longer unused).
  3. Scope / must-not-change: git diff 2773000..TIP touches ONLY tools/verify_wave.py +
     tools/test_verify_wave.py. Single-wave behavior byte-for-byte unchanged; firebreak
     classifier logic untouched; NO new caller-trusting input (no --expected-roster etc.);
     truth still derived from --plan/--spec/live git/re-read evidence.
  4. Least-confident (mine): the declared_waves=None permissive branch (plan with no
     `waves:` key skips the wave_count check) — is that an exploitable hole in wave mode,
     or safe because wave mode always declares `waves` and --reconcile always passes N?
  5. Regression/security: does sha256_file() match wave_artifact.py._sha256_file exactly
     (same bytes hashed the same way), so the tamper-evidence chain can never false-pass
     or false-fail? Any way a forged artifact still slips through the new checks?

GROUND-TRUTH FILES TO CROSS-CHECK (open them; do not trust this summary):
  - tools/verify_wave.py — verify_wave() new status/wave_count/prev-sha blocks (near the
    top of the reject-set); the new declared_waves + prev_artifact_path params; sha256_file();
    cmd_wave sibling-dir derivation; cmd_reconcile passing declared_waves=N + prev_artifact_path.
  - tools/wave_artifact.py — _validate_emit (status ∈ {PASS-EMITTED, ABORT}; wave_count int;
    prev_wave_output_sha null iff wave 1) and _sha256_file / cmd_emit (how
    prev_wave_artifact_sha is originally recorded — confirm verify recomputes it identically).
  - tools/test_verify_wave.py — build_two_wave_repo() fixture + the 4 new cases; confirm the
    forged-sha case FAILs BOTH --wave 2 and --reconcile, and the happy 2-wave reconcile PASSes.
  - docs/plans/...-plan.md §7 — the --wave and --reconcile reject-sets (esp. "a wave-count
    mismatch" and "prev_wave_artifact_sha ≠ recomputed sha256 of w<k-1>/wave.md").

DEFINITION OF DONE — you MUST complete every item and show its result inline:
  [ ] 1. Ran `python3 tools/test_verify_wave.py | tail -1` — paste the last line (expect 36/36).
  [ ] 2. Ran `python3 .claude/hooks/test_firebreak_classify.py | tail -1` — paste it (expect 284/284).
  [ ] 3. Ran `python3 tools/test_wave_artifact.py | tail -1` — paste it (expect 15/15).
  [ ] 4. Ran `git diff --name-only 2773000..HEAD` — paste it; confirm ONLY the two tools files.
  [ ] 5. Confirmed single-wave path byte-for-byte unchanged — cite that SKILL.md /
         swarm-runner.md / swarm-planner.md are absent from the diff, and that verify_wave
         is only reached in wave mode.
  [ ] 6. For each disclosed residual below — state blocker? yes/no + why.

DISCLOSED RESIDUALS (I already know about these — judge whether any is a NO-GO):
  - declared_waves=None permissive branch (item 4 above) — wave_count check skipped only
    when a plan omits `waves:`; production wave-mode plans always declare it; --reconcile
    passes N (never None).
  - The forged-sha test tampers by appending after the closing ``` fence (JSON still parses
    on purpose, to reach the sha check); genuine JSON-body tamper is caught by other §7 rejects.
  - Multi-wave --reconcile chain/ancestor reject cases (chain-break / earlier-wave-ancestor /
    final-wave-is-head / count-mismatch) remain live-spike-covered per §8, not unit tests —
    a pre-existing disclosed gap, unchanged by this fix.

RETURN EXACTLY THIS FORMAT (nothing that stalls; no preamble):
  Line 1: `VERDICT: GO`  or  `VERDICT: NO-GO`
  Then a table — one row per review item (1..5):
    | Item | OK? (RESOLVED/ISSUE) | File:section checked | One-sentence evidence |
  Then: `RESIDUALS: none block` or `RESIDUALS: <key> blocks because <reason>`.
  Then the DoD checklist above, each box checked with its pasted result.
  If NO-GO, ALSO append a ready-to-paste Claude Code fix handoff, EXACTLY:
    ----- CLAUDE CODE HANDOFF -----
    Work in /Users/alejandroguillen/Projects/sandbox
    Branch: feat/p1p2-unattended-swarm-wave-barrier
    Live HEAD: <the tip sha you reviewed>
    Fix these NO-GO findings in order (each: file, exact change, why):
      1. ...
    Definition of done: <what must be true + which test/grep proves each fix>.
    After fixing: run <commands>, then do a second self-review and report residual risks.
    -------------------------------

DO NOT:
  - ask which commit/branch/scope (it is the tip of feat/p1p2-unattended-swarm-wave-barrier);
  - propose or write code unless the verdict is NO-GO (then only in the handoff block);
  - return prose without the VERDICT line and the table;
  - stall for input — if a file you expect is missing, name it and treat it as a NO-GO reason.
```
