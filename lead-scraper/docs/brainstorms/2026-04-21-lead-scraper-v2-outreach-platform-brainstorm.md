---
topic: lead-scraper-v2-outreach-platform
date: 2026-04-21
status: planning-ready
revision: 3 (post-Codex review)
feed_forward:
  risk: "Perplexity Sonar API may produce different quality hooks than the chat interface used in Apr 20 batch"
  verify_first: true
  gate: "PASSED (2026-04-21). Use sonar-pro, not sonar."
benchmark:
  model: sonar-pro
  date: 2026-04-21
  result: "PASS — 4/5 Tier 1-3 hooks, 3/5 match or improve Apr 20"
  notes: "sonar failed 1/5. sonar-pro passed 4/5. Must include bio+role in prompt. ~$0.015/lead."
---

# Lead Scraper v2: Full Outreach Intelligence Platform

## What We're Building

Transform the lead-scraper from a contact-info finder into a full outreach intelligence platform. The current pipeline answers "how do I reach this person?" The Apr 20 outreach batch (30 sends, 3 warm leads) proved that "what do I say that makes them reply?" is the higher-value problem.

The v2 platform closes the loop: scrape leads, enrich contact info, classify segments, research personalized hooks via Perplexity, generate openers matched to segment templates, queue messages for human review, track outreach and conversion across named campaigns.

### Current State (What Exists)

- 5-step contact enrichment pipeline (bio parse, website fetch, deep crawl, venue scraper, Hunter.io)
- 3 active scrapers (Eventbrite, Facebook groups, Instagram hashtags)
- Flask UI with lead table, search, export
- SQLite with COALESCE update pattern, idempotent migrations
- 38 tests passing, clean single-writer architecture

### What's Missing (The Gap)

- No segment classification
- No hook research (finding what to say about a person)
- No hook quality scoring (attention vs surveillance hierarchy)
- No message generation or template engine
- No campaign management or outreach tracking
- No follow-up sequencing
- No network proximity scoring

## Why This Approach

The Apr 20 batch proved three durable laws (documented in `docs/research/outreach-strategy/enrichment-design-principles.md`):

1. **Enrichment depth > social proximity.** Perplexity-researched leads converted at 25%. Personal-write leads with highest mutual friends converted at 0%.
2. **Indirect CTA > direct CTA.** Connector template ("you know people") = 33%. Real estate template ("how fast do you respond") = 0%.
3. **Template-market fit is independent of personalization quality.** Great openers can't save templates that trigger vendor-pitch pattern matching.

Building this into the lead-scraper (rather than a separate tool) because the infrastructure is already there: migration pattern, persist function, step flags, Apify runner, Flask UI. Extract later if the outreach layer grows complex enough to justify separation.

## Key Decisions

### 1. Hook Research: Perplexity Sonar Pro API (benchmark passed)

- Proven via benchmark (2026-04-21): 4/5 leads returned Tier 1-3 hooks with source URLs.
- Model: `sonar-pro` (not `sonar`). Standard sonar failed 1/5; sonar-pro passed 4/5.
- ~$0.015/search. Batch of 200 leads = ~$3. Trivial cost.
- Prompt MUST include bio + activity + role context from the database (not just name + location). Name-only prompts fail.
- Prompt requests Tier 1-3 hooks (content created > opinions > events). Tier 4-5 results flagged as low quality.
- Every hook includes a source URL for "verify before sending" discipline.
- Leads where Sonar Pro returns no usable hook get flagged "WRITE OPENER YOURSELF" (expected ~30-40% of leads).
- **Rate limits:** 50 req/min. Batch of 200 leads = ~4 minutes. No throttling needed.

### 2. Segment Classification: LLM Classifier (Claude Haiku)

- Feed bio + activity + source into Haiku. ~$0.001/lead.
- Already have ANTHROPIC_API_KEY for the venue scraper step.
- Full classifier output set: real_estate, writer, wellness, musician, connector, small_biz, creative, nonprofit, tech, other.
- Confidence score: 0.0-1.0.
- **Confidence threshold:** < 0.7 routes to manual review queue, not auto-assignment.
- **Segment-to-template mapping (Phase 1):** See "Segment-Template Mapping" section below.

### 3. Outreach Execution: Human-in-the-Loop

- System generates openers + template-matched messages and queues them.
- Human reviews and approves each message before it goes out.
- Matches the "verify before sending" principle. No auto-send.
- Follow-ups also queued for review (system generates, human approves).

### 4. Phase 1 Channel: Facebook DM

- Phase 1 generates Facebook DM-ready messages. This is the proven channel from the Apr 20 batch.
- Messages are formatted for DM length and tone. No subject lines, no email formatting.
- Phase 2 adds Instagram DM and email variants with channel-specific formatting.

### 5. Template Parameterization

- Templates use variables for facts: `{{event_name}}`, `{{date}}`, `{{seat_count}}`, `{{format}}`.
- Voice and CTA structure stay fixed per segment.
- Each campaign provides its own variable values at creation time.
- **Validation:** If a required variable is missing from campaign config, `generate` step errors with a clear message listing the missing variable. Does not silently produce broken messages.
- The Apr 20 templates become the first template set, not the only one.

### 6. Interface: Enhanced Flask UI (Phase 2)

- Phase 1 is CLI-only for pipeline operations and campaign management.
- Phase 2 extends Flask app with campaign dashboard, lead queue with hook previews, approve/skip buttons, conversion charts.

### 7. Ambitious Features

**A. Batch Campaign Manager (Phase 1)**
- Named campaigns ("Amplify Workshop Apr 25", "Summer Audit Push").
- Explicit campaign membership via `campaign_leads` junction table (assigned before generation).
- Campaign has: name, target_date, segment_filter, template_vars_json, status (draft/active/complete).
- Delivery metrics (sent, approved, skipped) computed from outreach_queue.
- Outcome metrics (replied, warm, declined, booked, referred) computed from conversions.

**B. Auto Follow-Up Sequencing (Phase 2)**
- 3-touch sequence: opener -> value add -> soft close.
- Default delays: 3 days between touch 1-2, 5 days between touch 2-3. **These are assumptions, not proven from Apr 20 data.** Apr 20 was single-touch only.
- Each touch uses a different angle/template to avoid repetition.
- Tracks which touch number converted (for optimizing sequence design).
- All touches queued for human review before sending.
- Scheduling: `python run.py campaign followup` checks for leads past their next_followup date. Run manually or via cron.

**C. Network Graph Scoring (Phase 2)**
- Import mutual friend count + follower count data via CSV import.
- `priority_score` lives on `campaign_leads`, not on `leads`, because it is batch-relative (depends on max values in the campaign's lead set).
- Composite score: all inputs normalized to 0.0-1.0 range, then `(hook_score * 0.4) + (network_score * 0.3) + (reach_score * 0.3)`.
- **Missing data behavior:** If a lead has no mutual_friends or follower_count, score uses only hook_quality (1-factor score). No penalty for missing network data.
- **A/B testing deferred.** Not needed until there are enough campaigns to compare.

## Segment-Template Mapping

The classifier can output 10 segments but only some have tested templates. Phase 1 must define explicit routing.

### Supported Segments (Phase 1) -- have templates

| Segment | Template | Evidence Level | Notes |
|---------|----------|---------------|-------|
| connector | Connectors | **Strong** (2/6 warm, 33%) | Best performer. Indirect CTA proven. |
| writer | Writers | **Moderate** (1/5 warm, 20%) | Fear-disarming line proven. One hot lead. |
| small_biz | Small Biz | **Signal-rich, 0 conversions** (0/6, but 1 decline with competitor intel) | Template needs rewrite for craft-oriented operators. Use as-is for now, iterate. |
| real_estate | Real Estate | **Strong negative** (0/9) | Template confirmed failing. Included with warning: rewrite recommended before use. |

### Under-Sampled Segments (Phase 1) -- route to manual review

| Segment | Template | Evidence Level | Handling |
|---------|----------|---------------|----------|
| wellness | Wellness | **Under-sampled** (n=2, 0%) | Hold for manual review. Do not auto-generate. |
| musician | Musicians | **Under-sampled** (n=1, 0%) | Hold for manual review. Do not auto-generate. |

### Unsupported Segments (Phase 1) -- no template exists

| Segment | Handling |
|---------|----------|
| creative | Route to closest match (connector or writer) based on bio, OR hold for manual review. |
| nonprofit | Hold for manual review. No template. |
| tech | Hold for manual review. No template. |
| other | Hold for manual review. Catch-all. |

**Rule:** If classifier outputs an unsupported or under-sampled segment, the lead is marked `needs_manual_review` and excluded from auto-generation. Human decides template assignment.

## Decision Rules

These rules govern automated behavior. Each must be implemented as a check, not left to judgment during coding.

| Rule | Threshold | Behavior |
|------|-----------|----------|
| Segment confidence | < 0.7 | Route to manual review, do not auto-assign segment |
| Hook quality | Tier 1-3 (quality 1-3) | Generate opener automatically |
| Hook quality | Tier 4-5 (quality 4-5) | Hold. Flag as "low-quality hook, consider writing opener manually" |
| No hook found | Perplexity returns nothing usable | Hold. Flag as "WRITE OPENER YOURSELF." Do not generate template-only message |
| Template variable missing | Campaign config missing a required `{{var}}` | Error on `generate` step. List missing variables. Do not produce broken message |
| Unsupported segment | creative, nonprofit, tech, other | Hold for manual review. Do not auto-generate |
| Under-sampled segment | wellness, musician | Hold for manual review. Do not auto-generate |
| Missing network data | No mutual_friends or follower_count | Score uses hook_quality only (1-factor). No penalty |
| Follow-up timing | 3 days (touch 1-2), 5 days (touch 2-3) | **Assumptions.** Not validated by Apr 20 data (single-touch only). Label as defaults, not proven |

## Pre-Plan Verification: Perplexity Sonar API Benchmark

The brainstorm's "least confident" area is whether the Sonar API produces the same quality hooks as the manual Perplexity chat interface used in Apr 20. **This must be verified before planning builds around it.**

### Benchmark Design

**Sample:** 5 leads from the Apr 20 batch where we know the exact hook that was used:
1. Siraji Thomas -- Industry Pets episode on DJ Date Nite (Tier 1: content created)
2. Sacha Boutros -- Paris After Dark at Baker-Baum (Tier 2: event led)
3. Madison Keith -- Operation Max Wave, Blue Wave Radio (Tier 3: project led)
4. John Beaudry -- CanvasRebel interview, garden design as "translation" (Tier 2: opinion)
5. Becky Campbell -- Del Mar close, Caminito Punta Arenas (Tier 5: transaction)

**Prompt template:**
```
Find one recent, specific, verifiable public activity for [name] in [location].
Prefer: content they created (podcast episodes, articles, creative work)
over opinions they expressed (interviews, commentary)
over events they led
over awards they received
over transactions or metrics.
Return: the hook text (one sentence), the source URL, and which tier it falls into.
```

**Pass criteria:**
- At least 3 of 5 produce a Tier 1-3 hook with a valid source URL
- At least 2 of 5 match or improve on the hook found manually in Apr 20
- Source URLs are real and verifiable (not hallucinated)

**Fail criteria:**
- Fewer than 3 produce usable hooks
- Source URLs are hallucinated or broken
- Hooks are generic ("is a well-known figure in San Diego") rather than specific

**If pass:** Proceed to planning with Sonar API as primary hook research.
**If fail:** Fall back to Claude Haiku + web search, or keep manual Perplexity for high-value leads and build the pipeline around Claude for batch processing.

**Throughput assumptions:** Sonar allows 50 req/min. A batch of 200 leads completes in ~4 minutes. No special throttling needed.

## Implementation Phases

### Phase 1: Core Intelligence Pipeline (ship first)

Schema changes + segment classifier + Perplexity hook research + message generation + outreach queue + campaign manager. All CLI-operated. Facebook DM output only. This gets you from "here's their email" to "here's a Facebook DM ready to send, organized by campaign."

**What ships:**
- `python run.py enrich --step segment` -- classify leads
- `python run.py enrich --step hook` -- Perplexity hook research
- `python run.py campaign create` -- create campaign with template vars
- `python run.py campaign assign` -- assign leads to campaign (with hook quality gate)
- `python run.py campaign generate` -- generate messages for assigned leads
- `python run.py campaign queue` -- show pending messages for review
- `python run.py campaign approve` -- approve individual messages
- `python run.py campaign status` -- show delivery + outcome metrics
- `python run.py import --csv` -- flexible CSV import
- Parameterized templates in `templates/outreach/`

**What doesn't ship:** Follow-up sequencing, network graph scoring, priority scoring, Flask UI extensions, multi-channel variants.

### Phase 2: Outreach Engine (ship second)

Follow-up sequencing + network graph scoring + enhanced Flask UI + Instagram DM and email channel variants. This turns the tool from "generate one message per lead" into "run a multi-touch campaign with smart prioritization."

**What ships:**
- `python run.py campaign followup` -- generate touch 2-3 for non-responders
- `python run.py enrich --step score` -- compute priority_score
- CSV import for mutual friends/follower data
- Flask campaign dashboard + lead detail pages + conversion charts
- Channel-specific message variants

## Architecture Overview

### New Columns on leads Table (via migrate_db pattern)

```sql
-- Segment classification (Phase 1)
segment            TEXT    -- real_estate, writer, wellness, etc.
segment_confidence REAL    -- 0.0-1.0 from LLM classifier

-- Hook research (Phase 1)
hook_text          TEXT    -- "Industry Pets episode on DJ Date Nite and cat Monkey"
hook_type          TEXT    -- content_created, opinion, event, award, transaction
hook_source_url    TEXT    -- verification link
hook_quality       INTEGER -- 1-5 (1=best, 5=worst, matching tier hierarchy)

-- Network data (Phase 2 -- populated via CSV import)
mutual_friends     INTEGER -- from Facebook export + Claude Code browser enrichment
follower_count     INTEGER -- from source platform
```

Note: `priority_score` does NOT live on leads. It is batch-relative and lives on `campaign_leads`.

### New Tables

```sql
-- Campaign management (Phase 1)
CREATE TABLE campaigns (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    name              TEXT NOT NULL,
    target_date       TEXT,
    segment_filter    TEXT,    -- comma-separated segment names, or NULL for all
    template_vars_json TEXT,   -- JSON: {"event_name": "...", "date": "...", ...}
    status            TEXT NOT NULL DEFAULT 'draft',  -- draft, active, complete
    created_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now'))
);
-- Delivery metrics: COUNT on outreach_queue WHERE campaign_id = X GROUP BY status
-- Outcome metrics: COUNT on conversions WHERE campaign_id = X GROUP BY event_type

-- Campaign membership (Phase 1) -- explicit, before generation
CREATE TABLE campaign_leads (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id     INTEGER NOT NULL REFERENCES campaigns(id),
    lead_id         INTEGER NOT NULL REFERENCES leads(id),
    priority_score  REAL,    -- Phase 2: batch-relative composite score
    assigned_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now')),
    UNIQUE(campaign_id, lead_id)
);

-- Message queue (Phase 1) -- one row per lead per campaign per touch
CREATE TABLE outreach_queue (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id         INTEGER NOT NULL REFERENCES leads(id),
    campaign_id     INTEGER NOT NULL REFERENCES campaigns(id),
    channel         TEXT NOT NULL DEFAULT 'facebook_dm',
    touch_number    INTEGER NOT NULL DEFAULT 1,
    opener_text     TEXT,    -- personalized hook opener
    template_text   TEXT,    -- segment template with vars filled
    full_message    TEXT,    -- opener + template combined
    status          TEXT NOT NULL DEFAULT 'draft',  -- draft, approved, sent, skipped
    generated_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now')),
    approved_at     TEXT,
    sent_at         TEXT,
    next_followup   TEXT,    -- Phase 2: scheduled timestamp for next touch
    UNIQUE(lead_id, campaign_id, touch_number)
);

-- Conversion events (Phase 1) -- append-only log
CREATE TABLE conversions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id         INTEGER NOT NULL REFERENCES leads(id),
    campaign_id     INTEGER NOT NULL REFERENCES campaigns(id),
    event_type      TEXT NOT NULL,  -- replied, warm, declined, booked, referred
    notes           TEXT,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now'))
);
```

**Queue re-run behavior:** UNIQUE(lead_id, campaign_id, touch_number) prevents duplicate generation. Re-running `campaign generate` skips leads that already have a queue row for that touch. To regenerate, delete the existing queue row first.

### New Pipeline Steps

| Step | Phase | What it does | Cost |
|------|-------|-------------|------|
| `segment` | 1 | LLM classifier on bio + activity | ~$0.001/lead (Haiku) |
| `hook` | 1 | Perplexity Sonar Pro API research per lead | ~$0.015/lead |
| `generate` | 1 | Assemble opener + parameterized template into Facebook DM | ~$0.002/lead (Haiku) |
| `score` | 2 | Compute priority_score on campaign_leads from hook + network + reach | Free (local math) |

### Phase 1 CLI Commands

```bash
# Import leads from enriched Facebook CSV
python run.py import --csv enriched_friends.csv

# Classify and research
python run.py enrich --step segment
python run.py enrich --step hook

# Campaign operations
python run.py campaign create "Amplify Workshop Apr 25" \
  --segment connector,writer,small_biz \
  --var event_name="AI for Small Business Workshop" \
  --var date="April 25" --var seat_count=30 --var format="Half day, hands-on"

python run.py campaign assign 1 --min-hook-quality 3
python run.py campaign generate 1
python run.py campaign queue 1
python run.py campaign approve 1 --lead 42
python run.py campaign status 1

# Phase 2 only:
python run.py campaign followup 1
```

Note: `--min-score` removed from Phase 1 CLI (scoring is Phase 2).

## Template Evidence Levels

Not all 6 templates have equal evidence. The system should reflect this.

| Template | Evidence | Sends | Warm | Confidence |
|----------|----------|:-----:|:----:|------------|
| Connectors | **Strong** | 6 | 2 (33%) | High -- two independent warm leads, clear CTA pattern |
| Writers | **Moderate** | 5 | 1 (20%) | Moderate -- one hot lead, disarming line is strong signal |
| Small Biz | **Signal-rich, 0 conversion** | 6 | 0 | Low for conversion, high for intel gathering. Needs rewrite for craft operators |
| Real Estate | **Strong negative** | 9 | 0 | High confidence it FAILS. Rewrite before reuse |
| Wellness | **Under-sampled** | 2 | 0 | Cannot draw conclusions. n too small |
| Musicians | **Under-sampled** | 1 | 0 | Cannot draw conclusions. n too small |

## Resolved Questions

1. **Template storage:** Markdown files in `templates/outreach/`. One per segment. **DECIDED.**
2. **Perplexity API access:** Sonar API, gated by benchmark. **DECIDED.**
3. **Facebook data import:** Facebook CSV export -> Claude Code browser enrichment -> `python run.py import --csv`. Flexible column mapping. **DECIDED.**
4. **Template voice:** All 6 templates captured in `docs/research/outreach-strategy/template-effectiveness.md`. **DECIDED.**
5. **Campaign membership model:** Explicit `campaign_leads` junction table. Assigned before generation. **DECIDED.**
6. **Queue uniqueness:** UNIQUE(lead_id, campaign_id, touch_number). Re-run skips existing rows. **DECIDED.**
7. **Priority score location:** On `campaign_leads`, not `leads`. Batch-relative. **DECIDED.**
8. **Metrics split:** Delivery metrics from outreach_queue. Outcome metrics from conversions. **DECIDED.**
9. **Phase 1 channel:** Facebook DM only. Messages formatted for DM. **DECIDED.**
10. **Segment-template routing:** 4 supported, 2 under-sampled (hold), 4 unsupported (hold). **DECIDED.**
11. **Decision rules:** All 9 rules defined with explicit thresholds. **DECIDED.**
12. **Sonar API gate:** 5-lead benchmark with pass/fail criteria. **DECIDED.**
13. **Follow-up timing:** 3 days / 5 days labeled as assumptions, not Apr 20-proven. **DECIDED.**

## Feed-Forward

- **Hardest decision:** Building everything into lead-scraper vs. separate tools. Chose monolith-first for speed, with extraction as a future option. Risk mitigated by phasing.
- **Rejected alternatives:** Rule-based keyword classifier (too brittle for edge cases), Claude + web search for hooks (more expensive, no proven quality advantage -- but becomes the fallback if Sonar fails), auto-send (violates verify-before-sending discipline), A/B testing in v1 (not enough campaigns to compare).
- **Least confident:** Sonar Pro source URL accuracy. Siraji Thomas benchmark returned an episode reference that may be hallucinated. The "verify before sending" discipline is the last line of defense. Every hook source URL must be checked by the human before sending.
