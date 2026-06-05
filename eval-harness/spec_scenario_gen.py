"""Map extracted Claims to eval harness Scenario objects.

Each Claim becomes one Scenario with variant="with_rule" so that
build_prompt() injects the claim text as the rule. No synthetic
FailureClass objects needed -- the runner accepts rule_text directly.
"""

from __future__ import annotations

from models import Claim, Scenario


def claims_to_scenarios(
    claims: list[Claim],
    run_id: str,
) -> list[tuple[Scenario, str]]:
    """Map extracted claims to eval harness Scenario objects.

    Returns list of (Scenario, rule_text) tuples.
    rule_text is passed directly to build_prompt() -- no synthetic FC needed.

    Each claim becomes one Scenario with:
    - id: f"spec-{run_id[:8]}-{claim.id}"
    - variant: "with_rule" (MUST be with_rule for build_prompt to inject rule_text)
    - pair_group: None
    - stack: "generic"
    - expected_outcome: "pass"
    - expected_check_type: "deterministic" if claim has pattern, else "llm_judge"
    """
    results: list[tuple[Scenario, str]] = []

    for claim in claims:
        scenario_id = f"spec-{run_id[:8]}-{claim.id}"

        # Determine check type from claim's deterministic_check
        if claim.deterministic_check:
            check_type = "deterministic"
            det_pattern = claim.deterministic_check.pattern
            det_mode = claim.deterministic_check.mode
        else:
            check_type = "llm_judge"
            det_pattern = None
            det_mode = None

        scenario = Scenario(
            id=scenario_id,
            title=claim.text[:100],
            stack="generic",
            task_brief=claim.task_brief,
            inputs={},
            context_files=[],
            expected_check_type=check_type,
            expected_outcome="pass",
            deterministic_pattern=det_pattern,
            deterministic_mode=det_mode,
            tags=[claim.source],
            pair_group=None,
            variant="with_rule",
        )

        # rule_text is what build_prompt() injects when variant="with_rule"
        rule_text = f"Spec instruction: {claim.text}"

        results.append((scenario, rule_text))

    return results
