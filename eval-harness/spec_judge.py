"""Spec-adherence judge for the spec eval gate.

Reuses check_deterministic from judge.py for regex checks.
Has its own LLM judge with a richer tool schema and anti-leniency rubric
tailored to spec instruction adherence (not pitfall rule adherence).
"""

from __future__ import annotations

from pathlib import Path

import anthropic

from judge import check_deterministic
from models import CheckResult, EvalResult, Scenario

JUDGE_MODEL = "claude-sonnet-4-6"
JUDGES_DIR = Path(__file__).parent / "judges"
SPEC_JUDGE_PROMPT_FILE = "spec-eval-base.txt"

# Fail-fast: load judge prompt at module level
_JUDGE_PROMPT_PATH = JUDGES_DIR / SPEC_JUDGE_PROMPT_FILE
if not _JUDGE_PROMPT_PATH.exists():
    raise FileNotFoundError(
        f"Judge prompt not found: {_JUDGE_PROMPT_PATH}. "
        f"Cannot run spec eval gate without it."
    )
_JUDGE_PROMPT = _JUDGE_PROMPT_PATH.read_text()

# Tool schema: reasoning before verdict (chain-of-thought debiasing)
SPEC_JUDGE_TOOL = {
    "name": "submit_verdict",
    "description": "Submit your evaluation of whether the code follows the spec instruction.",
    "input_schema": {
        "type": "object",
        "properties": {
            "reasoning": {
                "type": "string",
                "description": (
                    "Step-by-step analysis following the 3-step evaluation process. "
                    "Quote specific code lines."
                ),
            },
            "supporting_evidence": {
                "type": "string",
                "description": (
                    "Exact code lines that support or contradict the spec instruction. "
                    "'No evidence found' if none."
                ),
            },
            "verdict": {
                "type": "string",
                "enum": ["pass", "fail"],
                "description": (
                    "Does the code follow the spec instruction? UNCLEAR maps to fail."
                ),
            },
            "confidence": {
                "type": "number",
                "description": "0.0-1.0 confidence in your verdict.",
            },
        },
        "required": ["reasoning", "supporting_evidence", "verdict", "confidence"],
    },
}


def evaluate_spec(
    eval_result: EvalResult,
    scenario: Scenario,
    rule_text: str,
    client: anthropic.Anthropic,
) -> EvalResult:
    """Evaluate a spec-eval scenario result using the appropriate judge.

    For deterministic checks: uses regex (same as pitfall eval).
    For llm_judge: uses the spec-adherence judge prompt with richer tool schema.

    Returns the EvalResult updated with verdict, evidence, and confidence.
    """
    agent_output = eval_result.agent_output

    if scenario.expected_check_type == "deterministic":
        check = check_deterministic(agent_output, scenario)
    elif scenario.expected_check_type == "hybrid":
        # Try deterministic first, fall back to LLM if it fails
        check = check_deterministic(agent_output, scenario)
        if check.verdict == "fail":
            check = _check_spec_llm_judge(agent_output, scenario, rule_text, client)
    else:
        check = _check_spec_llm_judge(agent_output, scenario, rule_text, client)

    return EvalResult(
        scenario_id=eval_result.scenario_id,
        fc_id=eval_result.fc_id,
        variant=eval_result.variant,
        run_number=eval_result.run_number,
        verdict=check.verdict,
        check_type=scenario.expected_check_type,
        evidence=check.evidence,
        confidence=check.confidence,
        agent_output=agent_output,
        prompt_mode=eval_result.prompt_mode,
        model_id=eval_result.model_id,
        input_tokens=eval_result.input_tokens,
        output_tokens=eval_result.output_tokens,
        judge_input_tokens=check.judge_input_tokens,
        judge_output_tokens=check.judge_output_tokens,
        duration_ms=eval_result.duration_ms,
    )


def _check_spec_llm_judge(
    output: str,
    scenario: Scenario,
    rule_text: str,
    client: anthropic.Anthropic,
) -> CheckResult:
    """Run the spec-adherence LLM judge via tool_use."""

    user_message = (
        f"## Spec Instruction\n\n{rule_text}\n\n"
        f"## Scenario\n\n{scenario.task_brief}\n\n"
        f"## Code Produced by Agent\n\n```\n{output}\n```\n\n"
        "Evaluate whether this code correctly follows the spec instruction. "
        "Use the submit_verdict tool to provide your structured evaluation."
    )

    try:
        response = client.messages.create(
            model=JUDGE_MODEL,
            max_tokens=1024,
            system=_JUDGE_PROMPT,
            messages=[{"role": "user", "content": user_message}],
            tools=[SPEC_JUDGE_TOOL],
            tool_choice={"type": "tool", "name": "submit_verdict"},
        )
    except (
        anthropic.RateLimitError,
        anthropic.APITimeoutError,
        anthropic.InternalServerError,
        anthropic.OverloadedError,
    ) as e:
        return CheckResult(
            verdict="error",
            evidence=f"Judge API error: {type(e).__name__}: {e}",
        )

    # Extract tool use result
    for block in response.content:
        if block.type == "tool_use" and block.name == "submit_verdict":
            tool_input = block.input
            verdict = tool_input.get("verdict", "fail")
            evidence = tool_input.get("supporting_evidence", "")
            confidence = tool_input.get("confidence", 0.5)

            return CheckResult(
                verdict=verdict,
                evidence=evidence,
                confidence=confidence,
                judge_input_tokens=response.usage.input_tokens,
                judge_output_tokens=response.usage.output_tokens,
            )

    return CheckResult(
        verdict="error",
        evidence="Judge did not produce a submit_verdict tool call",
        judge_input_tokens=response.usage.input_tokens,
        judge_output_tokens=response.usage.output_tokens,
    )
