# Codex §1 CODE review — result

**Verdict:** NO-GO (2 legitimate ISSUEs; 8/10 items RESOLVED). Reviewed tip
`d346dd758d6f3ebb6518f5912d7db2fed7edfbaf`. Review was well-formed (passed the
hardened-template acceptance checklist: VERDICT line, full table, DoD with pasted
test output — 284/284, 15/15, 32/32 — residuals judged none-block).

## Confirmed findings (both real; both are under-implemented plan §7 rejects)

1. **verify_wave not authoritative on artifact status/count (item 3).**
   `verify_wave()` (tools/verify_wave.py) never checks the artifact `status`, so a
   forged artifact with `status: ABORT` (or any non-`PASS-EMITTED`) but otherwise
   valid fields PASSES `--wave K`. Plan §7 `--wave` rejects "a wave-count mismatch"
   and the artifact must represent a PASS-EMITTED wave. Also `wave_count` is never
   compared to the plan's declared `waves`.

2. **prev_wave_artifact_sha never recomputed (item 10).** Plan §7 lists
   "`prev_wave_artifact_sha` ≠ recomputed sha256 of `w<k-1>/wave.md`" as a reject.
   `--wave K` (k>1) and `--reconcile` never recompute the prior artifact's sha256
   and compare — the `prev_artifact_path` variable in `cmd_reconcile` is unused.
   The tamper-evidence chain is incomplete.

## Everything else RESOLVED
Firebreak allowlist data-only (no logic/`-m`), atomic artifacts, barrier-loop order
matches §5 (no toggle), planner/runner wave-gating, tail-resume + reconcile
fail-closed, fixed constraints preserved, single-wave invariant. Disclosed residuals
judged none-block.

## Fix owner
Handed to a NEW Claude Code (cloud) session — see
`docs/reports/p1p2-spikes/codex-1-fix-handoff.md`. Fix scope: tools/verify_wave.py
(both modes) + tools/test_verify_wave.py regression cases; preserve single-wave +
constraints; keep 284/15 green and grow verify_wave beyond 32.
