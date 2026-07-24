# Codex P3 CODE-review — fix result (all 3 NO-GO findings closed)

**Status:** DONE. All three Codex NO-GO findings fixed on `feat/p3-harvest-and-darkness-tools`.
Reviewed tip was `840772f`; fix commits `d26f6d3` (tool+tests) + `364b7a0` (SKILL). Diff scope
stays within the reviewed files; the firebreak classifier + darkness tool are untouched.

## Fix #1 — SKILL WARN key → valid sequential `<run-id>-W<N>`
`.claude/skills/autopilot/SKILL.md` (Verify Harvest gate). The FAIL branch used a fixed
`<run-id>-WHARVEST` key, which `verify-self-audit` Gate 2 rejects (it requires exactly
`<run-id>-W<N>`, sequential from 1, no zero-padding, no gaps — confirmed at
`.claude/skills/verify-self-audit/SKILL.md:48-56`). SKILL now instructs `<run-id>-W<N>` and
documents choosing `<N>`: scan existing `<run-id>-W<k>` WARN keys in BUILD_TRACKING `## FAILURES`
+ gate reports, take the highest `<k>`, use `<k>+1` (first WARN is `W1`). The real 083 run
already assigned `083-W1` this way, so the fix matches live practice. **Fail-closed enforcement
lives in verify-self-audit Gate 2** (pre-existing): any malformed key — including `-WHARVEST`
or a non-sequential one — FAILs the self-audit gate.

## Fix #2 — row-scoped BIJECTION
`tools/verify_harvest.py`. The check counted `**root_cause_id:**` labels GLOBALLY
(`_BT_RC_RE.findall(failures)`), so one BUILD_TRACKING row listing two labels could satisfy two
REAL findings. New `_failure_rows()` splits `## FAILURES` into per-`###` blocks and returns the
SET of root_cause_ids each declares. BIJECTION is now true 1:1:
- every REAL rc maps to ≥1 block (else `missing`);
- no REAL rc spans >1 block (`multi`);
- **NEW:** no single block declares ≥2 distinct REAL rcs (`shared` — the exact hole Codex named).

## Fix #3 — reject non-positive thresholds
`tools/verify_harvest.py` `main()`. `--min-real`/`--min-netnew` were unbounded ints; a `0`/negative
floor makes the breadth/net-new comparisons vacuously true → a hollow harvest could PASS. They
must now be positive integers, rejected at the arg layer via `p.error()` → `EXIT_BAD_ARGS` (5),
fail-closed.

## Regression tests (12 → 17, all green)
- `one FAILURES row with two REAL rcs -> FAIL BIJECTION` (a merged-block fixture; global-findall
  would have PASSED it).
- `--min-real 0 -> exit 5 (BAD_ARGS)` + STATUS FAIL line; `--min-netnew 0 -> exit 5`;
  `--min-real negative -> exit 5`.
- Added a `bt_text` override to the `_make` fixture to build custom BUILD_TRACKING layouts.

## Definition of Done — evidence
- `python3 tools/test_verify_harvest.py | tail -1` → **17/17 passed**.
- `python3 tools/test_check_compounded_darkness.py | tail -1` → **13/13 passed** (untouched).
- `python3 .claude/hooks/test_firebreak_classify.py | tail -1` → **283/283 passed** (untouched).
- `git diff --name-only 840772f..HEAD -- . ':!docs/**'` → exactly `tools/verify_harvest.py`,
  `tools/test_verify_harvest.py`, `.claude/skills/autopilot/SKILL.md`.
- Firebreak: `.claude/hooks/firebreak-classify.py` NOT in the diff — `verify_harvest.py` stays
  TRUSTED-only + path-pinned; worker-denial covered by the classifier suite (still 283/283).

## Real-data observation (not a regression)
Running the fixed gate against the real `docs/reports/083` returns `FAIL -- BIJECTION -- REAL
root_cause_id(s) with no ## FAILURES row: ['RC-firebreak-cwd-root-drift']` (exit 1). This is a
PRE-EXISTING property of the 083 data: its harvest lists 7 REAL findings but BUILD_TRACKING has
6 `**root_cause_id:**` rows (H7/FC68 cwd-drift was deferred as a governance item, never given a
FAILURES row). The OLD global-findall logic flags it identically — both see the same 6 labels —
so this is NOT introduced by the fix; it is the gate correctly catching an untracked REAL finding
(083 self-certified before this tool existed).

## Residual risks (self-review of my own diff)
- `_failure_rows` splits on `^#{3,}\s` headings — matches the real BUILD_TRACKING format (083
  uses `### ` blocks, one `**root_cause_id:**` each) and the template. A BUILD_TRACKING that put
  all failures under a single heading (or no `###` headings) would collapse to one block and,
  with ≥2 REAL rcs, FAIL the shared-row check — correctly stricter, but worth knowing.
- The pre-existing EVIDENCE (relevance) and NET-NEW (registry) boundaries from the original
  review are unchanged by this fix; they remain disclosed residuals.
