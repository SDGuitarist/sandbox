"""Parse agent-pitfalls.md into structured FailureClass objects."""

from __future__ import annotations

import re
from pathlib import Path

from models import FailureClass

# Hardcoded tier lookup from brainstorm classification (23 Tier 1a + 2 Tier 1b + 16 Tier 2 + 4 Tier 3 + 2 Tier 4 = 47)
TIER_MAP: dict[str, str] = {
    # Tier 1a: Rule-clarity testing (23 FCs)
    "fc2": "1a", "fc4": "1a-mixed", "fc7": "1a", "fc9": "1a", "fc10": "1a",
    "fc14": "1a", "fc15": "1a", "fc16": "1a", "fc17": "1a", "fc19": "1a",
    "fc20": "1a", "fc23": "1a", "fc24": "1a", "fc25": "1a", "fc26": "1a",
    "fc27": "1a", "fc28": "1a", "fc33": "1a", "fc36": "1a", "fc39": "1a",
    "fc41": "1a", "fc46": "1a", "fc47": "1a",
    # Tier 1b: Spec-omission dominated (2 FCs)
    "fc1": "1b", "fc35": "1b",
    # Tier 2: Multi-file/multi-agent (16 FCs)
    "fc3": "2", "fc5": "2", "fc6": "2", "fc18": "2", "fc21": "2",
    "fc22": "2", "fc29": "2", "fc30": "2", "fc31": "2", "fc32": "2",
    "fc38": "2", "fc40": "2", "fc42": "2", "fc43": "2", "fc44": "2",
    "fc45": "2",
    # Tier 3: Requires real execution or tool-use eval (4 FCs)
    "fc8": "3", "fc13": "3", "fc34": "3", "fc37": "3",
    # Tier 4: Orchestrator/process-level (2 FCs)
    "fc11": "4", "fc12": "4",
}

# Heading pattern: ## Failure Class 7: Route Prefix Doubling {#fc7-route-prefix-doubling}
HEADING_RE = re.compile(
    r"^## Failure Class (\d+):\s*(.+?)\s*\{#(fc\d+-[\w-]+)\}\s*$"
)

# Rule blockquote: lines starting with "> " after **Agent rule:** or **Orchestrator rule:**
RULE_LABEL_RE = re.compile(r"^\*\*(Agent|Orchestrator) rule:\*\*\s*$")


def parse_pitfalls(path: Path) -> list[FailureClass]:
    """Parse agent-pitfalls.md and return all 47 FailureClass objects."""
    text = path.read_text()
    lines = text.splitlines()

    failure_classes: dict[str, FailureClass] = {}
    i = 0

    while i < len(lines):
        match = HEADING_RE.match(lines[i])
        if not match:
            i += 1
            continue

        fc_num = int(match.group(1))
        fc_name = match.group(2).strip()
        fc_anchor = match.group(3)
        fc_id = f"fc{fc_num}"
        fc_slug = fc_anchor[len(fc_id) + 1:]  # strip "fcN-" prefix from anchor

        # Find the rule blockquote within this FC section
        rule_text = ""
        j = i + 1
        while j < len(lines):
            # Stop at next heading or end of file
            if lines[j].startswith("## "):
                break

            # Look for **Agent rule:** or **Orchestrator rule:**
            if RULE_LABEL_RE.match(lines[j].strip()):
                # Collect blockquote lines
                rule_lines = []
                k = j + 1
                while k < len(lines) and lines[k].startswith("> "):
                    rule_lines.append(lines[k][2:])  # strip "> " prefix
                    k += 1
                rule_text = "\n".join(rule_lines).strip()
                break
            j += 1

        tier = TIER_MAP.get(fc_id, "2")  # default to Tier 2 if unknown

        failure_classes[fc_id] = FailureClass(
            id=fc_id,
            slug=fc_slug,
            name=fc_name,
            rule_text=rule_text,
            tier=tier,
        )

        i += 1

    # Validate we found all 47
    if len(failure_classes) != 47:
        found = sorted(failure_classes.keys(), key=lambda x: int(x[2:]))
        raise ValueError(
            f"Expected 47 failure classes, found {len(failure_classes)}: {found}"
        )

    # Validate no empty rule_text
    for fc in failure_classes.values():
        if not fc.rule_text:
            raise ValueError(f"{fc.id} ({fc.name}) has empty rule_text")

    return sorted(failure_classes.values(), key=lambda fc: int(fc.id[2:]))


if __name__ == "__main__":
    default_path = Path.home() / ".claude" / "docs" / "agent-pitfalls.md"
    fcs = parse_pitfalls(default_path)
    print(f"Parsed {len(fcs)} failure classes:")
    for fc in fcs:
        print(f"  {fc.id} ({fc.tier}): {fc.name}")
        print(f"    Rule: {fc.rule_text[:80]}...")
