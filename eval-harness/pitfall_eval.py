"""Pitfall Rule Eval Harness -- CLI entry point.

Tests whether agent pitfall rules are clear enough that LLM agents follow them.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import anthropic
import click
import yaml
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskID

from judge import JUDGE_MODEL, check_llm_judge, evaluate
from models import EvalResult, RunReport, Scenario, ScenarioFile
from parser import parse_pitfalls
from reporter import write_report
from runner import run_scenario
from scorer import score_all

console = Console()

PRICING = {
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.00},
    "claude-sonnet-4-6-20250514": {"input": 3.00, "output": 15.00},
}

STAGE_1_FCS = {
    "fc7", "fc14", "fc16", "fc19", "fc20", "fc23",
    "fc24", "fc28", "fc33", "fc36", "fc46", "fc47",
}

STAGE_2_FCS = {
    "fc1", "fc2", "fc4", "fc9", "fc10", "fc15",
    "fc17", "fc25", "fc26", "fc27", "fc35", "fc39", "fc41",
}

CALIBRATION_THRESHOLD = 0.90


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate USD cost from token counts."""
    prices = PRICING.get(model, {"input": 1.0, "output": 5.0})
    return (input_tokens / 1_000_000 * prices["input"] +
            output_tokens / 1_000_000 * prices["output"])


def load_scenarios(scenarios_dir: Path, fc_filter: set[str] | None = None) -> dict[str, ScenarioFile]:
    """Load and validate all scenario YAML files."""
    scenario_files: dict[str, ScenarioFile] = {}
    seen_ids: set[str] = set()

    for yaml_path in sorted(scenarios_dir.glob("*.yaml")):
        with open(yaml_path) as f:
            data = yaml.safe_load(f)

        try:
            sf = ScenarioFile(**data)
        except Exception as e:
            console.print(f"[red]Error in {yaml_path.name}:[/red] {e}")
            sys.exit(1)

        if fc_filter and sf.fc_id not in fc_filter:
            continue

        for s in sf.scenarios:
            if s.id in seen_ids:
                console.print(f"[red]Duplicate scenario ID:[/red] {s.id} in {yaml_path.name}")
                sys.exit(1)
            seen_ids.add(s.id)

        scenario_files[sf.fc_id] = sf

    return scenario_files


def load_checkpoint(checkpoint_path: Path) -> set[str]:
    """Load completed result keys from JSONL checkpoint."""
    completed = set()
    if not checkpoint_path.exists():
        return completed

    with open(checkpoint_path) as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                key = f"{entry['fc_id']}-{entry['scenario_id']}-{entry['variant']}-{entry['run_number']}"
                completed.add(key)
            except (json.JSONDecodeError, KeyError) as e:
                console.print(f"[yellow]Warning: skipping malformed checkpoint line {line_num}: {e}[/yellow]")

    return completed


def append_checkpoint(checkpoint_path: Path, result: EvalResult) -> None:
    """Append a single result to the JSONL checkpoint file."""
    with open(checkpoint_path, "a") as f:
        f.write(result.model_dump_json() + "\n")


def result_key(fc_id: str, scenario_id: str, variant: str, run_number: int) -> str:
    """Generate a stable result key for checkpoint dedup."""
    return f"{fc_id}-{scenario_id}-{variant}-{run_number}"


def run_calibration(
    pitfalls_path: Path,
    calibration_path: Path,
    verbose: bool = False,
) -> float:
    """Run LLM judge on calibration set and return agreement rate."""
    failure_classes = parse_pitfalls(pitfalls_path)
    fc_lookup = {fc.id: fc for fc in failure_classes}

    with open(calibration_path) as f:
        cal_data = yaml.safe_load(f)

    samples = cal_data.get("calibration_samples", [])
    if not samples:
        console.print("[red]No calibration samples found[/red]")
        return 0.0

    console.print(f"[bold]Running calibration on {len(samples)} samples...[/bold]")

    client = anthropic.Anthropic(max_retries=3)

    agree = 0
    disagree = 0
    errors = 0

    for i, sample in enumerate(samples, 1):
        fc_id = sample["fc_id"]
        expected = sample["expected_verdict"]
        agent_output = sample["agent_output"]

        fc = fc_lookup.get(fc_id)
        if not fc:
            console.print(f"  [yellow]Skip {sample['scenario_id']}: FC {fc_id} not found[/yellow]")
            errors += 1
            continue

        scenario = Scenario(
            id=sample["scenario_id"],
            title=sample["scenario_id"],
            stack="flask",
            task_brief="(calibration sample)",
            expected_check_type="llm_judge",
            expected_outcome="unknown",
        )

        result = check_llm_judge(agent_output, scenario, fc.rule_text, client, fc_id=fc_id)

        if result.verdict == "error":
            errors += 1
            if verbose:
                console.print(f"  [{i}/{len(samples)}] {sample['scenario_id']}: ERROR - {result.evidence}")
            continue

        match = result.verdict == expected
        if match:
            agree += 1
        else:
            disagree += 1

        if verbose or not match:
            status = "[green]AGREE[/green]" if match else "[red]DISAGREE[/red]"
            console.print(
                f"  [{i}/{len(samples)}] {sample['scenario_id']}: "
                f"expected={expected}, judge={result.verdict} {status}"
            )

    total = agree + disagree
    if total == 0:
        console.print("[red]No valid comparisons made[/red]")
        return 0.0

    rate = agree / total
    console.print(f"\n[bold]Calibration results:[/bold]")
    console.print(f"  Agreement: {agree}/{total} ({rate:.0%})")
    console.print(f"  Errors: {errors}")
    console.print(f"  Threshold: {CALIBRATION_THRESHOLD:.0%}")

    if rate >= CALIBRATION_THRESHOLD:
        console.print(f"  [bold green]PASS[/bold green] -- judge is calibrated")
    else:
        console.print(f"  [bold red]FAIL[/bold red] -- judge needs tuning")

    return rate


@click.command()
@click.option("--stage", type=click.Choice(["1", "2", "all"]), default="1",
              help="Stage 1 (deterministic only) is the safe default")
@click.option("--fc", "fc_filter", type=str, default=None,
              help="Run single FC (e.g., fc7)")
@click.option("--runs", type=int, default=3, help="Runs per scenario")
@click.option("--pitfalls", type=click.Path(exists=True),
              default=str(Path.home() / ".claude" / "docs" / "agent-pitfalls.md"),
              help="Path to agent-pitfalls.md")
@click.option("--output-dir", type=click.Path(), default="reports",
              help="Directory for report output")
@click.option("--model-agent", type=str, default="claude-haiku-4-5-20251001",
              help="Pinned model for agent under test")
@click.option("--dry-run", is_flag=True, help="Validate scenarios without API calls")
@click.option("--resume", type=str, default=None,
              help="Resume from run-id (JSONL checkpoint)")
@click.option("--cost-cap", type=float, default=10.0, help="Max USD per run")
@click.option("--calibrate", is_flag=True, help="Run calibration gate only")
@click.option("--verbose", is_flag=True)
def main(
    stage: str,
    fc_filter: str | None,
    runs: int,
    pitfalls: str,
    output_dir: str,
    model_agent: str,
    dry_run: bool,
    resume: str | None,
    cost_cap: float,
    calibrate: bool,
    verbose: bool,
) -> None:
    """Pitfall Rule Eval Harness -- test agent rule clarity."""

    # 0. Calibration gate
    if calibrate:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            console.print("[red]ANTHROPIC_API_KEY not set[/red]")
            sys.exit(1)
        cal_path = Path(__file__).parent / "calibration" / "calibration-set.yaml"
        if not cal_path.exists():
            console.print(f"[red]Calibration set not found: {cal_path}[/red]")
            sys.exit(1)
        rate = run_calibration(Path(pitfalls), cal_path, verbose=verbose)
        sys.exit(0 if rate >= CALIBRATION_THRESHOLD else 1)

    # 1. Parse agent-pitfalls.md
    console.print("[bold]Parsing agent-pitfalls.md...[/bold]")
    pitfalls_path = Path(pitfalls)
    failure_classes = parse_pitfalls(pitfalls_path)
    fc_lookup = {fc.id: fc for fc in failure_classes}
    console.print(f"  Parsed {len(failure_classes)} failure classes")

    # 2. Determine which FCs to run
    if fc_filter:
        target_fcs = {fc_filter}
        if fc_filter not in fc_lookup:
            console.print(f"[red]Unknown FC: {fc_filter}[/red]")
            console.print(f"  Valid IDs: {', '.join(sorted(fc_lookup.keys()))}")
            sys.exit(1)
    elif stage == "1":
        target_fcs = STAGE_1_FCS
    elif stage == "2":
        target_fcs = STAGE_2_FCS
    elif stage == "all":
        target_fcs = STAGE_1_FCS | STAGE_2_FCS
    else:
        target_fcs = STAGE_1_FCS

    # 3. Load and validate scenario files
    scenarios_dir = Path(__file__).parent / "scenarios"
    scenario_files = load_scenarios(scenarios_dir, target_fcs)

    if not scenario_files:
        console.print("[red]No scenario files found for target FCs[/red]")
        sys.exit(1)

    total_scenarios = sum(len(sf.scenarios) for sf in scenario_files.values())
    total_calls = total_scenarios * runs
    console.print(f"  {len(scenario_files)} FCs, {total_scenarios} scenarios, {total_calls} API calls planned")

    # 4. Dry run
    if dry_run:
        est_input = total_calls * 500
        est_output = total_calls * 300
        est_cost = estimate_cost(model_agent, est_input, est_output)
        console.print(f"\n[bold]Dry run summary:[/bold]")
        console.print(f"  FCs: {sorted(scenario_files.keys())}")
        console.print(f"  Scenarios: {total_scenarios}")
        console.print(f"  Runs per scenario: {runs}")
        console.print(f"  Total API calls: {total_calls}")
        console.print(f"  Estimated cost: ${est_cost:.2f}")
        console.print(f"  Cost cap: ${cost_cap:.2f}")
        return

    # 5. Validate API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        console.print("[red]ANTHROPIC_API_KEY not set[/red]")
        sys.exit(1)

    client = anthropic.Anthropic(max_retries=3)

    # 5b. Auto-run calibration gate when stage includes LLM judge (Stage 2)
    if stage in ("2", "all") and target_fcs & STAGE_2_FCS:
        cal_path = Path(__file__).parent / "calibration" / "calibration-set.yaml"
        if cal_path.exists():
            console.print("\n[bold]Auto-running calibration gate (Stage 2 requires judge)...[/bold]")
            rate = run_calibration(Path(pitfalls), cal_path, verbose=verbose)
            if rate < CALIBRATION_THRESHOLD:
                console.print("[red]Calibration failed -- aborting Stage 2 run[/red]")
                sys.exit(1)
        else:
            console.print("[yellow]Warning: calibration set not found, skipping calibration gate[/yellow]")

    # 6. Set up checkpoint
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    run_id = resume or datetime.now().strftime("%Y-%m-%d-%H%M")
    checkpoint_path = out_dir / f"{run_id}.jsonl"
    completed_keys = load_checkpoint(checkpoint_path)

    if completed_keys:
        console.print(f"  Resuming run {run_id}: {len(completed_keys)} results already completed")

    # 7. Run scenarios
    all_results: list[EvalResult] = []
    total_input_tokens = 0
    total_output_tokens = 0
    total_cost = 0.0
    fixtures_dir = scenarios_dir / "fixtures"

    if checkpoint_path.exists():
        with open(checkpoint_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = EvalResult.model_validate_json(line)
                    all_results.append(r)
                    total_input_tokens += r.input_tokens
                    total_output_tokens += r.output_tokens
                    total_cost += estimate_cost(model_agent, r.input_tokens, r.output_tokens)
                    total_cost += estimate_cost(JUDGE_MODEL, r.judge_input_tokens, r.judge_output_tokens)
                except Exception:
                    pass

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        console=console,
    ) as progress:
        task = progress.add_task("Evaluating...", total=total_calls - len(completed_keys))

        for fc_id in sorted(scenario_files.keys()):
            sf = scenario_files[fc_id]
            fc = fc_lookup[fc_id]

            for scenario in sf.scenarios:
                for run_num in range(1, runs + 1):
                    key = result_key(fc_id, scenario.id, scenario.variant, run_num)

                    if key in completed_keys:
                        continue

                    progress.update(task, description=f"{fc_id} / {scenario.id} / run {run_num}")

                    result = run_scenario(
                        scenario=scenario,
                        rule_text=fc.rule_text,
                        fc_id=fc.id,
                        variant=scenario.variant,
                        run_number=run_num,
                        client=client,
                        model=model_agent,
                        fixtures_dir=fixtures_dir if fixtures_dir.exists() else None,
                    )

                    result = evaluate(result, scenario, rule_text=fc.rule_text, client=client)

                    agent_cost = estimate_cost(model_agent, result.input_tokens, result.output_tokens)
                    judge_cost = estimate_cost(JUDGE_MODEL, result.judge_input_tokens, result.judge_output_tokens)
                    call_cost = agent_cost + judge_cost
                    total_input_tokens += result.input_tokens
                    total_output_tokens += result.output_tokens
                    total_cost += call_cost

                    append_checkpoint(checkpoint_path, result)
                    all_results.append(result)

                    progress.advance(task)

                    if total_cost >= cost_cap:
                        console.print(f"\n[red]Cost cap reached: ${total_cost:.4f} >= ${cost_cap:.2f}[/red]")
                        console.print("Producing partial report with completed FCs...")
                        break
                else:
                    continue
                break
            else:
                continue
            break

    # 8. Score
    console.print(f"\n[bold]Scoring {len(all_results)} results...[/bold]")
    fc_scores = score_all(all_results, fc_lookup)

    if not fc_scores:
        console.print("[red]No FCs could be scored (all results errored)[/red]")
        sys.exit(1)

    # 9. Generate report
    report = RunReport(
        timestamp=datetime.now(),
        stage=stage,
        model_agent=model_agent,
        model_judge=None,
        temperature=0.0,
        max_tokens_agent=2048,
        total_cost_usd=total_cost,
        total_input_tokens=total_input_tokens,
        total_output_tokens=total_output_tokens,
        fc_scores=fc_scores,
        calibration_accuracy=None,
    )

    md_path, json_path = write_report(report, out_dir, run_id)

    # 10. Print summary
    console.print(f"\n[bold green]Report written:[/bold green]")
    console.print(f"  Markdown: {md_path}")
    console.print(f"  JSON: {json_path}")
    console.print(f"  Cost: ${total_cost:.4f}")
    console.print(f"  FCs scored: {len(fc_scores)}")

    clear = sum(1 for fc in fc_scores if fc.bucket == "CLEAR")
    ambig = sum(1 for fc in fc_scores if fc.bucket == "AMBIGUOUS")
    broken = sum(1 for fc in fc_scores if fc.bucket == "BROKEN")
    console.print(f"  CLEAR: {clear} | AMBIGUOUS: {ambig} | BROKEN: {broken}")


if __name__ == "__main__":
    main()
