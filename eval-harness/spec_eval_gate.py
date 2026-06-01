"""Spec Eval Gate: test whether agents can follow a spec's instructions.

Pre-swarm gate (step 9w.8) that extracts testable claims from spec
tables and prose, generates scenarios, runs them through the eval harness,
and blocks the swarm if agents can't reliably follow the spec.

Exit codes:
  0 = PASS (all HIGH-confidence claims passed)
  1 = FAIL / WARN_UNSCORABLE / RETRY (gate blocks the swarm)
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

import click
import httpx

import anthropic

from exceptions import ExtractionError
from extractor import deduplicate_claims, extract_prose_claims, parse_tables, strip_tables
from models import Claim, ClaimResult, EvalResult, GateStatus, Scenario, CONFIDENCE_THRESHOLD
from runner import run_scenario
from spec_judge import evaluate_spec
from spec_scenario_gen import claims_to_scenarios
from spec_scorer import GateConfig, score_gate


DEFAULT_CONCURRENCY = 10


def _haiku_cost(input_tokens: int, output_tokens: int) -> float:
    """Haiku pricing: $0.80/M input, $4/M output."""
    return (input_tokens * 0.80 + output_tokens * 4.0) / 1_000_000


def _sonnet_cost(input_tokens: int, output_tokens: int) -> float:
    """Sonnet pricing: $3/M input, $15/M output."""
    return (input_tokens * 3.0 + output_tokens * 15.0) / 1_000_000


def _run_and_judge(
    scenario: Scenario,
    rule_text: str,
    client: anthropic.Anthropic,
    max_tokens_scenario: int,
) -> tuple[EvalResult, float]:
    """Sync function called inside a thread. Returns (result, cost)."""
    result = run_scenario(
        scenario,
        rule_text,
        scenario.id,
        "with_rule",
        1,
        client,
        max_tokens=max_tokens_scenario,
    )
    cost = _haiku_cost(result.input_tokens, result.output_tokens)

    result = evaluate_spec(result, scenario, rule_text, client)
    cost += _sonnet_cost(result.judge_input_tokens, result.judge_output_tokens)

    return result, cost


async def _run_scenarios_concurrent(
    scenarios_and_rules: list[tuple[Scenario, str]],
    client: anthropic.Anthropic,
    cost_cap: float,
    max_tokens_scenario: int,
    concurrency: int = DEFAULT_CONCURRENCY,
) -> tuple[list[EvalResult], float]:
    """Run scenarios concurrently. Returns (results, total_cost).

    Costs are accumulated after gather completes to avoid race conditions.
    The cost cap is checked between batches as a best-effort early stop.
    """
    sem = asyncio.Semaphore(concurrency)
    total_cost = 0.0

    async def run_one(scenario: Scenario, rule_text: str) -> tuple[EvalResult, float] | None:
        async with sem:
            if total_cost >= cost_cap:
                return None
            return await asyncio.to_thread(
                _run_and_judge, scenario, rule_text, client, max_tokens_scenario
            )

    tasks = [run_one(s, r) for s, r in scenarios_and_rules]
    raw = await asyncio.gather(*tasks)

    # Aggregate costs sequentially after all tasks complete (no race)
    eval_results: list[EvalResult] = []
    for item in raw:
        if item is not None:
            result, cost = item
            eval_results.append(result)
            total_cost += cost

    return eval_results, total_cost


def _eval_results_to_claim_results(
    eval_results: list[EvalResult],
    claims: list[Claim],
    scenario_to_claim: dict[str, str],
) -> list[ClaimResult]:
    """Convert EvalResults to ClaimResults for the scorer.

    Uses a pre-built scenario_id -> claim_id mapping instead of
    parsing claim_id from scenario_id (which breaks when run_id
    contains dashes).
    """
    claim_map = {c.id: c for c in claims}
    results: list[ClaimResult] = []

    for er in eval_results:
        claim_id = scenario_to_claim.get(er.scenario_id, er.scenario_id)

        claim = claim_map.get(claim_id)
        claim_text = claim.text if claim else er.scenario_id

        passed = er.verdict == "pass"
        is_error = er.verdict == "error"

        results.append(
            ClaimResult(
                claim_id=claim_id,
                claim_text=claim_text,
                passed=passed,
                evidence=er.evidence,
                is_error=is_error,
            )
        )

    return results


async def _run_gate(
    spec_path: str,
    output_dir: str,
    confidence_threshold: float,
    min_high_claims: int,
    cost_cap: float,
    max_tokens_scenario: int,
    concurrency: int,
    dry_run: bool,
    verbose: bool,
) -> int:
    """Main gate logic. Returns exit code (0=PASS, 1=FAIL)."""
    start_time = time.monotonic()

    # Validate spec path
    real_path = os.path.realpath(spec_path)
    if not os.path.isfile(real_path):
        click.echo(f"Error: spec file not found: {spec_path}", err=True)
        return 1

    # Read spec
    spec_text = Path(real_path).read_text()
    if not spec_text.strip():
        click.echo("WARN_UNSCORABLE: Spec document is empty", err=True)
        return 1

    # Token pre-check (rough: 1 token ~= 4 chars)
    approx_tokens = len(spec_text) // 4
    if approx_tokens > 80_000:
        click.echo(
            "Error: Spec exceeds context window limit (~80K tokens). "
            "Split into sections.",
            err=True,
        )
        return 1

    # Phase 2a: Extract table claims (deterministic)
    table_claims = parse_tables(spec_text)
    if verbose:
        click.echo(f"Table claims extracted: {len(table_claims)}")

    # Phase 2b: Extract prose claims (LLM)
    spec_without_tables = strip_tables(spec_text)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        if dry_run:
            click.echo(
                "Warning: ANTHROPIC_API_KEY not set. Skipping prose extraction.",
                err=True,
            )
            prose_claims = []
        else:
            click.echo(
                "ENV_ERROR: ANTHROPIC_API_KEY not set. Required for prose extraction "
                "and scenario execution.",
                err=True,
            )
            return 2  # env error, not spec failure
    else:
        # Long timeout for Sonnet extraction (large input)
        extraction_client = anthropic.Anthropic(
            max_retries=3,
            timeout=httpx.Timeout(600.0, connect=10.0),
        )
        # Short timeout for Haiku scenarios + Sonnet judge (small input)
        scenario_client = anthropic.Anthropic(
            max_retries=3,
            timeout=httpx.Timeout(60.0, connect=10.0),
        )
        try:
            prose_claims = extract_prose_claims(spec_without_tables, extraction_client)
        except ExtractionError as e:
            click.echo(f"Extraction error: {e}", err=True)
            return 1

    if verbose:
        click.echo(f"Prose claims extracted: {len(prose_claims)}")

    # Phase 2c: Deduplicate
    all_claims = deduplicate_claims(table_claims + prose_claims)
    if verbose:
        click.echo(f"Total claims after dedup: {len(all_claims)}")

    # Check minimum extraction threshold
    high_claims = [c for c in all_claims if c.confidence >= confidence_threshold]
    if len(high_claims) < min_high_claims:
        click.echo(
            f"WARN_UNSCORABLE: Only {len(high_claims)} HIGH-confidence claims "
            f"(need >= {min_high_claims})",
        )
        if not dry_run:
            return 1

    # Generate run_id
    run_id = f"spec-eval-{int(time.time())}"

    # Dry run: write extraction output and exit
    if dry_run:
        report_dir = Path(output_dir) / run_id
        report_dir.mkdir(parents=True, exist_ok=True)

        extraction_data = {
            "run_id": run_id,
            "spec_path": spec_path,
            "total_claims": len(all_claims),
            "high_confidence": len(high_claims),
            "low_confidence": len(all_claims) - len(high_claims),
            "claims": [c.model_dump() for c in all_claims],
        }
        extraction_path = report_dir / "extraction.json"
        extraction_path.write_text(json.dumps(extraction_data, indent=2))

        click.echo(f"\n--- Dry Run: {len(all_claims)} claims extracted ---")
        click.echo(f"HIGH confidence (>= {confidence_threshold}): {len(high_claims)}")
        click.echo(f"LOW confidence: {len(all_claims) - len(high_claims)}")
        click.echo(f"\nExtraction saved to: {extraction_path}")

        for c in all_claims:
            marker = "HIGH" if c.confidence >= confidence_threshold else "LOW "
            det = " [det]" if c.deterministic_check else " [llm]"
            click.echo(f"  [{marker}] {c.id}: {c.text[:70]}{det}")

        return 0

    # Phase 3: Generate scenarios
    scenarios_and_rules = claims_to_scenarios(all_claims, run_id)

    # Build scenario_id -> claim_id lookup for result mapping
    scenario_to_claim: dict[str, str] = {}
    for (scenario, _rule_text), claim in zip(scenarios_and_rules, all_claims):
        scenario_to_claim[scenario.id] = claim.id

    if verbose:
        click.echo(f"Scenarios generated: {len(scenarios_and_rules)}")

    # Phase 4-5: Run scenarios concurrently and judge
    eval_results, total_cost = await _run_scenarios_concurrent(
        scenarios_and_rules, scenario_client, cost_cap, max_tokens_scenario, concurrency
    )

    if total_cost >= cost_cap:
        click.echo(
            f"Warning: cost cap reached (${total_cost:.3f} >= ${cost_cap}). "
            f"Partial run: {len(eval_results)}/{len(scenarios_and_rules)} scenarios.",
            err=True,
        )

    # Convert to ClaimResults for scorer
    claim_results = _eval_results_to_claim_results(eval_results, all_claims, scenario_to_claim)

    # Score
    runtime_ms = int((time.monotonic() - start_time) * 1000)
    config = GateConfig(
        confidence_threshold=confidence_threshold,
        min_high_claims=min_high_claims,
    )
    gate_result = score_gate(
        claim_results,
        all_claims,
        config,
        cost_usd=total_cost,
        runtime_ms=runtime_ms,
        spec_path=spec_path,
        run_id=run_id,
    )

    # Write JSON report
    report_dir = Path(output_dir) / run_id
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "spec-eval-gate.json"
    report_path.write_text(json.dumps(gate_result.model_dump(), indent=2))

    # Console summary
    click.echo(f"\n{'='*50}")
    click.echo(f"SPEC EVAL GATE: {gate_result.status.value}")
    click.echo(f"{'='*50}")
    click.echo(
        f"HIGH confidence: {gate_result.high_confidence.passed}/"
        f"{gate_result.high_confidence.total} passed"
    )
    click.echo(
        f"LOW confidence:  {gate_result.low_confidence.passed}/"
        f"{gate_result.low_confidence.total} passed (warnings only)"
    )
    click.echo(f"Cost: ${gate_result.cost_usd:.3f} | Runtime: {runtime_ms}ms")
    click.echo(f"Report: {report_path}")

    if gate_result.failed_details:
        click.echo(f"\nFailed claims ({len(gate_result.failed_details)}):")
        for f in gate_result.failed_details:
            click.echo(f"  FAIL: {f.claim_id} -- {f.claim_text[:60]}")
            click.echo(f"        Evidence: {f.evidence[:80]}")

    if gate_result.low_warnings and verbose:
        click.echo(f"\nLow-confidence warnings ({len(gate_result.low_warnings)}):")
        for w in gate_result.low_warnings:
            click.echo(f"  WARN: {w.claim_id} -- {w.claim_text[:60]}")

    # Write verification artifact on PASS (prevents gate-bypass bugs like Run 054)
    if gate_result.status == GateStatus.PASS:
        verification_path = report_dir / "spec-eval-verification.md"
        verification_path.write_text(
            f"STATUS: PASS\n"
            f"high_passed: {gate_result.high_confidence.passed}/{gate_result.high_confidence.total}\n"
            f"cost_usd: {gate_result.cost_usd:.3f}\n"
            f"report: {report_path}\n"
        )

    # Exit codes: 0=PASS, 1=FAIL/WARN/RETRY, 2=ENV_ERROR (set earlier)
    return 0 if gate_result.status == GateStatus.PASS else 1


@click.command()
@click.argument("spec_path", type=click.Path(exists=True))
@click.option("--output-dir", default="reports", type=click.Path())
@click.option("--confidence-threshold", default=CONFIDENCE_THRESHOLD, type=float)
@click.option("--min-high-claims", default=3, type=int)
@click.option("--cost-cap", default=1.0, type=float)
@click.option("--max-tokens-scenario", default=1024, type=int)
@click.option("--concurrency", default=DEFAULT_CONCURRENCY, type=int,
              help="Max concurrent scenario runs")
@click.option("--dry-run", is_flag=True, help="Extract claims only, don't run scenarios")
@click.option("--verbose", is_flag=True)
def main(
    spec_path: str,
    output_dir: str,
    confidence_threshold: float,
    min_high_claims: int,
    cost_cap: float,
    max_tokens_scenario: int,
    concurrency: int,
    dry_run: bool,
    verbose: bool,
) -> None:
    """Spec Eval Gate: test whether agents can follow a spec's instructions."""
    exit_code = asyncio.run(
        _run_gate(
            spec_path,
            output_dir,
            confidence_threshold,
            min_high_claims,
            cost_cap,
            max_tokens_scenario,
            concurrency,
            dry_run,
            verbose,
        )
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
