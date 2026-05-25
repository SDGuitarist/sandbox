"""Pydantic models and data structures for the pitfall eval harness."""

from __future__ import annotations

import dataclasses
from datetime import datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, model_validator


# --- Shared type aliases ---

Tier = Literal["1a", "1a-mixed", "1b", "2", "3", "4"]
Variant = Literal["with_rule", "without_rule", "adversarial"]
CheckType = Literal["deterministic", "llm_judge", "hybrid"]
Verdict = Literal["pass", "fail", "error", "skip"]
Bucket = Literal["CLEAR", "AMBIGUOUS", "BROKEN"]
PromptMode = Literal["focused"]


# --- Parsed from agent-pitfalls.md ---

class FailureClass(BaseModel):
    """A single failure class parsed from agent-pitfalls.md."""
    id: str
    slug: str
    name: str
    rule_text: str
    tier: Tier


# --- Scenario YAML models ---

class Scenario(BaseModel):
    """One scenario within a YAML file."""
    id: str
    title: str
    stack: Literal["flask", "express", "nextjs", "supabase", "sqlite", "generic"]
    task_brief: str
    inputs: dict[str, Any] = {}
    context_files: list[str] = []
    expected_check_type: CheckType
    expected_outcome: Literal["pass", "fail", "unknown"]
    deterministic_pattern: str | None = None
    deterministic_mode: Literal["presence", "absence"] | None = None
    tags: list[str] = []
    pair_group: str | None = None
    variant: Variant = "with_rule"


class ScenarioFile(BaseModel):
    """One YAML file per FC, containing multiple scenarios."""
    fc_id: str
    fc_slug: str
    scenarios: list[Scenario]

    @model_validator(mode="after")
    def validate_ids_match_fc(self) -> Self:
        for s in self.scenarios:
            if not s.id.startswith(self.fc_id):
                raise ValueError(
                    f"Scenario '{s.id}' must start with fc_id '{self.fc_id}'"
                )
        return self

    @model_validator(mode="after")
    def validate_deterministic_fields(self) -> Self:
        for s in self.scenarios:
            if s.expected_check_type in ("deterministic", "hybrid"):
                if not s.deterministic_pattern:
                    raise ValueError(
                        f"Scenario '{s.id}' needs deterministic_pattern "
                        f"for check_type '{s.expected_check_type}'"
                    )
                if not s.deterministic_mode:
                    raise ValueError(
                        f"Scenario '{s.id}' needs deterministic_mode "
                        f"for check_type '{s.expected_check_type}'"
                    )
        return self

    @model_validator(mode="after")
    def validate_pair_groups(self) -> Self:
        groups: dict[str, set[str]] = {}
        for s in self.scenarios:
            if s.pair_group:
                groups.setdefault(s.pair_group, set()).add(s.variant)
        for group, variants in groups.items():
            if "with_rule" not in variants:
                raise ValueError(f"Pair group '{group}' missing with_rule variant")
            if "without_rule" not in variants:
                raise ValueError(f"Pair group '{group}' missing without_rule variant")
        return self


# --- Evaluation results ---

@dataclasses.dataclass(frozen=True)
class CheckResult:
    """Internal return type for deterministic and judge checks."""
    verdict: Literal["pass", "fail", "error"]
    evidence: str
    confidence: float = 1.0
    judge_input_tokens: int = 0
    judge_output_tokens: int = 0


class EvalResult(BaseModel):
    """One result per scenario run."""
    scenario_id: str
    fc_id: str
    variant: Variant
    run_number: int
    verdict: Verdict
    check_type: CheckType
    evidence: str
    confidence: float
    agent_output: str
    prompt_mode: PromptMode = "focused"
    model_id: str
    input_tokens: int
    output_tokens: int
    judge_input_tokens: int = 0
    judge_output_tokens: int = 0
    duration_ms: int


# --- Scoring and reporting ---

class FCScore(BaseModel):
    """Aggregated score for one FC."""
    fc_id: str
    tier: Literal["1a", "1a-mixed", "1b"]
    pass_rate_with_rule: float
    pass_rate_without_rule: float | None = None
    delta: float | None = None
    bucket: Bucket
    ci_lower: float
    ci_upper: float
    scenario_count: int
    run_count: int
    promotable_cases: list[str] = []


class RunReport(BaseModel):
    """Top-level report for a harness run."""
    timestamp: datetime
    stage: Literal["1", "2", "all"]
    model_agent: str
    model_judge: str | None = None
    temperature: float
    max_tokens_agent: int
    total_cost_usd: float
    total_input_tokens: int
    total_output_tokens: int
    fc_scores: list[FCScore]
    calibration_accuracy: float | None = None
    report_caveat: str = (
        "These results estimate rule clarity/comprehension under controlled "
        "prompting. They do not estimate adherence under realistic swarm "
        "cognitive load."
    )
