# Browser Outreach Sender -- Brainstorm

**Date:** 2026-05-08
**Status:** Complete
**Next:** `/workflows:plan`

## What We're Building

Two new modules inside the existing lead scraper that replace Perplexity's browser assistant:

1. **AI Quality Gate** -- Claude API + `requests` to verify hooks before sending
2. **Browser Sender** -- Playwright (headed Chrome) to send approved messages via Facebook Messenger and Instagram DM

Together they complete the outreach pipeline: lead scraper generates messages, quality gate verifies them, browser sender delivers them.

## Why We're Building This

- Perplexity browser assistant has a usage cap ($20/mo Pro plan). We hit it today.
- Original target was 3,000-6,000 leads by May 30 (23 sending days inclusive). Realistic ceiling with 3 accounts at safe send rates is 1,520-1,770 (see Daily Capacity Model). Reaching 3,000+ requires 5+ accounts or accepting higher restriction risk.
- At current manual pace (15-20/day), we'd only reach ~440. Automation with 3 accounts targets 75-120/day at steady state.
- Owning the automation removes the dependency entirely. Cost shifts to Claude API (~$0.01-0.03/lead) and zero cap on Playwright.

## Why This Approach (Hybrid)

**Approach chosen:** `requests` + Claude API for verification, Playwright only for DM sending.

**Why not Playwright for everything?** Browser overhead is wasteful for verification when the verify URL is a public web page. HTTP fetch does the same job in milliseconds vs. 2-5 second page loads. However, the public/login-walled split varies by pipeline stage (see DB Reality below).

**Why not Browser-Use AI agent?** Our workflow is completely structured (known URLs, known messages, known steps). AI navigation adds unpredictability to a problem that doesn't require it. We're replacing a usage cap, not replacing intelligence.

**Core insight:** The lead scraper already has the intelligence (hooks, messages, templates). We just need a reliable delivery mechanism and a safety net for hallucinations.

**DB Reality -- verify URL breakdown (queried 2026-05-08):**

| Pipeline Stage | Total Rows | Has Verify URL | Public (fetchable) | Login-walled (IG/FB) | Missing URL |
|---|---|---|---|---|---|
| All hooks in DB | 1,121 | 1,121 | 821 (73.2%) | 300 (26.8%) | 0 |
| Outreach queue (all statuses) | 210 | 204 | 140 (66.7% of total) | 64 (30.5% of total) | 6 (2.9%) |
| Current drafts | 7 | 7 | 1 (14.3%) | 6 (85.7%) | 0 |

Note: Outreach queue percentages are of 210 total rows (not 204). The 6 rows with missing verify URLs have no hook_source_url and cannot be AI-verified -- they go to `needs_review`.

**Implication:** The hybrid approach (requests for public, skip for login-walled) works well at scale across the full DB. But for the current draft batch, 6/7 leads have login-walled verify URLs -- meaning the AI quality gate can only independently verify 1 of 7 right now. As more drafts are generated from the broader pool, the 73% public ratio will hold. The quality gate's value increases with volume.

## Platform Risk

**Meta does not publish safe DM automation thresholds.** There is no documented "X messages/day is safe" number. Facebook and Instagram Terms of Service prohibit automated messaging and unsolicited promotional messages. Accounts may be temporarily restricted (24-72 hour messaging blocks) or permanently banned.

**What we know:**
- Restrictions are triggered by volume, velocity, and recipient behavior (reports, blocks)
- New accounts are restricted more aggressively than established ones
- Unsolicited DMs to non-connections carry higher risk than messages to friends/followers
- There is no appeal process for permanent messaging bans

**Required mitigations (non-negotiable):**

1. **Go/no-go decision:** Before launching the sender at scale, user must explicitly accept the risk that accounts may be restricted or banned. This is a business decision, not a technical one.
2. **Small live spike test:** First run sends 5-10 messages from the personal account. Wait 24 hours. If no restriction, increase to 15-20. Ramp gradually -- never jump to full capacity on day one.
3. **Kill switch:** The sender must support immediate stop (Ctrl+C or a stop file). If a CAPTCHA, "you're going too fast" warning, or messaging restriction appears, the sender halts and logs the event.
4. **Per-account restriction handling:** If an account hits a restriction, sender automatically marks it `restricted` and stops sending from it. User must manually acknowledge and set a cooldown period (48-72 hours) before the account can resume. Other accounts continue. See Account Status State Machine for exact transitions.
5. **Manual fallback:** If all accounts are restricted, the user must be able to send manually using the same queue. The system degrades to a message list, not a dead tool.

## Key Decisions

### 1. Lives inside the lead scraper project
- Direct SQLite access to `outreach_queue` and `leads` tables
- Shared config, same CLI (`python run.py`)
- No API bridge needed

### 2. Two separate steps, not one loop
- **Step 1:** Run quality gate on a batch (e.g., 50 leads). Review results.
- **Step 2:** Run browser sender on approved leads only.
- Safer -- human can eyeball gate decisions before anything sends.

### 3. Both platforms from day one
- Facebook Messenger + Instagram DM
- Platform inferred from `profile_url` domain (facebook.com vs instagram.com)
- Different send flows for each (Messenger vs IG DM have different UIs)

### 4. Headed browser always
- Visible Chrome window so user can watch, intervene, build trust
- No headless mode (Facebook/Instagram also more likely to detect headless)

### 5. Multiple accounts from Week 1
- Start with personal Facebook account on Day 1
- Create 2-3 additional accounts (Amplify Workshop, Amplify AI business) by end of Week 1
- Structure code so adding accounts is a config change (browser profile per account)
- Round-robin assignment across accounts from the start

## AI Quality Gate -- 9 Failure Modes

These are real failure modes observed in today's outreach batches. The quality gate must screen for all of them.

### Pre-Send Checks (quality gate catches these)

| # | Failure Mode | Check | Priority |
|---|---|---|---|
| 1 | **Wrong person on verify URL** | Name on verify page != DM target name | HIGH |
| 2 | **Hook not findable on verify page** | Specific project/event/claim not on page | HIGH |
| 3 | **Verify URL completely wrong source** | Page topic unrelated to hook and target | MEDIUM |
| 4 | **Duplicate lead** | Same name/handle appears multiple times in batch | HIGH (deterministic) |
| 5 | **Org/brand account** | DM target is a company, not an individual | HIGH (deterministic) |
| 6 | **DM route not valid** | URL is Eventbrite/Linktree/website, not IG or FB | HIGH (deterministic) |
| 7 | **Hook premise doesn't match activity** | Person's actual profile contradicts the hook claim | MEDIUM |
| 9 | **Out-of-audience / geography** | Person clearly not in SoCal or not in creative industries | LOW |

### Runtime Checks (browser sender catches these)

| # | Failure Mode | Check |
|---|---|---|
| 8 | **DMs restricted / inaccessible** | No Message button on profile, friend-only DMs |

### Implementation Priority

**Tier 1 (deterministic, no AI needed):**
- #4 Dedup by name/handle (SQL query)
- #5 Org detection (regex on name: Films, Media, TV, Productions, Agency, LLC, Inc)
- #6 DM route validation (URL domain must be facebook.com or instagram.com)

**Tier 2 (AI-powered, Claude API + web fetch):**
- #1 Name match (fetch verify URL, ask Claude: "Is this page about [lead name]?")
- #2 Hook claim present (fetch verify URL, ask Claude: "Does this page mention [specific claim]?")
- #3 Source relevance (same Claude call can assess overall relevance)
- #7 Activity match (Claude checks if profile type matches workshop audience)

**Tier 3 (nice-to-have):**
- #9 Geography check (Claude can flag if page shows non-SoCal location)

**Login-walled verify URLs (Instagram/Facebook):**
- `requests` will get a blank page for verify URLs on instagram.com or facebook.com
- These leads have `hook_verified=1` from the scraper's **auto/trusted verification** (Tier A bio extraction or same-platform keyword matching). This is NOT independent AI page verification -- it means the scraper found the lead's name + hook keywords on the source page via automated checks, or extracted the hook directly from the bio. It does not mean a human or AI read the page and confirmed the hook is accurate.
- **Decision:** Login-walled leads pass through the quality gate's Tier 1 deterministic checks (dedup, org detection, DM route validation) and then go to `needs_review` status -- NOT auto-approve.
- **Manual review requirement:** For the first batch and any batch where login-walled leads exceed 50% of drafts, the user must manually review login-walled leads before approving. This is especially critical now: current drafts are 6/7 (85.7%) login-walled.
- **Sampling after trust is established:** Once the user has manually reviewed 50+ login-walled leads and confirms the scraper's auto-verification is reliable (e.g., <10% error rate), login-walled leads can be switched to auto-approve. This is a config flag, not a code change.
- **Rationale:** The scraper's keyword matching catches obvious mismatches but misses the subtler failures Perplexity caught today (wrong person with same name, hook premise that contradicts actual activity). Until we have confidence data, manual review is the safe default.

## Integration Contract

### Full Pipeline Flow (existing + new)

```
campaign create -> campaign assign -> campaign generate (drafts) -> QUALITY GATE (new) -> human review -> BROWSER SENDER (new)
```

Steps 1-3 already exist in the lead scraper CLI. Steps 4-6 are what we're building.

### Current Queue Reality (queried 2026-05-08)

| Status | Count | Notes |
|---|---|---|
| draft | 7 | Ready for quality gate |
| approved | 0 | None yet -- no gate exists |
| sent | 60 | Sent via Perplexity browser assistant |
| skipped | 142 | Skipped by Perplexity (quality issues) |
| declined | 1 | Recipient declined |

**12 campaigns exist** (2 waves x 6 segments: connector, musician, writer, filmmaker, creative, small_biz). To reach 3,000+ sends, new campaign batches must be generated via `campaign assign` + `campaign generate` for the remaining unassigned leads.

### Quality Gate reads from:
```
outreach_queue: lead_id, campaign_id, full_message, status (WHERE status = 'draft')
leads: name, profile_url, hook_text, hook_source_url, hook_verified, segment
```

### Quality Gate writes to:
```
outreach_queue: status -> 'approved', 'skipped', or 'needs_review'
New column: skip_reason TEXT (why the gate rejected or flagged it)
New column: gate_checked_at TEXT (timestamp of verification)
```
- `needs_review`: lead might be salvageable (e.g., wrong hook but real person in-audience). User can manually fix the hook/message and re-run gate or force-approve.

### Browser Sender reads from:
```
outreach_queue: lead_id, campaign_id, full_message (WHERE status = 'approved')
leads: name, profile_url
sender_accounts: id, platform, profile_path, daily_cap, sends_today, status
```

### Browser Sender writes to:
```
outreach_queue: status -> 'sent', sent_at -> timestamp, sender_account_id -> which account sent it
Or: status -> 'skipped' with skip_reason = 'dm_restricted' (check #8)
sender_accounts: sends_today incremented, status -> 'restricted' if blocked
```

## Schema Migration Scope

This build requires modifying the existing database. All changes are in-scope for the plan.

**outreach_queue table:**
- Recreate CHECK constraint on `status` to add `needs_review` (SQLite requires table recreation -- same pattern used in `_migrate_outreach_statuses()` in db.py)
- Add column: `skip_reason TEXT` (quality gate rejection reason)
- Add column: `gate_checked_at TEXT` (verification timestamp)
- Add column: `sender_account_id INTEGER` (which account sent this message)

**New table: sender_accounts**
- See Account/Session Architecture section below

**Campaign CLI updates:**
- Add `python run.py campaign gate <id>` command (run quality gate on a campaign's drafts)
- Add `python run.py campaign send <id>` command (run browser sender on approved messages)
- Update `show-queue` to display gate status, skip reasons, and sender account
- Add status transitions: draft -> needs_review, needs_review -> approved (manual force-approve)

## Rate Limiting Strategy

- **Quality gate:** No rate limiting needed for `requests` fetches. Claude API has no practical cap.
- **Browser sender:** Human-like delays between messages.
  - 30-60 second random delay between sends (mimics typing/reading)
  - 5-10 minute pause every 15-20 messages (mimics taking a break)
  - Daily cap per account: configurable in `sender_accounts` table (default 30). Spike test starts at 5-10, warmup ramps gradually (see Daily Capacity Model).
  - Track sends per account per day via `sends_today` counter in `sender_accounts`

## Account / Session Architecture

### Account Config (new table: sender_accounts)
```
sender_accounts:
  id INTEGER PRIMARY KEY
  name TEXT (e.g., "personal", "amplify-workshop", "amplify-ai")
  platform TEXT ("facebook", "instagram", or "both")
  profile_dir TEXT (path to Playwright persistent storage state)
  daily_cap INTEGER DEFAULT 30
  sends_today INTEGER DEFAULT 0
  last_send_at TEXT
  status TEXT DEFAULT 'active' CHECK(status IN ('active', 'restricted', 'cooldown', 'disabled'))
  restricted_at TEXT
  cooldown_until TEXT
  created_at TEXT DEFAULT (datetime('now'))
```

### Persistent Browser Profiles
- Each account gets a dedicated Playwright persistent storage directory (e.g., `~/.browser-profiles/personal/`, `~/.browser-profiles/amplify-workshop/`)
- On first run, Playwright opens a headed browser for manual login. User logs in once, cookies are saved in the profile directory.
- Subsequent runs reuse the saved session -- no login needed unless session expires.
- If a session expires (Facebook forces re-login), the sender detects it (checks for login page) and pauses that account.

### Per-Account Daily Send Counters
- `sends_today` resets at midnight (or on first send of a new calendar day)
- Before each send, check: `sends_today < daily_cap AND status = 'active'`
- After each send: increment `sends_today`, update `last_send_at`

### Platform Routing
- Lead's platform inferred from `profile_url` domain: `facebook.com` -> Facebook Messenger, `instagram.com` -> Instagram DM
- Account's `platform` field determines which leads it can send to
- If account platform is "both", it can send to either platform
- Round-robin across eligible active accounts for each lead's platform

### Account Status State Machine

```
                   ┌─────────────────────────────────┐
                   │                                 │
                   v                                 │
  ┌──────────┐  restriction   ┌────────────┐  user sets   ┌──────────┐  cooldown_until  ┌────────┐
  │  active   │──detected────>│ restricted │──cooldown───>│ cooldown │───passes────────>│ active │
  └──────────┘               └────────────┘  date        └──────────┘                  └────────┘
       │                          │                           │
       │ user disables            │ user disables             │ user disables
       v                          v                           v
  ┌──────────┐               ┌──────────┐               ┌──────────┐
  │ disabled │               │ disabled │               │ disabled │
  └──────────┘               └────────────┘             └──────────┘
```

**Transitions:**

| From | To | Trigger | Who/What |
|---|---|---|---|
| `active` | `restricted` | Sender detects CAPTCHA, "going too fast", messaging block, or login page | Automatic (sender code) |
| `restricted` | `cooldown` | User sets `cooldown_until` date (e.g., 48h from now) | Manual (user via CLI: `run.py account cooldown <id> --hours 48`) |
| `cooldown` | `active` | Current time >= `cooldown_until` AND `sends_today` reset to 0 | Automatic (checked before each send run) |
| any | `disabled` | User disables account permanently | Manual (user via CLI: `run.py account disable <id>`) |
| `disabled` | `active` | User re-enables account | Manual (user via CLI: `run.py account enable <id>`) |

**On restriction detection (automatic):**
1. Sender immediately stops sending from that account
2. Sets `status = 'restricted'`, `restricted_at = now()`
3. Logs the event: account name, restriction signal detected, messages sent that day
4. Switches to next active account (if any)
5. If no active accounts remain: halts run, prints summary, exits

**Key rule:** No automatic transition from `restricted` to `cooldown` or `active`. The user must explicitly acknowledge the restriction and set a cooldown period. This prevents the system from silently resuming on a flagged account.

## Open Questions

*All resolved during brainstorm.*

## Resolved Questions

1. **Where does the app live?** Inside lead scraper (same repo, shared DB).
2. **Headed or headless?** Headed always.
3. **Separate steps or one loop?** Separate (verify batch, then send batch).
4. **Both platforms day one?** Yes, Facebook + Instagram.
5. **Account rotation?** Multiple accounts from Week 1 (personal + 2-3 business accounts).
6. **Which approach?** Hybrid (requests for gate, Playwright for sending).
7. **What does the quality gate catch?** 9 documented failure modes from real data.

## Daily Capacity Model (May 8 through May 30)

**23 sending days** (May 8 through May 30 inclusive). Workshop is May 30 -- messages can still go out that morning.

### Assumptions
- Personal account (established): can ramp to 30/day after spike test
- New business accounts: need 3-5 day warmup before reaching 20/day
- Warmup sequence per new account: 5 -> 10 -> 15 -> 20 -> 25 -> 30/day
- If an account gets restricted, it enters 48-72 hour cooldown (0 sends)

### Daily Capacity Projection

| Phase | Dates | Days | Accounts Active | Daily Total | Phase Sends | Running Total |
|---|---|---|---|---|---|---|
| Spike test | May 8-9 | 2 | 1 (personal) @ 5-10 | 5-10 | 15 | 15 |
| Ramp personal | May 10-12 | 3 | 1 (personal) @ 15-20-25 | 15-25 | 60 | 75 |
| Add accounts + warmup | May 13-16 | 4 | 1 @ 30 + 2 @ 5-20 | 40-70 | 220 | 295 |
| Steady state | May 17-23 | 7 | 3 @ 25-30 | 75-90 | 580 | 875 |
| Push | May 24-30 | 7 | 3 @ 30-40 | 90-120 | 735 | 1,610 |

**Conservative total: ~1,520** (assumes one account restricted for 3 days during steady state, reducing that phase by ~90. Calculated: 1,610 - 90 = 1,520).

**Optimistic total: ~1,770** (no restrictions, all 3 accounts hit 30/day by May 17, push to 40/day in final week). Calculated: 15 + 60 + 220 + 630 + 840 = 1,765.

### What this means
- 3,000 sends by May 30 is **not achievable** with 3 accounts at safe send rates
- To reach 3,000: need 5+ accounts at 30/day or 3 accounts at 50+/day (high restriction risk)
- To reach 6,000: not modeled -- would require 8+ accounts or rates that will trigger restrictions
- **Recommended target:** 1,520-1,770 sends (quality over quantity). Each verified, well-targeted message is worth more than 3 rushed ones that damage the brand.

### Restriction Contingency
- If personal account restricted in Week 1 (before business accounts ready): manual sending from the queue as fallback
- If a business account restricted during warmup: replace with a new account, restart warmup
- If 2+ accounts restricted simultaneously: pause automated sending for 72 hours, send manually from remaining accounts

## Feed-Forward

- **Hardest decision:** Hybrid vs. Playwright-for-everything. Chose hybrid because 73.2% of all hooks (821/1,121) have public verify URLs where HTTP fetch is 100x faster than browser. However, current drafts are 85.7% login-walled (6/7) -- the quality gate's AI verification helps most at scale, not for the first batch. Login-walled leads go to `needs_review` (manual review required until trust is established after 50+ manual checks).
- **Rejected alternatives:** Browser-Use AI agent (unpredictable for a structured workflow), Playwright-only (too slow for verification at scale), building as a separate project (unnecessary complexity when the lead scraper already has the data and config).
- **Least confident:** Two things. (1) Facebook/Instagram's reaction to automated DMs -- Meta publishes no safe thresholds, and unsolicited promotional DMs violate their Terms. The spike test + gradual ramp + kill switch + explicit cooldown state machine mitigate this, but account restrictions are likely at some point, not hypothetical. (2) The 3,000-6,000 target is not achievable at safe send rates with 3 accounts. Conservative ceiling is ~1,520, optimistic ~1,770. The user needs to decide: accept the lower number, add more accounts, or accept higher restriction risk.
