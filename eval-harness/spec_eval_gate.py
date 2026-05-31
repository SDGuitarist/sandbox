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
from dataclasses import dataclass, field
from pathlib import Path

import click
import httpx

import anthropic

from exceptions import ExtractionError, SpecEvalError
from extractor import deduplicate_claims, extract_prose_claims, parse_tables, strip_tables
from models import Claim, ClaimResult, EvalResult, GateStatus, CONFIDENCE_THRESHOLD
from runner import run_scenario
from spec_judge import evaluate_spec
from spec_scenario_gen import claims_to_scenarios
from spec_scorer import GateConfig, score_gate


CONCURRENCY_LIMIT = 5


@dataclass
class CostTracker:
    """Track API costs across concurrent calls."""

    cap: float = 1.0
    total: float = 0.0
    haiku_tokens: int = 0
    sonnet_tokens: int = 0

    def add_haiku(self, input_tokens: int, output_tokens: int) -> None:
        # Haiku pricing: $0.80/M input, $4/M output
        cost = (input_tokens * 0.80 + output_tokens * 4.0) / 1_000_000
        self.total += cost
        self.haiku_tokens += input_tokens + output_tokens

    def add_sonnet(self, input_tokens: int, output_tokens: int) -> None:
        # Sonnet pricing: $3/M input, $15/M output
        cost = (input_tokens * 3.0 + output_tokens * 15.0) / 1_000_000
        self.total += cost
        self.sonnet_tokens += input_tokens + output_tokens

    @property
    def exceeded(self) -> bool:
        return self.total >= self.cap


def _run_and_judge(
    scenario,
    rule_text: str,
    client: anthropic.Anthropic,
    max_tokens_scenario: int,
) -> tuple[EvalResult, CostTracker]:
    """Sync function called inside a thread. Uses sync anthropic.Anthropic client."""
    tracker = CostTracker()

    result = run_scenario(
        scenario,
        rule_text,
        scenario.id,
        "with_rule",
        1,
        client,
        max_tokens=max_tokens_scenario,
    )
    tracker.add_haiku(result.input_tokens, result.output_tokens)

    result = evaluate_spec(result, scenario, rule_text, client)
    tracker.add_sonnet(result.judge_input_tokens, result.judge_output_tokens)

    return result, tracker


async def _run_scenarios_concurrent(
    scenarios_and_rules: list[tuple],
    client: anthropic.Anthropic,
    cost_tracker: CostTracker,
    max_tokens_scenario: int,
) -> list[EvalResult]:
    """Run scenarios concurrently with semaphore-based throttling."""
    sem = asyncio.Semaphore(CONCURRENCY_LIMIT)
    results: list[EvalResult | None] = []

    async def run_one(scenario, rule_text) -> EvalResult | None:
        async with sem:
            if cost_tracker.exceeded:
                return None
            result, local_cost = await asyncio.to_thread(
                _run_and_judge, scenario, rule_text, client, max_tokens_scenario
            )
            cost_tracker.total += local_cost.total
            cost_tracker.haiku_tokens += local_cost.haiku_tokens
            cost_tracker.sonnet_tokens += local_cost.sonnet_tokens
            return result

    tasks = [run_one(s, r) for s, r in scenarios_and_rules]
    results = await asyncio.gather(*tasks)
    return [r for r in results if r is not None]


def _eval_results_to_claim_results(
    eval_results: list[EvalResult],
    claims: list[Claim],
) -> list[ClaimResult]:
    """Convert EvalResults to ClaimResults for the scorer."""
    claim_map = {c.id: c for c in claims}
    results: list[ClaimResult] = []

    for er in eval_results:
        # Extract claim_id from scenario_id: "spec-{run_id[:8]}-{claim.id}"
        parts = er.scenario_id.split("-", 2)
        claim_id = parts[2] if len(parts) > 2 else er.scenario_id

        claim = claim_map.get(claim_id)
        claim_text = claim.text if claim else er.scenario_id

        passed = er.verdict == "pass"
        evidence = er.evidence if er.verdict != "error" else "error"

        results.append(
            ClaimResult(
                claim_id=claim_id,
                claim_text=claim_text,
                passed=passed,
                evidence=evidence,
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
                "Error: ANTHROPIC_API_KEY not set. Required for prose extraction "
                "and scenario execution.",
                err=True,
            )
            return 1
    else:
        client = anthropic.Anthropic(
            max_retries=3,
            timeout=httpx.Timeout(180.0, connect=5.0),
        )
        try:
            prose_claims = extract_prose_claims(spec_without_tables, client)
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
    if verbose:
        click.echo(f"Scenarios generated: {len(scenarios_and_rules)}")

    # Phase 4-5: Run scenarios concurrently and judge
    cost_tracker = CostTracker(cap=cost_cap)

    eval_results = await _run_scenarios_concurrent(
        scenarios_and_rules, client, cost_tracker, max_tokens_scenario
    )

    if cost_tracker.exceeded:
        click.echo(
            f"Warning: cost cap reached (${cost_tracker.total:.3f} >= ${cost_cap}). "
            f"Partial run: {len(eval_results)}/{len(scenarios_and_rules)} scenarios.",
            err=True,
        )

    # Convert to ClaimResults for scorer
    claim_results = _eval_results_to_claim_results(eval_results, all_claims)

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
        cost_usd=cost_tracker.total,
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

    # Exit code: 0 for PASS, 1 for everything else
    return 0 if gate_result.status == GateStatus.PASS else 1


@click.command()
@click.argument("spec_path", type=click.Path(exists=True))
@click.option("--output-dir", default="reports", type=click.Path())
@click.option("--confidence-threshold", default=CONFIDENCE_THRESHOLD, type=float)
@click.option("--min-high-claims", default=3, type=int)
@click.option("--cost-cap", default=1.0, type=float)
@click.option("--max-tokens-scenario", default=1024, type=int)
@click.option("--dry-run", is_flag=True, help="Extract claims only, don't run scenarios")
@click.option("--verbose", is_flag=True)
def main(
    spec_path: str,
    output_dir: str,
    confidence_threshold: float,
    min_high_claims: int,
    cost_cap: float,
    max_tokens_scenario: int,
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
            dry_run,
            verbose,
        )
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
