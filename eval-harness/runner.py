"""Run scenarios against the Anthropic API and return raw results."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Literal

import anthropic

from models import CheckResult, EvalResult, FailureClass, Scenario


DEFAULT_AGENT_MODEL = "claude-haiku-4-5-20251001"


def build_prompt(
    scenario: Scenario,
    fc: FailureClass,
    variant: Literal["with_rule", "without_rule"],
    fixtures_dir: Path | None = None,
) -> tuple[str, str]:
    """Build system and user messages for the focused prompt mode.

    Returns (system_message, user_message).
    """
    system = f"You are a senior {scenario.stack} developer.\n"
    if variant == "with_rule":
        system += "Complete the task below. Follow the rules provided."
    else:
        system += "Complete the task below."

    user_parts = []

    if variant == "with_rule":
        user_parts.append(f"Rules:\n{fc.rule_text}")

    user_parts.append(f"Task:\n{scenario.task_brief.strip()}")

    # Load fixture files if any
    if scenario.context_files and fixtures_dir:
        for cf in scenario.context_files:
            fixture_path = fixtures_dir / cf
            if fixture_path.exists():
                content = fixture_path.read_text()
                user_parts.append(f"Existing code ({cf}):\n```\n{content}\n```")

    user_parts.append("Respond with ONLY the code. No explanations, no markdown fences.")

    return system, "\n\n".join(user_parts)


def run_scenario(
    scenario: Scenario,
    fc: FailureClass,
    variant: Literal["with_rule", "without_rule"],
    run_number: int,
    client: anthropic.Anthropic,
    model: str = DEFAULT_AGENT_MODEL,
    temperature: float = 0.0,
    max_tokens: int = 2048,
    fixtures_dir: Path | None = None,
) -> EvalResult:
    """Call the API with a scenario prompt and return the raw result.

    The verdict field is set to "skip" -- the caller (CLI) runs the judge
    separately and assembles the final verdict.
    """
    system_msg, user_msg = build_prompt(scenario, fc, variant, fixtures_dir)

    start_ms = time.monotonic_ns() // 1_000_000

    try:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_msg,
            messages=[{"role": "user", "content": user_msg}],
        )
    except anthropic.AuthenticationError:
        raise  # never retry, abort the entire run
    except anthropic.BadRequestError as e:
        duration = (time.monotonic_ns() // 1_000_000) - start_ms
        return EvalResult(
            scenario_id=scenario.id,
            fc_id=fc.id,
            variant=variant,
            run_number=run_number,
            verdict="error",
            check_type=scenario.expected_check_type,
            evidence=f"BadRequestError: {e.message}",
            confidence=0.0,
            agent_output="",
            model_id=model,
            input_tokens=0,
            output_tokens=0,
            duration_ms=duration,
        )
    except (
        anthropic.RateLimitError,
        anthropic.APITimeoutError,
        anthropic.InternalServerError,
    ) as e:
        # Retry is handled by the SDK's built-in retry (max_retries on client).
        # If we still get here, all retries were exhausted.
        duration = (time.monotonic_ns() // 1_000_000) - start_ms
        return EvalResult(
            scenario_id=scenario.id,
            fc_id=fc.id,
            variant=variant,
            run_number=run_number,
            verdict="error",
            check_type=scenario.expected_check_type,
            evidence=f"{type(e).__name__}: {e}",
            confidence=0.0,
            agent_output="",
            model_id=model,
            input_tokens=0,
            output_tokens=0,
            duration_ms=duration,
        )

    duration = (time.monotonic_ns() // 1_000_000) - start_ms

    # Extract text output
    agent_output = ""
    for block in response.content:
        if hasattr(block, "text"):
            agent_output += block.text

    if not agent_output.strip():
        return EvalResult(
            scenario_id=scenario.id,
            fc_id=fc.id,
            variant=variant,
            run_number=run_number,
            verdict="error",
            check_type=scenario.expected_check_type,
            evidence="Empty agent output (0 tokens)",
            confidence=0.0,
            agent_output="",
            model_id=model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            duration_ms=duration,
        )

    return EvalResult(
        scenario_id=scenario.id,
        fc_id=fc.id,
        variant=variant,
        run_number=run_number,
        verdict="skip",  # placeholder -- judge fills in the real verdict
        check_type=scenario.expected_check_type,
        evidence="",
        confidence=0.0,
        agent_output=agent_output,
        model_id=model,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        duration_ms=duration,
    )
