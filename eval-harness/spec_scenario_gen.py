"""Map extracted Claims to eval harness Scenario objects.

Each Claim becomes one Scenario with variant="with_rule" so that
build_prompt() injects the claim text as the rule. No synthetic
FailureClass objects needed -- the runner accepts rule_text directly.
"""

from __future__ import annotations

from models import Claim, Scenario


# Allowed Scenario.stack literal values (must match models.Scenario.stack)
_ALLOWED_STACKS = {"flask", "express", "nextjs", "supabase", "sqlite", "generic"}


def detect_stack(spec_text: str) -> str:
    """Detect the spec's primary tech stack to prime the scenario agent.

    The scenario agent is system-prompted "You are a senior {stack} developer"
    (runner.build_prompt). Without a real stack it defaults to "generic" and
    free-associates into the wrong language (Go/TypeScript/Supabase for a
    Flask spec), making every generated scenario non-credible. Detect the
    stack from the spec so the agent writes code in the right language.

    Returns one of the Scenario.stack literal values. Falls back to "generic"
    only when no known stack keyword is present.
    """
    t = spec_text.lower()
    # Order matters: most specific framework wins.
    if "next.js" in t or "nextjs" in t:
        return "nextjs"
    if "express" in t and ("node" in t or "better-sqlite3" in t or "javascript" in t):
        return "express"
    if "flask" in t:
        return "flask"
    if "supabase" in t:
        return "supabase"
    if "sqlite" in t:
        return "sqlite"
    return "generic"


def claims_to_scenarios(
    claims: list[Claim],
    run_id: str,
    stack: str = "generic",
) -> list[tuple[Scenario, str]]:
    """Map extracted claims to eval harness Scenario objects.

    Returns list of (Scenario, rule_text) tuples.
    rule_text is passed directly to build_prompt() -- no synthetic FC needed.

    Each claim becomes one Scenario with:
    - id: f"spec-{run_id[:8]}-{claim.id}"
    - variant: "with_rule" (MUST be with_rule for build_prompt to inject rule_text)
    - pair_group: None
    - stack: the detected spec stack (so the agent writes the right language)
    - expected_outcome: "pass"
    - expected_check_type: "deterministic" ONLY for table claims with a
      presence pattern (a required code identifier tied to a direct
      "write function X" task -- reliable). Everything else -- absence-mode
      checks and ALL prose-derived checks -- is routed to the context-aware
      LLM judge. Naive substring grep otherwise produces false positives
      (the no-FTS5 'match' rule hits the spec's required `re.match`; a negative
      constraint's own text is flagged as a "violation") and false negatives
      (whole-codebase patterns absent from a single per-claim code slice).
    """
    if stack not in _ALLOWED_STACKS:
        stack = "generic"

    results: list[tuple[Scenario, str]] = []

    for claim in claims:
        scenario_id = f"spec-{run_id[:8]}-{claim.id}"

        # Reliable deterministic check ONLY for table-extracted presence
        # patterns. Absence-mode and all prose claims -> LLM judge.
        det = claim.deterministic_check
        use_deterministic = (
            det is not None
            and det.mode == "presence"
            and claim.source == "table"
        )
        if use_deterministic:
            check_type = "deterministic"
            det_pattern = det.pattern
            det_mode = det.mode
        else:
            check_type = "llm_judge"
            det_pattern = None
            det_mode = None

        scenario = Scenario(
            id=scenario_id,
            title=claim.text[:100],
            stack=stack,
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
