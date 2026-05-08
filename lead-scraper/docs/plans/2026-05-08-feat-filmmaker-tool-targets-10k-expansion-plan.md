---
title: "feat: Expand Scraper Targets to 10K via Filmmaker Tool Communities"
type: feat
status: active
date: 2026-05-08
origin: docs/brainstorms/2026-05-08-filmmaker-tool-targets-10k-brainstorm.md
feed_forward:
  risk: "Most SD-specific tool groups may not exist on Facebook. Volume target (10K) may require revisiting the SD-only constraint."
  verify_first: true
---

# feat: Expand Scraper Targets to 10K via Filmmaker Tool Communities

## Overview

Scale the lead scraper from ~1,200 leads to 10,000+ by expanding Facebook groups, Instagram hashtags, and Eventbrite keywords to cover filmmaker tool communities. Tony Amat (May 7 meeting) validated the scraper but wants 10x volume for the October Spark Studios workshop. He specifically named Premiere Pro SD groups and DaVinci Resolve users.

This is primarily a **config expansion + manual research task**, not a code change. The only code change is increasing Instagram's `max_profiles` cap.

## Problem Statement / Motivation

Current config has only 2 Facebook groups, 16 Instagram hashtags, and 14 Eventbrite keywords, all generic creative/musician terms. Zero filmmaker-tool-specific communities. Filmmakers organize around their tools (editing software, cameras, screenwriting apps), and those communities are high-intent targets for the workshop.

(See brainstorm: `docs/brainstorms/2026-05-08-filmmaker-tool-targets-10k-brainstorm.md` for full toolkit map and key decisions.)

## Proposed Solution

Three phases: (1) manual validation of which targets actually exist, (2) config.py update, (3) run and monitor.

### Key Decisions (from brainstorm)

1. **Filmmakers first, adjacent creatives secondary** -- enrichment pipeline classifies segments
2. **Volume-first across all tools** -- no tier prioritization, scrape everything simultaneously
3. **SD-specific groups only** -- avoids Jamie Lee Kendall location problem
4. **All three sources** -- Facebook + Instagram + Eventbrite
5. **One-time bulk scrape** -- not recurring. $10-30/cycle budget.

## Technical Considerations

### Config Format (exact syntax for each source)

All changes go in `config.py` SOURCES dict (lines 42-99):

**Facebook** -- append group URLs to the `groups` list:
```python
"groups": [
    # existing
    "https://www.facebook.com/groups/1488967914699762/",
    "https://www.facebook.com/groups/mexicanfilmmakerssd/",
    # new -- add validated URLs here
    "https://www.facebook.com/groups/VALIDATED_GROUP_ID/",
]
```
All groups go in one Apify call. No per-group cost. Watch 300s timeout if 20+ groups.

**Instagram** -- append hashtag strings (no `#`) to the `hashtags` list:
```python
"hashtags": [
    # existing 16 hashtags
    "SanDiegoMusician", "SanDiegoComposer", ...
    # new -- add validated hashtags here
    "SDVideoEditor", "SanDiegoEditor", ...
],
"max_profiles": 400,  # MUST INCREASE from 100 (~35 hashtags x 10 results)
```
**Critical:** `max_profiles` is a GLOBAL limit across all hashtags, not per-hashtag. With 35+ hashtags and `max_profiles: 100`, you get ~3 results per hashtag. Set to 400 (~35 hashtags x 10 results each = 350, rounded up).

**Eventbrite** -- append keyword strings to the `keywords` list:
```python
"keywords": [
    # existing 14 keywords
    "composer showcase", "film composer", ...
    # new -- add validated keywords here
    "video editing San Diego", "screenwriting San Diego", ...
]
```
**Warning:** Eventbrite runs one Apify actor call PER keyword. Going from 14 to 25+ keywords means 25+ separate Apify runs. Most expensive source to scale. Keep additions targeted.

### Scaling Risks

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Facebook 300s Apify timeout with 20+ groups | Scrape fails, fewer leads than expected per source | Split into two batches if needed. Detect by comparing per-source SQLite counts before/after scrape. |
| Instagram max_profiles too low | Most new hashtags return zero results | Set to 400 (math: ~35 hashtags x 10 results). Adjust up if validation confirms 40+ hashtags. |
| Eventbrite cost scales linearly | Budget overrun | Cap at 25 keywords total. Most filmmaker-tool keywords won't return SD events anyway. |
| Enrichment cost at 10K leads | Segment + hook steps call LLMs per lead | Use `--limit` flag on segment/hook. Enrich in batches of 50-100. |

## Implementation Phases

### Phase 1: Manual Target Validation (No Code)

Search Facebook, Instagram, and Eventbrite manually to validate which targets actually exist. Expect 40-60% of tool-specific SD groups won't exist. That's fine. General filmmaker groups carry the volume.

**Facebook groups to search for:**

*General filmmaker (highest volume, most likely to exist):*
- "San Diego Filmmakers"
- "San Diego Indie Film"
- "San Diego Film Community"
- "FilmNet San Diego"
- "San Diego Documentary Filmmakers"
- "48 Hour Film Project San Diego"
- "San Diego Short Film"
- "San Diego Film Crew"

*Tool-specific -- Editing (check if they exist):*
- "Premiere Pro San Diego" / "San Diego Video Editors"
- "DaVinci Resolve San Diego" / "Blackmagic San Diego"
- "Final Cut Pro San Diego"
- "San Diego Post Production"

*Tool-specific -- VFX / Motion Graphics:*
- "After Effects San Diego"
- "Blender San Diego" / "Blender Users San Diego"
- "San Diego VFX" / "San Diego Motion Graphics"

*Tool-specific -- Color Grading:*
- "San Diego Colorists" / "Color Grading San Diego"

*Tool-specific -- Audio / Sound:*
- "Pro Tools San Diego"
- "San Diego Composers" / "San Diego Film Composers"
- "San Diego Sound Design" / "San Diego Audio Post"
- "San Diego Music Production"

*Tool-specific -- Camera / Cinematography:*
- "San Diego Cinematographers" / "San Diego DPs"
- "San Diego Camera Operators"
- "Blackmagic Camera San Diego"
- "Sony Alpha San Diego" / "Sony Filmmakers San Diego"

*Tool-specific -- Writing / Pre-Production:*
- "San Diego Screenwriters" / "Screenwriters San Diego"
- "San Diego Film Writers"
- "Final Draft Users San Diego"

*Tool-specific -- Distribution:*
- "San Diego Film Distribution"

*AI-Adjacent:*
- "AI Filmmaking San Diego" / "AI Video San Diego"

*Adjacent creative (secondary):*
- "San Diego Photographers" (already in high-priority list)
- "San Diego Podcasters"
- "San Diego YouTubers"

**For each group found, record:**
- Full Facebook URL
- Member count
- Last post date (active = post within 30 days)
- SD-specific? (group name or description references San Diego)

**Instagram hashtags to validate:**

For each hashtag, check TWO things:
1. **Post volume:** Does it have 50+ posts? If under 50, skip it.
2. **Local signal:** Do at least some posts geolocate to San Diego or mention SD in captions? A hashtag with 500 posts but zero SD connection is noise.

*Editing:*
- `#SDVideoEditor`, `#SanDiegoEditor`, `#SanDiegoPostProduction`
- `#PremiereProSD`, `#DaVinciResolveSD`, `#FinalCutProSD`

*VFX / Motion Graphics:*
- `#SDVFX`, `#SanDiegoVFX`, `#SanDiegoMotionGraphics`, `#BlenderSD`

*Color Grading:*
- `#SDColorist`, `#SanDiegoColorGrading`

*Audio / Sound:*
- `#SDComposer`, `#SanDiegoComposer`, `#SDSoundDesign`, `#SanDiegoFilmScore`

*Camera / Cinematography:*
- `#SDCinematographer`, `#SanDiegoDP`, `#SanDiegoCinematography`

*Writing:*
- `#SDScreenwriter`, `#SanDiegoScreenwriter`, `#SanDiegoFilmwriter`

*General filmmaker:*
- `#SDIndieFilm`, `#SanDiegoFilmCommunity`, `#SDFilmCrew`, `#SanDiegoDocumentary`

*AI-Adjacent:*
- `#AIFilmmaking`, `#AIFilmmakingSD`

**Eventbrite keywords to validate (check returns current or recent SD events):**

*Tool-specific:*
- "Premiere Pro San Diego"
- "DaVinci Resolve San Diego"
- "Blender San Diego"
- "Pro Tools San Diego"

*Workflow-specific:*
- "video editing San Diego"
- "screenwriting San Diego"
- "screenplay San Diego"
- "film writing San Diego"
- "film scoring San Diego"
- "music production San Diego"
- "cinematography San Diego"
- "camera workshop San Diego"
- "VFX San Diego"
- "motion graphics San Diego"

*General filmmaker:*
- "indie film San Diego"
- "short film San Diego"
- "documentary San Diego"
- "film festival San Diego"

*AI-Adjacent:*
- "AI filmmaking San Diego"
- "AI video San Diego"

**Note:** Cap total Eventbrite keywords at 25 (including existing 14 = only 11 new slots). The list above has 20 candidates. Validate all, then pick the top 11 that return actual SD events. Prioritize generic terms ("video editing San Diego") over tool-specific terms ("Premiere Pro San Diego") since generic terms return more events.

**Output:** A validated checklist split into "confirmed" and "doesn't exist" for each source.

**Go/no-go gate:** After validation, estimate total **scrape-realistic** leads from confirmed targets. Do NOT use raw member counts or post volumes. The scraper does not extract all members. Use these conversion rates:

- **Facebook:** The scraper extracts post authors + top commenters from recent posts, not the full member list. Estimate ~10-20% of group members will appear as scrapable leads. A 500-member group yields ~50-100 leads.
- **Instagram:** Capped by `max_profiles` (400 total across all hashtags). With dedup, expect ~250-350 unique leads regardless of hashtag count.
- **Eventbrite:** Yields ~5-20 leads per keyword for SD-scoped events. 25 keywords = ~125-500 leads.

**Threshold:** If scrape-realistic estimate totals under 2,000 leads, STOP and revisit the SD-only constraint before proceeding to Phase 2. If estimate is 2,000-4,000, proceed but flag that 10K requires additional sources (Meetup, LinkedIn, or national groups with location filter). Above 4,000 means the SD-only approach is working.

### Phase 2: Update config.py

After Phase 1 validation:

1. Add all confirmed Facebook group URLs to `SOURCES["facebook"]["groups"]`
2. Add all confirmed Instagram hashtags to `SOURCES["instagram"]["hashtags"]`
3. Increase `SOURCES["instagram"]["max_profiles"]` from 100 to 400
4. Add confirmed Eventbrite keywords to `SOURCES["eventbrite"]["keywords"]` (cap at 25 total)

**Files changed:** `config.py` only.

### Phase 3: Run Scrape and Monitor

```bash
# 1. Record baseline counts BEFORE scraping
sqlite3 leads.db "SELECT source, COUNT(*) as count FROM leads GROUP BY source"
sqlite3 leads.db "SELECT COUNT(*) as total FROM leads"

# 2. Run the full scrape
python run.py scrape --location "San Diego, CA"

# 3. Record post-scrape counts and compare
sqlite3 leads.db "SELECT source, COUNT(*) as count FROM leads GROUP BY source"
sqlite3 leads.db "SELECT COUNT(*) as total FROM leads"

# 4. Dry-run dedup first -- review proposed merges before applying
python run.py dedup
# Review the output: check each duplicate group makes sense
# Only then apply:
python run.py dedup --apply

# 5. Enrich in batches (control LLM costs)
python run.py enrich --step bio
python run.py enrich --step website
python run.py enrich --step segment --limit 100
python run.py enrich --step hook --limit 100
```

**Note:** There is no `python run.py stats` command. Use the SQLite queries above for before/after counts.

**Monitor:**
- Per-source lead count before vs. after (SQLite queries above)
- Apify cost for this cycle (check Apify dashboard)
- Facebook scraper: if post-scrape Facebook count barely increased despite 15+ groups, the 300s timeout likely fired. Split groups into two config batches and re-run.
- Dedup dry-run output: review merge groups before applying. Watch for false-positive name matches (common names matching unrelated people across sources).

## Acceptance Tests

### Config Validation (Phase 2)
- WHEN config.py is updated THE SYSTEM SHALL parse without syntax errors: `python -c "from config import SOURCES; print('OK')"`
- WHEN Facebook groups are expanded THE SYSTEM SHALL have 10+ groups: `python -c "from config import SOURCES; assert len(SOURCES['facebook']['groups']) >= 10, f'Only {len(SOURCES[\"facebook\"][\"groups\"])} groups'"`
- WHEN Instagram max_profiles is updated THE SYSTEM SHALL be 400: `python -c "from config import SOURCES; assert SOURCES['instagram']['max_profiles'] == 400"`
- WHEN Eventbrite keywords are expanded THE SYSTEM SHALL have at most 25 total: `python -c "from config import SOURCES; assert len(SOURCES['eventbrite']['keywords']) <= 25, f'{len(SOURCES[\"eventbrite\"][\"keywords\"])} exceeds 25 cap'"`

### Scrape Execution (Phase 3)
- WHEN `python run.py scrape --location "San Diego, CA"` runs THE SYSTEM SHALL report insert/skip/reject counts per source and exit 0
- WHEN Facebook has 15+ groups THE SYSTEM SHALL show a Facebook lead count increase in post-scrape SQLite query. If count barely changed, Apify timeout fired.
- WHEN Instagram runs with max_profiles=400 THE SYSTEM SHALL show Instagram lead count increase. If zero new leads, the Apify actor may have failed.
- WHEN per-source counts are compared before/after THE SYSTEM SHALL show increases for at least 2 of 3 sources (Facebook, Instagram, Eventbrite)

### Dedup Verification (Phase 3)
- WHEN `python run.py dedup` runs (dry run, no --apply) THE SYSTEM SHALL list duplicate groups with lead IDs, names, and match type (email or name)
- WHEN reviewing dedup output, operator SHALL verify no false-positive name matches (e.g., two different "John Smith" leads from different sources that are actually different people)
- WHEN `python run.py dedup --apply` runs after manual review THE SYSTEM SHALL report merge count and removed duplicate count

### Error Cases
- WHEN a Facebook group URL is invalid or private THE SYSTEM SHALL skip it and continue with remaining groups
- WHEN an Instagram hashtag has zero posts THE SYSTEM SHALL return zero results for that hashtag without failing the overall scrape
- WHEN an Eventbrite keyword returns no SD events THE SYSTEM SHALL return empty results without failing

### Verification Commands
```bash
# Config checks
python -c "from config import SOURCES; print(f'FB groups: {len(SOURCES[\"facebook\"][\"groups\"])}')"
python -c "from config import SOURCES; print(f'IG hashtags: {len(SOURCES[\"instagram\"][\"hashtags\"])}')"
python -c "from config import SOURCES; print(f'IG max_profiles: {SOURCES[\"instagram\"][\"max_profiles\"]}')"
python -c "from config import SOURCES; print(f'EB keywords: {len(SOURCES[\"eventbrite\"][\"keywords\"])}')"

# Lead counts (run before AND after scrape)
sqlite3 leads.db "SELECT source, COUNT(*) as count FROM leads GROUP BY source"
sqlite3 leads.db "SELECT COUNT(*) as total FROM leads"

# Dedup dry run
python run.py dedup
```

## Dependencies & Risks

| Dependency | Status | Risk |
|-----------|--------|------|
| Apify account with sufficient credits | Active | Low -- $10-30 budget confirmed |
| Facebook group URLs (manual research) | Phase 1 | Medium -- many tool-specific groups may not exist |
| Instagram hashtag validation | Phase 1 | Medium -- invented hashtags may have zero volume |
| Eventbrite keyword validation | Phase 1 | Low -- generic film keywords will return results |

**Biggest risk:** Phase 1 reveals too few SD-specific groups exist. Mitigation: general filmmaker groups (San Diego Filmmakers, 48 Hour Film Project, FilmNet) will carry the volume. If scrape-realistic estimate after Phase 1 is under 2,000, revisit the SD-only constraint before proceeding (see go/no-go gate in Phase 1). If 2,000-4,000, proceed but plan additional sources to close the gap to 10K.

## Sources & References

- **Origin brainstorm:** [docs/brainstorms/2026-05-08-filmmaker-tool-targets-10k-brainstorm.md](docs/brainstorms/2026-05-08-filmmaker-tool-targets-10k-brainstorm.md) -- full toolkit map, key decisions (volume-first, SD-only, all three sources, one-time scrape)
- **Config file:** `config.py:42-99` (SOURCES dict)
- **Facebook scraper:** `scrapers/facebook.py` (one Apify call for all groups)
- **Instagram scraper:** `scrapers/instagram.py` (global max_profiles limit)
- **Eventbrite scraper:** `scrapers/eventbrite.py` (one Apify call per keyword)
- **Ingest uniqueness:** `ingest.py` uses `INSERT OR IGNORE` keyed on `UNIQUE(source, profile_url)`. Same person from two sources creates two rows. Cross-source dedup is a separate step.
- **Cross-source dedup:** `run.py dedup` merges duplicates in two passes: (1) `LOWER(email)` exact match, (2) `LOWER(TRIM(name))` exact match for remaining leads where email IS NULL. Always dry-run first (`python run.py dedup`), review output, then `python run.py dedup --apply`.
- **Location lesson:** Jamie Lee Kendall incident (feedback_scraper-location-signal.md)
- **Tony meeting notes:** `~/Documents/dev-notes/2026-05-07.md:30` ("wants 10x volume")

## Feed-Forward

- **Hardest decision:** SD-specific only limits volume. Realistic estimate is 3,000-6,000, not 10,000. May need to revisit after Phase 1.
- **Rejected alternatives:** National groups with location filtering (higher volume but Jamie Lee problem). Risk-tier prioritization (unnecessary since enrichment classifies).
- **Least confident:** Whether Phase 1 will yield enough confirmed targets to justify the SD-only constraint. The go/no-go gate (under 2,000 scrape-realistic = stop and revisit) will force the decision.
