from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import sqlite3
import smtplib
import subprocess
import time
from datetime import datetime, timezone
from email.message import EmailMessage

from config import (
    get_alert_email_from,
    get_alert_email_to,
    get_smtp_host,
    get_smtp_password,
    get_smtp_port,
    get_smtp_use_tls,
    get_smtp_username,
)

# Canonical DB path: same directory as this file
DB_PATH = Path(__file__).parent / "leads.db"
DB_JOB_LOCKFILE = Path.home() / ".lead-scraper-db.lock"
DB_HEALTH_DROP_WARN_FRACTION = 0.20
DB_HEALTH_DROP_WARN_MIN_LEADS = 100
DB_HEALTH_DROP_WARN_MIN_BYTES = 256 * 1024


class MigrationRequired(RuntimeError):
    """Raised when a normal startup sees a migration that must be run explicitly."""


class MigrationSafetyError(RuntimeError):
    """Raised when a database operation would risk the production database."""


class DatabaseHealthError(MigrationSafetyError):
    """Raised when the database is missing, corrupted, or looks wiped."""


def _is_production_db(db_path):
    """Return True if db_path is the real production leads.db."""
    return Path(db_path).resolve() == DB_PATH.resolve()


def _running_under_pytest():
    return bool(os.environ.get("PYTEST_CURRENT_TEST"))


def _assert_not_pytest_production(db_path):
    if _running_under_pytest() and _is_production_db(db_path):
        raise MigrationSafetyError(
            "Tests may not open the production leads.db. Pass a tmp_path database instead."
        )


def _assert_production_file_ready(db_path, *, allow_create=False):
    if not _is_production_db(db_path):
        return
    if allow_create:
        return
    path = Path(db_path)
    if not path.exists():
        raise MigrationSafetyError(
            f"Production database is missing: {path}. Restore from backup; "
            "normal startup will not create an empty leads.db."
        )
    if path.stat().st_size == 0:
        raise MigrationSafetyError(
            f"Production database is empty: {path}. Restore from backup; "
            "normal startup will not bootstrap a blank leads.db."
        )


def _destructive_migration_allowed(db_path, *, allow_production=False):
    """Guard: destructive migrations (DROP TABLE) only allowed if:
    1. db_path is not the production DB, OR
    2. production destruction was explicitly requested by a migration command.
    """
    if not _is_production_db(db_path):
        return True  # Test DB or copy -- always allowed
    return allow_production


@contextmanager
def get_db(db_path=DB_PATH, *, allow_create=False):
    """Context manager for SQLite connections. Works from CLI and Flask."""
    db_path = Path(db_path)
    _assert_not_pytest_production(db_path)
    _assert_production_file_ready(db_path, allow_create=allow_create)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


_SAFE_IDENTIFIER = re.compile(r"^[a-z_]+$")


def _backup_wal_safe(db_path):
    """WAL-safe backup via sqlite3.backup(). Called once before any schema change."""
    backup = db_path.with_suffix(
        f".backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.db"
    )
    src_conn = sqlite3.connect(str(db_path))
    dst_conn = sqlite3.connect(str(backup))
    src_conn.backup(dst_conn)
    dst_conn.close()
    src_conn.close()
    print(f"Backup created: {backup.name}")


def get_db_health_snapshot_path(db_path=DB_PATH) -> Path:
    db_path = Path(db_path)
    return db_path.with_suffix(".health.json")


def _load_db_health_snapshot(db_path=DB_PATH) -> dict | None:
    snapshot_path = get_db_health_snapshot_path(db_path)
    if not snapshot_path.exists():
        return None
    return json.loads(snapshot_path.read_text())


def write_db_health_snapshot(db_path=DB_PATH, health=None) -> dict:
    if health is None:
        health = collect_db_health(db_path)
    snapshot_path = get_db_health_snapshot_path(db_path)
    snapshot_path.write_text(json.dumps(health, indent=2, sort_keys=True) + "\n")
    return health


def _send_macos_notification(title: str, message: str) -> None:
    script = (
        'display notification '
        f'"{message.replace(chr(34), chr(39))}" '
        f'with title "{title.replace(chr(34), chr(39))}"'
    )
    try:
        subprocess.run(
            ["osascript", "-e", script],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return


def _send_email_notification(subject: str, message: str) -> None:
    smtp_host = get_smtp_host()
    smtp_from = get_alert_email_from()
    smtp_to = get_alert_email_to()
    if not smtp_host or not smtp_from or not smtp_to:
        return

    email = EmailMessage()
    email["Subject"] = subject
    email["From"] = smtp_from
    email["To"] = smtp_to
    email.set_content(message)

    with smtplib.SMTP(smtp_host, get_smtp_port(), timeout=10) as server:
        if get_smtp_use_tls():
            server.starttls()
        username = get_smtp_username()
        password = get_smtp_password()
        if username and password:
            server.login(username, password)
        server.send_message(email)


def collect_db_health(db_path=DB_PATH) -> dict:
    db_path = Path(db_path)
    health = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "db_path": str(db_path),
        "exists": db_path.exists(),
        "file_size": db_path.stat().st_size if db_path.exists() else 0,
        "integrity_ok": False,
        "integrity_message": "missing",
        "missing_tables": [],
        "lead_count": None,
        "campaign_count": None,
        "queue_count": None,
    }
    if not health["exists"]:
        return health
    if health["file_size"] == 0:
        health["integrity_message"] = "empty"
        return health

    conn = sqlite3.connect(str(db_path))
    try:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        core_tables = {"leads", "campaigns", "outreach_queue"}
        missing_tables = sorted(core_tables - tables)
        health["missing_tables"] = missing_tables
        if missing_tables:
            health["integrity_message"] = "missing core tables"
            return health

        integrity_row = conn.execute("PRAGMA integrity_check").fetchone()
        integrity_message = integrity_row[0] if integrity_row else "unknown"
        health["integrity_message"] = integrity_message
        health["integrity_ok"] = integrity_message == "ok"
        health["lead_count"] = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        health["campaign_count"] = conn.execute("SELECT COUNT(*) FROM campaigns").fetchone()[0]
        health["queue_count"] = conn.execute("SELECT COUNT(*) FROM outreach_queue").fetchone()[0]
        return health
    finally:
        conn.close()


def evaluate_db_health(health: dict, previous: dict | None = None, *, expected_drop_allowed=False):
    hard_errors = []
    warnings = []

    if not health["exists"]:
        hard_errors.append(f"Database file is missing: {health['db_path']}")
        return hard_errors, warnings
    if health["file_size"] == 0:
        hard_errors.append(f"Database file is empty: {health['db_path']}")
        return hard_errors, warnings
    if health["missing_tables"]:
        hard_errors.append(
            "Core tables are missing: " + ", ".join(health["missing_tables"])
        )
    if not health["integrity_ok"]:
        hard_errors.append(
            f"SQLite integrity check failed: {health['integrity_message']}"
        )

    if previous is None:
        return hard_errors, warnings

    previous_leads = previous.get("lead_count")
    current_leads = health.get("lead_count")
    if (
        not expected_drop_allowed
        and previous_leads is not None
        and current_leads is not None
        and previous_leads >= DB_HEALTH_DROP_WARN_MIN_LEADS
    ):
        drop = previous_leads - current_leads
        if current_leads == 0 and previous_leads > 0:
            hard_errors.append(
                f"Lead count collapsed from {previous_leads} to 0 since the last snapshot."
            )
        elif drop > 0 and (drop / previous_leads) >= DB_HEALTH_DROP_WARN_FRACTION:
            warnings.append(
                f"Lead count dropped from {previous_leads} to {current_leads} "
                f"({drop} fewer, {drop / previous_leads:.0%} drop)."
            )

    previous_size = previous.get("file_size")
    current_size = health.get("file_size")
    if (
        previous_size
        and current_size is not None
        and previous_size >= DB_HEALTH_DROP_WARN_MIN_BYTES
        and current_size < previous_size
    ):
        byte_drop = previous_size - current_size
        if (byte_drop / previous_size) >= DB_HEALTH_DROP_WARN_FRACTION:
            warnings.append(
                f"Database file size dropped from {previous_size} bytes to "
                f"{current_size} bytes ({byte_drop / previous_size:.0%} drop)."
            )

    for label, key in (("campaign count", "campaign_count"), ("queue count", "queue_count")):
        previous_value = previous.get(key)
        current_value = health.get(key)
        if (
            previous_value is not None
            and current_value is not None
            and previous_value > 0
            and current_value < previous_value
        ):
            drop = previous_value - current_value
            if (drop / previous_value) >= DB_HEALTH_DROP_WARN_FRACTION:
                warnings.append(
                    f"{label.capitalize()} dropped from {previous_value} to {current_value}."
                )

    return hard_errors, warnings


def run_db_health_check(
    db_path=DB_PATH,
    *,
    refresh_snapshot=False,
    expected_drop_allowed=False,
    notify=False,
):
    health = collect_db_health(db_path)
    previous = _load_db_health_snapshot(db_path)
    hard_errors, warnings = evaluate_db_health(
        health,
        previous,
        expected_drop_allowed=expected_drop_allowed,
    )
    if hard_errors:
        if notify:
            _send_macos_notification("Lead Scraper DB Alert", hard_errors[0])
            _send_email_notification("Lead Scraper DB Alert", hard_errors[0])
        raise DatabaseHealthError(" ; ".join(hard_errors))
    if warnings and notify:
        _send_macos_notification("Lead Scraper DB Warning", warnings[0])
        _send_email_notification("Lead Scraper DB Warning", warnings[0])
    if refresh_snapshot:
        write_db_health_snapshot(db_path, health)
    return health, warnings


def create_backup(db_path=DB_PATH):
    """Create a WAL-safe backup of the given database."""
    db_path = Path(db_path)
    _assert_not_pytest_production(db_path)
    _assert_production_file_ready(db_path)
    _backup_wal_safe(db_path)


def acquire_db_job_lock(lock_path=DB_JOB_LOCKFILE):
    """Acquire a global DB job lock. Returns True if acquired."""
    lock_path = Path(lock_path)
    if lock_path.exists():
        try:
            old_pid = int(lock_path.read_text().strip())
            os.kill(old_pid, 0)
            return False
        except (ValueError, ProcessLookupError, PermissionError):
            pass

    lock_path.write_text(str(os.getpid()))
    return True


def release_db_job_lock(lock_path=DB_JOB_LOCKFILE):
    """Release the global DB job lock."""
    lock_path = Path(lock_path)
    if lock_path.exists():
        lock_path.unlink()


@contextmanager
def db_job_lock(lock_path=DB_JOB_LOCKFILE):
    """Context manager for the global DB job lock."""
    if not acquire_db_job_lock(lock_path):
        raise MigrationSafetyError(
            f"Another DB job is running. Wait or remove stale lock: {lock_path}"
        )
    try:
        yield
    finally:
        release_db_job_lock(lock_path)


def migrate_db(db_path=DB_PATH, *, allow_destructive=False):
    """Run all schema migrations. Idempotent and safe to re-run."""
    db_path = Path(db_path)
    _assert_not_pytest_production(db_path)
    _assert_production_file_ready(db_path)
    if not db_path.exists():
        return  # No DB to migrate; init_db will create fresh schema

    # --- leads table column additions ---
    new_columns = [
        ("phone", "TEXT"),
        ("website", "TEXT"),
        ("enriched_at", "TEXT"),
        ("social_handles", "TEXT"),
        ("profile_bio", "TEXT"),
        ("ig_profile_enriched_at", "TEXT"),
        ("segment", "TEXT"),
        ("segment_confidence", "REAL"),
        ("hook_text", "TEXT"),
        ("hook_source_url", "TEXT"),
        ("hook_quality", "INTEGER"),
        ("manual_approved", "INTEGER DEFAULT 0"),
        ("hook_verified", "INTEGER DEFAULT 0"),
        ("is_sendable", "INTEGER DEFAULT 1"),
        ("sendable_reason", "TEXT"),
        ("skip_count", "INTEGER DEFAULT 0"),
    ]
    with get_db(db_path) as conn:
        existing = {row[1] for row in conn.execute("PRAGMA table_info(leads)")}
        to_add = [(n, t) for n, t in new_columns if n not in existing]

        # Check if sender migrations are needed
        sender_table_exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='sender_accounts'"
        ).fetchone()
        needs_queue_migration = _needs_queue_migration(conn)

        if needs_queue_migration and _is_production_db(db_path) and not allow_destructive:
            raise MigrationRequired(
                "Production outreach_queue needs a destructive schema migration. "
                "Run: python run.py migrate --allow-destructive-production"
            )

        needs_backup = to_add or not sender_table_exists or needs_queue_migration

        if needs_backup:
            _backup_wal_safe(db_path)

        if to_add:
            for col_name, col_type in to_add:
                if not _SAFE_IDENTIFIER.match(col_name):
                    raise ValueError(f"Unsafe column name: {col_name!r}")
                conn.execute(f"ALTER TABLE leads ADD COLUMN {col_name} {col_type}")

    # --- sender module migrations (always run, independent of leads) ---
    _create_sender_accounts(db_path)
    _migrate_needs_review_status(db_path, allow_destructive=allow_destructive)


def _needs_queue_migration(conn):
    """Check if outreach_queue needs the needs_review + sender migration."""
    create_sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='outreach_queue'"
    ).fetchone()
    if not create_sql:
        return False  # Table doesn't exist yet

    cols = {row[1] for row in conn.execute("PRAGMA table_info('outreach_queue')")}
    already_has_status = "'needs_review'" in create_sql[0]
    already_has_columns = {'skip_reason', 'gate_checked_at', 'sender_account_id'}.issubset(cols)
    already_has_fk = any(
        row['table'] == 'sender_accounts'
        for row in conn.execute("PRAGMA foreign_key_list('outreach_queue')").fetchall()
    )
    return not (already_has_status and already_has_columns and already_has_fk)


def _create_sender_accounts(db_path=DB_PATH):
    """Create sender_accounts table. Idempotent: CREATE IF NOT EXISTS."""
    with get_db(db_path) as conn:
        conn.execute("""
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
            )
        """)


def _migrate_needs_review_status(db_path=DB_PATH, *, allow_destructive=False):
    """Add needs_review status, skip_reason, gate_checked_at, sender_account_id FK.

    Recreates outreach_queue (SQLite can't ALTER CHECK constraints).
    Stages and validates the replacement table before dropping the old table.

    DESTRUCTIVE: uses DROP TABLE. Guarded against accidental production runs.
    Use `python run.py migrate --allow-destructive-production` for production.
    """
    db_path = Path(db_path)
    _assert_not_pytest_production(db_path)
    _assert_production_file_ready(db_path)
    with get_db(db_path) as conn:
        create_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='outreach_queue'"
        ).fetchone()
        if not create_sql:
            return  # Table doesn't exist yet (initial setup handles it)

        cols = {row[1] for row in conn.execute("PRAGMA table_info('outreach_queue')")}
        already_has_status = "'needs_review'" in create_sql[0]
        already_has_columns = {'skip_reason', 'gate_checked_at', 'sender_account_id'}.issubset(cols)
        already_has_fk = any(
            row['table'] == 'sender_accounts'
            for row in conn.execute("PRAGMA foreign_key_list('outreach_queue')").fetchall()
        )

        if already_has_status and already_has_columns and already_has_fk:
            return  # Already migrated

    # Past this point: DROP TABLE will happen. Block unless explicitly allowed.
    if not _destructive_migration_allowed(db_path, allow_production=allow_destructive):
        raise MigrationRequired(
            "Production outreach_queue needs a destructive schema migration. "
            "Run: python run.py migrate --allow-destructive-production"
        )

    with get_db(db_path) as conn:
        pre_count = conn.execute("SELECT COUNT(*) FROM outreach_queue").fetchone()[0]
        cols = {row[1] for row in conn.execute("PRAGMA table_info('outreach_queue')")}
        skip_reason_expr = "skip_reason" if "skip_reason" in cols else "NULL"
        gate_checked_at_expr = "gate_checked_at" if "gate_checked_at" in cols else "NULL"
        sender_account_expr = "sender_account_id" if "sender_account_id" in cols else "NULL"

        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DROP TABLE IF EXISTS outreach_queue_new")
        conn.execute("""
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
            )
        """)

        conn.execute(f"""
            INSERT INTO outreach_queue_new
                (id, lead_id, campaign_id, opener_text, template_text, full_message,
                 status, generated_at, approved_at, sent_at,
                 skip_reason, gate_checked_at, sender_account_id)
            SELECT id, lead_id, campaign_id, opener_text, template_text, full_message,
                   status, generated_at, approved_at, sent_at,
                   {skip_reason_expr}, {gate_checked_at_expr}, {sender_account_expr}
            FROM outreach_queue
        """)

        staged_count = conn.execute(
            "SELECT COUNT(*) FROM outreach_queue_new"
        ).fetchone()[0]
        if staged_count != pre_count:
            raise MigrationSafetyError(
                f"Migration staged data loss: {pre_count} rows before, "
                f"{staged_count} staged"
            )

        staged_cols = {
            row[1] for row in conn.execute("PRAGMA table_info('outreach_queue_new')")
        }
        missing = {'skip_reason', 'gate_checked_at', 'sender_account_id'} - staged_cols
        if missing:
            raise MigrationSafetyError(
                f"Migration failed before table swap; missing columns: {sorted(missing)}"
            )

        conn.execute("DROP TABLE outreach_queue")
        conn.execute("ALTER TABLE outreach_queue_new RENAME TO outreach_queue")
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_outreach_queue_campaign_status
                ON outreach_queue(campaign_id, status)
        """)

        post_count = conn.execute("SELECT COUNT(*) FROM outreach_queue").fetchone()[0]
        if post_count != pre_count:
            raise MigrationSafetyError(
                f"Migration data loss after table swap: {pre_count} rows before, "
                f"{post_count} after"
            )

        print(f"outreach_queue migrated: {post_count} rows preserved (== {pre_count}), "
              f"needs_review status + 3 columns + FK added")


def _migrate_outreach_statuses(db_path=DB_PATH, *, allow_destructive=False):
    """Expand outreach_queue status CHECK to include response tracking statuses.

    NOTE: Superseded by _migrate_needs_review_status() which adds the same
    statuses plus needs_review, skip_reason, gate_checked_at, sender_account_id.
    Kept for backwards compatibility; delegates to the safer combined migration.
    """
    _migrate_needs_review_status(db_path, allow_destructive=allow_destructive)


def init_db(db_path=DB_PATH, *, allow_destructive=False, allow_create_production=False):
    """Create tables from schema.sql and schema_campaigns.sql. Safe to call repeatedly."""
    db_path = Path(db_path)
    _assert_not_pytest_production(db_path)
    _assert_production_file_ready(db_path, allow_create=allow_create_production)

    ran_pre_schema_migration = False
    if _is_production_db(db_path) and db_path.exists():
        with get_db(db_path) as conn:
            needs_queue_migration = _needs_queue_migration(conn)
        if needs_queue_migration:
            if not allow_destructive:
                raise MigrationRequired(
                    "Production outreach_queue needs a destructive schema migration. "
                    "Run: python run.py migrate --allow-destructive-production"
                )
            migrate_db(db_path, allow_destructive=True)
            ran_pre_schema_migration = True

    base_dir = Path(__file__).parent
    with get_db(db_path, allow_create=allow_create_production) as conn:
        conn.executescript((base_dir / "schema.sql").read_text())
        campaigns_schema = base_dir / "schema_campaigns.sql"
        if campaigns_schema.exists():
            conn.executescript(campaigns_schema.read_text())
    if not ran_pre_schema_migration:
        migrate_db(db_path, allow_destructive=allow_destructive)
    # Index on leads columns added by migrate_db (must run after migration)
    with get_db(db_path) as conn:
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_leads_segment_quality "
            "ON leads(segment, hook_quality)"
        )
