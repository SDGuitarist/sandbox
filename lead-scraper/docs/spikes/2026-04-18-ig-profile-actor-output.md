# Instagram Profile Actor Spike Results

**Date:** 2026-04-19
**Actor:** `apify/instagram-profile-scraper`
**Input:** `{"usernames": ["_mare_collective_", "_kaizen.fm"]}`
**Cost:** < $0.01
**Run ID:** OmDAcoB2i3D0f8tsf

## Profile-Level Fields Returned

### Account 1: `_kaizen.fm` (personal account, DJ)

```json
{
  "inputUrl": "https://www.instagram.com/_kaizen.fm",
  "id": "77790830317",
  "username": "_kaizen.fm",
  "url": "https://www.instagram.com/_kaizen.fm",
  "fullName": "Smokey Chaiyavong",
  "biography": "KAIZEN\nTech House × Bass House\nIsland • Hip Hop • R&B\nNorCal ⇄ San Diego 🌊\nBookings + Collabs ↓ 🌙🐺",
  "externalUrls": [],
  "followersCount": 152,
  "followsCount": 454,
  "highlightReelCount": 0,
  "isBusinessAccount": false,
  "businessCategoryName": "DJ",
  "private": false,
  "verified": false,
  "igtvVideoCount": 0,
  "relatedProfiles": [],
  "postsCount": 64
}
```

### Account 2: `_mare_collective_` (business account, photographer)

```json
{
  "inputUrl": "https://www.instagram.com/_mare_collective_",
  "id": "47817381608",
  "username": "_mare_collective_",
  "url": "https://www.instagram.com/_mare_collective_",
  "fullName": "Maré Collective Editorial Portraits & Brand Films | San Diego",
  "biography": "Henry Arroyo\nEditorial Portraits & Brand Films | San Diego\nElevating creators, models & personal brands\nCinematic. Intentional. Impactful.\nBook via DM",
  "externalUrls": [],
  "followersCount": 40,
  "followsCount": 19,
  "highlightReelCount": 0,
  "isBusinessAccount": true,
  "businessCategoryName": "None",
  "private": false,
  "verified": false,
  "igtvVideoCount": 0,
  "relatedProfiles": [],
  "postsCount": 35
}
```

## Key Findings

### Fields PRESENT
- `biography` (full bio text, not truncated)
- `externalUrls` (array, not `externalUrl` singular)
- `fullName`
- `username`
- `isBusinessAccount`
- `businessCategoryName`
- `followersCount`, `followsCount`, `postsCount`
- `latestPosts` (array of recent posts with full data)

### Fields ABSENT
- `publicEmail` -- NOT returned
- `publicPhoneNumber` -- NOT returned
- `public_email` -- NOT returned
- `public_phone_number` -- NOT returned
- No email field of any kind
- No phone field of any kind

### Field Name Corrections
- `externalUrls` (plural array), NOT `externalUrl` (singular string)
- Both accounts returned `externalUrls: []` (empty)

## Implications for the Plan

1. **No direct email/phone from this actor.** The `apify/instagram-profile-scraper` does NOT return email or phone fields. These require the mobile API with cookies, which this actor doesn't use.

2. **`biography` is the main value.** Full bio text is returned (not truncated like the hashtag scraper caption). Bio parsing (Change 2) will extract any contact info people put in their bio text.

3. **`externalUrls` needs plural handling.** Both test accounts had empty arrays, but accounts with link-in-bio will populate this. The plan assumed `externalUrl` (singular string) -- needs to be updated to handle an array.

4. **`isBusinessAccount` and `businessCategoryName` are useful metadata.** Can be stored for filtering/prioritization.

5. **The actor also returns `latestPosts`** with full captions, mentions, hashtags, and tagged users -- additional data for contact extraction from post text.
