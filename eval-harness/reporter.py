"""Generate markdown and JSON reports from eval results."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from models import FCScore, RunReport


def generate_markdown(report: RunReport) -> str:
    """Generate the markdown report string."""
    lines = []

    # Header with mandatory caveat
    lines.append("# Pitfall Rule Eval Report")
    lines.append(f"> {report.report_caveat}")
    lines.append("")

    # Run metadata
    lines.append("## Run Metadata")
    lines.append(f"- **Date:** {report.timestamp.strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"- **Stage:** {report.stage}")
    lines.append(f"- **Agent model:** {report.model_agent}")
    if report.model_judge:
        lines.append(f"- **Judge model:** {report.model_judge}")
    lines.append(f"- **Temperature:** {report.temperature}")
    lines.append(f"- **Total cost:** ${report.total_cost_usd:.4f}")
    lines.append(f"- **Total tokens:** {report.total_input_tokens:,} in / {report.total_output_tokens:,} out")
    if report.calibration_accuracy is not None:
        lines.append(f"- **Calibration accuracy:** {report.calibration_accuracy:.0%}")
    lines.append("")

    # Results summary table
    lines.append("## Results Summary")
    lines.append("")
    lines.append("| FC | Type | With Rule | 95% CI | Without Rule | Delta | Bucket | Promotable |")
    lines.append("|----|------|-----------|--------|-------------|-------|--------|------------|")

    for fc in report.fc_scores:
        with_pct = f"{fc.pass_rate_with_rule:.0%}"
        ci = f"[{fc.ci_lower:.0%}-{fc.ci_upper:.0%}]"
        without_pct = f"{fc.pass_rate_without_rule:.0%}" if fc.pass_rate_without_rule is not None else "--"
        delta_str = f"{fc.delta:+.0%}" if fc.delta is not None else "--"
        promo = ", ".join(fc.promotable_cases) if fc.promotable_cases else "--"
        lines.append(f"| {fc.fc_id.upper()} | {fc.tier} | {with_pct} | {ci} | {without_pct} | {delta_str} | {fc.bucket} | {promo} |")

    lines.append("")

    # Injection priority (sorted by delta descending)
    scored_with_delta = [fc for fc in report.fc_scores if fc.delta is not None]
    if scored_with_delta:
        lines.append("## Injection Priority (by delta, descending)")
        lines.append("")
        by_delta = sorted(scored_with_delta, key=lambda fc: fc.delta, reverse=True)
        for i, fc in enumerate(by_delta, 1):
            label = "load-bearing" if fc.delta > 0.20 else "moderate" if fc.delta > 0.05 else "low impact"
            lines.append(f"{i}. **{fc.fc_id.upper()}** delta={fc.delta:+.0%} ({label})")
        lines.append("")

    # Promotable cases
    all_promotable = [
        (fc.fc_id, case)
        for fc in report.fc_scores
        for case in fc.promotable_cases
    ]
    if all_promotable:
        lines.append("## Promotable Cases")
        lines.append("")
        for fc_id, case_id in all_promotable:
            lines.append(f"- **{fc_id.upper()}**: `{case_id}` -- reproducible failure, candidate for regression suite")
        lines.append("")

    # Summary stats
    lines.append("## Summary")
    lines.append("")
    clear = sum(1 for fc in report.fc_scores if fc.bucket == "CLEAR")
    ambig = sum(1 for fc in report.fc_scores if fc.bucket == "AMBIGUOUS")
    broken = sum(1 for fc in report.fc_scores if fc.bucket == "BROKEN")
    lines.append(f"- **CLEAR:** {clear} FCs")
    lines.append(f"- **AMBIGUOUS:** {ambig} FCs")
    lines.append(f"- **BROKEN:** {broken} FCs")
    lines.append(f"- **Total FCs scored:** {len(report.fc_scores)}")
    lines.append("")

    return "\n".join(lines)


def write_report(
    report: RunReport,
    output_dir: Path,
    run_id: str,
) -> tuple[Path, Path]:
    """Write markdown and JSON reports to the output directory.

    Returns (markdown_path, json_path).
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    md_path = output_dir / f"{run_id}.md"
    json_path = output_dir / f"{run_id}.json"

    # Markdown
    md_content = generate_markdown(report)
    md_path.write_text(md_content)

    # JSON
    json_content = report.model_dump_json(indent=2)
    json_path.write_text(json_content)

    return md_path, json_path
