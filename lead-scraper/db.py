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


def migrate_db(db_path=DB_PATH):
    """Add new columns to existing leads table. Idempotent and safe to re-run."""
    if not db_path.exists():
        return  # No DB to migrate; init_db will create fresh schema

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
    ]
    with get_db(db_path) as conn:
        existing = {row[1] for row in conn.execute("PRAGMA table_info(leads)")}
        to_add = [(n, t) for n, t in new_columns if n not in existing]
        if not to_add:
            return  # Schema is up to date, no backup needed

        # Backup only when we actually need to alter the schema
        # Use sqlite3.backup() instead of shutil.copy2() -- WAL-safe
        backup = db_path.with_suffix(
            f".backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.db"
        )
        src_conn = sqlite3.connect(str(db_path))
        dst_conn = sqlite3.connect(str(backup))
        src_conn.backup(dst_conn)
        dst_conn.close()
        src_conn.close()

        for col_name, col_type in to_add:
            if not _SAFE_IDENTIFIER.match(col_name):
                raise ValueError(f"Unsafe column name: {col_name!r}")
            conn.execute(f"ALTER TABLE leads ADD COLUMN {col_name} {col_type}")


def _migrate_outreach_statuses(db_path=DB_PATH):
    """Expand outreach_queue status CHECK to include response tracking statuses.

    SQLite doesn't support ALTER CHECK, so we recreate the table if needed.
    Uses get_db to avoid WAL lock conflicts with other connections.
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
