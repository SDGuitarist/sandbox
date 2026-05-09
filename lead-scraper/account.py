"""Sender account management: CRUD + state machine for sender_accounts table.

Single-writer rule: only this module writes to sender_accounts.
State machine: active -> restricted -> cooldown -> active (or any -> disabled).
"""

from datetime import datetime, timedelta
from pathlib import Path

from db import get_db, DB_PATH

BROWSER_PROFILES_DIR = Path.home() / ".browser-profiles"


def add_account(name, platform='both', profile_dir=None, daily_cap=30,
                db_path=DB_PATH):
    """Insert a new sender account.

    Auto-generates profile_dir as ~/.browser-profiles/<name>/ if not specified.
    Raises sqlite3.IntegrityError if name already exists.
    """
    if profile_dir is None:
        profile_dir = str(BROWSER_PROFILES_DIR / name)

    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO sender_accounts (name, platform, profile_dir, daily_cap) "
            "VALUES (?, ?, ?, ?)",
            (name, platform, profile_dir, daily_cap),
        )
    print(f"Account '{name}' added (platform={platform}, cap={daily_cap}).")
    print(f"Profile dir: {profile_dir}")
    print(f"Next: python run.py account login {name}")


def list_accounts(db_path=DB_PATH):
    """Print all sender accounts with status and send counts."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT id, name, platform, status, sends_today, daily_cap, "
            "last_send_at, risk_acknowledged, cooldown_until "
            "FROM sender_accounts ORDER BY id"
        ).fetchall()

    if not rows:
        print("No sender accounts. Add one: python run.py account add <name>")
        return

    print(f"\n{'ID':<4} {'Name':<20} {'Platform':<10} {'Status':<12} "
          f"{'Sends':<10} {'Risk':<6} {'Last Send'}")
    print("-" * 80)
    for r in rows:
        sends = f"{r['sends_today']}/{r['daily_cap']}"
        risk = "yes" if r['risk_acknowledged'] else "no"
        last = r['last_send_at'] or "-"
        status = r['status']
        if status == 'cooldown' and r['cooldown_until']:
            status = f"cooldown ({r['cooldown_until'][:16]})"
        print(f"{r['id']:<4} {r['name']:<20} {r['platform']:<10} {status:<12} "
              f"{sends:<10} {risk:<6} {last}")
    print(f"\nTotal: {len(rows)} accounts")


def get_active_account(platform, db_path=DB_PATH):
    """Return the next eligible account for sending on the given platform.

    Eligible: status='active', sends_today < daily_cap, risk_acknowledged=1,
    platform matches (exact or 'both'). Picks lowest sends_today (load balance).
    Returns None if no eligible accounts.
    """
    today = datetime.now().strftime("%Y-%m-%d")

    with get_db(db_path) as conn:
        # Lazy reset: reset sends_today for any active account on a new day
        conn.execute(
            "UPDATE sender_accounts SET sends_today = 0, last_reset_date = ? "
            "WHERE status = 'active' AND (last_reset_date IS NULL OR last_reset_date != ?)",
            (today, today),
        )

        row = conn.execute(
            "SELECT * FROM sender_accounts "
            "WHERE status = 'active' "
            "AND sends_today < daily_cap "
            "AND risk_acknowledged = 1 "
            "AND platform IN (?, 'both') "
            "ORDER BY sends_today ASC LIMIT 1",
            (platform,),
        ).fetchone()

    return dict(row) if row else None


def increment_sends(account_id, db_path=DB_PATH):
    """Atomically increment sends_today and update last_send_at.

    Lazy-resets sends_today if it's a new day. Only increments if status='active'.
    Raises AssertionError if account not found or not active.
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    today = now[:10]

    with get_db(db_path) as conn:
        # Lazy reset for this specific account
        conn.execute(
            "UPDATE sender_accounts SET sends_today = 0, last_reset_date = ? "
            "WHERE id = ? AND (last_reset_date IS NULL OR last_reset_date != ?)",
            (today, account_id, today),
        )

        cursor = conn.execute(
            "UPDATE sender_accounts "
            "SET sends_today = sends_today + 1, last_send_at = ? "
            "WHERE id = ? AND status = 'active'",
            (now, account_id),
        )
        assert cursor.rowcount > 0, (
            f"increment_sends failed: account {account_id} not found or not active"
        )


def mark_restricted(account_id, db_path=DB_PATH):
    """Set status='restricted'. Only transitions active -> restricted.

    Raises AssertionError if account not active.
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_db(db_path) as conn:
        cursor = conn.execute(
            "UPDATE sender_accounts SET status = 'restricted', restricted_at = ? "
            "WHERE id = ? AND status = 'active'",
            (now, account_id),
        )
        assert cursor.rowcount > 0, (
            f"mark_restricted failed: account {account_id} not found or not active"
        )
    print(f"Account {account_id} marked restricted at {now}.")


def set_cooldown(account_id, hours, db_path=DB_PATH):
    """Set cooldown period. Only transitions restricted -> cooldown.

    Raises AssertionError if account not in 'restricted' status.
    """
    now = datetime.now()
    until = (now + timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")

    with get_db(db_path) as conn:
        cursor = conn.execute(
            "UPDATE sender_accounts SET status = 'cooldown', cooldown_until = ? "
            "WHERE id = ? AND status = 'restricted'",
            (until, account_id),
        )
        assert cursor.rowcount > 0, (
            f"set_cooldown failed: account {account_id} not found or not restricted"
        )
    print(f"Account {account_id} cooling down until {until}.")


def check_cooldown_expired(db_path=DB_PATH):
    """Reactivate any accounts whose cooldown has expired.

    Automatically called before each send run. Transitions cooldown -> active.
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    today = now[:10]

    with get_db(db_path) as conn:
        cursor = conn.execute(
            "UPDATE sender_accounts "
            "SET status = 'active', sends_today = 0, last_reset_date = ?, "
            "cooldown_until = NULL, restricted_at = NULL "
            "WHERE status = 'cooldown' AND cooldown_until <= ?",
            (today, now),
        )
        if cursor.rowcount > 0:
            print(f"Reactivated {cursor.rowcount} account(s) from cooldown.")


def disable_account(account_id, db_path=DB_PATH):
    """Disable an account (any status -> disabled).

    Raises AssertionError if account not found.
    """
    with get_db(db_path) as conn:
        cursor = conn.execute(
            "UPDATE sender_accounts SET status = 'disabled' "
            "WHERE id = ? AND status != 'disabled'",
            (account_id,),
        )
        assert cursor.rowcount > 0, (
            f"disable_account failed: account {account_id} not found or already disabled"
        )
    print(f"Account {account_id} disabled.")


def enable_account(account_id, db_path=DB_PATH):
    """Re-enable a disabled account. Resets sends_today.

    Only transitions disabled -> active.
    Raises AssertionError if account not disabled.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    with get_db(db_path) as conn:
        cursor = conn.execute(
            "UPDATE sender_accounts "
            "SET status = 'active', sends_today = 0, last_reset_date = ? "
            "WHERE id = ? AND status = 'disabled'",
            (today, account_id),
        )
        assert cursor.rowcount > 0, (
            f"enable_account failed: account {account_id} not found or not disabled"
        )
    print(f"Account {account_id} re-enabled.")


def confirm_risk(account_id, db_path=DB_PATH):
    """Acknowledge Meta restriction/ban risk for this account.

    Prompts user with risk warning and requires 'y' confirmation.
    Must be done per-account before any sends will use it.
    """
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT name, risk_acknowledged FROM sender_accounts WHERE id = ?",
            (account_id,),
        ).fetchone()
        assert row, f"Account {account_id} not found."

        if row['risk_acknowledged']:
            print(f"Account '{row['name']}' already has risk acknowledged.")
            return

    print("\n" + "=" * 60)
    print("WARNING: AUTOMATED DM SENDING RISK")
    print("=" * 60)
    print(f"Account: {row['name']}")
    print()
    print("Sending automated DMs via Facebook/Instagram may result in:")
    print("  - Temporary restrictions on your account")
    print("  - Permanent account suspension or ban")
    print("  - Loss of followers, messages, and account history")
    print()
    print("Meta does not publish safe DM thresholds. Any automated")
    print("sending carries inherent risk. Start with low daily caps")
    print("and monitor for restriction signals.")
    print("=" * 60)

    answer = input("\nDo you accept this risk? (y/N): ").strip().lower()
    if answer != 'y':
        print("Risk not acknowledged. Account will not be used for sending.")
        return

    with get_db(db_path) as conn:
        cursor = conn.execute(
            "UPDATE sender_accounts SET risk_acknowledged = 1 WHERE id = ?",
            (account_id,),
        )
        assert cursor.rowcount > 0, f"confirm_risk update failed for account {account_id}"
    print(f"Risk acknowledged for '{row['name']}'. Account eligible for sending.")
