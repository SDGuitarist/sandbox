from contextlib import contextmanager
from pathlib import Path
import re
import sqlite3
from datetime import datetime

# Canonical DB path: same directory as this file
DB_PATH = Path(__file__).parent / "leads.db"


@contextmanager
def get_db(db_path=DB_PATH):
    """Context manager for SQLite connections. Works from CLI and Flask."""
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


def migrate_db(db_path=DB_PATH):
    """Run all schema migrations. Idempotent and safe to re-run."""
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
    _migrate_needs_review_status(db_path)


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


def _migrate_needs_review_status(db_path=DB_PATH):
    """Add needs_review status, skip_reason, gate_checked_at, sender_account_id FK.

    Recreates outreach_queue (SQLite can't ALTER CHECK constraints).
    Pre/post row count assertion prevents silent data loss.
    """
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
        print(f"outreach_queue migrated: {post_count} rows preserved (== {pre_count}), "
              f"needs_review status + 3 columns + FK added")


def _migrate_outreach_statuses(db_path=DB_PATH):
    """Expand outreach_queue status CHECK to include response tracking statuses.

    NOTE: Superseded by _migrate_needs_review_status() which adds the same
    statuses plus needs_review, skip_reason, gate_checked_at, sender_account_id.
    Kept for backwards compat -- runs first, then _migrate_needs_review_status()
    handles the rest.
    """
    if not db_path.exists():
        return

    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='outreach_queue'"
        ).fetchone()
        if not row or "'replied'" in row[0]:
            return  # Table doesn't exist yet or already migrated

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
                                CHECK(status IN ('draft', 'approved', 'sent', 'skipped',
                                                 'replied', 'booked', 'declined', 'no_response')),
                generated_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now')),
                approved_at     TEXT,
                sent_at         TEXT,
                UNIQUE(lead_id, campaign_id)
            );
            INSERT INTO outreach_queue_new SELECT * FROM outreach_queue;
            DROP TABLE outreach_queue;
            ALTER TABLE outreach_queue_new RENAME TO outreach_queue;
            CREATE INDEX IF NOT EXISTS idx_outreach_queue_campaign_status
                ON outreach_queue(campaign_id, status);
        """)
        conn.execute("PRAGMA foreign_keys=ON")


def init_db(db_path=DB_PATH):
    """Create tables from schema.sql and schema_campaigns.sql. Safe to call repeatedly."""
    base_dir = Path(__file__).parent
    with get_db(db_path) as conn:
        conn.executescript((base_dir / "schema.sql").read_text())
        campaigns_schema = base_dir / "schema_campaigns.sql"
        if campaigns_schema.exists():
            conn.executescript(campaigns_schema.read_text())
    migrate_db(db_path)  # Ensure existing DBs get new columns
    _migrate_outreach_statuses(db_path)  # Expand status CHECK constraint
    # Index on leads columns added by migrate_db (must run after migration)
    with get_db(db_path) as conn:
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_leads_segment_quality "
            "ON leads(segment, hook_quality)"
        )
