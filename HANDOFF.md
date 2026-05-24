# HANDOFF -- Sandbox

**Date:** 2026-05-23
**Branch:** `feat/pitfall-eval-harness`
**Phase:** Work -- Stage 1 COMPLETE, Stage 2 next

## Stage 1 Results

Gate PASSED. 12 FCs scored, $1.19 total cost, 360 API calls.

| Result | Count | FCs |
|--------|-------|-----|
| CLEAR | 10 | FC7, FC14, FC19, FC23, FC24, FC28, FC33, FC36, FC46, FC47 |
| AMBIGUOUS | 1 | FC16 (80%, seed data scenario fails) |
| BROKEN | 1 | FC20 (47%, cron concurrency rule unclear) |

**Load-bearing rules (highest delta):** FC24 (+100%), FC47 (+100%), FC23 (+73%), FC16 (+60%), FC19 (+40%), FC36 (+33%)
**Model already knows:** FC7, FC14, FC28, FC33, FC46 (all +0% delta)

Report: `eval-harness/reports/2026-05-23-2218.md`

## Before Stage 2: Fix Broken Rules

1. **Rewrite FC20 rule** in `~/.claude/docs/agent-pitfalls.md` -- BROKEN at 47%. The "atomic claim pattern" wording isn't producing correct code. 3 promotable cases: fc20-notification-sender, fc20-report-generator, fc20-webhook-retry.
2. **Investigate FC16 seed data failure** -- AMBIGUOUS at 80%. The "ON CONFLICT DO NOTHING" part of the rule may need emphasis. 1 promotable case: fc16-seed-data.
3. **Re-run FC20 and FC16** after rewrites to verify the fix: `python3 pitfall_eval.py --fc fc20 --runs 3`

## Next Session: Stage 2

1. Write `judges/base-judge.txt` and 13 per-FC judge prompts
2. Write `calibration/calibration-set.yaml` (20 hand-labeled cases)
3. Add LLM judge to `judge.py` (Sonnet, structured output via tool_use)
4. Add calibration gate to CLI
5. Write 13 Stage 2 scenario YAML files
6. Full run: `python3 pitfall_eval.py --stage all --runs 3`

## Key Files

- Plan: `docs/plans/2026-05-23-feat-pitfall-eval-harness-plan.md`
- Brainstorm: `docs/brainstorms/2026-05-23-pitfall-eval-harness-brainstorm.md`
- Stage 1 report: `eval-harness/reports/2026-05-23-2218.md`
- Pitfalls source: `~/.claude/docs/agent-pitfalls.md`

## Feed-Forward

Stage 1 confirmed the harness produces actionable signal. The "wall of CLEAR scores" risk was partially realized (10/12 CLEAR) but the delta ranking and 2 non-CLEAR FCs delivered exactly the diagnostic value we designed for. FC24 and FC47 are the most load-bearing rules in the entire pitfall set.
