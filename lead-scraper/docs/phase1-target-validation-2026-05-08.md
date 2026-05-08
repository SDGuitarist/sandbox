# Phase 1: Target Validation Findings (FINAL)

**Date:** 2026-05-08
**Plan:** docs/plans/2026-05-08-feat-filmmaker-tool-targets-10k-expansion-plan.md
**Phase:** Work - Phase 1 (Manual Target Validation) -- COMPLETE

---

## Facebook Groups -- FINAL

### All verified groups with real member counts

**Already in config (2 groups):**

| Group | URL | Members |
|-------|-----|---------|
| San Diego Actors and Filmmakers | `/groups/1488967914699762/` | 18,900 |
| Mexican Filmmakers SD | `/groups/mexicanfilmmakerssd/` | -- |

**New groups to add (13 groups, verified):**

| # | Group | URL | Members | Last Post | Category |
|---|-------|-----|---------|-----------|----------|
| 1 | San Diego Photographers | `/groups/SanDiegoPhotographers/` | 13,400 | May 5 | Adjacent - photo |
| 2 | San Diego Actors | `/groups/sandiegoactors/` | 9,500 | Today | Performer |
| 3 | SD Film Production Network | `/groups/sandiegofilmnetwork/` | 6,900 | Today | Filmmaker - core |
| 4 | SD & TJ Film Community (Film Consortium) | `/groups/filmconsortiumsd/` | 5,300 | Today | Filmmaker - core |
| 5 | SD 48 Hour Film Project | `/groups/SanDiego48HFP/` | 5,300 | Today | Filmmaker - core |
| 6 | Film/Video Production Crew SD | `/groups/audiovisualproductioncrewsd/` | 4,900 | Today | Filmmaker - crew |
| 7 | CASTNCREWSD | `/groups/castncrew/` | 3,300 | Today | Filmmaker - crew |
| 8 | SDSU Theatre and Film | `/groups/SDSUTheatreTVAndFilm/` | 1,900 | Yesterday | Filmmaker - institutional |
| 9 | SD Women's Film Network | `/groups/244108549311595/` | 1,800 | May 6 | Filmmaker - core |
| 10 | SD Writers | `/groups/SanDiegoWriters/` | 1,500 | Today | Writing (Tier 1 audience) |
| 11 | SD Media Pros | `/groups/sdmediapros/` | 1,300 | Today | Media - broad |
| 12 | SD YouTubers & Content Creators | `/groups/257380068144396/` | 567 | Private | Adjacent - creators |
| 13 | BB: SD Music Community | `/groups/BBSanDiegoCA/` | 365 | Today | Composers (Tier 3 audience) |

**Total new members: 56,032 across 13 groups**
**Total after expansion: 15 groups (2 existing + 13 new)**

### Groups eliminated

**Dead/deleted (3):** SD Premiere Pro Users, SD Photographers 2nd, SD Modeling & Photography
**Too small (1):** San Diego Filmmakers (28 members)
**Tool-specific SD groups (0 found):** All ~25 tool-specific searches returned nothing. Confirmed: filmmakers don't organize by tool at the local level.

---

## Instagram Hashtags -- FINAL

Source: Perplexity heuristic estimates + Google Sheet audit. Instagram removed public post counts in 2022. Estimates are directional, not precise.

**KEEP (4 hashtags -- add to config):**

| Hashtag | Est. Posts | SD Signal | Notes |
|---------|-----------|-----------|-------|
| SanDiegoFilmCommunity | 100-500 | Yes | Strongest community tag |
| SanDiegoCinematography | 50-200 | Yes | Strongest cinematography tag for SD |
| SanDiegoDocumentary | 50-200 | Yes | Doc community active in SD |
| SDIndieFilm | 50-150 | Yes | Active indie film tag |

**BORDERLINE (5 hashtags -- verify in IG app before adding):**

| Hashtag | Est. Posts | SD Signal | Notes |
|---------|-----------|-----------|-------|
| SanDiegoComposer | ~25 | Yes | Borderline on volume |
| SDCinematographer | ~25 | Yes | Borderline on volume |
| SanDiegoDP | ~25 | Yes | Small but on-target |
| SanDiegoScreenwriter | ~25 | Yes | Borderline on volume |
| SDFilmCrew | ~25 | Yes | Borderline on volume |

**SKIP (19 hashtags):**

All software+SD combos (PremiereProSD, DaVinciResolveSD, FinalCutProSD, BlenderSD), all ambiguous "SD" abbreviations (SDColorist, SDVFX, SDComposer, SDSoundDesign), AIFilmmaking (huge but no SD signal), and remaining low-volume tags.

**Total Instagram after expansion:** 16 existing + 4 confirmed KEEPs + up to 5 borderlines = 20-25 hashtags
**max_profiles:** Increase from 100 to 400

---

## Eventbrite Keywords -- FINAL

**8 new keywords to add:**

| # | Keyword |
|---|---------|
| 1 | screenwriting San Diego |
| 2 | cinematography San Diego |
| 3 | film festival San Diego |
| 4 | indie film San Diego |
| 5 | documentary San Diego |
| 6 | short film San Diego |
| 7 | video editing San Diego |
| 8 | filmmaking San Diego |

**Total after expansion:** 14 existing + 8 new = 22 (under 25 cap, 3 slots remaining)

---

## Final Scrape-Realistic Estimate

### Facebook (13 new groups, 56,032 total members)

| Group | Members | Est. 10% | Est. 20% |
|-------|---------|----------|----------|
| SD Photographers | 13,400 | 1,340 | 2,680 |
| SD Actors | 9,500 | 950 | 1,900 |
| SD Film Production Network | 6,900 | 690 | 1,380 |
| SD & TJ Film Community | 5,300 | 530 | 1,060 |
| SD 48 Hour Film Project | 5,300 | 530 | 1,060 |
| Film/Video Crew SD | 4,900 | 490 | 980 |
| CASTNCREWSD | 3,300 | 330 | 660 |
| SDSU Theatre & Film | 1,900 | 190 | 380 |
| SD Women's Film Network | 1,800 | 180 | 360 |
| SD Writers | 1,500 | 150 | 300 |
| SD Media Pros | 1,300 | 130 | 260 |
| SD YouTubers | 567 | 57 | 113 |
| BB: SD Music Community | 365 | 37 | 73 |
| **Subtotal (new)** | **56,032** | **5,604** | **11,206** |

### Combined

| Source | Conservative (10%) | Optimistic (20%) |
|--------|-------------------|-----------------|
| Facebook (13 new groups) | 5,604 | 11,206 |
| Instagram (20-25 hashtags, cap 400) | 250 | 350 |
| Eventbrite (22 keywords) | 150 | 400 |
| Existing leads in DB | 1,211 | 1,211 |
| **Total** | **~7,215** | **~13,167** |

### vs. Tony's Target

| Target | Estimate | Verdict |
|--------|----------|---------|
| 2,000 (stop threshold) | 7,215+ | Cleared by 3.6x |
| 10,000 (Tony's ask) | 7,215 - 13,167 | Conservative falls short. Optimistic exceeds. |

**Cross-source dedup will reduce totals.** Same person in SD Film Production Network and 48HFP is common. Expect 10-20% overlap. Net realistic range: **~6,000-11,000.**

---

## Go/No-Go Decision (FINAL)

**Verdict: FULL GREEN LIGHT**

- Conservative estimate (7,215) is 3.6x the stop threshold.
- After dedup (~6,000-11,000 net), realistic range brackets Tony's 10K target.
- SD-only approach is fully viable. No need to revisit the constraint.
- No need for Meetup or LinkedIn as secondary sources for this expansion.

**Proceed to Phase 2** (config.py update) with all verified targets.

---

## Phase 2 Config Changes (Ready to Execute)

### config.py SOURCES changes:

**Facebook:** Add 13 group URLs to `SOURCES["facebook"]["groups"]`
**Instagram:** Add 4 confirmed hashtags (+ up to 5 borderlines after app verification) to `SOURCES["instagram"]["hashtags"]`. Increase `max_profiles` from 100 to 400.
**Eventbrite:** Add 8 keywords to `SOURCES["eventbrite"]["keywords"]`

---

## Feed-Forward

- **Hardest decision:** Whether to include adjacent groups (Photographers 13.4K, Actors 9.5K, YouTubers 567). They inflate the numbers but dilute filmmaker focus. Included because the enrichment pipeline classifies segments and filmmaker segment gets priority outreach.
- **Rejected alternatives:** (1) Waiting for borderline Instagram verification before proceeding. Rejected because 4 KEEPs are enough and borderlines are additive. (2) Excluding institutional groups (SDSU). Included because students are workshop-age and interested.
- **Least confident:** The 10-20% scrape rate. The Facebook scraper extracts post authors + top commenters, not member lists. Low-post-frequency groups yield less. The Photographers group (13.4K) could yield 5% instead of 10% if most members lurk.
- **Surprises:**
  - SD Actors and Filmmakers (18.9K) was already in config as the unnamed "general group." Biggest group, already being scraped.
  - Premiere Pro Users Group (Tony's pick) is dead. Worth mentioning.
  - Alex's group memberships surfaced 7 groups web search completely missed. Best discovery method.
  - Real member counts (avg ~4,300) are 4-8x the original plan assumption (500-1,000).
  - Tool-specific SD groups confirmed nonexistent (0/25). Filmmakers organize by role and city, not by software.
