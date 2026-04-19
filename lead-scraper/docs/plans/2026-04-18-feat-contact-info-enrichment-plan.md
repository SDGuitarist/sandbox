---
title: "Contact Info Enrichment -- Emails, Phones, Social Handles"
phase: plan
created: 2026-04-18
revised: 2026-04-19
feed_forward:
  risk: "Official Instagram profile actor returns NO email/phone fields. Alternative actor (logical_scrapers) is unverified."
  verify_first: true
---

# Contact Info Enrichment Plan

## Problem

587 leads in the database. Only 24 have emails (all from Eventbrite). Zero from Facebook or Instagram. The scraper collects names and profile URLs but the enrichment pipeline can't extract contact info because social media profiles require authentication to view as HTML.

## Spike Results (2026-04-19)

Ran `apify/instagram-profile-scraper` on 2 real accounts. Full results in `docs/spikes/2026-04-18-ig-profile-actor-output.md`.

**Key findings:**
- `publicEmail` / `publicPhoneNumber` -- **NOT RETURNED** by this actor
- `biography` -- present and full (not truncated like hashtag captions)
- `externalUrls` -- present as an **array** (not singular `externalUrl`), empty for both test accounts
- `isBusinessAccount`, `businessCategoryName` -- present and useful for filtering

**Conclusion:** The official `apify/instagram-profile-scraper` uses the web API which no longer returns email/phone fields. Only the mobile API (with cookies) returns `public_email` and `public_phone_number`. We need either a different actor that uses the mobile API, or a multi-step approach.

## What Exactly Is Changing

Four changes, reprioritized based on spike results:

### Change 1: Bio Parsing for Contact Info (zero cost, highest certainty)

**What:** Scan the `bio` and `profile_bio` fields of all leads for emails, phone numbers, and social media handles using regex. Zero API cost.

**Why:** People put contact info directly in their Instagram bios and Facebook posts. Example from our data: `"Ask me anything on IG @JamariJonesATL"`. This data is already in the database but not being parsed. The spike confirmed that `biography` from the profile actor contains richer text than the hashtag caption, making this even more valuable.

**Selection criteria:**
```sql
SELECT id, bio, profile_bio FROM leads
WHERE (bio IS NOT NULL OR profile_bio IS NOT NULL)
  AND (email IS NULL OR phone IS NULL OR social_handles IS NULL)
```

Covers any lead missing any of the three contact fields.

**How:**
- Add `parse_bio(text: str) -> ParsedContactInfo` to `enrich_parsers.py`
- Extend `ParsedContactInfo` dataclass to include `social_handles: list[str]`
- Reuse existing `EMAIL_RE` for emails
- Add phone regex: `r'\b(?:\+?1[-.\s]?)?\(?[2-9]\d{2}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'`
- Add social handle regexes (keyword-prefix-only, no bare `@handle`):
  - Instagram: `r'(?:IG|instagram|insta)[:\s|]*@?([a-zA-Z0-9_.]{3,30})'`
  - Twitter/X: `r'(?:twitter|x\.com)[:\s|/]*@?([a-zA-Z0-9_]{1,15})'`
  - LinkedIn: `r'linkedin\.com/in/([a-zA-Z0-9\-]+)'`
  - TikTok: `r'(?:tiktok|tik tok)[:\s|]*@?([a-zA-Z0-9_.]{2,24})'`
  - YouTube: `r'(?:youtube\.com|youtu\.be)/(?:@|channel/|c/)([a-zA-Z0-9_\-]+)'`
- Stopword list for defense-in-depth: `["everyone", "here", "channel", "group", "all", "admin", "admins", "moderator", "mod"]`
- Add `enrich_from_bios()` in `enrich.py`
- Parse both `bio` and `profile_bio`, merge results, deduplicate

**`social_handles` serialization:** JSON array of strings, each prefixed with the platform:
```json
["instagram:username", "twitter:handle", "linkedin:in/name"]
```
JSON (not comma-separated) because handles can contain commas. Stored as TEXT in SQLite. Parsed with `json.loads()` on read.

**Files to change:**
- `enrich_parsers.py` -- extend `ParsedContactInfo`, add `parse_bio()`
- `enrich.py` -- add `enrich_from_bios()`

### Change 2: Instagram Profile Enrichment with Alternative Actor (spike required)

**What:** Replace `apify/instagram-profile-scraper` with `logical_scrapers/instagram-profile-scraper` which claims to return business email, phone, and 50+ fields including bio links. If the spike fails, fall back to the official actor for biography + externalUrls only.

**Why:** The official actor does NOT return email/phone. The `logical_scrapers` actor advertises these fields and costs $2/1K profiles (~$0.50 for our 248 leads). It likely uses the mobile API with cookies.

**Step 2a: Spike (gate)**
Run `logical_scrapers/instagram-profile-scraper` on the same 2 accounts (`_mare_collective_`, `_kaizen.fm`). Record exact output keys. Compare against the official actor's output.

```python
from scrapers._apify_helpers import run_actor
import json
result = run_actor('logical_scrapers/instagram-profile-scraper', {
    'usernames': ['_mare_collective_', '_kaizen.fm']
})
print(json.dumps(result, indent=2))
```

Save output to `docs/spikes/2026-04-19-ig-logical-scrapers-output.json`.

**Gate criteria:**
- If it returns email/phone fields (even empty for personal accounts) -> use this actor
- If it returns the same fields as the official actor -> fall back to official actor for bio + externalUrls only
- If it errors or requires paid rental -> evaluate cost, decide with user

**Step 2b: Implementation (post-spike)**

**Enrichment state:** New column `ig_profile_enriched_at TEXT` tracks whether the profile actor has run, independent of the `enriched_at` column that `cmd_scrape` auto-sets on every run.

**Selection criteria:**
```sql
SELECT id, profile_url FROM leads
WHERE source = 'instagram' AND ig_profile_enriched_at IS NULL
```

**How:**
- Add `enrich_instagram_profiles()` in `enrich.py`
- Extract username from `profile_url` (strip `https://www.instagram.com/`)
- Batch usernames in groups of 20 with 2-second delay
- From the response, extract and persist (field names TBD by spike):
  - Email field -> `leads.email` (COALESCE)
  - Phone field -> `leads.phone` (COALESCE)
  - `externalUrls` (array) -> first URL into `leads.website` (COALESCE)
  - `biography` -> `leads.profile_bio` (new column, does NOT overwrite `bio`)
- Run `parse_bio()` on `biography` to extract social handles
- **Immediately crawl** any discovered `externalUrls` via `_enrich_single_lead()` inline
- Set `ig_profile_enriched_at = now`

**Bio preservation:** `bio` keeps original source text (caption/post). New `profile_bio` column stores full Instagram biography. Neither is mutated after initial write.

**Files to change:**
- `enrich.py` -- add `enrich_instagram_profiles()`
- `config.py` -- add actor config (actor ID TBD by spike)
- `run.py` -- wire into `python run.py enrich`

### Change 3: Website Contact Crawling with `vdrmota/contact-info-scraper`

**What:** For leads that have a `website` URL (from Eventbrite organizer pages or Instagram `externalUrls`), use the `vdrmota/contact-info-scraper` Apify actor to crawl the website and extract emails, phones, and social profiles.

**Why:** Our existing `_enrich_single_lead()` fetches one page and runs regex. The `vdrmota` actor is smarter -- it crawls multiple subpages, prioritizes /contact and /about pages, and extracts structured data including social media profiles. It's free (pay-per-event, $5 free credits included).

**This replaces the existing website enrichment approach** for leads that have a website URL. The existing `_fetch_page()` + `parse_profile_page()` pipeline stays as a fallback for leads where the actor fails.

**How:**
- Add `enrich_websites_deep()` in `enrich.py`
- Select leads where `website IS NOT NULL AND email IS NULL`
- Batch website URLs and run `vdrmota/contact-info-scraper`
- From the response, extract:
  - `emails` (array) -> first into `leads.email` (COALESCE)
  - `phones` (array) -> first into `leads.phone` (COALESCE)
  - `instagrams`, `twitters`, `linkedIns`, `facebooks` -> merge into `leads.social_handles`
- Fall back to existing `_enrich_single_lead()` for any URLs the actor fails on

**Files to change:**
- `enrich.py` -- add `enrich_websites_deep()`
- `config.py` -- add `vdrmota/contact-info-scraper` actor config

### Change 4: Read-Path Updates (CSV Export + UI)

**What:** Add `social_handles` and `profile_bio` to CSV export and the web UI table.

**CSV export (`run.py:cmd_export`):**
- Add `social_handles` and `profile_bio` to `fieldnames` list

**Web UI (`templates/index.html`):**
- Add Email, Phone, and Social columns

**Files to change:**
- `run.py` -- add fields to `cmd_export` fieldnames
- `templates/index.html` -- add 3 columns

## Schema Changes (all in one migration)

Add to `db.py:migrate_db()`:
- `ig_profile_enriched_at TEXT`
- `profile_bio TEXT`
- `social_handles TEXT`

## What Must Not Change

- Existing 24 emails must not be overwritten (COALESCE)
- `bio` column must not be mutated -- original source text preserved
- SSRF protection in `_fetch_page()` stays intact
- No scraping of private/login-required pages
- Apify token stays in `.env`, never in code
- `UNIQUE(source, profile_url)` constraint stays
- Existing test suite (38 tests) continues to pass
- `cmd_scrape` auto-enrichment behavior unchanged

## Acceptance Tests

### Happy Path

- WHEN `python run.py enrich` runs THE SYSTEM SHALL parse bios of all leads missing email, phone, or social_handles
- WHEN a lead's bio contains `"IG: @somename"` THE SYSTEM SHALL store `["instagram:somename"]` in social_handles
- WHEN a lead's bio contains `"twitter.com/myhandle"` THE SYSTEM SHALL store `["twitter:myhandle"]` in social_handles
- WHEN a lead's bio contains `booking@studio.com` THE SYSTEM SHALL store it in the email column
- WHEN a lead's bio contains `(619) 555-1234` THE SYSTEM SHALL store it in the phone column
- WHEN the Instagram profile actor returns a biography THE SYSTEM SHALL store it in `profile_bio` (NOT overwrite `bio`)
- WHEN the profile actor returns `externalUrls` with URLs THE SYSTEM SHALL store the first URL in `website` (COALESCE) AND immediately crawl it
- WHEN `vdrmota/contact-info-scraper` finds emails on a lead's website THE SYSTEM SHALL store the first email in `leads.email` (COALESCE)
- WHEN `vdrmota/contact-info-scraper` finds social profiles on a website THE SYSTEM SHALL merge them into `leads.social_handles`
- WHEN social_handles already has values and new handles are found THE SYSTEM SHALL merge (deduplicate, no overwrite)
- WHEN `python run.py export --output out.csv` runs THE SYSTEM SHALL include `social_handles` and `profile_bio` columns
- WHEN the web UI loads THE SYSTEM SHALL display Email, Phone, and Social columns

### Error/Edge Cases

- WHEN the Apify actor returns no data for a username THE SYSTEM SHALL set `ig_profile_enriched_at` to now (no crash, no retry loop)
- WHEN a bio contains `photo@2x.png` THE SYSTEM SHALL NOT extract it as an email
- WHEN a bio contains `@everyone` or `@admins` THE SYSTEM SHALL NOT extract it as a social handle (stopword)
- WHEN a bio contains `@americanportra` (bare @ with no platform keyword) THE SYSTEM SHALL NOT extract it
- WHEN a lead already has an email from Eventbrite THE SYSTEM SHALL NOT overwrite it (COALESCE)
- WHEN `cmd_scrape` auto-runs `enrich_leads()` THE SYSTEM SHALL NOT interfere with `ig_profile_enriched_at`
- WHEN `migrate_db()` runs on a DB that already has the new columns THE SYSTEM SHALL be a no-op (idempotent)
- WHEN `migrate_db()` runs on a fresh DB from `schema.sql` THE SYSTEM SHALL not error
- WHEN social_handles is empty THE SYSTEM SHALL store NULL, not `[]` or `""`
- WHEN `vdrmota/contact-info-scraper` returns no results for a URL THE SYSTEM SHALL fall back to existing `_enrich_single_lead()`

### Verification Commands

```bash
# After bio parsing (Change 1):
sqlite3 leads.db "SELECT COUNT(*) FROM leads WHERE social_handles IS NOT NULL"
# Expected: > 0

sqlite3 leads.db "SELECT name, social_handles FROM leads WHERE social_handles IS NOT NULL LIMIT 5"
# Expected: JSON arrays like ["instagram:somename"]

# After full enrichment:
sqlite3 leads.db "SELECT source,
  COUNT(*) as total,
  SUM(CASE WHEN email IS NOT NULL THEN 1 ELSE 0 END) as has_email,
  SUM(CASE WHEN phone IS NOT NULL THEN 1 ELSE 0 END) as has_phone,
  SUM(CASE WHEN social_handles IS NOT NULL THEN 1 ELSE 0 END) as has_social,
  SUM(CASE WHEN ig_profile_enriched_at IS NOT NULL THEN 1 ELSE 0 END) as ig_enriched
FROM leads GROUP BY source"

# Confirm bio column NOT mutated:
sqlite3 leads.db "SELECT COUNT(*) FROM leads WHERE profile_bio IS NOT NULL AND bio = profile_bio"
# Expected: 0 or very few (bio is caption, profile_bio is full biography)

# Export includes new columns:
python run.py export --output /tmp/test_export.csv
head -1 /tmp/test_export.csv | grep -c "social_handles"
# Expected: 1

python -m pytest tests/ -v
# 38 existing + new tests all passing
```

## Implementation Order

1. **Change 1: Bio parsing** -- zero cost, immediate results, validates regex. Write tests first.
2. **Change 2a: Spike `logical_scrapers` actor** -- < $0.01. Gates whether we get email/phone from Instagram.
3. **Change 2b: Instagram profile enrichment** -- implement with whichever actor the spike validates.
4. **Change 3: Website deep crawl** -- `vdrmota/contact-info-scraper` on discovered websites.
5. **Change 4: Read-path updates** -- CSV + UI columns.
6. **Schema migration** -- runs once at startup. All 3 new columns added together.

## Estimated Apify Cost

| Step | Actor | Cost |
|------|-------|------|
| Spike (logical_scrapers) | `logical_scrapers/instagram-profile-scraper` | < $0.01 |
| Instagram profiles (248) | TBD by spike | ~$0.50 at $2/1K |
| Website crawl | `vdrmota/contact-info-scraper` | Free tier ($5 credits) |
| **Total** | | **~$1-2** |

## Test Plan

### Parser Tests (`tests/test_enrich.py`)

**Bio email extraction:**
- `parse_bio("Contact: booking@studio.com")` -> emails: `["booking@studio.com"]`
- `parse_bio("photo@2x.png")` -> emails: `[]`
- `parse_bio("email me at hello@example.com for bookings")` -> emails: `["hello@example.com"]`
- `parse_bio("")` -> emails: `[]`, phones: `[]`, social_handles: `[]`

**Bio phone extraction:**
- `parse_bio("Call (619) 555-1234")` -> phones match
- `parse_bio("Call 619-555-1234")` -> phones match
- `parse_bio("Call 619.555.1234")` -> phones match
- `parse_bio("#sandiegophotographer #12345")` -> phones: `[]`

**Social handle extraction (keyword-prefix required):**
- `parse_bio("IG: @somename")` -> `["instagram:somename"]`
- `parse_bio("instagram @my_handle")` -> `["instagram:my_handle"]`
- `parse_bio("insta: coolperson")` -> `["instagram:coolperson"]`
- `parse_bio("twitter.com/myhandle")` -> `["twitter:myhandle"]`
- `parse_bio("x.com/myhandle")` -> `["twitter:myhandle"]`
- `parse_bio("linkedin.com/in/john-doe")` -> `["linkedin:in/john-doe"]`
- `parse_bio("tiktok @dancer123")` -> `["tiktok:dancer123"]`
- `parse_bio("youtube.com/@channelname")` -> `["youtube:channelname"]`

**False-positive tests (MUST NOT match):**
- `parse_bio("@everyone come to the event")` -> social_handles: `[]`
- `parse_bio("Photo by @americanportra")` -> social_handles: `[]`
- `parse_bio("Vendor Team @westandmadisonevents")` -> social_handles: `[]`
- `parse_bio("#SDCreatives #sandiegophotographer")` -> social_handles: `[]`
- `parse_bio("Contact @admin for help")` -> social_handles: `[]`

### Migration Tests (`tests/test_migration.py`)

- `test_migrate_adds_new_columns`: verify 3 new columns exist after migration
- `test_migrate_idempotent`: run `migrate_db()` twice, no error
- `test_migrate_preserves_data`: insert lead, migrate, data intact
- `test_fresh_db_then_migrate`: `init_db()` then `migrate_db()`, no error

### Selection Logic Tests (`tests/test_enrich.py`)

- `test_bio_enrich_selects_missing_email`: lead with bio, no email -> selected
- `test_bio_enrich_selects_missing_phone`: lead with bio + email, no phone -> selected
- `test_bio_enrich_selects_missing_social`: lead with bio + email + phone, no social -> selected
- `test_bio_enrich_skips_complete_lead`: lead with all 3 fields -> NOT selected
- `test_bio_enrich_skips_no_bio`: lead with no bio/profile_bio -> NOT selected
- `test_ig_profile_selects_unenriched`: IG lead, `ig_profile_enriched_at IS NULL` -> selected
- `test_ig_profile_skips_enriched`: IG lead, `ig_profile_enriched_at` set -> NOT selected
- `test_ig_profile_ignores_enriched_at`: IG lead, `enriched_at` set but `ig_profile_enriched_at NULL` -> selected
- `test_ig_profile_skips_non_instagram`: FB lead -> NOT selected

### Integration Tests

- `test_enrich_does_not_overwrite_existing_email`: COALESCE preserves first-write
- `test_social_handles_json_roundtrip`: write `["instagram:user"]`, `json.loads()` returns list
- `test_bio_not_mutated_by_profile_enrichment`: `bio` unchanged after profile enrichment writes `profile_bio`

## Most Likely Way This Plan Is Wrong

The `logical_scrapers/instagram-profile-scraper` may also fail to return email/phone fields -- it's a third-party actor and its mobile API access may be unreliable or broken. If both Instagram actor spikes fail, the only paths to email/phone are:

1. Bio parsing (Change 1) -- extracts contact info people typed into their bios
2. Website crawling (Change 3) -- extracts from personal/business websites
3. Manual lookup -- not scalable but some high-value leads justify it

In that scenario, the realistic yield is: bio parsing finds ~5-15% of leads with some contact info, website crawling finds another ~10-20% of leads that have websites. Combined, we might get from 24 emails to 60-80 emails. Not transformative, but a real improvement.

## Feed-Forward

- **Hardest decision:** Whether to invest in alternative Instagram actors vs. accepting that email/phone from Instagram is fundamentally limited. Chose to spike `logical_scrapers` because the cost is < $0.01 and it either works or we have a definitive answer. Bio parsing + website crawling are the reliable baseline regardless.
- **Rejected alternatives:** (1) Maigret OSINT -- aggressive scraping, brand risk. (2) Instagram Graph API -- requires target to be business account + our own authenticated Facebook page, impractical for cold leads. (3) Overwriting `bio` with profile biography -- destroys provenance. (4) Comma-separated social_handles -- handles can contain commas, JSON is unambiguous. (5) Second-pass website crawl -- replaced with inline crawl after profile enrichment + `vdrmota` actor for deeper crawl.
- **Least confident:** Whether the keyword-prefix-only regex approach misses real social handles listed as bare `@handle`. After implementation, spot-check: `SELECT bio FROM leads WHERE bio LIKE '%@%' AND social_handles IS NULL LIMIT 20`.
