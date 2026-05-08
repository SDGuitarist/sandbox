---
title: "10K Target Expansion: Filmmaker Tool Communities"
problem: Scale lead scraper from 1,211 to 10K+ by targeting filmmaker tool communities
solution: Expand Facebook groups (2->15), Instagram hashtags (15->19, max_profiles 100->400), Eventbrite keywords (14->20). SD-specific only.
tags: [lead-scraper, facebook, instagram, eventbrite, config, scaling, filmmaker, apify]
date: 2026-05-08
trigger: Tony Amat meeting (May 7) -- wants 10x volume for October Spark Studios workshop
---

# 10K Target Expansion: Filmmaker Tool Communities

## What Happened

Tony Amat validated the lead scraper but wanted 10x volume (1,500 -> 10,000+). We mapped every tool filmmakers use to find SD-specific communities, validated them via web search + Perplexity browser audits + manual Instagram checks, then updated config.py and ran the scrape.

**Result:** 1,211 -> 2,901 leads in one scrape cycle (+1,690, 140% increase).

## Key Lessons

### 1. Tool-specific local groups don't exist

Searched for ~25 tool-specific SD Facebook groups (Premiere Pro San Diego, DaVinci Resolve San Diego, After Effects San Diego, etc.). Found exactly ONE (Premiere Pro Users Group), and it was deleted/unavailable. Filmmakers organize by role and city ("San Diego Filmmakers," "SD 48 Hour Film Project"), not by software.

**Apply when:** Planning community-based lead scraping for any creative vertical. Don't assume tool-specific local groups exist. Search for role-based and community-based groups instead.

### 2. Your own group memberships are the best discovery method

Web search found 5 viable groups. Browsing Alex's Facebook group memberships surfaced 7 additional high-quality groups that web search completely missed. Including the largest one: SD Actors and Filmmakers (18.9K members, already in config as the unnamed "general group").

**Apply when:** Expanding Facebook group targets. Always check what groups the user is already a member of before doing web search.

### 3. Perplexity browser assistant for Facebook audits

Perplexity's browser assistant can visit Facebook group pages and extract member counts, last post dates, and description text. This eliminated the need for manual browsing of 16 groups. It correctly identified 3 deleted groups and 1 too-small group.

**Cannot do:** Instagram hashtag validation. Instagram blocks automated browsing and removed public post counts in 2022. Use a Google Sheet with deep links and manual phone tapping instead (~15 min for 28 hashtags).

### 4. Instagram max_profiles is a global cap, not per-hashtag

The Apify Instagram hashtag scraper's `max_profiles` setting caps total results across ALL hashtags, not per-hashtag. With 19 hashtags and max_profiles=100, you get ~5 results per hashtag. Bumping to 400 yielded +762 new leads (vs. baseline 738).

**Apply when:** Adding Instagram hashtags to config. Always increase max_profiles proportionally: target ~10-20 results per hashtag.

### 5. Facebook 300s Apify timeout is real at 15+ groups

The Facebook scraper sends all groups in one Apify call. With 15 groups, it hit the 300s timeout and returned ~85% of results (1,627 of ~1,928). Not fatal but leaves leads on the table.

**Fix:** Split groups into 2 batches of 7-8 and run the scrape command twice.

### 6. Scrape-realistic estimates need real member counts

Original plan assumed 500-1,000 average members per SD Facebook group. Reality was ~4,300 average. The estimate flipped from "barely viable" (2,436) to "green light" (7,215+). Always get real member counts before estimating.

### 7. Empty leads.db is a recurring hazard

The main leads.db was found empty (0 bytes) at start of Phase 3. The safe backup from the same day had all 1,211 leads. This is the third time data loss has occurred in this project.

**Always:** Check `ls -la leads.db` file size before running any scrape. If 0 bytes, restore from latest backup-safe file before proceeding.

## Numbers

| Metric | Before | After |
|--------|--------|-------|
| Facebook groups | 2 | 15 |
| Instagram hashtags | 15 | 19 |
| Instagram max_profiles | 100 | 400 |
| Eventbrite keywords | 14 | 20 |
| Total leads | 1,211 | 2,901 |
| New leads (one cycle) | -- | +1,690 |

## Files Changed

- `config.py` (SOURCES dict: groups, hashtags, keywords, max_profiles)

## Follow-up

1. Split Facebook groups into 2 batches to recover ~300 missed leads
2. Run segment + hook enrichment on 1,690 new leads
3. Re-run dedup after Hunter.io adds emails
4. Second scrape cycle in a few weeks for new group activity
