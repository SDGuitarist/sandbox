Read ~/Projects/sandbox/lead-scraper/docs/handoff-lead-recycling.md.
  Implement all three changes (dedup filter fix, auto-recycle skipped hooks,
  skip counter). Relevant files: campaign.py, db.py, tests/test_campaign.py. Run
   tests after each change.


# Handoff: Lead Recycling Pipeline

## Context
Read `docs/plans/` for any existing plans first. The lead-scraper at `~/Projects/sandbox/lead-scraper/` just got a major pipeline overhaul (commit `4147394`). Six quality gates now block bad leads before they reach send lists. But skipped leads are permanently dead — once skipped in any campaign, the dedup filter blocks them from all future campaigns. This wastes good leads that just had bad hooks.

## What to implement (three changes)

### 1. Fix the dedup filter in `campaign.py` `assign_leads()`
**Current (line ~125):** `AND id NOT IN (SELECT lead_id FROM campaign_leads)`
**Problem:** Blocks ALL leads in any campaign, including skipped ones.
**Fix:** Only exclude leads that were SENT or are currently DRAFT:
```sql
AND id NOT IN (
  SELECT cl.lead_id FROM campaign_leads cl
  JOIN outreach_queue oq ON cl.lead_id = oq.lead_id AND cl.campaign_id = oq.campaign_id
  WHERE oq.status IN ('sent', 'draft', 'approved', 'replied', 'booked')
)
```
Skipped, declined, and no-response leads become eligible for future campaigns.

### 2. Auto-recycle skipped hooks
When a lead is marked "skipped" in `campaign.py` `skip_message()`, clear its hook fields so it re-enters the enrichment pool on the next `enrich --step hook` run:
```python
# After marking status = 'skipped' in outreach_queue:
conn.execute(
    "UPDATE leads SET hook_text = NULL, hook_source_url = NULL, "
    "hook_quality = NULL, hook_verified = 0 WHERE id = ?",
    (lead_id,)
)
```
This gives the lead a fresh hook next time enrichment runs.

### 3. Add skip counter to prevent infinite recycling
**New column:** `skip_count INTEGER DEFAULT 0` in `leads` table (add to `db.py` `migrate_db()`)
**On skip:** Increment: `UPDATE leads SET skip_count = skip_count + 1 WHERE id = ?`
**At assignment:** Add filter: `AND skip_count < 3` — after 3 skips, deprioritize (don't assign automatically, but keep in DB for manual review).

## Key files
- `campaign.py` — `assign_leads()` (dedup filter ~line 125), `skip_message()` (hook recycling)
- `db.py` — `migrate_db()` (add skip_count column)
- `enrich.py` — no changes needed, existing `enrich_hook()` already picks up leads with NULL hooks
- `tests/test_campaign.py` — update dedup test, add skip-recycle test, add skip-count test

## What must not change
- The six quality gates (hook_verified, is_sendable, screening, consistency)
- Existing sent/approved/booked lead tracking
- DB safety rules: one process at a time, backup after every op

## Acceptance tests
- WHEN a lead is skipped in campaign 7 THE SYSTEM SHALL clear its hook fields
- WHEN a lead with skip_count < 3 gets a new hook THE SYSTEM SHALL be assignable to campaign 13
- WHEN a lead has skip_count >= 3 THE SYSTEM SHALL not be auto-assigned to campaigns
- WHEN a lead was sent in campaign 7 THE SYSTEM SHALL not be assignable to campaign 13
- WHEN enrichment runs THE SYSTEM SHALL pick up recycled leads (hook_text IS NULL)

## Verification
```bash
.venv/bin/python3 -m pytest tests/ -v
python3 run.py campaign status 7  # existing data intact
sqlite3 leads.db "SELECT skip_count, COUNT(*) FROM leads GROUP BY skip_count"
```

## Current DB state
- 1,211 total leads
- 501 fully gated (hook_verified=1, is_sendable=1)
- 63 DMs sent across campaigns 1-7
- 144 skipped (these should become recyclable after this change)
- Wave 2 campaigns 8-12 (connector, musician, creative, writer, small_biz) created but not yet generated

## Feed-Forward
- **Hardest decision:** Whether to clear hooks on skip or just mark for re-enrichment. Clearing is simpler and lets the improved Tier A pipeline take another shot.
- **Rejected alternative:** Manual triage of all skipped leads. Too much user time for diminishing returns when automated re-enrichment is available.
- **Least confident:** The skip_count threshold of 3. Might need tuning based on real recycling data.
