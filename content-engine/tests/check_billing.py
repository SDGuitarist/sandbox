"""Billing-invariant verification (plan §Acceptance Tests).

The #1 rule: copy-gen runs ONLY on Claude Code (Max). Nothing in the skill or the
content-engine scripts may EXECUTE the credit-billed content_pipeline.py, read/use
ANTHROPIC_API_KEY, or call api.anthropic.com. But the skill legitimately MENTIONS those
forbidden names in prose to explain the ban, so a plain `grep` false-positives on them.

This checker inspects EXECUTABLE command patterns and ignores explanatory mentions. It
flags a line only when a forbidden name appears in a real usage context:

  1. content_pipeline.py run by an interpreter  (python/bash/sh/source/./ /uv/poetry/exec)
  2. ANTHROPIC_API_KEY used as a variable/env    ($VAR, ${VAR, export, =, os.environ/getenv)
  3. api.anthropic.com called as a URL/endpoint   (http(s)://… or …/path)

Bare mentions like "never execute content_pipeline.py" or "do not read ANTHROPIC_API_KEY"
are SAFE and do not fail the check.

Scope: the content-batch SKILL.md + content-engine scripts/*.sh, *.plist, and *.py.
It never scans content_pipeline.py itself (that is the excluded voice-spec source, which
legitimately uses the raw API).

Usage:
  lead-scraper/.venv/bin/python content-engine/tests/check_billing.py
Exit 0 = clean (PASS), 1 = a forbidden executable path was found (FAIL).
"""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]          # sandbox/
ENGINE = REPO / "content-engine"
SKILL = REPO / ".claude" / "skills" / "content-batch" / "SKILL.md"

# Forbidden EXECUTABLE patterns (usage context, not bare prose mention).
FORBIDDEN = [
    ("executes content_pipeline.py",
     re.compile(r"\b(python[0-9.]*|python3|bash|sh|zsh|source|\./|uv|poetry|exec|runpy)\b[^\n]*content_pipeline")),
    ("uses ANTHROPIC_API_KEY as a variable/env",
     re.compile(r"\$\{?ANTHROPIC_API_KEY|export\s+ANTHROPIC_API_KEY|ANTHROPIC_API_KEY\s*=|(?:os\.)?environ\[[^\]]*ANTHROPIC_API_KEY|getenv\([^)]*ANTHROPIC_API_KEY")),
    ("calls api.anthropic.com endpoint",
     re.compile(r"https?://api\.anthropic\.com|api\.anthropic\.com/")),
]


def scan(path: Path) -> list[tuple[int, str, str]]:
    hits = []
    for n, line in enumerate(path.read_text().splitlines(), 1):
        for label, rx in FORBIDDEN:
            if rx.search(line):
                hits.append((n, label, line.strip()))
    return hits


def main() -> int:
    targets = []
    if SKILL.exists():
        targets.append(SKILL)
    scripts = ENGINE / "scripts"
    targets += sorted(scripts.glob("*.sh")) + sorted(scripts.glob("*.plist"))
    # Exclude this checker itself — it holds the forbidden patterns as regex data.
    targets += [p for p in sorted(ENGINE.rglob("*.py")) if p.name != "check_billing.py"]

    failed = False
    for t in targets:
        hits = scan(t)
        rel = t.relative_to(REPO)
        if hits:
            failed = True
            for n, label, line in hits:
                print(f"FAIL {rel}:{n} — {label}: {line}")
        else:
            print(f"ok   {rel}")

    print("BILLING GUARD:", "FAIL — forbidden executable path found" if failed
          else "PASS — no credit-billed path (explanatory mentions ignored)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
