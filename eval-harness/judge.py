"""Evaluate agent output using deterministic checks (Stage 1) and LLM judge (Stage 2)."""

from __future__ import annotations

import re
from pathlib import Path

import anthropic

from models import CheckResult, EvalResult, Scenario

JUDGE_MODEL = "claude-sonnet-4-6-20250514"
JUDGES_DIR = Path(__file__).parent / "judges"


def check_deterministic(output: str, scenario: Scenario) -> CheckResult:
    """Run regex-based deterministic check against agent output.

    Returns CheckResult with confidence=1.0 (deterministic checks are binary).
    """
    if not scenario.deterministic_pattern:
        return CheckResult(
            verdict="error",
            evidence="No deterministic_pattern defined for this scenario",
        )

    pattern = scenario.deterministic_pattern
    match = re.search(pattern, output, re.IGNORECASE | re.MULTILINE | re.DOTALL)

    if scenario.deterministic_mode == "absence":
        if match:
            return CheckResult(
                verdict="fail",
                evidence=f"Found violation pattern: {match.group()}",
            )
        return CheckResult(
            verdict="pass",
            evidence="No violation pattern found",
        )
    else:
        if match:
            return CheckResult(
                verdict="pass",
                evidence=f"Found required pattern: {match.group()}",
            )
        return CheckResult(
            verdict="fail",
            evidence=f"Required pattern not found: {pattern}",
        )


def load_judge_prompt(fc_id: str) -> str | None:
    """Load per-FC judge prompt. Returns None if not found."""
    fc_path = JUDGES_DIR / f"{fc_id}.txt"
    if fc_path.exists():
        return fc_path.read_text()
    return None


def check_llm_judge(
    output: str,
    scenario: Scenario,
    rule_text: str,
    client: anthropic.Anthropic,
    fc_id: str | None = None,
) -> CheckResult:
    """Run LLM judge (Sonnet) via tool_use for structured response.

    fc_id loads per-FC judge prompts. If not provided, extracted from scenario.id.
    """
    if fc_id is None:
        fc_id = scenario.id.split("-")[0]

    base_path = JUDGES_DIR / "base-judge.txt"
    if not base_path.exists():
        return CheckResult(
            verdict="error",
            evidence="base-judge.txt not found in judges/",
        )
    base_prompt = base_path.read_text()

    fc_prompt = load_judge_prompt(fc_id) or ""

    system = base_prompt
    if fc_prompt:
        system += f"\n\n## FC-Specific Guidance\n\n{fc_prompt}"

    user_message = f"""## Rule

{rule_text}

## Scenario

{scenario.title}: {scenario.task_brief.strip()}

## Code Sample

{output}

Evaluate whether this code follows the rule."""

    try:
        response = client.messages.create(
            model=JUDGE_MODEL,
            max_tokens=512,
            system=system,
            messages=[{"role": "user", "content": user_message}],
            tools=[{
                "name": "submit_verdict",
                "description": "Submit your evaluation verdict for this code sample.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "verdict": {
                            "type": "string",
                            "enum": ["pass", "fail", "unclear"],
                            "description": "Whether the code follows the rule.",
                        },
                        "confidence": {
                            "type": "number",
                            "minimum": 0.0,
                            "maximum": 1.0,
                            "description": "Your confidence in this verdict (0.0-1.0).",
                        },
                        "evidence": {
                            "type": "string",
                            "description": "Brief explanation of why this verdict (1-2 sentences).",
                        },
                    },
                    "required": ["verdict", "confidence", "evidence"],
                },
            }],
            tool_choice={"type": "tool", "name": "submit_verdict"},
        )

        judge_input = getattr(response.usage, "input_tokens", 0)
        judge_output = getattr(response.usage, "output_tokens", 0)

        for block in response.content:
            if block.type == "tool_use" and block.name == "submit_verdict":
                verdict_raw = block.input.get("verdict", "error")
                verdict = "fail" if verdict_raw == "unclear" else verdict_raw
                confidence = block.input.get("confidence", 0.5)
                evidence = block.input.get("evidence", "No evidence provided")
                return CheckResult(
                    verdict=verdict,
                    evidence=f"[LLM judge, {verdict_raw}] {evidence}",
                    confidence=confidence,
                    judge_input_tokens=judge_input,
                    judge_output_tokens=judge_output,
                )

        return CheckResult(
            verdict="error",
            evidence="LLM judge did not use submit_verdict tool",
        )

    except Exception as e:
        return CheckResult(
            verdict="error",
            evidence=f"LLM judge error: {e}",
        )


def evaluate(
    result: EvalResult,
    scenario: Scenario,
    rule_text: str = "",
    client: anthropic.Anthropic | None = None,
) -> EvalResult:
    """Evaluate an EvalResult's agent_output and return with verdict filled in."""
    if result.verdict == "error":
        return result

    if scenario.expected_check_type == "deterministic":
        check = check_deterministic(result.agent_output, scenario)
        return result.model_copy(update={
            "verdict": check.verdict,
            "evidence": check.evidence,
            "confidence": check.confidence,
        })

    if scenario.expected_check_type == "hybrid":
        check = check_deterministic(result.agent_output, scenario)
        if check.verdict == "pass":
            return result.model_copy(update={
                "verdict": "pass",
                "evidence": check.evidence,
                "confidence": 1.0,
            })
        if client and rule_text:
            judge_check = check_llm_judge(
                result.agent_output, scenario, rule_text, client
            )
            return result.model_copy(update={
                "verdict": judge_check.verdict,
                "evidence": f"[det: {check.evidence}] {judge_check.evidence}",
                "confidence": judge_check.confidence,
                "judge_input_tokens": judge_check.judge_input_tokens,
                "judge_output_tokens": judge_check.judge_output_tokens,
            })
        return result.model_copy(update={
            "verdict": check.verdict,
            "evidence": f"[deterministic only] {check.evidence}",
            "confidence": check.confidence,
        })

    if scenario.expected_check_type == "llm_judge":
        if client and rule_text:
            check = check_llm_judge(
                result.agent_output, scenario, rule_text, client
            )
            return result.model_copy(update={
                "verdict": check.verdict,
                "evidence": check.evidence,
                "confidence": check.confidence,
                "judge_input_tokens": check.judge_input_tokens,
                "judge_output_tokens": check.judge_output_tokens,
            })
        return result.model_copy(update={
            "verdict": "skip",
            "evidence": "LLM judge not available (no client or rule_text)",
            "confidence": 0.0,
        })

    return result
