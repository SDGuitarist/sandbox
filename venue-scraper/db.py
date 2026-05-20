"""Database connection and migration for venue-scraper.

Safety patterns ported from lead-scraper db.py:
- Explicit migrate command (never auto-run on startup)
- pytest guard (_assert_not_pytest_production)
- WAL-safe backup via sqlite3.backup()
- Connection context manager with WAL, foreign keys, busy_timeout
"""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

# Canonical DB path: same directory as this file
DB_PATH = Path(__file__).parent / "venues.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"
HEALTH_PATH = DB_PATH.with_suffix(".health.json")

VALID_STATUSES = ("new", "contacted", "replied", "partnered", "declined")


def _is_production_db(db_path: Path) -> bool:
    """Return True if db_path is the real production venues.db."""
    return Path(db_path).resolve() == DB_PATH.resolve()


def _running_under_pytest() -> bool:
    return bool(os.environ.get("PYTEST_CURRENT_TEST"))


def _assert_not_pytest_production(db_path: Path) -> None:
    """Guard: tests may not touch the production database."""
    if _running_under_pytest() and _is_production_db(db_path):
        raise RuntimeError(
            "Tests may not open the production venues.db. "
            "Pass a tmp_path database instead."
        )


@contextmanager
def get_db(db_path: Path = DB_PATH):
    """Context manager for SQLite connections.

    Enables WAL mode, foreign keys, and busy_timeout.
    Auto-commits on success, rolls back on exception.
    """
    db_path = Path(db_path)
    _assert_not_pytest_production(db_path)
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


def backup_db(db_path: Path = DB_PATH) -> Path:
    """WAL-safe backup via sqlite3.backup(). Returns backup path.

    MUST use sqlite3.backup() -- shutil.copy2() corrupts WAL databases.
    """
    db_path = Path(db_path)
    if not db_path.exists():
        raise FileNotFoundError(f"Cannot backup: {db_path} does not exist")
    backup_path = db_path.with_suffix(
        f".backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.db"
    )
    src = sqlite3.connect(str(db_path))
    dst = sqlite3.connect(str(backup_path))
    src.backup(dst)
    dst.close()
    src.close()
    print(f"Backup created: {backup_path.name}")
    return backup_path


def init_db(db_path: Path = DB_PATH) -> None:
    """Create tables from schema.sql. Called ONLY via 'python scrape.py migrate'.

    Uses individual conn.execute() calls -- NEVER executescript()
    (executescript issues implicit COMMIT, breaking transactional guarantees).
    """
    schema = SCHEMA_PATH.read_text()

    # Back up existing DB before schema changes
    if Path(db_path).exists() and Path(db_path).stat().st_size > 0:
        backup_db(db_path)

    with get_db(db_path) as conn:
        # Split on semicolons and execute each statement individually
        for statement in schema.split(";"):
            statement = statement.strip()
            if statement:
                conn.execute(statement)

    _write_health_snapshot(db_path)
    print(f"Migration complete: {db_path}")


def require_db(db_path: Path = DB_PATH) -> None:
    """Check that the DB exists. Error with helpful message if not.

    Call this before any operation that reads/writes venues.
    """
    if not Path(db_path).exists():
        raise FileNotFoundError(
            f"Database not found: {db_path}\n"
            "Run 'python scrape.py migrate' first to create the database."
        )


def _write_health_snapshot(db_path: Path = DB_PATH) -> None:
    """Write a health snapshot after migration."""
    db_path = Path(db_path)
    health_path = db_path.with_suffix(".health.json")
    with get_db(db_path) as conn:
        venue_count = conn.execute("SELECT COUNT(*) FROM venues").fetchone()[0]
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    snapshot = {
        "timestamp": datetime.now().isoformat(),
        "file_size_bytes": db_path.stat().st_size,
        "venue_count": venue_count,
        "integrity": integrity,
    }
    health_path.write_text(json.dumps(snapshot, indent=2))


# --- Venue CRUD (single-writer pattern) ---

def upsert_venue(conn: sqlite3.Connection, venue: dict) -> int:
    """Insert or update a venue by source_url. Returns the venue ID.

    Single-writer: ALL venue writes go through this function.
    """
    conn.execute(
        """INSERT INTO venues (name, source_url, email, phone, address, website,
            description, venue_type, social_links, capacity, pricing,
            star_rating, review_count, scraped_at)
        VALUES (:name, :source_url, :email, :phone, :address, :website,
            :description, :venue_type, :social_links, :capacity, :pricing,
            :star_rating, :review_count, datetime('now'))
        ON CONFLICT(source_url) DO UPDATE SET
            name = :name,
            email = COALESCE(:email, venues.email),
            phone = COALESCE(:phone, venues.phone),
            address = COALESCE(:address, venues.address),
            website = COALESCE(:website, venues.website),
            description = COALESCE(:description, venues.description),
            venue_type = COALESCE(:venue_type, venues.venue_type),
            social_links = COALESCE(:social_links, venues.social_links),
            capacity = COALESCE(:capacity, venues.capacity),
            pricing = COALESCE(:pricing, venues.pricing),
            star_rating = COALESCE(:star_rating, venues.star_rating),
            review_count = COALESCE(:review_count, venues.review_count),
            updated_at = datetime('now')
        """,
        {
            "name": venue["name"],
            "source_url": venue["source_url"],
            "email": venue.get("email"),
            "phone": venue.get("phone"),
            "address": venue.get("address"),
            "website": venue.get("website"),
            "description": venue.get("description"),
            "venue_type": venue.get("venue_type"),
            "social_links": json.dumps(venue.get("social_links", [])),
            "capacity": venue.get("capacity") or venue.get("capacity_range"),
            "pricing": venue.get("pricing") or venue.get("pricing_range"),
            "star_rating": venue.get("star_rating"),
            "review_count": venue.get("review_count"),
        },
    )
    row = conn.execute(
        "SELECT id FROM venues WHERE source_url = :source_url",
        {"source_url": venue["source_url"]},
    ).fetchone()
    return row["id"]


def ensure_outreach_status(conn: sqlite3.Connection, venue_id: int) -> None:
    """Create outreach_status='new' for a venue if it doesn't have one."""
    conn.execute(
        "INSERT OR IGNORE INTO outreach_status (venue_id, status) VALUES (?, 'new')",
        (venue_id,),
    )


def set_outreach_status(
    venue_id: int, status: str, notes: str | None = None, db_path: Path = DB_PATH
) -> bool:
    """Update a venue's outreach status. Returns True if venue exists."""
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status '{status}'. Must be one of: {VALID_STATUSES}")
    with get_db(db_path) as conn:
        # Verify venue exists
        venue = conn.execute("SELECT id FROM venues WHERE id = ?", (venue_id,)).fetchone()
        if not venue:
            return False
        conn.execute(
            """INSERT INTO outreach_status (venue_id, status, notes)
            VALUES (?, ?, ?)
            ON CONFLICT(venue_id) DO UPDATE SET
                status = excluded.status,
                notes = excluded.notes,
                changed_at = datetime('now')
            """,
            (venue_id, status, notes),
        )
    return True


def list_venues_by_status(
    status: str | None = None, db_path: Path = DB_PATH
) -> list[dict]:
    """List venues, optionally filtered by outreach status."""
    with get_db(db_path) as conn:
        if status:
            if status not in VALID_STATUSES:
                raise ValueError(
                    f"Invalid status '{status}'. Must be one of: {VALID_STATUSES}"
                )
            rows = conn.execute(
                """SELECT v.id, v.name, v.source_url, v.email, v.phone,
                    v.venue_type, o.status, o.notes, o.changed_at
                FROM venues v
                LEFT JOIN outreach_status o ON v.id = o.venue_id
                WHERE o.status = ?
                ORDER BY v.id
                """,
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT v.id, v.name, v.source_url, v.email, v.phone,
                    v.venue_type, o.status, o.notes, o.changed_at
                FROM venues v
                LEFT JOIN outreach_status o ON v.id = o.venue_id
                ORDER BY v.id
                """
            ).fetchall()
    return [dict(r) for r in rows]
