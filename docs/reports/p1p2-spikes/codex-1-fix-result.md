# Codex §1 CODE review — fix result (both NO-GO gaps closed)

**Status:** DONE. Both under-implemented plan §7 rejects are now enforced in
`tools/verify_wave.py` (both `--wave K` and `--reconcile`), with regression tests.
Single-wave behavior and all fixed constraints are unchanged.

Branch tip after fix: `feat/p1p2-unattended-swarm-wave-barrier` (run `git rev-parse`
for the live sha; at write time `c0c1adf`). Fix commits: `c7c4da5` (tool) +
`c0c1adf` (tests). Prior review: `codex-1-code-review-result.md`.

## Fix 1 — reject non-PASS-EMITTED / count-mismatched artifact (item 3)
`verify_wave()` now, immediately after the run-identity checks:
- FAILs unless `art["status"] == "PASS-EMITTED"` → `artifact status <x> != PASS-EMITTED`.
  A forged `ABORT` (or any non-PASS-EMITTED) artifact with otherwise-valid fields no
  longer passes `--wave K`.
- FAILs unless `int(art["wave_count"])` equals the plan's declared `waves`
  (`parse_waves_frontmatter`). The declared count is threaded in via a new
  `declared_waves` param so BOTH `cmd_wave` (parses it from `--plan`) and
  `cmd_reconcile` (passes `N`) enforce it → `wave_count <a> != plan declared waves <b>`.

## Fix 2 — recompute + enforce prev_wave_artifact_sha (item 10)
For every wave `k > 1`, `verify_wave()` recomputes `sha256` over the raw bytes of
`w<k-1>/wave.md` and FAILs on mismatch or a missing prior file
→ `prev_wave_artifact_sha mismatch: recorded <x> != recomputed sha256 of w<k-1>/wave.md <y>`.
- `--wave K`: `cmd_wave` derives the prior dir as the sibling `w<K-1>/` of
  `--reports-dir` (`os.path.dirname(os.path.normpath(reports_dir))/w<K-1>/wave.md`).
- `--reconcile`: now USES the previously-unused `prev_artifact_path` (the tracked
  `w<k-1>/wave.md`), which Codex flagged as dead.
- New `sha256_file()` helper mirrors `wave_artifact.py._sha256_file` (share-not-import —
  the verifier stays a standalone trusted script).

## Regression tests (32 → 36, all green)
- `test_wave_status_abort_rejected` — ABORT artifact FAILs `--wave` (`!= PASS-EMITTED`).
- `test_wave_wrong_wave_count_rejected` — `wave_count=2` vs declared `waves:1` FAILs `--wave`.
- `test_wave_forged_prev_artifact_sha_rejected` — a real 2-wave git fixture; tampering
  `w1/wave.md` after emit makes w2's recorded `prev_wave_artifact_sha` stale → FAILs
  both `--wave 2` AND `--reconcile`.
- `test_reconcile_prev_artifact_sha_enforced` — the happy 2-wave chain PASSes only when
  the recomputed prior-artifact sha matches (proves `prev_artifact_path` is live).
- New fixture `build_two_wave_repo()` (models wave1 → routes wave2, chained via
  `--prev-artifact`); `_emit_wave` gains an optional `prev_artifact` + per-wave payload file.

## Definition of Done — evidence
- `python3 tools/test_verify_wave.py | tail -1` → **36/36 passed** (was 32; +4 new).
- `python3 .claude/hooks/test_firebreak_classify.py | tail -1` → **284/284 passed** (unchanged).
- `python3 tools/test_wave_artifact.py | tail -1` → **15/15 passed** (unchanged).
- `git diff --name-only 2773000..HEAD` → only `tools/verify_wave.py` +
  `tools/test_verify_wave.py`. SKILL.md / swarm-runner.md / swarm-planner.md untouched;
  firebreak-classify.py logic untouched; no new caller-trusting inputs (truth still
  derived from `--plan`/`--spec-path`/live git/re-read evidence).

## Residual risks (self-review of my own diff)
- `declared_waves` is `None` when a plan has no `waves:` key; the `wave_count` equality
  check is then skipped (permissive). This cannot regress single-wave (verify_wave is
  only invoked in wave mode) and never adds a false failure — but it means a malformed
  wave-mode plan with no `waves:` would not catch a wrong `wave_count`. Acceptable:
  production wave-mode plans always declare `waves`, and `--reconcile` passes `N` (never
  None). Not a new failure surface.
- The forged-sha fixture tampers by appending AFTER the closing ```` ``` ```` fence, so
  the JSON block still parses (proven: `--reconcile` reaches wave 2 before failing).
  Real tamper of the JSON body would be caught earlier by the other §7 rejects.
- Multi-wave `--reconcile` chain/ancestor reject cases (chain-break / earlier-wave-
  ancestor / final-wave-is-head / count-mismatch) remain covered by the live spike per
  plan §8, not unit tests — unchanged by this fix (pre-existing disclosed gap).
