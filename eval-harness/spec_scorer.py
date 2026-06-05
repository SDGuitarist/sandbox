"""Gate scoring logic for the spec eval gate.

Applies a confidence-filtered 100% threshold:
- HIGH confidence claims (>= threshold) must ALL pass to gate PASS
- LOW confidence claims are reported as warnings but never block
- Error rate > 20% among HIGH claims triggers RETRY (transient issue)
"""

from __future__ import annotations

from dataclasses import dataclass

from models import (
    Claim,
    ClaimResult,
    GateResult,
    GateStatus,
    TierSummary,
    CONFIDENCE_THRESHOLD,
)


@dataclass
class GateConfig:
    """Configuration for gate scoring. Extracted from CLI options."""

    confidence_threshold: float = CONFIDENCE_THRESHOLD
    min_high_claims: int = 3
    max_error_rate: float = 0.20


def score_gate(
    results: list[ClaimResult],
    claims: list[Claim],
    config: GateConfig = GateConfig(),
    *,
    cost_usd: float = 0.0,
    runtime_ms: int = 0,
    spec_path: str = "",
    run_id: str = "",
) -> GateResult:
    """Score spec-eval results using confidence-filtered 100% threshold.

    Gate rules:
    1. Partition claims into HIGH (>= threshold) and LOW (< threshold)
    2. If HIGH count < min_high_claims: WARN_UNSCORABLE
    3. If HIGH error rate > max_error_rate: RETRY
    4. If ALL HIGH claims pass: PASS
    5. If ANY HIGH claim fails: FAIL

    LOW claims are reported as warnings but never block.
    """
    # Build a lookup from claim_id to confidence
    confidence_map: dict[str, float] = {c.id: c.confidence for c in claims}

    # Partition results into HIGH and LOW
    high_results: list[ClaimResult] = []
    low_results: list[ClaimResult] = []

    for r in results:
        conf = confidence_map.get(r.claim_id, 0.0)
        if conf >= config.confidence_threshold:
            high_results.append(r)
        else:
            low_results.append(r)

    # Count HIGH outcomes
    high_passed = sum(1 for r in high_results if r.passed)
    high_failed = sum(1 for r in high_results if not r.passed and not r.is_error)
    high_errors = sum(1 for r in high_results if r.is_error)
    high_total = len(high_results)

    # Count LOW outcomes
    low_passed = sum(1 for r in low_results if r.passed)
    low_failed = sum(1 for r in low_results if not r.passed and not r.is_error)
    low_errors = sum(1 for r in low_results if r.is_error)
    low_total = len(low_results)

    high_summary = TierSummary(
        total=high_total, passed=high_passed, failed=high_failed, errors=high_errors
    )
    low_summary = TierSummary(
        total=low_total, passed=low_passed, failed=low_failed, errors=low_errors
    )

    # Collect failed details and low warnings
    failed_details = [r for r in high_results if not r.passed]
    low_warnings = [r for r in low_results if not r.passed]

    # Determine gate status
    status = _determine_status(high_total, high_passed, high_errors, config)

    return GateResult(
        status=status,
        high_confidence=high_summary,
        low_confidence=low_summary,
        failed_details=failed_details,
        low_warnings=low_warnings,
        cost_usd=cost_usd,
        runtime_ms=runtime_ms,
        spec_path=spec_path,
        run_id=run_id,
    )


def _determine_status(
    high_total: int,
    high_passed: int,
    high_errors: int,
    config: GateConfig,
) -> GateStatus:
    """Apply the gate rules to determine status."""
    # Rule 2: Not enough HIGH claims to score
    if high_total < config.min_high_claims:
        return GateStatus.WARN_UNSCORABLE

    # Rule 3: Too many errors (transient issue, suggest retry)
    error_rate = high_errors / high_total if high_total > 0 else 0.0
    if error_rate > config.max_error_rate:
        return GateStatus.RETRY

    # Rule 4: All HIGH claims pass
    if high_passed == high_total:
        return GateStatus.PASS

    # Rule 5: Any HIGH claim fails (errors count as failures here)
    return GateStatus.FAIL
