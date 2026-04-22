---
title: "Lead Scraper v2 Phase 1: Core Intelligence Pipeline"
type: feat
status: active
date: 2026-04-21
revision: 2 (post-Codex plan review, 8 findings addressed)
origin: docs/brainstorms/2026-04-21-lead-scraper-v2-outreach-platform-brainstorm.md
benchmark:
  model: sonar-pro
  result: "PASS — 4/5 Tier 1-3 hooks with context-enriched prompt"
  date: 2026-04-21
feed_forward:
  risk: "Opener generation quality is unproven. Sonar Pro benchmark tested hook research, not opener writing. Run 5-lead opener benchmark before full batch generation."
  verify_first: true
---

# Lead Scraper v2 Phase 1: Core Intelligence Pipeline

## Overview

Transform the lead-scraper from a contact-info finder into an outreach intelligence platform. Phase 1 adds: segment classification (Claude Haiku), hook research (Perplexity Sonar Pro), parameterized message generation, an outreach queue with human-in-the-loop approval, campaign management, and CSV import for Facebook-sourced leads. All CLI-operated. Facebook DM output only.

**Origin:** See [brainstorm](../brainstorms/2026-04-21-lead-scraper-v2-outreach-platform-brainstorm.md) for all decisions, decision rules, template evidence levels, and benchmark results.

**Phase 1 workflow:** scrape/import leads -> classify segment -> research hook -> create campaign -> assign leads -> generate messages -> review queue (verify URLs) -> approve/skip -> mark sent after manual DM -> check status.

**Phase 1 stops at:** Manual Facebook DM send. No automated sending. No outcome tracking (replied/warm/declined). No follow-up sequences. Those are Phase 2.

## What Exactly Is Changing

Eight changes, ordered by dependency:

### Change 1: Schema Migration (new columns + new tables)

**What:** Add 5 columns to `leads` table, create 3 new tables, and fix the existing WAL-unsafe backup in `migrate_db`.

**New columns on `leads` (via `migrate_db` pattern in `db.py:38-45`):**

```python
new_columns = [
    # ... existing columns ...
    ("segment", "TEXT"),
    ("segment_confidence", "REAL"),
    ("hook_text", "TEXT"),
    ("hook_source_url", "TEXT"),
    ("hook_quality", "INTEGER"),  # 1-5 tier (1=best). 0=no hook found.
]
```

Derive hook type label from `hook_quality` at display time -- no `hook_type` column:
```python
TIER_LABELS = {1: "content_created", 2: "opinion", 3: "event", 4: "award", 5: "transaction", 0: "no_hook"}
```

**New tables (`schema_campaigns.sql`, loaded by second `executescript()` in existing `init_db()`):**

```sql
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS campaigns (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    name              TEXT NOT NULL,
    target_date       TEXT,
    segment_filter    TEXT,
    template_vars_json TEXT CHECK(json_valid(template_vars_json) OR template_vars_json IS NULL),
    status            TEXT NOT NULL DEFAULT 'draft'
                      CHECK(status IN ('draft', 'active', 'complete')),
    created_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now'))
);

CREATE TABLE IF NOT EXISTS campaign_leads (
    campaign_id     INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    lead_id         INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    assigned_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now')),
    PRIMARY KEY (campaign_id, lead_id)
);

CREATE TABLE IF NOT EXISTS outreach_queue (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id         INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    campaign_id     INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    opener_text     TEXT,
    template_text   TEXT,
    full_message    TEXT,
    status          TEXT NOT NULL DEFAULT 'draft'
                    CHECK(status IN ('draft', 'approved', 'sent', 'skipped')),
    generated_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now')),
    approved_at     TEXT,
    sent_at         TEXT,
    UNIQUE(lead_id, campaign_id)
);
```

**Not in Phase 1 schema:** `conversions` table (no outcome tracking), `touch_number` (no follow-up sequences), `channel` (Facebook DM only), `hook_type` (derived from hook_quality), `next_followup`.

**WAL-safe backup fix:** Replace `shutil.copy2()` in `migrate_db()` with `sqlite3.backup()`:

```python
# db.py -- replace shutil.copy2(db_path, backup) with:
import sqlite3 as _sqlite3
source = _sqlite3.connect(str(db_path))
dest = _sqlite3.connect(str(backup))
source.backup(dest)
dest.close()
source.close()
```

This prevents corrupted backups when WAL has uncommitted data. ~5 lines, fixes an existing bug.

**Files to change:**
- `db.py` -- add 5 entries to `new_columns`, add second `executescript()` in `init_db()`, fix `migrate_db()` backup
- `schema_campaigns.sql` -- new file

**Risk:** Low (not zero -- the WAL backup fix touches existing code). Migration is idempotent. Test backup roundtrip in test_migration.py.

### Change 2: Segment Classifier (`enrich --step segment`)

**What:** LLM classifier using Claude Haiku 4.5 that reads bio + activity and outputs a segment label + confidence score.

**Function signature:** `def enrich_segment(*, db_path: Path = DB_PATH) -> EnrichmentResult`

**Selection criteria:** `SELECT id, name, bio, profile_bio, activity, source FROM leads WHERE segment IS NULL`

**Implementation: `client.messages.parse()` with Pydantic for guaranteed valid output:**

```python
from pydantic import BaseModel, Field
from typing import Literal

class LeadClassification(BaseModel):
    segment: Literal[
        "real_estate", "writer", "wellness", "musician",
        "connector", "small_biz", "creative", "nonprofit", "tech", "other"
    ]
    confidence: float = Field(ge=0.0, le=1.0)
```

With `messages.parse()` + `Literal[...]`, constrained decoding guarantees:
- Valid JSON (always)
- Segment value in the 10-option enum (always)
- Float confidence value (always)

**Therefore, the only real failure modes are:**
- API error (RateLimitError, APITimeoutError, APIConnectionError) -> return `("other", 0.0)`
- Model refusal (stop_reason == "refusal") -> return `("other", 0.0)`
- Pydantic validation error (confidence outside 0-1 after constrained decoding -- extremely rare) -> return `("other", 0.0)`

**Pre-filter:** Skip API call for bios under 3 chars. Return `("other", 0.1)` locally.

**Prompt caching:** Wrap system prompt with `cache_control: {"type": "ephemeral"}` for 90% cheaper system prompt tokens.

**Persist:** `_persist_segment(lead_id, segment, confidence, db_path)` using direct SET. Comment in code: "No COALESCE -- selection query guarantees segment IS NULL."

**Cost:** ~$0.001/lead with prompt caching. Batch of 200 = ~$0.10.

**Files to change:**
- `enrich.py` -- add `enrich_segment()`, `_get_leads_for_segment()`, `_persist_segment()`, Pydantic model
- `run.py` -- add `"segment"` to `steps` dict and `choices` list
- `requirements.txt` -- add `anthropic>=0.25` and `pydantic>=2.0`

### Change 3: Hook Research (`enrich --step hook`)

**What:** Perplexity Sonar Pro API call per lead to find a Tier 1-3 outreach hook.

**Function signature:** `def enrich_hook(*, db_path: Path = DB_PATH) -> EnrichmentResult`

**Selection criteria:** `SELECT ... FROM leads WHERE hook_text IS NULL AND segment IS NOT NULL`

**CRITICAL: Extract source URLs from `citations` response field, NOT from model JSON output.** Sonar Pro hallucates URLs when forced to embed them in structured output. The `citations` array contains real URLs from Perplexity's search engine.

**Structured output via `response_format` -- request `hook_text` + `source_description` + `tier`, NOT `source_url`:**

```python
"response_format": {
    "type": "json_schema",
    "json_schema": {
        "schema": {
            "type": "object",
            "properties": {
                "hook_text": {"type": "string"},
                "source_description": {"type": "string"},
                "tier": {"type": "integer"}
            },
            "required": ["hook_text", "tier"]
        }
    }
}
# After response:
citations = data.get("citations", [])
source_url = citations[0] if citations else None  # Real URL from Perplexity's search
```

**Prompt must include bio + activity + location from database (name-only prompts fail benchmark).**

**Decision rules:** Tier 1-3 -> eligible for generation. Tier 4-5 -> held. No hook -> held (hook_quality=0). Parse failure -> skip, no crash.

**Persist:** `_persist_hook(lead_id, hook_text, hook_source_url, hook_quality, db_path)` using direct SET.

**Cost:** ~$0.02-0.03/lead (tokens + search fee). Batch of 200 = ~$4-6.

**Rate limiting:** `time.sleep(1.2)` between calls (50 req/min limit). Exponential backoff + jitter on 429. `timeout=60` (Sonar Pro does real-time web search).

**Files to change:**
- `enrich.py` -- add `enrich_hook()`, `_get_leads_for_hook()`, `_persist_hook()`
- `run.py` -- add `"hook"` to `steps` dict and `choices` list
- `config.py` -- add `get_perplexity_key()` (same pattern as `get_apify_token()`)

### Change 4: Template Files

**What:** Create 4 parameterized markdown template files for supported segments.

**Files to create:**
```
templates/outreach/connector.md
templates/outreach/writer.md
templates/outreach/small_biz.md
templates/outreach/real_estate.md
```

Only segments with auto-generation support. Wellness, musician, creative, nonprofit, tech, other are held for manual review -- no dead template files.

**Template format:** YAML frontmatter + body with `{{var}}` placeholders. Variables: `{{event_name}}`, `{{date}}`, `{{seat_count}}`, `{{format}}`.

**Template discovery uses repo-relative path, not CWD:**
```python
TEMPLATES_DIR = Path(__file__).parent / "templates" / "outreach"
available_segments = [p.stem for p in TEMPLATES_DIR.glob("*.md")]
```

### Change 5: Campaign Management (`run.py campaign`)

**What:** New `campaign` subcommand with nested actions: `create`, `assign`, `generate`, `queue`, `approve`, `skip`, `sent`, `status`.

**New file: `campaign.py`** -- owns all writes to `campaigns`, `campaign_leads`, `outreach_queue` tables.

**Functions:**

1. **`create_campaign(name, segment_filter, template_vars, target_date, db_path)`** -- INSERT into campaigns, return campaign_id. Parse `--var key=value` pairs into JSON dict.

2. **`assign_leads(campaign_id, min_hook_quality, db_path)`** -- Derive available segments from template directory: `available = [p.stem for p in TEMPLATES_DIR.glob("*.md")]`. SELECT leads matching campaign's segment_filter WHERE hook_quality <= min_hook_quality AND hook_quality > 0 AND segment_confidence >= 0.7 AND segment IN (available). `INSERT INTO campaign_leads ... ON CONFLICT(campaign_id, lead_id) DO NOTHING`. Print count assigned.

3. **`generate_messages(campaign_id, db_path)`** -- For each campaign_lead without an outreach_queue row:
   - Read lead's hook_text, hook_source_url, segment, name
   - Read template from `TEMPLATES_DIR / f"{segment}.md"` (repo-relative)
   - Read campaign's template_vars_json
   - **Validate:** all `{{variables}}` in template have values. Error with clear message if any missing.
   - Fill template variables
   - Call Claude Haiku to generate opener from hook_text + lead name
   - `INSERT INTO outreach_queue ... ON CONFLICT(lead_id, campaign_id) DO NOTHING`

4. **`show_queue(campaign_id, db_path)`** -- SELECT from outreach_queue JOIN leads WHERE status='draft'. Print each message with: **lead name, hook text, hook_source_url (for verification), full message preview.** The `hook_source_url` is the human's verification checkpoint -- they click it before approving.

5. **`approve_message(campaign_id, lead_id, db_path)`** -- Atomic claim: `UPDATE outreach_queue SET status='approved', approved_at=now WHERE campaign_id=? AND lead_id=? AND status='draft'`. Check rowcount.

6. **`skip_message(campaign_id, lead_id, db_path)`** -- `UPDATE outreach_queue SET status='skipped' WHERE campaign_id=? AND lead_id=? AND status='draft'`. Check rowcount.

7. **`mark_sent(campaign_id, lead_id, db_path)`** -- `UPDATE outreach_queue SET status='sent', sent_at=now WHERE campaign_id=? AND lead_id=? AND status='approved'`. Check rowcount. This is called after the human manually sends the DM.

8. **`show_status(campaign_id, db_path)`** -- Print:
   - Campaign name, target date, segment filter
   - Lead counts: assigned (campaign_leads), with messages (outreach_queue)
   - Delivery metrics: COUNT by outreach_queue.status (draft, approved, sent, skipped)

**Files to change:** `campaign.py` (new), `run.py` (add `cmd_campaign` and subparsers)

### Change 6: Held Leads Command (`run.py leads held`)

**What:** A query command that surfaces leads held from auto-generation, with the reason.

**CLI:** `python run.py leads held`

**Query (computed, no new table):**

```sql
-- Low confidence classification
SELECT id, name, segment, segment_confidence, 'low_confidence' as hold_reason
FROM leads WHERE segment_confidence IS NOT NULL AND segment_confidence < 0.7

UNION ALL

-- No hook found
SELECT id, name, segment, segment_confidence, 'no_hook' as hold_reason
FROM leads WHERE hook_quality = 0

UNION ALL

-- Low quality hook (tier 4-5)
SELECT id, name, segment, segment_confidence, 'low_quality_hook' as hold_reason
FROM leads WHERE hook_quality >= 4

UNION ALL

-- Unsupported segment (no template file)
SELECT id, name, segment, segment_confidence, 'unsupported_segment' as hold_reason
FROM leads WHERE segment IS NOT NULL
  AND segment NOT IN ({available_segments_placeholder})
```

Output: table with name, segment, hook_quality, hold_reason. No new table -- "manual review queue" is just a query with labeled reasons.

**Files to change:** `run.py` (add `leads held` subcommand), `models.py` (add `query_held_leads()`)

### Change 7: CSV Import (`run.py import`)

**What:** Import leads from an enriched Facebook CSV export.

**Logic in `ingest.py` as `import_from_csv()` (keeps `run.py` thin):**

```python
def import_from_csv(csv_path: str, source: str = "csv_import", db_path=DB_PATH) -> tuple[int, int, int]:
```

**CSV import contract matches `ingest_leads` INSERT path exactly.** `ingest_leads` writes: `name, bio, location, email, website, profile_url, activity, source`. CSV import maps to these fields only:

| CSV Header (case-insensitive) | Maps to |
|------------------------------|---------|
| `name` / `Name` | `name` (required) |
| `profile_url` / `Profile URL` / `url` | `profile_url` (required) |
| `bio` / `Bio` | `bio` |
| `location` / `Location` | `location` |
| `email` / `Email` | `email` |
| `website` / `Website` | `website` |

**Not mapped in Phase 1:** `phone` (not in `ingest_leads` INSERT), `mutual_friends`, `follower_count` (Phase 2 schema). If the CSV has these columns, they are silently ignored. To add `phone` support, extend the `ingest_leads` INSERT statement and `NormalizedLead` TypedDict -- that's a Phase 2 change.

**Files to change:** `ingest.py` (add `import_from_csv()`), `run.py` (add `cmd_import`), `models.py` (add `"csv_import"` to `VALID_SOURCES`)

### Change 8: Update `enrich --step all` ordering

**What:** Wire segment + hook into the step dict. `segment` after contact enrichment (reads bio). `hook` after segment (requires segment).

```python
steps = {
    "bio": enrich_from_bios, "website": enrich_leads, "deep": enrich_websites_deep,
    "venue": enrich_with_venue_scraper, "hunter": enrich_with_hunter,
    "segment": enrich_segment,  # NEW
    "hook": enrich_hook,        # NEW
}
```

**Files to change:** `run.py` (update `steps` dict and `choices` list)

## Pre-Implementation Gate: Opener Generation Benchmark

The Feed-Forward "least confident" item is opener generation quality. The Sonar Pro benchmark tested hook *research*, not opener *writing*. Before running `campaign generate` on a real batch:

**Benchmark design:** Generate openers for 5 Apr 20 leads where we know the original opener Alex wrote.

| Lead | Known Hook | Known Opener (Apr 20) |
|------|-----------|----------------------|
| Siraji Thomas | Industry Pets episode on DJ Date Nite | "Raj, the Industry Pets episode on DJ Date Nite and her cat Monkey had a real softness to it..." |
| Sacha Boutros | Paris After Dark at Baker-Baum | "Sacha, Paris After Dark at the Baker-Baum last fall was a real statement of intent..." |
| Madison Keith | Operation Max Wave, Blue Wave Radio | "Madison, Operation Max Wave was a solid one to watch unfold over those four months..." |
| John Beaudry | CanvasRebel interview | "John, your CanvasRebel interview had a line that stuck with me about garden design being translation..." |
| Becky Campbell | Del Mar close | "Becky, saw that Caminito Punta Arenas close in Del Mar last spring..." |

**Rubric (each opener scored 1-4):**
1. **Sounds like Alex** -- casual, specific, not generic vendor pitch
2. **Hook-specific** -- references the exact activity, not a paraphrase
3. **1-2 sentences** -- DM length, not email length
4. **Opens a conversation** -- ends with something the recipient might respond to

**Pass criteria:** 4/5 openers score 3+ on all 4 rubric items.

**If fail:** Add voice guide reference to the Haiku prompt. The voice guide at `docs/research/outreach-strategy/template-effectiveness.md` documents the opener patterns that worked. Include 2-3 example openers in the system prompt as few-shot examples.

**When to run:** After Change 5 is implemented (campaign generate exists), before running the first real campaign. This is a manual test, not an automated gate.

## What Must Not Change

- Existing 5-step enrichment pipeline behavior
- Existing 38 tests pass
- `UNIQUE(source, profile_url)` constraint on leads
- COALESCE pattern in `_persist_lead_update`
- SSRF protection in `_fetch_page()`
- API tokens in `.env`, never in code
- Single-writer rule: `ingest.py` owns INSERT on leads, `enrich.py` owns UPDATE on leads, `campaign.py` owns writes to campaign/queue tables
- `cmd_scrape` auto-enrichment behavior
- Flask UI unchanged (CLI only in Phase 1)

## Acceptance Tests

### Segment Classification

- WHEN `enrich --step segment` runs THE SYSTEM SHALL classify all leads with NULL segment
- WHEN Haiku returns segment="writer", confidence=0.85 THE SYSTEM SHALL store both values on the lead
- WHEN bio is under 3 chars THE SYSTEM SHALL skip the API call and store segment="other", confidence=0.1
- WHEN the API returns a rate limit error THE SYSTEM SHALL return segment="other", confidence=0.0 (graceful degradation)
- WHEN the model refuses to classify THE SYSTEM SHALL return segment="other", confidence=0.0

### Hook Research

- WHEN `enrich --step hook` runs THE SYSTEM SHALL research hooks for all leads with segment set but hook_text NULL
- WHEN Sonar Pro returns a Tier 1 hook THE SYSTEM SHALL store hook_text, hook_source_url (from citations[0]), hook_quality=1
- WHEN Sonar Pro returns "cannot find information" THE SYSTEM SHALL store hook_quality=0
- WHEN PERPLEXITY_API_KEY is not set THE SYSTEM SHALL print warning and return empty result

### Campaign Workflow

- WHEN `campaign create "Workshop" --segment connector,writer --var date="April 25"` THE SYSTEM SHALL create a campaign and print its ID
- WHEN `campaign assign 1 --min-hook-quality 3` THE SYSTEM SHALL assign leads with hook_quality 1-3, segment_confidence >= 0.7, and segment in available templates
- WHEN `campaign generate 1` THE SYSTEM SHALL generate a draft message for each assigned lead
- WHEN a template contains `{{date}}` and campaign provides date="April 25" THE SYSTEM SHALL replace it
- WHEN a required template variable is missing THE SYSTEM SHALL error with the missing variable name
- WHEN `campaign generate` is re-run THE SYSTEM SHALL skip leads with existing queue rows

### Queue Review (URL Verification)

- WHEN `campaign queue 1` THE SYSTEM SHALL display each draft with: lead name, hook text, **hook_source_url**, and full message
- WHEN the reviewer sees the hook_source_url THE SYSTEM SHALL have provided a clickable URL they can verify before approving
- WHEN a lead has no hook_source_url (citations were empty) THE SYSTEM SHALL display "NO SOURCE URL -- verify hook manually" in the queue output

### Approval / Skip / Sent

- WHEN `campaign approve 1 --lead 42` THE SYSTEM SHALL set status='approved' with timestamp (atomic claim, rowcount check)
- WHEN approve is called on an already-approved message THE SYSTEM SHALL print "already approved or not found"
- WHEN `campaign skip 1 --lead 42` THE SYSTEM SHALL set status='skipped' on draft messages
- WHEN `campaign sent 1 --lead 42` THE SYSTEM SHALL set status='sent' with timestamp on approved messages
- WHEN sent is called on a draft (not approved) message THE SYSTEM SHALL print "must approve before marking sent"

### Status

- WHEN `campaign status 1` THE SYSTEM SHALL print counts for draft, approved, sent, skipped

### Held Leads

- WHEN `leads held` runs THE SYSTEM SHALL display leads held from auto-generation with reasons (low_confidence, no_hook, low_quality_hook, unsupported_segment)

### CSV Import

- WHEN `import --csv friends.csv` THE SYSTEM SHALL import leads mapping only fields that `ingest_leads` supports (name, bio, location, email, website, profile_url, source)
- WHEN CSV has a "phone" column THE SYSTEM SHALL silently ignore it (not in `ingest_leads` INSERT path)
- WHEN CSV headers have mixed casing THE SYSTEM SHALL match case-insensitively

### Schema

- WHEN `migrate_db()` runs THE SYSTEM SHALL add 5 new columns idempotently
- WHEN `init_db()` runs THE SYSTEM SHALL create campaigns, campaign_leads, outreach_queue tables idempotently
- WHEN `migrate_db()` backs up the DB THE SYSTEM SHALL use sqlite3.backup() (WAL-safe), not shutil.copy2()

### Verification Commands

```bash
# Segment classification:
sqlite3 leads.db "SELECT segment, COUNT(*) FROM leads WHERE segment IS NOT NULL GROUP BY segment"

# Hook research:
sqlite3 leads.db "SELECT hook_quality, COUNT(*) FROM leads WHERE hook_quality IS NOT NULL GROUP BY hook_quality"

# Campaign workflow:
sqlite3 leads.db "SELECT * FROM campaigns"
sqlite3 leads.db "SELECT COUNT(*) FROM campaign_leads WHERE campaign_id = 1"
sqlite3 leads.db "SELECT l.name, oq.status, l.hook_source_url, oq.full_message FROM outreach_queue oq JOIN leads l ON oq.lead_id = l.id WHERE oq.campaign_id = 1"

# Held leads:
python run.py leads held

# All existing tests:
python -m pytest tests/ -v
```

## Implementation Order

1. **Change 1: Schema migration** -- 5 columns + 3 tables + WAL-safe backup fix. Low risk. Enables everything.
2. **Change 4: Template files** -- create 4 markdown files. Zero risk. Needed by Change 5.
3. **Change 7: CSV import** -- import command. Independent. Enables testing with real Facebook data.
4. **Change 2: Segment classifier** -- `enrich --step segment`. Needs `anthropic` + `pydantic` in requirements.
5. **Change 3: Hook research** -- `enrich --step hook`. Needs Perplexity key. Depends on segment.
6. **Change 5: Campaign management** -- create/assign/generate/queue/approve/skip/sent/status. Depends on segment + hook.
7. **Change 6: Held leads** -- `leads held` command. Independent but most useful after segment + hook.
8. **Change 8: Step ordering** -- wire segment + hook into `--step all`.

Each change is one commit (~50-100 lines). Tests alongside each change. Run opener benchmark after Change 5 before first real campaign.

## Estimated API Cost

| Step | API | Cost per lead | Batch of 200 |
|------|-----|--------------|-------------|
| Segment classifier | Claude Haiku 4.5 | ~$0.001 (with prompt caching) | ~$0.10 |
| Hook research | Perplexity Sonar Pro | ~$0.02-0.03 (tokens + search fee) | ~$4-6 |
| Opener generation | Claude Haiku 4.5 | ~$0.002 | ~$0.40 |
| **Total** | | ~$0.023-0.033 | **~$4.50-6.50** |

## Test Plan

### Schema Tests (`tests/test_migration.py`)

- `test_migrate_adds_segment_columns` -- segment + segment_confidence exist
- `test_migrate_adds_hook_columns` -- hook_text, hook_source_url, hook_quality exist
- `test_campaign_tables_created` -- campaigns, campaign_leads, outreach_queue exist
- `test_campaign_tables_idempotent` -- init_db twice, no error
- `test_backup_uses_sqlite_api` -- migrate_db uses sqlite3.backup, not shutil.copy2

### Segment Classifier Tests (`tests/test_segment.py`)

- `test_segment_selects_null_segment_only` -- segment=NULL selected, set skipped
- `test_segment_stores_result` -- segment + confidence populated
- `test_segment_prefilters_empty_bios` -- bio < 3 chars -> "other", 0.1 without API call
- `test_segment_handles_api_error` -- RateLimitError -> "other", 0.0
- `test_segment_handles_refusal` -- stop_reason="refusal" -> "other", 0.0

### Hook Research Tests (`tests/test_hook.py`)

- `test_hook_requires_segment` -- segment=NULL not selected
- `test_hook_stores_result_with_citation_url` -- hook_text + hook_source_url from citations[0] + hook_quality
- `test_hook_stores_no_hook` -- "cannot find" -> hook_quality=0
- `test_hook_handles_empty_citations` -- no citations -> hook_source_url=NULL
- `test_hook_skips_if_no_api_key` -- prints warning, returns empty result

### Campaign Tests (`tests/test_campaign.py`)

- `test_create_campaign` -- row in campaigns with template_vars_json
- `test_assign_filters_by_segment_and_quality` -- correct leads assigned
- `test_assign_derives_segments_from_templates` -- only segments with template files eligible
- `test_generate_fills_template_variables` -- `{{date}}` replaced
- `test_generate_errors_on_missing_variable` -- clear error message
- `test_generate_skips_existing_queue_row` -- re-run idempotent
- `test_queue_shows_hook_source_url` -- URL visible in queue output
- `test_approve_atomic_claim` -- draft -> approved, rowcount=1
- `test_approve_already_approved` -- rowcount=0
- `test_skip_message` -- draft -> skipped
- `test_sent_requires_approved` -- draft -> sent fails, approved -> sent succeeds
- `test_status_shows_counts` -- correct delivery counts

### CSV Import Tests (`tests/test_import.py`)

- `test_import_basic_csv` -- rows imported, counts correct
- `test_import_flexible_headers` -- mixed casing works
- `test_import_ignores_phone_column` -- phone not in ingest path, silently ignored
- `test_import_skips_missing_name` -- rejected count incremented
- `test_import_dedup` -- duplicate profile_url skipped

### Held Leads Tests (`tests/test_held.py`)

- `test_held_shows_low_confidence` -- confidence < 0.7 with reason
- `test_held_shows_no_hook` -- hook_quality=0 with reason
- `test_held_shows_unsupported_segment` -- segment not in template dir with reason

## Most Likely Way This Plan Is Wrong

1. **Opener generation quality.** Gated by the 5-lead benchmark (see Pre-Implementation Gate). If the benchmark fails, the mitigation is adding voice guide examples to the Haiku prompt.

2. **Haiku classifier on minimal bios.** ~30% of leads may have bios too short for confident classification. Pre-filter catches empties, but 10-50 char bios may produce low-confidence results routing to manual review. Acceptable -- manual review fills the gap.

3. **Sonar Pro citation accuracy.** 37% of claims may not match their cited source. URLs are real but content attribution is imperfect. The `campaign queue` showing `hook_source_url` is the verification checkpoint. Operational cost: ~10-20% of hooks need manual URL checking.

## Sources & References

### Origin

- **Brainstorm:** [docs/brainstorms/2026-04-21-lead-scraper-v2-outreach-platform-brainstorm.md](../brainstorms/2026-04-21-lead-scraper-v2-outreach-platform-brainstorm.md)

### Internal

- Enrichment step pattern: `enrich.py:159`
- Migration pattern: `db.py:33-61`
- CLI subcommand pattern: `run.py:124-157`
- Ingest INSERT path: `ingest.py:29-34` (name, bio, location, email, website, profile_url, activity, source -- no phone)
- Hunter.io rate limiting: `enrich.py:434-534`

### Cross-Project

- Atomic claim: `gig-lead-responder/docs/solutions/architecture/atomic-claim-for-concurrent-state-transitions.md`
- Human-in-the-loop state machine: `gig-lead-responder/docs/solutions/architecture/follow-up-pipeline-human-in-the-loop-lifecycle.md`

## Feed-Forward

- **Hardest decision:** Where `sent` status tracking lives. Chose to add `campaign sent` command in Phase 1 (3 lines of code) rather than leaving dead statuses in the schema. This completes the approve -> sent workflow without adding outcome tracking (conversions table deferred to Phase 2).
- **Rejected alternatives:** Putting campaign logic in `enrich.py` (violates single-writer), Jinja2 for templates (YAGNI), `phone` in CSV import (not in `ingest_leads` INSERT path -- extend later).
- **Least confident:** Opener generation quality. Gated by 5-lead benchmark with rubric (sounds like Alex, hook-specific, 1-2 sentences, opens conversation). If benchmark fails, add voice guide examples to Haiku prompt. Voice guide deferred to benchmark result -- not pre-baked into Phase 1 implementation.
