---
title: "feat: Browser Outreach Sender (Quality Gate + Playwright DM Automation)"
type: feat
status: active
date: 2026-05-08
origin: docs/brainstorms/2026-05-08-browser-outreach-sender-brainstorm.md
feed_forward:
  risk: "Meta publishes no safe DM thresholds. Restriction signals must be discovered during spike test. Playwright selectors are fragile against Meta UI changes."
  verify_first: true
---

# feat: Browser Outreach Sender

## Overview

Two new modules inside the lead scraper that replace Perplexity's browser assistant:

1. **AI Quality Gate** (`quality_gate.py`) -- verifies hooks using Claude API + HTTP fetch. 9 failure modes across 3 tiers.
2. **Browser Sender** (`browser_sender.py`) -- Playwright (headed Chrome) sends DMs via Facebook Messenger and Instagram.

Volume decision: **build for 1 account, rotation-ready.** Soft target ~1,500. `campaign send` always requires `--limit N` (no default "send all"). Before any automated send, the user must run `account confirm-risk <name>` to acknowledge Meta restriction/ban risk. This is a prerequisite, not a post-spike-test step.

(See brainstorm: `docs/brainstorms/2026-05-08-browser-outreach-sender-brainstorm.md`)

## Problem Statement / Motivation

Perplexity browser assistant hit its $20/mo usage cap today (May 8). 7 draft messages sit in the queue with 0 approved. The workshop is May 30 (23 sending days inclusive). Manual pace (15-20/day) reaches ~440. Automation with adaptive tuning targets 75-120/day at steady state, realistic ceiling 1,520-1,770 with 3 accounts.

Existing pipeline stops at `campaign generate` -- the quality gate and browser sender close the loop.

```
campaign create -> assign -> generate (drafts) -> QUALITY GATE (new) -> human review -> BROWSER SENDER (new)
```

## What Must Not Change

- Existing 210 outreach_queue rows (migration preserves all data)
- Campaign workflow (create -> assign -> generate still works independently)
- `verify_hooks()` in enrich.py (separate verification, not replaced)
- Single-writer rule: `campaign.py` owns all outreach_queue writes
- Template system and opener generation (untouched)
- Flask web UI endpoints (read-only, no changes needed)

## Proposed Solution

### Architecture

```
run.py (CLI)
  |-- cmd_campaign()
  |     |-- "gate"  -> quality_gate.run_gate(campaign_id)
  |     |-- "send"  -> browser_sender.run_send(campaign_id)
  |     |-- "requeue" -> campaign.requeue_lead()
  |
  |-- cmd_account()
        |-- "add"          -> account.add_account()
        |-- "list"         -> account.list_accounts()
        |-- "login"        -> account.login_account()
        |-- "confirm-risk" -> account.confirm_risk()
        |-- "cooldown"     -> account.set_cooldown()
        |-- "disable"      -> account.disable_account()
        |-- "enable"       -> account.enable_account()

quality_gate.py         -- verification logic (reads DB, returns decisions)
  calls campaign.py     -- for all outreach_queue writes (single-writer preserved)

browser_sender.py       -- Playwright automation (reads DB, returns results)
  calls campaign.py     -- for status -> sent / skipped writes
  calls account.py      -- for sends_today increment, restriction status

account.py              -- owns sender_accounts table (new single-writer)
campaign.py             -- gains 8 functions: gate_approve(), gate_skip(),
                           gate_needs_review(), force_approve(), force_skip(),
                           mark_sent_by_sender(), skip_dm_restricted(), requeue_lead()
```

**Single-writer rule preserved:** quality_gate.py and browser_sender.py never write directly to outreach_queue. They call campaign.py functions. account.py owns sender_accounts exclusively.

### New Files

| File | Purpose | Owns Table |
|---|---|---|
| `quality_gate.py` | Hook verification logic (Tier 1 deterministic + Tier 2 AI) | None (delegates to campaign.py) |
| `browser_sender.py` | Playwright DM send automation | None (delegates to campaign.py + account.py) |
| `account.py` | Sender account CRUD + state machine | `sender_accounts` |

### Modified Files

| File | Changes |
|---|---|
| `campaign.py` | Add: `gate_approve()`, `gate_skip()`, `gate_needs_review()`, `force_approve()`, `force_skip()`, `mark_sent_by_sender()`, `skip_dm_restricted()`, `requeue_lead()` (8 functions, all atomic with status-constrained WHERE + rowcount check) |
| `run.py` | Add: `campaign gate`, `campaign send`, `campaign requeue` subcommands. Add: `account` top-level command with subcommands. |
| `db.py` | Add: `_migrate_needs_review_status()` (recreate outreach_queue with updated CHECK constraint + 3 new columns in one step), `_create_sender_accounts()` (new table) |
| `requirements.txt` | Add: `playwright>=1.40` |

## Implementation Phases

### Phase 1: Foundation (Days 1-2)

**Goal:** Schema ready, accounts manageable, Playwright installed, first login saved.

#### 1a. Schema Migration (`db.py`)

**Restructure `migrate_db()`:** The existing function has an early return when no new columns are needed for the leads table. The new migrations must not be gated by that early return. Structure:

```python
def migrate_db(db_path=DB_PATH):
    # --- existing leads table column additions (unchanged) ---
    existing = {row[1] for row in conn.execute("PRAGMA table_info('leads')")}
    new_cols = [c for c in LEAD_COLUMNS if c[0] not in existing]
    if new_cols:
        _backup_wal_safe(db_path)
        for col_name, col_def in new_cols:
            conn.execute(f"ALTER TABLE leads ADD COLUMN {col_name} {col_def}")

    # --- NEW: sender module migrations (always run, independent of leads) ---
    _create_sender_accounts(db_path)          # idempotent: CREATE IF NOT EXISTS
    _migrate_needs_review_status(db_path)     # idempotent: checks sqlite_master first
```

**WAL-safe backup:** Take backup ONCE before any schema change (leads OR sender migrations), not per-migration. Use `sqlite3.backup()` (existing pattern). Only if at least one migration will run.

**`_create_sender_accounts()`** -- must run BEFORE queue migration (FK dependency):
```sql
CREATE TABLE IF NOT EXISTS sender_accounts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL UNIQUE,
    platform        TEXT NOT NULL DEFAULT 'both'
                    CHECK(platform IN ('facebook', 'instagram', 'both')),
    profile_dir     TEXT NOT NULL,
    daily_cap       INTEGER NOT NULL DEFAULT 30,
    sends_today     INTEGER NOT NULL DEFAULT 0,
    last_send_at    TEXT,
    last_reset_date TEXT,
    status          TEXT NOT NULL DEFAULT 'active'
                    CHECK(status IN ('active', 'restricted', 'cooldown', 'disabled')),
    restricted_at   TEXT,
    cooldown_until  TEXT,
    risk_acknowledged INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now'))
);
```

`last_reset_date`: YYYY-MM-DD when sends_today was last reset. Lazy check: if `last_reset_date != today (local time)`, reset sends_today before any send.

`risk_acknowledged`: 0 by default. Set to 1 via `account confirm-risk <name>` before any send (prerequisite, not post-spike-test). `get_active_account()` filters on `risk_acknowledged=1`, so unacknowledged accounts are never used for sending.

**`_migrate_needs_review_status()`** -- recreate outreach_queue:
```python
def _migrate_needs_review_status(db_path=DB_PATH):
    with get_db(db_path) as conn:
        # Check-before-act: skip ONLY if ALL migration targets are already present
        create_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='outreach_queue'"
        ).fetchone()
        if not create_sql:
            return  # Table doesn't exist yet (initial setup handles it)

        cols = {row[1] for row in conn.execute("PRAGMA table_info('outreach_queue')")}
        already_has_status = "'needs_review'" in create_sql[0]
        already_has_columns = {'skip_reason', 'gate_checked_at', 'sender_account_id'}.issubset(cols)
        already_has_fk = any(
            'sender_accounts' in str(row)
            for row in conn.execute("PRAGMA foreign_key_list('outreach_queue')").fetchall()
        )

        if already_has_status and already_has_columns and already_has_fk:
            return  # Fully migrated -- all 3 conditions met

        # Record pre-migration row count
        pre_count = conn.execute("SELECT COUNT(*) FROM outreach_queue").fetchone()[0]

        conn.execute("PRAGMA foreign_keys=OFF")
        conn.executescript("""
            CREATE TABLE outreach_queue_new (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id         INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
                campaign_id     INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
                opener_text     TEXT,
                template_text   TEXT,
                full_message    TEXT,
                status          TEXT NOT NULL DEFAULT 'draft'
                                CHECK(status IN ('draft','approved','sent','skipped','needs_review',
                                                 'replied','booked','declined','no_response')),
                generated_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now')),
                approved_at     TEXT,
                sent_at         TEXT,
                skip_reason     TEXT,
                gate_checked_at TEXT,
                sender_account_id INTEGER REFERENCES sender_accounts(id) ON DELETE SET NULL,
                UNIQUE(lead_id, campaign_id)
            );

            INSERT INTO outreach_queue_new
                (id, lead_id, campaign_id, opener_text, template_text, full_message,
                 status, generated_at, approved_at, sent_at,
                 skip_reason, gate_checked_at, sender_account_id)
            SELECT id, lead_id, campaign_id, opener_text, template_text, full_message,
                   status, generated_at, approved_at, sent_at,
                   NULL, NULL, NULL
            FROM outreach_queue;

            DROP TABLE outreach_queue;
            ALTER TABLE outreach_queue_new RENAME TO outreach_queue;

            CREATE INDEX IF NOT EXISTS idx_outreach_queue_campaign_status
                ON outreach_queue(campaign_id, status);
        """)
        conn.execute("PRAGMA foreign_keys=ON")

        # Post-migration verification
        post_cols = {row[1] for row in conn.execute("PRAGMA table_info('outreach_queue')")}
        assert 'skip_reason' in post_cols, "Migration failed: skip_reason missing"
        assert 'gate_checked_at' in post_cols, "Migration failed: gate_checked_at missing"
        assert 'sender_account_id' in post_cols, "Migration failed: sender_account_id missing"

        post_count = conn.execute("SELECT COUNT(*) FROM outreach_queue").fetchone()[0]
        assert post_count == pre_count, (
            f"Migration data loss: {pre_count} rows before, {post_count} after"
        )
        print(f"Migration complete: {post_count} rows preserved (verified == {pre_count}), "
              f"needs_review status + 3 columns + FK added")
```

**Key migration details:**
- `sender_account_id REFERENCES sender_accounts(id) ON DELETE SET NULL` -- if an account is deleted, sent messages keep their record but lose the FK link
- `_create_sender_accounts()` runs first (FK target must exist)
- Skip condition requires ALL THREE: `needs_review` in CHECK, all 3 new columns present, sender_accounts FK present. Partial migration state triggers re-run.
- Pre-migration row count recorded, post-migration count asserted equal (prevents silent data loss)
- Post-migration `PRAGMA table_info` verification confirms all 3 columns exist
- Explicit column names in INSERT prevent silent data corruption

**Migration safety (from solution docs):**
- Use explicit key-existence checks, not falsy checks (gigprep lesson)
- Check-before-act: inspect sqlite_master before each migration
- WAL-safe backup via `sqlite3.backup()` before first schema change
- Post-migration verification with PRAGMA table_info

#### 1b. Account Module (`account.py`)

New module, single-writer for `sender_accounts`.

**Functions:**
```python
def add_account(name, platform='both', profile_dir=None, daily_cap=30, db_path=DB_PATH):
    """Insert new account. Auto-generates profile_dir if not specified.
    Default: ~/.browser-profiles/<name>/
    Raises ValueError if name already exists."""

def list_accounts(db_path=DB_PATH):
    """Print all accounts with: name, platform, status, sends_today/daily_cap, last_send_at."""

def get_active_account(platform, db_path=DB_PATH):
    """Return next eligible account for sending on given platform.
    Eligible: status='active' AND sends_today < daily_cap AND risk_acknowledged=1
              AND platform IN (platform, 'both').
    Round-robin: pick account with lowest sends_today (load balance).
    Returns None if no eligible accounts (including when none have risk_acknowledged)."""

def increment_sends(account_id, db_path=DB_PATH):
    """Atomic: UPDATE sends_today = sends_today + 1, last_send_at = now()
    WHERE id = account_id AND status = 'active'.
    Check rowcount > 0. Reset sends_today if new day (lazy reset)."""

def mark_restricted(account_id, db_path=DB_PATH):
    """Set status='restricted', restricted_at=now(). Log event."""

def set_cooldown(account_id, hours, db_path=DB_PATH):
    """Requires status='restricted'. Set status='cooldown', cooldown_until=now()+hours."""

def check_cooldown_expired(db_path=DB_PATH):
    """Check all cooldown accounts. If cooldown_until <= now(), set status='active', sends_today=0."""

def disable_account(account_id, db_path=DB_PATH):
    """Set status='disabled'."""

def enable_account(account_id, db_path=DB_PATH):
    """Set status='active', sends_today=0, last_reset_date=today."""

def confirm_risk(account_id, db_path=DB_PATH):
    """Set risk_acknowledged=1. Prints Meta restriction/ban risk warning.
    User must confirm interactively (y/N prompt). Required before campaign send
    will use this account. Per-account: each account must be individually acknowledged."""
```

**State machine transitions (from brainstorm):**

| From | To | Trigger | Function |
|---|---|---|---|
| `active` | `restricted` | Sender detects restriction | `mark_restricted()` -- automatic |
| `restricted` | `cooldown` | User sets cooldown hours | `set_cooldown()` -- manual CLI |
| `cooldown` | `active` | cooldown_until passes | `check_cooldown_expired()` -- automatic, checked before each send run |
| any | `disabled` | User disables | `disable_account()` -- manual CLI |
| `disabled` | `active` | User enables | `enable_account()` -- manual CLI, resets sends_today |

**Key rule:** No automatic `restricted -> active`. User must explicitly acknowledge.

#### 1c. Account CLI (`run.py`)

```
python run.py account add <name> [--platform fb|ig|both] [--daily-cap 30]
python run.py account list
python run.py account login <name>          # opens headed browser for manual login
python run.py account confirm-risk <name>  # acknowledge Meta risk (required before send)
python run.py account cooldown <name> --hours 48
python run.py account disable <name>
python run.py account enable <name>
```

`account login` opens a Playwright headed browser using the account's profile_dir. User logs in manually. Session saved to profile_dir. Browser closes when user presses Enter in the terminal.

#### 1d. Playwright Setup

- Add `playwright>=1.40` to requirements.txt
- `pip install playwright && playwright install chromium`
- Profile directories at `~/.browser-profiles/<account-name>/`
- Add `~/.browser-profiles/` to .gitignore (session cookies are sensitive)

**Persistent context pattern:**
```python
from playwright.sync_api import sync_playwright

def open_browser(profile_dir: str, headless: bool = False):
    """Launch Chromium with persistent storage state."""
    pw = sync_playwright().start()
    context = pw.chromium.launch_persistent_context(
        user_data_dir=profile_dir,
        headless=headless,
        viewport={"width": 1280, "height": 800},
    )
    return pw, context
```

### Phase 2: Minimal Sender + Spike Test (Days 2-3)

**Goal:** Get to first real send ASAP. Minimal Playwright sender + spike test. Quality gate comes after.

**Phase gate:** Phase 1 (schema + accounts + Playwright login) must be complete before starting. The spike test uses manually approved leads (existing `campaign approve` command), NOT the quality gate.

#### 2a. Send Flow Architecture (`browser_sender.py`)

```python
def run_send(campaign_id, limit, db_path=DB_PATH):
    """
    Main entry point. Called from CLI: campaign send <id> --limit N
    
    0. GO/NO-GO GATE: get_active_account() only returns accounts with
       risk_acknowledged=1. If no eligible account, refuse to send.
       Print: "No risk-acknowledged accounts. Run 'account confirm-risk <name>' first."
    1. Check for lockfile (~/.browser-sender.lock). Prevent concurrent runs.
    2. Check cooldown expirations (account.check_cooldown_expired())
    3. Query approved messages: outreach_queue WHERE status='approved' AND campaign_id=?
    4. Take first N (limit is always required, enforced by argparse)
    5. For each message:
       a. Get eligible account (account.get_active_account(platform))
       b. If no account: halt, print summary, exit
       c. Open/reuse browser for that account's profile
       d. Detect platform from lead's profile_url
       e. Send message via platform-specific flow
       f. On success: campaign.mark_sent_by_sender(lead_id, campaign_id, account_id)
       g. On DM restricted: campaign.skip_dm_restricted(lead_id, campaign_id)
       h. On restriction detected: account.mark_restricted(account_id), switch account
       i. Adaptive delay before next message
       j. Check stop file (~/.browser-sender.stop) before next message
    6. Print summary: sent, skipped, errors
    7. Remove lockfile
    """
```

**Lockfile for concurrency safety (SpecFlow Gap 13):**
- Create `~/.browser-sender.lock` with PID at start
- Check if existing lock's PID is still running (stale lock protection)
- Remove on clean exit or Ctrl+C (signal handler)

#### 2b. Facebook Messenger Send Flow

**Initial approach (selectors discovered during spike test):**
```python
def send_facebook_dm(page, profile_url, message):
    """
    1. Navigate to profile_url (e.g., https://www.facebook.com/username)
    2. Wait for page load (networkidle)
    3. Look for "Message" button -- click it
       - If not found: return 'dm_restricted' (no Message button = friend-only)
    4. Wait for Messenger chat input to appear
    5. Click the input, type message (character by character with small delays)
       - Try typing first (more human-like). Fall back to clipboard paste if typing is too slow or breaks on Meta's React inputs. Spike test will determine which works.
    6. Press Enter to send
    7. Wait 2-3 seconds for message to appear in thread
    8. Confirm: check if message text appears in conversation
       - If yes: return 'sent'
       - If no: return 'send_failed'
    9. Check for restriction signals after send (see 2d)
    """
```

**Typing strategy:** Start with character-by-character (`page.type()` with delay). If Meta's React inputs don't cooperate (common with contenteditable divs), fall back to clipboard paste (`page.fill()` or `pyperclip` + Ctrl+V). Spike test determines which works.

#### 2c. Instagram DM Send Flow

```python
def send_instagram_dm(page, profile_url, message):
    """
    1. Navigate to profile_url (e.g., https://www.instagram.com/username)
    2. Wait for page load
    3. Look for "Message" button -- click it
       - If not found (private account, no follow): return 'dm_restricted'
    4. Wait for DM input to appear (Instagram redirects to /direct/t/...)
    5. Click input, type message with delays
    6. Press Enter to send
    7. Wait for message to appear in thread
    8. Confirm delivery
    9. Check for restriction signals
    """
```

**Platform detection:**
```python
def detect_platform(profile_url):
    """Return 'facebook' or 'instagram' from URL domain."""
    from urllib.parse import urlparse
    domain = urlparse(profile_url).netloc.lower()
    if 'instagram.com' in domain:
        return 'instagram'
    if 'facebook.com' in domain:
        return 'facebook'
    return None  # Invalid -- should have been caught by quality gate
```

#### 2d. Restriction Detection

**Signals to check after each send (discovered incrementally during spike test):**

```python
RESTRICTION_SIGNALS = {
    "facebook": [
        # Text on page that indicates restriction
        "you can't send messages",
        "you're temporarily blocked",
        "try again later",
        "we limit how often",
        "action blocked",
    ],
    "instagram": [
        "try again later",
        "action blocked",
        "we restrict certain activity",
        "challenge_required",
    ],
    "login_page": [
        # URL patterns that indicate session expired
        "login",
        "checkpoint",
    ],
}
```

**Check function:**
```python
def check_for_restriction(page, platform):
    """
    Run after each send attempt.
    1. Check page URL for login/checkpoint redirects
    2. Check page text content for restriction signal strings
    3. Check for CAPTCHA iframes
    Returns: None (safe) or str (restriction type detected)
    """
```

**These signals are initial guesses.** The spike test (Phase 4) will reveal actual signals. Plan allocates explicit time for discovery and updating RESTRICTION_SIGNALS.

#### 2e. Adaptive Delays (from solution doc: research-agent/adaptive-batch-backoff)

```python
class AdaptiveDelay:
    """
    Start with short delays. Increase after restriction signals.
    Only sleep AFTER actual issue, not defensively before every operation.
    """
    def __init__(self):
        self.base_delay = 30      # seconds, minimum between sends
        self.max_delay = 90       # seconds, maximum between sends
        self.current_delay = 30
        self.sends_since_issue = 0
        self.batch_pause_every = 15  # pause every N messages
        self.batch_pause_duration = 300  # 5 minute pause
    
    def next_delay(self):
        """Return delay in seconds. Increases after restriction, decreases after successful sends."""
        import random
        jitter = random.uniform(0.8, 1.2)
        return self.current_delay * jitter
    
    def on_success(self):
        """Gradually reduce delay after consecutive successes."""
        self.sends_since_issue += 1
        if self.sends_since_issue > 10 and self.current_delay > self.base_delay:
            self.current_delay = max(self.base_delay, self.current_delay - 5)
    
    def on_warning(self):
        """Increase delay after a soft warning (slow page load, unusual UI)."""
        self.current_delay = min(self.max_delay, self.current_delay + 15)
        self.sends_since_issue = 0
    
    def should_batch_pause(self, sends_in_session):
        """Return True if it's time for a break."""
        return sends_in_session > 0 and sends_in_session % self.batch_pause_every == 0
```

#### 2f. Kill Switch

Two mechanisms:

1. **Ctrl+C (signal handler):** On SIGINT, finish current send status update, print summary, clean up lockfile, exit.
2. **Stop file:** Check for `~/.browser-sender.stop` before each message. If exists, stop gracefully. Remove stop file after stopping.

```python
import signal

def setup_kill_switch():
    """Register signal handler and return stop-check function."""
    stop_requested = False
    
    def handler(signum, frame):
        nonlocal stop_requested
        stop_requested = True
        print("\nStop requested. Finishing current message...")
    
    signal.signal(signal.SIGINT, handler)
    
    def should_stop():
        return stop_requested or Path("~/.browser-sender.stop").expanduser().exists()
    
    return should_stop
```

**On graceful stop:**
- Current message: if send was successful, mark as sent. If interrupted mid-send, leave as approved (will retry next run).
- Print: X sent, Y remaining, account sends_today summary.
- Remove lockfile.

#### 2g. Spike Test Protocol (end of Phase 2)

**Day 2-3 (as soon as Phase 1 + minimal sender work):**

1. `python run.py account add personal --platform both`
2. `python run.py account login personal` -- log in to Facebook + Instagram
3. `python run.py account confirm-risk personal` -- acknowledge Meta restriction/ban risk (prerequisite for any send)
4. Manually approve 5 existing drafts: `python run.py campaign approve <id> --lead <id>` x 5
5. `python run.py campaign send <id> --limit 5`
6. **Watch the headed browser.** Note:
   - Exact selectors for "Message" button (Facebook and Instagram)
   - Any pop-ups or modals that appear
   - How the DM input looks (selector)
   - Whether typing works or needs clipboard
   - Any restriction signals
7. Wait 24 hours.
8. Check account: any messaging restrictions?
9. If clear: increase to --limit 15-20. If restricted: log signals, update RESTRICTION_SIGNALS, wait 48h.

**After spike test:** Update `browser_sender.py` with discovered selectors and restriction signals. This is expected -- the plan allocates Phase 2 time for iteration.

### Phase 3: Quality Gate (Days 3-5)

**Goal:** Verify drafts before approval. 3 tiers. Login-walled leads to needs_review. Can start while spike test results are pending (24h wait).

#### 3a. Quality Gate Architecture (`quality_gate.py`)

```python
def run_gate(campaign_id, limit=0, db_path=DB_PATH):
    """
    Main entry point. Called from CLI: campaign gate <id> [--limit N]
    
    1. Query drafts: outreach_queue WHERE status='draft' AND campaign_id=?
       - If limit > 0, take first N
       - Skip leads where gate_checked_at is not NULL (already gated, unless --force)
    2. Run Tier 1 deterministic checks on all drafts (fast, no API)
    3. For remaining leads, run Tier 2 AI checks:
       a. If verify URL is login-walled (IG/FB domain): -> needs_review
       b. If verify URL is missing: -> needs_review
       c. Fetch verify URL via requests (10s timeout, 1 retry)
       d. Send page text + hook + lead name to Claude API
       e. Parse Claude response -> approve / skip / needs_review
    4. Write results via campaign.py functions
    5. Print summary: X approved, Y skipped (with reasons), Z needs_review
    """
```

#### 3b. Tier 1 Deterministic Checks (no API, instant)

```python
def tier1_checks(leads, db_path=DB_PATH):
    """
    Run on all drafts. Returns dict: {lead_id: ('skip'|'pass', reason)}
    
    Check #4 - Dedup: GROUP BY lower(name) or lower(profile_url handle).
        If duplicate found, skip all but the first.
    
    Check #5 - Org detection: regex on lead name.
        Patterns: Films, Media, TV, Productions, Agency, LLC, Inc, Church, YMCA, College
        (reuse existing _check_is_org patterns from enrich.py if available)
    
    Check #6 - DM route validation: profile_url must contain
        'facebook.com' or 'instagram.com'. Reject Eventbrite, Linktree, etc.
    """
```

#### 3c. Tier 2 AI Checks (Claude API + HTTP fetch)

```python
def tier2_check(lead, session, client, db_path=DB_PATH):
    """
    For a single lead with a public (non-login-walled) verify URL.
    
    1. Fetch verify URL (reuse enrich.py's _fetch_page pattern):
       - SSRF protection: call _is_safe_url(url) before fetch. Blocks private IPs (127.0.0.0/8, 10.0.0.0/8, etc.) and non-HTTP schemes. Also validates final URL after redirects.
       - timeout=10s, stream=True, allow_redirects=True
       - Response size cap: read max 500KB (resp.raw.read(500_000, decode_content=True))
       - Post-redirect SSRF check: if final URL != original, re-validate with _is_safe_url()
       - 1 retry on timeout/connection error (inline, 2s backoff -- reliability solution doc)
       - On 404/403/permanent failure: return ('needs_review', 'verify_url_dead')
       - On redirect to login page: return ('needs_review', 'verify_url_login_walled')
       - On SSRF block: return ('needs_review', 'verify_url_unsafe')
       - Extract text content (strip HTML tags, limit to first 5000 chars for Claude prompt)
    
    2. Send to Claude Haiku:
       model: claude-haiku-4-5
       max_tokens: 300
       
       System prompt:
       "You are a quality gate for outreach messages. Given a lead's name, hook text,
       and the content of a verification page, determine if the hook is accurate.
       
       Check these things:
       1. NAME_MATCH: Is this page about the same person as the lead? (not a different person with the same name)
       2. HOOK_PRESENT: Is the specific claim in the hook (project name, event, achievement) mentioned on this page?
       3. RELEVANT_SOURCE: Is the page's topic related to the hook and the lead's profile?
       4. AUDIENCE_FIT: Does the person appear to be a filmmaker, creative professional, or someone who would benefit from an AI ethics workshop in San Diego?
       
       Respond with JSON:
       {
         \"decision\": \"approve\" | \"skip\" | \"needs_review\",
         \"reason\": \"brief explanation\",
         \"checks\": {
           \"name_match\": true|false,
           \"hook_present\": true|false,
           \"relevant_source\": true|false,
           \"audience_fit\": true|false
         }
       }
       
       Decision rules:
       - If name_match=false: skip (wrong person)
       - If hook_present=false AND relevant_source=false: skip (hallucinated hook)
       - If hook_present=false BUT relevant_source=true: needs_review (hook may need rewrite)
       - If all checks pass: approve
       - If audience_fit=false but other checks pass: needs_review (might be wrong segment)"
       
    3. Parse response. Use Pydantic model for structured output (existing pattern).
       Fall back to needs_review with reason='gate_parse_error' if JSON parsing fails.
    
    4. Rate limiting: 0.5s delay between requests.get() calls to same domain.
       No rate limit between Claude API calls (0.1s courtesy delay, same as existing).
    
    5. **Haiku accuracy audit:** After first 50 AI-gated leads, the user manually
       spot-checks 10 approved and 10 skipped leads. If either set has >20% errors
       (approved leads that should have been skipped, or skipped leads that were
       actually fine), escalate to Sonnet for Tier 2 checks. If >30% error rate,
       pause AI gate and fall back to manual review only until prompt is revised.
       Track in a simple tally: `gate_audit_approved_correct`, `gate_audit_skip_correct`
       in a local file or env var (not DB -- this is a one-time calibration).
    """
```

#### 3d. Login-Walled and Missing URL Handling

```python
def classify_verify_url(hook_source_url):
    """
    Returns: 'public', 'login_walled', or 'missing'
    """
    if not hook_source_url:
        return 'missing'
    domain = urlparse(hook_source_url).netloc.lower()
    if 'instagram.com' in domain or 'facebook.com' in domain:
        return 'login_walled'
    return 'public'
```

- `public`: Run full Tier 2 AI check
- `login_walled`:
  ```python
  if AUTO_APPROVE_LOGIN_WALLED:
      # Trust established: auto-approve (still runs Tier 1 deterministic checks)
      campaign.gate_approve(campaign_id, lead_id)
  else:
      # Default: route to manual review
      campaign.gate_needs_review(campaign_id, lead_id, 'login_walled_auto_verified')
  ```
  These have `hook_verified=1` from the scraper's trusted verification but no independent AI check.
- `missing`: Route to `needs_review` with reason `'no_verify_url'`

**AUTO_APPROVE_LOGIN_WALLED config:**
- Location: environment variable `AUTO_APPROVE_LOGIN_WALLED=0` (default) in `.env`
- Loaded in `quality_gate.py` at module level: `AUTO_APPROVE_LOGIN_WALLED = os.getenv('AUTO_APPROVE_LOGIN_WALLED', '0') == '1'`
- Switch to `1` after the user has manually reviewed 50+ login-walled leads and confirmed <10% error rate
- When `True`: login-walled leads auto-approve (still pass Tier 1 deterministic checks)
- When `False` (default): login-walled leads go to `needs_review` for manual inspection

### Phase 4: Full CLI Integration + Ramp (Days 4-6)

#### 4a. New Campaign CLI Commands

```
python run.py campaign gate <id> [--limit 50] [--force]
    Run quality gate on campaign's draft messages.
    --limit: process only first N drafts (default: all)
    --force: re-gate leads that already have gate_checked_at

python run.py campaign send <id> --limit <N>
    Send approved messages via Playwright.
    --limit: always required (enforced by argparse, no default).
    Prevents accidental bulk sends. Use --limit 5 for spike test,
    --limit 30 for daily batches at steady state.

python run.py campaign requeue <id> --lead <lead_id>
    Move a skipped or needs_review lead back to draft status for re-gating.
    Only works for: skipped -> draft, needs_review -> draft.
    Clears skip_reason and gate_checked_at.

python run.py campaign force-approve <id> --lead <lead_id>
    Manually approve a needs_review lead after human review.
    Only works for: needs_review -> approved.

python run.py campaign force-skip <id> --lead <lead_id> [--reason "explanation"]
    Manually reject a needs_review lead after human review.
    Only works for: needs_review -> skipped.

python run.py campaign queue <id> [--status draft|approved|needs_review|skipped|sent]
    Existing command (already named `queue` in run.py), updated:
    - Default: show all non-sent statuses (draft + approved + needs_review + skipped)
    - Add columns: status, skip_reason, gate_checked_at
    - Add --status filter

python run.py campaign approve-all <id>
    Existing command, behavior clarified: ONLY transitions draft -> approved.
    Does NOT touch needs_review items. Unchanged code, but add a print
    showing how many needs_review items were skipped.
```

#### 4b. New Status Transitions in `campaign.py`

All functions follow the atomic claim pattern: `UPDATE ... WHERE status = '<expected>' AND campaign_id = ? AND lead_id = ?`, then check `cursor.rowcount > 0`. Return False with warning if rowcount is 0 (lead not in expected state).

```python
def gate_approve(campaign_id, lead_id, db_path=DB_PATH) -> bool:
    """draft -> approved. Sets gate_checked_at.
    WHERE status='draft' AND campaign_id=? AND lead_id=?
    Returns False if rowcount == 0 (not draft or not found)."""

def gate_skip(campaign_id, lead_id, reason, db_path=DB_PATH) -> bool:
    """draft -> skipped. Sets skip_reason, gate_checked_at.
    WHERE status='draft' AND campaign_id=? AND lead_id=?"""

def gate_needs_review(campaign_id, lead_id, reason, db_path=DB_PATH) -> bool:
    """draft -> needs_review. Sets skip_reason (as review reason), gate_checked_at.
    WHERE status='draft' AND campaign_id=? AND lead_id=?"""

def force_approve(campaign_id, lead_id, db_path=DB_PATH) -> bool:
    """needs_review -> approved. For manual approval after review.
    WHERE status='needs_review' AND campaign_id=? AND lead_id=?"""

def force_skip(campaign_id, lead_id, reason, db_path=DB_PATH) -> bool:
    """needs_review -> skipped. For manual rejection after review.
    WHERE status='needs_review' AND campaign_id=? AND lead_id=?"""

def mark_sent_by_sender(campaign_id, lead_id, account_id, db_path=DB_PATH) -> bool:
    """approved -> sent. Sets sent_at, sender_account_id.
    WHERE status='approved' AND campaign_id=? AND lead_id=?"""

def skip_dm_restricted(campaign_id, lead_id, db_path=DB_PATH) -> bool:
    """approved -> skipped. For browser sender when DMs are inaccessible.
    Sets skip_reason='dm_restricted'.
    WHERE status='approved' AND campaign_id=? AND lead_id=?
    Note: This is distinct from gate_skip (which operates on drafts).
    The sender needs its own transition because the lead was already approved
    but DMs failed at runtime."""

def requeue_lead(campaign_id, lead_id, db_path=DB_PATH) -> bool:
    """skipped|needs_review -> draft. Clears skip_reason, gate_checked_at.
    WHERE status IN ('skipped','needs_review') AND campaign_id=? AND lead_id=?"""
```

**approve_all behavior:** Only transitions `draft -> approved`, NOT `needs_review -> approved`. This preserves the manual review gate. Separate `force-approve-all` command if needed later.

#### 4c. Daily Operational Playbook

```
Morning:
  1. python run.py account list          # check account statuses
  2. python run.py campaign assign <id>   # assign new leads if needed
  3. python run.py campaign generate <id> --limit 50  # generate new drafts

Midday:
  4. python run.py campaign gate <id>     # verify the batch
  5. python run.py campaign queue <id> --status needs_review  # review flagged leads
  6. Manually force-approve or skip needs_review items

Afternoon:
  7. python run.py campaign send <id>     # send approved messages
  8. Watch the headed browser. Intervene if needed.
  
Evening:
  9. python run.py campaign queue <id> --status sent  # check what went out
  10. Note any issues for tomorrow
```

Time estimates:
- Steps 1-3: ~5 minutes
- Steps 4-6: ~10-20 minutes (gate runs ~2-5 min for 50 leads, review takes human time)
- Steps 7-8: ~30-60 minutes (30-40 messages at 30-60s delays)
- Total: ~1 hour of active attention per day

## System-Wide Impact

- **Interaction graph:** CLI commands -> campaign.py (writes) -> SQLite. Playwright runs in a separate process (headed Chrome). No callbacks, no middleware.
- **Error propagation:** Playwright errors caught in browser_sender.py, mapped to skip/restrict actions. Claude API errors caught in quality_gate.py, mapped to needs_review. DB errors propagate up (existing pattern).
- **State lifecycle risks:** Interrupted send could leave a message in `approved` that was actually sent. Mitigated by: the message appears in the chat thread, and the recipient won't receive it twice. Worst case: a manual `mark_sent` fixes it.
- **API surface parity:** No web UI changes. CLI is the only interface.

## Acceptance Tests

### Happy Path (EARS format)

- WHEN the user runs `campaign gate <id>` with 50 draft messages THE SYSTEM SHALL verify each draft and set status to approved, skipped, or needs_review with appropriate skip_reason
- WHEN the user runs `campaign send <id>` with 10 approved messages THE SYSTEM SHALL open a headed Chrome browser, send each message via the lead's platform, and update status to 'sent' with timestamp and sender_account_id
- WHEN the quality gate encounters a public verify URL THE SYSTEM SHALL fetch the page, send content to Claude API, and apply the 4-check decision matrix (name_match, hook_present, relevant_source, audience_fit)
- WHEN the quality gate encounters a login-walled verify URL THE SYSTEM SHALL route the lead to needs_review with reason 'login_walled_auto_verified'
- WHEN the browser sender successfully sends a DM THE SYSTEM SHALL increment the account's sends_today counter and apply an adaptive delay before the next message

### Error Cases

- WHEN a verify URL returns 404 THE SYSTEM SHALL set status to needs_review with skip_reason='verify_url_dead'
- WHEN the browser sender detects a restriction signal THE SYSTEM SHALL immediately stop that account (status='restricted'), log the event, and switch to the next active account
- WHEN all active accounts are exhausted (restricted or at daily cap) THE SYSTEM SHALL halt the send run and print a summary with account statuses
- WHEN the user presses Ctrl+C during a send run THE SYSTEM SHALL finish the current message's status update, print a summary, and clean up the lockfile
- WHEN `campaign send` is already running (lockfile exists) THE SYSTEM SHALL refuse to start and print "Another send process is running (PID: X)"
- WHEN a lead has no Message button on their profile THE SYSTEM SHALL skip that lead with skip_reason='dm_restricted' and continue to the next

### Migration & Data Integrity

- WHEN `migrate_db()` runs on a database with 210 outreach_queue rows THE SYSTEM SHALL preserve all 210 rows with identical data in the original columns
- WHEN `migrate_db()` runs twice THE SYSTEM SHALL be idempotent (second run is a no-op, verified by sqlite_master check)
- WHEN a sender_account is deleted THE SYSTEM SHALL set `sender_account_id = NULL` on outreach_queue rows that referenced it (ON DELETE SET NULL)
- WHEN `migrate_db()` completes THE SYSTEM SHALL verify new columns exist via PRAGMA table_info and print row count

### Account State Machine

- WHEN an active account's sends_today reaches daily_cap THE SYSTEM SHALL skip that account in get_active_account() and try the next
- WHEN a restricted account has no cooldown_until set THE SYSTEM SHALL NOT auto-transition to active (user must run `account cooldown`)
- WHEN a cooldown account's cooldown_until has passed THE SYSTEM SHALL auto-transition to active with sends_today=0 on the next send run
- WHEN `account confirm-risk` has not been run on any account THE SYSTEM SHALL refuse to execute `campaign send`

### Quality Gate Edge Cases

- WHEN Claude API returns invalid JSON THE SYSTEM SHALL set status to needs_review with skip_reason='gate_parse_error'
- WHEN AUTO_APPROVE_LOGIN_WALLED=0 and verify URL is login-walled THE SYSTEM SHALL route to needs_review (not auto-approve)
- WHEN AUTO_APPROVE_LOGIN_WALLED=1 and verify URL is login-walled THE SYSTEM SHALL auto-approve (after passing Tier 1 checks)
- WHEN `campaign approve-all <id>` is run THE SYSTEM SHALL only transition draft->approved, NOT needs_review->approved

### Manual Fallback

- WHEN all accounts are restricted THE SYSTEM SHALL print the outreach queue with approved messages so the user can copy-paste manually
- WHEN the user runs existing `campaign approve <id> --lead <lead_id>` on a draft THE SYSTEM SHALL still work (existing manual approval path is unchanged)

### Verification Commands

```bash
# Schema migration + verification
python -c "import db; db.migrate_db()" && echo "Migration OK"
sqlite3 leads.db ".schema outreach_queue" | grep needs_review
sqlite3 leads.db ".schema outreach_queue" | grep sender_account_id
sqlite3 leads.db ".schema sender_accounts"
sqlite3 leads.db "SELECT COUNT(*) FROM outreach_queue"  # should be 210
# Idempotency: run again, no error
python -c "import db; db.migrate_db()" && echo "Idempotent OK"
# FK behavior: ON DELETE SET NULL
sqlite3 leads.db "PRAGMA foreign_key_list('outreach_queue')" | grep sender_accounts

# Account management
python run.py account add personal --platform both
python run.py account list
python run.py account login personal  # manual login, then press Enter

# Go/no-go gate: should refuse before confirm-risk
python run.py campaign send 7 --limit 5  # expect: "Run account confirm-risk first"
python run.py account confirm-risk personal
python run.py campaign send 7 --limit 5  # now works

# Quality gate
python run.py campaign gate 7 --limit 5
python run.py campaign queue 7 --status needs_review
python run.py campaign queue 7 --status approved

# Approve-all must NOT touch needs_review
python run.py campaign approve-all 7
python run.py campaign queue 7 --status needs_review  # should still have items

# Browser sender (spike test)
python run.py campaign send 7 --limit 5
python run.py account list  # check sends_today

# Requeue
python run.py campaign requeue 7 --lead 42
```

## Dependencies & Risks

| Dependency | Risk | Mitigation |
|---|---|---|
| Playwright + Chromium | ~200MB download, first-time setup | One-time install, cached in profile_dir |
| Meta UI stability | Facebook/Instagram change selectors frequently | Selectors in constants at top of browser_sender.py, easy to update. Headed mode lets user spot changes. |
| Meta restriction thresholds | Unknown, no published numbers | Spike test, adaptive delays, kill switch, account state machine |
| Claude API availability | Outage blocks quality gate | Gate is a separate step; user can manually approve if API is down |
| SQLite concurrent writes | Two CLI instances could race | Lockfile for sender. Gate is fast enough to be single-user. |

## Sources & References

### Origin

- **Brainstorm:** [docs/brainstorms/2026-05-08-browser-outreach-sender-brainstorm.md](docs/brainstorms/2026-05-08-browser-outreach-sender-brainstorm.md) -- Key decisions carried forward: hybrid approach (requests + Playwright), 9 failure modes, account state machine, adaptive delays, login-walled leads to needs_review.

### Internal References

- Schema migration pattern: `db.py:_migrate_outreach_statuses()` (lines 75-114)
- Atomic update pattern: `campaign.py:approve_message()` (lines ~230)
- Hook verification pattern: `enrich.py:verify_hooks()` (lines 1693-1787)
- CLI dispatch pattern: `run.py:cmd_campaign()` (lines ~300)
- Resilience patterns: `resilience.py:parse_retry_after()` (retry cap at 120s)
- Org detection: `enrich.py:_check_is_org()` patterns

### Solution Docs Applied

- **Reliability hardening** (lead-scraper): inline retry loops, tier=-1 sentinel for transient failures
- **Adaptive batch backoff** (research-agent): only sleep AFTER actual issue, not defensively
- **Atomic claim** (gig-lead-responder): UPDATE WHERE + rowcount for state transitions
- **Schema migration chains** (gigprep): explicit key-existence checks, check-before-act
- **Quality gate enforcement** (research-agent): concrete action menus, not vague instructions

## Feed-Forward

- **Hardest decision:** Where to put the write boundary. quality_gate.py and browser_sender.py could write directly to the DB, but preserving campaign.py as single-writer for outreach_queue keeps the codebase consistent with its own documented conventions. The trade-off is more functions in campaign.py, but each is a 5-line atomic UPDATE.
- **Rejected alternatives:** Direct DB writes from new modules (breaks single-writer), Flask API endpoints for sender (unnecessary complexity for a CLI-first tool), headless browser (higher detection risk, can't visually monitor).
- **Least confident:** Three things, in order of impact: (1) **Rapid account restriction** -- if Meta restricts accounts faster than the user can add/warm them, the tool degrades to a message list (manual copy-paste from the queue). The go/no-go gate + spike test + kill switch mitigate this, but the outcome is not under our control. (2) **Playwright selector stability** -- selectors will be discovered during spike test and WILL break when Meta updates UI. Mitigation: selectors as constants, headed mode for instant visibility, manual fallback always works. (3) **Claude Haiku accuracy** -- concrete audit: after 50 AI-gated leads, spot-check 10 approved + 10 skipped. If >20% error rate, escalate to Sonnet. If >30%, pause AI gate entirely.
