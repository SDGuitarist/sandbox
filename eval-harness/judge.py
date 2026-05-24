"""Evaluate agent output using deterministic checks (Stage 1) and LLM judge (Stage 2)."""

from __future__ import annotations

import re

from models import CheckResult, EvalResult, Scenario


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
        # Pattern must NOT appear (e.g., /categories/categories/)
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
        # Pattern MUST appear (e.g., escape() call)
        if match:
            return CheckResult(
                verdict="pass",
                evidence=f"Found required pattern: {match.group()}",
            )
        return CheckResult(
            verdict="fail",
            evidence=f"Required pattern not found: {pattern}",
        )


def evaluate(result: EvalResult, scenario: Scenario) -> EvalResult:
    """Evaluate an EvalResult's agent_output and return a new EvalResult with verdict filled in.

    For Stage 1, only deterministic checks are used.
    For Stage 2 (hybrid/llm_judge), this would also call the LLM judge -- not implemented yet.
    """
    if result.verdict == "error":
        # Already errored during API call, don't evaluate
        return result

    if scenario.expected_check_type == "deterministic":
        check = check_deterministic(result.agent_output, scenario)
        return result.model_copy(update={
            "verdict": check.verdict,
            "evidence": check.evidence,
            "confidence": check.confidence,
        })

    if scenario.expected_check_type == "hybrid":
        # Hybrid: run deterministic first
        check = check_deterministic(result.agent_output, scenario)
        if check.verdict == "pass":
            # Deterministic pass is final (no judge call)
            return result.model_copy(update={
                "verdict": "pass",
                "evidence": check.evidence,
                "confidence": 1.0,
            })
        # Deterministic failed -- in Stage 2, would call LLM judge here.
        # For Stage 1, we accept the deterministic failure as final.
        return result.model_copy(update={
            "verdict": check.verdict,
            "evidence": f"[deterministic pre-check] {check.evidence}",
            "confidence": check.confidence,
        })

    if scenario.expected_check_type == "llm_judge":
        # Not implemented in Stage 1
        return result.model_copy(update={
            "verdict": "skip",
            "evidence": "LLM judge not available in Stage 1",
            "confidence": 0.0,
        })

    return result
