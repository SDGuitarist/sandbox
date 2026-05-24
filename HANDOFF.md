# HANDOFF -- Sandbox

**Date:** 2026-05-23
**Branch:** `feat/pitfall-eval-harness`
**Phase:** Work -- Stage 1 gate test pending

## Current State

Pitfall Rule Eval Harness Stage 1 pipeline is fully built and dry-run validated.
12 FCs, 120 scenarios, 360 API calls planned (~$0.58/run). Awaiting live API test.

3 commits on feature branch:
1. Foundation: models.py, parser.py, 3 pilot scenario files, brainstorm + plan docs
2. Core modules: runner.py, judge.py, scorer.py, reporter.py, pitfall_eval.py
3. Remaining 9 scenario YAML files

## Immediate: Stage 1 Gate Test

Run in terminal:

```bash
export ANTHROPIC_API_KEY=sk-ant-your-key-here

cd ~/Projects/sandbox/eval-harness

# Quick single-FC test (~$0.02, ~30 seconds)
python3 pitfall_eval.py --fc fc7 --runs 1

# Full Stage 1 gate (~$0.58, ~15 minutes)
python3 pitfall_eval.py --stage 1 --runs 3
```

Gate passes when: 12 FC scores in report, no pipeline crashes.

## Next Session: Stage 2

After Stage 1 gate passes:
1. Write `judges/base-judge.txt` and 13 per-FC judge prompts
2. Write `calibration/calibration-set.yaml` (20 hand-labeled cases)
3. Add LLM judge to `judge.py` (Sonnet, structured output via tool_use)
4. Add calibration gate to CLI
5. Write 13 Stage 2 scenario YAML files
6. Full run: `python3 pitfall_eval.py --stage all --runs 3`

## Key Files

- Plan: `docs/plans/2026-05-23-feat-pitfall-eval-harness-plan.md`
- Brainstorm: `docs/brainstorms/2026-05-23-pitfall-eval-harness-brainstorm.md`
- Pitfalls source: `~/.claude/docs/agent-pitfalls.md` (read-only after FC45/FC46 prerequisite)

## Feed-Forward Risk

Most Tier 1a FCs may score >95% (CLEAR). The with/without-rule delta still produces an injection priority ranking even if all scores are high.
