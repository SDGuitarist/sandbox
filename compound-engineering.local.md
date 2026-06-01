# Review Context -- Sandbox Eval Harness (Spec Eval Gate)

## Risk Chain

**Brainstorm risk:** "Quality of LLM-extracted prose claims is untested. Harness reuse requires careful model adaptation."

**Plan mitigation:** Blocking prerequisite -- extraction prompt must be tested against 2 real specs (WRC, Ethics Toolkit) with --dry-run before implementing Phases 3-5. Confidence threshold raised from 0.85 to 0.90 due to LLM overconfidence.

**Work risk (from Feed-Forward):** "Whether the 24 WRC failures include false positives from the anti-leniency judge."

**Review resolution:** 7 agents (python, security, performance, architecture, simplicity, agent-native, learnings), 3 P1s fixed (CostTracker race, missing verification artifact, exit code ambiguity), 8 P2s + 8 P3s deferred. Feed-Forward risk (extraction quality) was validated -- 81% pass rate with 24 genuine failures on WRC. Anti-leniency bias remains open for human triage on first real swarm run.

## Files to Scrutinize

| File | What changed | Risk area |
|------|-------------|-----------|
| eval-harness/spec_eval_gate.py | New CLI entry point, async orchestration | Cost cap race (P1 fixed), concurrent execution correctness |
| eval-harness/extractor.py | Table parser + prose extraction + dedup | Table filter false negatives (skip real code tables), prompt injection via spec content |
| eval-harness/spec_judge.py | Anti-leniency LLM judge | False positive rate on complex multi-step instructions |
| eval-harness/spec_scorer.py | Confidence-filtered 100% threshold | Threshold calibration (0.90 may be too strict or too loose) |
| eval-harness/models.py | 7 new types added | Type compatibility with existing pitfall eval models |
| eval-harness/runner.py | Signature change: rule_text: str | Backward compat with pitfall_eval.py callers |

## Plan Reference

`eval-harness/docs/plans/2026-05-24-feat-spec-eval-gate-plan.md`
