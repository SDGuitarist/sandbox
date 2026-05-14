"""Browser-based DM sender using Playwright.

Sends approved outreach messages via Facebook Messenger and Instagram DMs.
Delegates all DB writes to campaign.py (outreach_queue) and account.py
(sender_accounts) to preserve single-writer rule.
"""

import os
import random
import signal
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse

from db import get_db, DB_PATH
from account import (
    get_active_account, increment_sends, mark_restricted,
    check_cooldown_expired,
)
from campaign import mark_sent_by_sender, skip_dm_restricted

LOCKFILE = Path.home() / ".browser-sender.lock"
STOPFILE = Path.home() / ".browser-sender.stop"

# ---------------------------------------------------------------------------
# Restriction detection
# ---------------------------------------------------------------------------

RESTRICTION_SIGNALS = {
    "facebook": [
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
}

LOGIN_URL_SIGNALS = ["login", "checkpoint"]


def detect_platform(profile_url):
    """Return 'facebook' or 'instagram' from URL domain. None if unknown."""
    domain = urlparse(profile_url).netloc.lower()
    if "instagram.com" in domain:
        return "instagram"
    if "facebook.com" in domain:
        return "facebook"
    return None


def check_for_restriction(page, platform):
    """Check page for restriction signals after a send attempt.

    Returns None if safe, or a string describing the restriction type.
    """
    current_url = page.url.lower()
    for signal_str in LOGIN_URL_SIGNALS:
        if signal_str in current_url:
            return f"session_expired ({signal_str} in URL)"

    try:
        page_text = page.inner_text("body").lower()
    except Exception:
        return None  # Can't read page, don't false-positive

    signals = RESTRICTION_SIGNALS.get(platform, [])
    for signal_str in signals:
        if signal_str in page_text:
            return f"restriction ({signal_str})"

    return None


# ---------------------------------------------------------------------------
# Adaptive delays
# ---------------------------------------------------------------------------

class AdaptiveDelay:
    """Delay manager that increases after issues, decreases after success."""

    def __init__(self):
        self.base_delay = 30       # seconds minimum between sends
        self.max_delay = 90        # seconds maximum
        self.current_delay = 30
        self.sends_since_issue = 0
        self.batch_pause_every = 15
        self.batch_pause_duration = 300  # 5 minutes

    def next_delay(self):
        """Return delay in seconds with jitter."""
        jitter = random.uniform(0.8, 1.2)
        return self.current_delay * jitter

    def on_success(self):
        """Gradually reduce delay after consecutive successes."""
        self.sends_since_issue += 1
        if self.sends_since_issue > 10 and self.current_delay > self.base_delay:
            self.current_delay = max(self.base_delay, self.current_delay - 5)

    def on_warning(self):
        """Increase delay after a soft warning."""
        self.current_delay = min(self.max_delay, self.current_delay + 15)
        self.sends_since_issue = 0

    def should_batch_pause(self, sends_in_session):
        """Return True if it's time for a longer break."""
        return sends_in_session > 0 and sends_in_session % self.batch_pause_every == 0


# ---------------------------------------------------------------------------
# Kill switch
# ---------------------------------------------------------------------------

def setup_kill_switch():
    """Register SIGINT handler. Return a should_stop() callable."""
    state = {"stop": False}

    def handler(signum, frame):
        state["stop"] = True
        print("\nStop requested. Finishing current message...")

    signal.signal(signal.SIGINT, handler)

    def should_stop():
        return state["stop"] or STOPFILE.exists()

    return should_stop


# ---------------------------------------------------------------------------
# Lockfile
# ---------------------------------------------------------------------------

def acquire_lock():
    """Create lockfile with PID. Returns True if acquired, False if another run active."""
    if LOCKFILE.exists():
        try:
            old_pid = int(LOCKFILE.read_text().strip())
            # Check if process is still running
            os.kill(old_pid, 0)
            return False  # Process still alive
        except (ValueError, ProcessLookupError, PermissionError):
            pass  # Stale lock, safe to overwrite

    LOCKFILE.write_text(str(os.getpid()))
    return True


def release_lock():
    """Remove lockfile."""
    if LOCKFILE.exists():
        LOCKFILE.unlink()


# ---------------------------------------------------------------------------
# Platform send flows
# ---------------------------------------------------------------------------

def send_facebook_dm(page, profile_url, message):
    """Send a DM via Facebook Messenger.

    Returns: 'sent', 'dm_restricted', or 'send_failed'.
    Updated after spike test #1: clipboard paste, role-based selectors.
    """
    try:
        page.goto(profile_url, wait_until="networkidle", timeout=30000)
    except Exception:
        page.goto(profile_url, timeout=30000)

    time.sleep(2)  # Let Facebook JS finish rendering

    # Find "Message" button
    msg_button = page.get_by_role("button", name="Message", exact=True)
    try:
        msg_button.wait_for(state="visible", timeout=10000)
    except Exception:
        # Fallback: aria-label and CSS selectors
        msg_button = page.locator(
            'div[aria-label="Message"], '
            'a[aria-label="Message"], '
            'div[role="button"]:has-text("Message")'
        ).first
        try:
            msg_button.wait_for(state="visible", timeout=5000)
        except Exception:
            return "dm_restricted"

    msg_button.click()

    # Wait for Messenger chat input
    chat_input = page.get_by_role("textbox")
    try:
        chat_input.wait_for(state="visible", timeout=15000)
    except Exception:
        chat_input = page.locator(
            'div[role="textbox"][contenteditable="true"]'
        ).last
        try:
            chat_input.wait_for(state="visible", timeout=5000)
        except Exception:
            return "send_failed"

    chat_input.click()
    time.sleep(0.5)

    # Clipboard paste (same fix as Instagram)
    subprocess.run(
        ["pbcopy"],
        input=message.encode("utf-8"),
        check=True,
    )
    page.keyboard.press("Meta+v")
    time.sleep(1)

    # Verify text appeared before sending
    try:
        input_text = chat_input.inner_text()
        if not input_text.strip():
            chat_input.type(message, delay=30)
            time.sleep(0.5)
    except Exception:
        pass

    page.keyboard.press("Enter")
    time.sleep(3)

    # Verify message appeared in conversation
    try:
        snippet = message[:50]
        if page.locator(f"text={snippet}").count() > 0:
            return "sent"
        remaining = chat_input.inner_text()
        if not remaining.strip():
            return "sent"
    except Exception:
        pass

    return "send_failed"


def send_instagram_dm(page, profile_url, message):
    """Send a DM via Instagram.

    Returns: 'sent', 'dm_restricted', or 'send_failed'.
    Updated after spike test #1: use get_by_role for resilience,
    clipboard paste for contenteditable, verify message appeared.
    """
    try:
        page.goto(profile_url, wait_until="networkidle", timeout=30000)
    except Exception:
        page.goto(profile_url, timeout=30000)

    time.sleep(2)  # Let Instagram JS finish rendering

    # Find "Message" button using role-based selector (resilient to DOM changes)
    msg_button = page.get_by_role("button", name="Message", exact=True)
    try:
        msg_button.wait_for(state="visible", timeout=10000)
    except Exception:
        # Fallback: broader CSS selector
        msg_button = page.locator(
            'div[role="button"]:has-text("Message"), '
            'button:has-text("Message"), '
            'a:has-text("Message")'
        ).first
        try:
            msg_button.wait_for(state="visible", timeout=5000)
        except Exception:
            return "dm_restricted"

    msg_button.click()

    # Wait for navigation to DM thread
    try:
        page.wait_for_url("**/direct/**", timeout=15000)
    except Exception:
        # May already be on direct page or URL pattern differs
        time.sleep(3)

    # Find chat input using role-based selector
    chat_input = page.get_by_role("textbox")
    try:
        chat_input.wait_for(state="visible", timeout=15000)
    except Exception:
        # Fallback: CSS selectors for contenteditable
        chat_input = page.locator(
            'div[contenteditable="true"], '
            'p[contenteditable="true"]'
        ).last
        try:
            chat_input.wait_for(state="visible", timeout=5000)
        except Exception:
            return "send_failed"

    # Click to focus the input
    chat_input.click()
    time.sleep(0.5)

    # Use clipboard paste -- fill()/type() don't work on Instagram's
    # contenteditable React inputs (discovered in spike test #1)
    subprocess.run(
        ["pbcopy"],
        input=message.encode("utf-8"),
        check=True,
    )
    # Cmd+V on macOS to paste
    page.keyboard.press("Meta+v")
    time.sleep(1)

    # Verify text appeared in the input before sending
    try:
        input_text = chat_input.inner_text()
        if not input_text.strip():
            # Paste didn't work -- try type() as last resort
            chat_input.type(message, delay=30)
            time.sleep(0.5)
    except Exception:
        pass  # Can't verify, proceed anyway

    page.keyboard.press("Enter")
    time.sleep(3)

    # Verify: check if our message text appears in the conversation
    try:
        # Look for our message in the thread (first 50 chars to avoid partial matches)
        snippet = message[:50]
        if page.locator(f"text={snippet}").count() > 0:
            return "sent"
        # Fallback: if we can't find the text, check if the input cleared
        # (Instagram clears input after successful send)
        remaining = chat_input.inner_text()
        if not remaining.strip():
            return "sent"  # Input cleared = likely sent
    except Exception:
        pass

    return "send_failed"


# ---------------------------------------------------------------------------
# Main send loop
# ---------------------------------------------------------------------------

def run_send(campaign_id, limit, db_path=DB_PATH):
    """Send approved messages via Playwright browser automation.

    Requires: at least one risk-acknowledged account, approved messages in queue.
    Uses lockfile to prevent concurrent runs (leads.db safety).
    """
    # 0. Lockfile -- prevent concurrent DB access
    if not acquire_lock():
        print("Another send session is running. Remove ~/.browser-sender.lock if stale.")
        return

    try:
        _run_send_inner(campaign_id, limit, db_path)
    finally:
        release_lock()
        # Clean up stop file if it was used
        if STOPFILE.exists():
            STOPFILE.unlink()


def _run_send_inner(campaign_id, limit, db_path):
    """Inner send loop (lockfile already acquired)."""
    from playwright.sync_api import sync_playwright

    # 1. Check cooldown expirations
    check_cooldown_expired(db_path)

    # 2. Query approved messages
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT oq.lead_id, oq.full_message, l.name, l.profile_url "
            "FROM outreach_queue oq "
            "JOIN leads l ON oq.lead_id = l.id "
            "WHERE oq.campaign_id = ? AND oq.status = 'approved' "
            "ORDER BY oq.id LIMIT ?",
            (campaign_id, limit),
        ).fetchall()

    if not rows:
        print("No approved messages to send.")
        return

    print(f"Found {len(rows)} approved messages to send.\n")

    # 3. GO/NO-GO: check for eligible account
    test_account = get_active_account("facebook", db_path)
    if not test_account:
        test_account = get_active_account("instagram", db_path)
    if not test_account:
        print("No risk-acknowledged accounts available.")
        print("Run: python run.py account confirm-risk <name>")
        return

    # 4. Set up kill switch and delay manager
    should_stop = setup_kill_switch()
    delay = AdaptiveDelay()

    # 5. Track results
    sent_count = 0
    skipped_count = 0
    failed_count = 0
    active_browsers = {}  # account_id -> (pw, context)

    try:
        pw = sync_playwright().start()

        for i, row in enumerate(rows):
            if should_stop():
                print("\nStopping gracefully...")
                break

            lead_id = row["lead_id"]
            lead_name = row["name"][:30]
            profile_url = row["profile_url"]
            message = row["full_message"]

            # Detect platform
            platform = detect_platform(profile_url) if profile_url else None
            if not platform:
                print(f"  {i+1}/{len(rows)} {lead_name}: no valid profile URL, skipping")
                skip_dm_restricted(campaign_id, lead_id, db_path)
                skipped_count += 1
                continue

            # Get eligible account for this platform
            account = get_active_account(platform, db_path)
            if not account:
                print(f"\nNo eligible account for {platform}. Stopping.")
                break

            account_id = account["id"]

            # Open or reuse browser for this account
            if account_id not in active_browsers:
                profile_dir = account["profile_dir"]
                Path(profile_dir).mkdir(parents=True, exist_ok=True)
                context = pw.chromium.launch_persistent_context(
                    user_data_dir=profile_dir,
                    headless=False,
                    viewport={"width": 1280, "height": 800},
                )
                active_browsers[account_id] = context
                print(f"  Opened browser for account '{account['name']}'")

            context = active_browsers[account_id]
            page = context.pages[0] if context.pages else context.new_page()

            # Send message
            print(f"  {i+1}/{len(rows)} {lead_name} ({platform})...", end=" ", flush=True)

            if platform == "facebook":
                result = send_facebook_dm(page, profile_url, message)
            else:
                result = send_instagram_dm(page, profile_url, message)

            # Handle result
            if result == "sent":
                mark_sent_by_sender(campaign_id, lead_id, account_id, db_path)
                increment_sends(account_id, db_path)
                delay.on_success()
                sent_count += 1
                print("sent")
            elif result == "dm_restricted":
                skip_dm_restricted(campaign_id, lead_id, db_path)
                skipped_count += 1
                print("DM restricted (no Message button)")
            else:
                failed_count += 1
                print("send failed")
                delay.on_warning()

            # Check for account-level restriction after send
            restriction = check_for_restriction(page, platform)
            if restriction:
                print(f"\n  RESTRICTION DETECTED: {restriction}")
                print(f"  Marking account '{account['name']}' as restricted.")
                mark_restricted(account_id, db_path)
                # Close this account's browser
                if account_id in active_browsers:
                    active_browsers[account_id].close()
                    del active_browsers[account_id]
                continue  # Try next message with different account

            # Batch pause check
            if delay.should_batch_pause(sent_count):
                pause = delay.batch_pause_duration
                print(f"\n  Batch pause: {pause // 60} minutes...")
                time.sleep(pause)

            # Delay before next send
            if i < len(rows) - 1:
                wait = delay.next_delay()
                print(f"  Waiting {wait:.0f}s...", end=" ", flush=True)
                time.sleep(wait)
                print("ok")

    finally:
        # Close all browsers
        for ctx in active_browsers.values():
            try:
                ctx.close()
            except Exception:
                pass
        try:
            pw.stop()
        except Exception:
            pass

    # Print summary
    print(f"\n{'='*40}")
    print(f"Send complete:")
    print(f"  Sent:    {sent_count}")
    print(f"  Skipped: {skipped_count}")
    print(f"  Failed:  {failed_count}")
    print(f"{'='*40}")
