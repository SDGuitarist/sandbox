---
status: pending
priority: p2
issue_id: "013"
tags: [code-review, architecture, deployment]
---

# Make VENUE_SCRAPER_DIR Configurable via Environment Variable

## Problem Statement
`VENUE_SCRAPER_DIR = Path(__file__).parent.parent / "venue-scraper"` hardcodes a sibling directory assumption. Breaks if either project is moved, reorganized, or run in CI.

## Findings
- **Source:** Architecture Strategist
- **File:** `enrich.py` line 21

## Proposed Solution
```python
VENUE_SCRAPER_DIR = Path(os.environ.get(
    "VENUE_SCRAPER_DIR",
    str(Path(__file__).parent.parent / "venue-scraper")
))
```
Preserves current default. Add to `.env.example`.

## Acceptance Criteria
- [ ] Works with default (no env var set)
- [ ] Works with custom `VENUE_SCRAPER_DIR` env var
- [ ] Documented in `.env.example`
