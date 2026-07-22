STATUS: spec-eval SKIPPED (advisory, not run — Max-only billing guardrail)

Step 9w.8 is ADVISORY and non-blocking. The spec_eval_gate.py harness invokes the raw
Anthropic API (ANTHROPIC_API_KEY), which is credit-billed. The launch guardrail for this run
is "NEVER pay usage credits — Max subscription only", so the harness was deliberately NOT run.

This is recorded as an advisory skip (equivalent in effect to the historical WAIVED_BY_HUMAN
disposition — spec-eval returned FAIL and was human-waived 2-for-2 in runs 068/069 with ~0%
observed precision). It does NOT gate the spawn. The blocking pre-spawn signals are the
structural gates 9w.5 (consistency: PASS) and 9w.6 (completeness: PASS), both CLEARED
(docs/reports/083/gate-verification.md STATUS: CLEARED).
