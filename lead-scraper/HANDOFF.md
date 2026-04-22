# Lead Scraper -- Handoff

**Date:** 2026-04-21
**Branch:** `feat/v2-outreach-intelligence` (10 commits ahead of master)
**Tests:** 139/139 passing
**Phase:** Work complete -- ready for review

## Current State

Phase 1 of the outreach intelligence platform is implemented. Full compound cycle through brainstorm (3 revisions + Codex review), plan (2 revisions + Codex review + deepening with 5 research agents), work (8 changes + opener benchmark), ready for review.

## What Works Now

```bash
cd ~/Projects/sandbox/lead-scraper
source .venv/bin/activate

# Import Facebook leads
python run.py import --csv friends.csv

# Classify segments (Claude Haiku 4.5)
python run.py enrich --step segment

# Research hooks (Perplexity Sonar Pro)
python run.py enrich --step hook

# Create and run a campaign
python run.py campaign create "Workshop" --segment connector,writer \
  --var date="April 25" --var seat_count=30 --var format="workshop" --var event_name="AI Workshop"
python run.py campaign assign 1 --min-hook-quality 3
python run.py campaign generate 1

# Review (shows hook_source_url for verification)
python run.py campaign queue 1

# Approve, skip, or mark sent
python run.py campaign approve 1 --lead 42
python run.py campaign skip 1 --lead 43
python run.py campaign sent 1 --lead 42

# Check status
python run.py campaign status 1

# See what needs manual review
python run.py leads held
```

## Next Session: Review

Run `/workflows:review` on the `feat/v2-outreach-intelligence` branch. Key areas to scrutinize:

1. **Sonar Pro citation extraction** -- verify `citations[0]` is the right source URL strategy
2. **Segment classifier prompt** -- check Haiku's Pydantic constrained output actually works on real leads
3. **Campaign assign SQL** -- the segment filter + quality filter + confidence filter + template directory intersection
4. **Opener generation prompt** -- the anti-parrot few-shot format passed benchmark 4/5 but hasn't been tested on real leads
5. **WAL backup fix** -- replaced shutil.copy2 with sqlite3.backup in migrate_db

## Benchmarks Completed

| Benchmark | Model | Result | Date |
|-----------|-------|--------|------|
| Hook research | Sonar Pro | PASS 4/5 with context | 2026-04-21 |
| Hook research | Sonar (standard) | FAIL 1/5 | 2026-04-21 |
| Opener generation v1 | Haiku (naive prompt) | FAIL 0/5 (parrots hook) | 2026-04-21 |
| Opener generation v4 | Haiku (anti-parrot few-shot) | PASS 4/5 | 2026-04-21 |

## Key Files (Phase 1 additions)

| File | What it does |
|------|-------------|
| `campaign.py` | Campaign CRUD, message generation, queue review, approval workflow |
| `schema_campaigns.sql` | 3 new tables: campaigns, campaign_leads, outreach_queue |
| `templates/outreach/*.md` | 4 parameterized segment templates (connector, writer, small_biz, real_estate) |
| `enrich.py` (extended) | +enrich_segment() (Haiku classifier), +enrich_hook() (Sonar Pro) |
| `ingest.py` (extended) | +import_from_csv() with flexible column mapping |
| `models.py` (extended) | +query_held_leads() with labeled hold reasons |
| `config.py` (extended) | +get_perplexity_key() |

## Docs

- **Brainstorm:** `docs/brainstorms/2026-04-21-lead-scraper-v2-outreach-platform-brainstorm.md`
- **Plan:** `docs/plans/2026-04-21-feat-lead-scraper-v2-phase1-outreach-intelligence-plan.md`
- **Research:** `docs/research/outreach-strategy/` (segment analysis, enrichment principles, template effectiveness)
- **Prior solution:** `docs/solutions/2026-04-19-contact-enrichment-5-step-pipeline.md`

## Phase 2 (deferred)

- Follow-up sequencing (multi-touch campaigns)
- Network graph scoring (mutual friends + follower count)
- Conversions table (outcome tracking: replied, warm, declined)
- Enhanced Flask UI (campaign dashboard, lead detail, conversion charts)
- Multi-channel support (Instagram DM, email)
- Phone field in CSV import (extend ingest_leads INSERT)

## Feed-Forward

- **Hardest decision:** Opener generation prompt. Naive prompts score 0/5 (Haiku parrots hooks). INPUT/OUTPUT few-shot format with explicit "NEVER copy" rule scores 4/5. The format matters more than the instructions.
- **Rejected alternatives:** Standard Sonar (1/5 vs Sonar Pro 4/5), hook_type column (derive from hook_quality), conversions table in Phase 1 (no way to record outcomes yet), Jinja2 templates (YAGNI).
- **Least confident:** Real-world performance on leads Haiku hasn't seen in few-shot examples. The benchmark used 5 leads from the Apr 20 batch. First real campaign will be the true test.
