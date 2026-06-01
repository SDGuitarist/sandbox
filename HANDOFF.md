# HANDOFF -- Sandbox Eval Harness

**Date:** 2026-06-01
**Branch:** `feat/pitfall-eval-harness`
**Phase:** P2s resolved. Compound cycle complete.

## Current State

The spec eval gate (step 9w.8) is complete. All 3 P1s and 7 P2s from the 7-agent review have been fixed. 8 P3s remain deferred (nice-to-have). Pipeline validated end-to-end on WRC spec: 130 claims, 81% HIGH pass rate, $0.90, ~6.5 min.

## Key Artifacts

| Phase | Location |
|-------|----------|
| Brainstorm | `eval-harness/docs/brainstorms/2026-05-24-spec-eval-gate-brainstorm.md` |
| Plan | `eval-harness/docs/plans/2026-05-24-feat-spec-eval-gate-plan.md` |
| Review | 7-agent review, P1s fixed in `b4270fa`, P2s fixed in `2c8786b` |
| Solution | `docs/solutions/2026-06-01-spec-eval-gate-pre-swarm-validation.md` |
| Calibration | `eval-harness/calibration/spec-eval/` (WRC + Ethics Toolkit extraction artifacts) |

## P2 Fixes Applied (commit `2c8786b`)

- `is_error: bool` field replaces `evidence == "error"` stringly-typed sentinel
- `Scenario` import added to spec_eval_gate.py
- Judge prompt loaded at module level, raises `FileNotFoundError` if missing
- `.venv/bin/python3` replaces bare `python3` in SKILL.md
- `ScoringError` dead class removed from exceptions.py
- `--concurrency` CLI option added, default 10 (was hardcoded 5)
- Split timeouts: 600s for extraction client, 60s for scenario client

## Deferred P3s (nice-to-have)

- Prompt injection hardening (XML tags in runner/judge)
- Remove redundant blocklist in `_is_code_testable_table`
- `os.path` vs `pathlib` inconsistency
- `GateConfig` as dataclass vs Pydantic

## Three Questions

1. **Hardest decision?** Table filter design -- allowlist-by-header with conservative default-skip. Validated by 81% pass rate with 24 genuine failures vs 62% without filtering.
2. **What was rejected?** No filter (62%, $3, 86 false failures). Section-name filter (fragile). LLM classification (adds cost). Percentage threshold >= 80% (waters down gate).
3. **Least confident about?** Whether the 24 WRC failures include false positives from the anti-leniency judge. First real swarm run using this gate will calibrate.

## Prompt for Next Session

```
Read HANDOFF.md for context. This is the eval harness in sandbox.
Spec eval gate is fully complete (P1s + P2s fixed, P3s deferred).
Next: merge to master, or start new brainstorm for next feature.
```
