"""Aggregate EvalResults into FCScores with Wilson CI and promotable case detection."""

from __future__ import annotations

import math
from collections import defaultdict

from models import EvalResult, FCScore, FailureClass


def wilson_score_interval(successes: int, n: int) -> tuple[float, float]:
    """Wilson score 95% CI for binary outcomes. No scipy needed."""
    if n == 0:
        return (0.0, 1.0)
    z = 1.96  # hardcoded for 95% confidence
    p_hat = successes / n
    denom = 1 + z**2 / n
    center = (p_hat + z**2 / (2 * n)) / denom
    margin = (z / denom) * math.sqrt(p_hat * (1 - p_hat) / n + z**2 / (4 * n**2))
    return (max(0.0, center - margin), min(1.0, center + margin))


def find_promotable_cases(results: list[EvalResult], min_fails: int = 2) -> list[str]:
    """Find scenarios with reproducible failures (2+ of 3 runs).

    Uses FINAL verdicts only. For hybrid FCs, this means post-judge verdicts.
    """
    # Group by scenario_id
    by_scenario: dict[str, list[EvalResult]] = defaultdict(list)
    for r in results:
        by_scenario[r.scenario_id].append(r)

    promotable = []
    for scenario_id, runs in by_scenario.items():
        fail_count = sum(1 for r in runs if r.verdict == "fail")
        total = len(runs)
        if total > 0 and fail_count >= min_fails:
            # For LLM-judge checks, also require high confidence
            if any(r.check_type in ("llm_judge", "hybrid") for r in runs):
                high_conf_fails = sum(
                    1 for r in runs
                    if r.verdict == "fail" and r.confidence >= 0.8
                )
                if high_conf_fails >= min_fails:
                    promotable.append(scenario_id)
            else:
                promotable.append(scenario_id)

    return sorted(promotable)


def score_fc(
    results: list[EvalResult],
    fc: FailureClass,
) -> FCScore | None:
    """Compute pass rate, delta, bucket, CI, and promotable cases for one FC.

    Returns None if all results errored (no usable data).
    """
    with_rule = [
        r for r in results
        if r.variant == "with_rule" and r.verdict not in ("error", "skip")
    ]
    without_rule = [
        r for r in results
        if r.variant == "without_rule" and r.verdict not in ("error", "skip")
    ]

    if not with_rule:
        return None  # all results errored -- skip with warning

    # Pass rates
    passes_with = sum(1 for r in with_rule if r.verdict == "pass")
    pass_rate_with = passes_with / len(with_rule)

    pass_rate_without = None
    if without_rule:
        passes_without = sum(1 for r in without_rule if r.verdict == "pass")
        pass_rate_without = passes_without / len(without_rule)

    # Delta
    delta = None
    if pass_rate_without is not None:
        delta = pass_rate_with - pass_rate_without

    # Wilson CI on with_rule pass rate
    ci_lower, ci_upper = wilson_score_interval(passes_with, len(with_rule))

    # Scoring bucket
    if pass_rate_with > 0.95:
        bucket = "CLEAR"
    elif pass_rate_with >= 0.70:
        bucket = "AMBIGUOUS"
    else:
        bucket = "BROKEN"

    # Promotable cases (from with_rule results only)
    promotable = find_promotable_cases(with_rule)

    # Determine tier for report (only 1a, 1a-mixed, 1b are scored in v1)
    tier = fc.tier
    if tier not in ("1a", "1a-mixed", "1b"):
        tier = "1a"  # shouldn't happen in v1 but safe default

    # Count unique scenarios
    scenario_ids = {r.scenario_id for r in with_rule}

    return FCScore(
        fc_id=fc.id,
        tier=tier,
        pass_rate_with_rule=round(pass_rate_with, 4),
        pass_rate_without_rule=round(pass_rate_without, 4) if pass_rate_without is not None else None,
        delta=round(delta, 4) if delta is not None else None,
        bucket=bucket,
        ci_lower=round(ci_lower, 4),
        ci_upper=round(ci_upper, 4),
        scenario_count=len(scenario_ids),
        run_count=len(with_rule),
        promotable_cases=promotable,
    )


def score_all(
    results: list[EvalResult],
    failure_classes: dict[str, FailureClass],
) -> list[FCScore]:
    """Score all FCs from a batch of results."""
    by_fc: dict[str, list[EvalResult]] = defaultdict(list)
    for r in results:
        by_fc[r.fc_id].append(r)

    scores = []
    for fc_id, fc_results in sorted(by_fc.items()):
        fc = failure_classes.get(fc_id)
        if not fc:
            continue
        score = score_fc(fc_results, fc)
        if score:
            scores.append(score)

    return scores
