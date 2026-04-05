import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


DB_PATH = "chat.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"

WINDOW_SECONDS = 60
MAX_MESSAGES_PER_WINDOW = 20
MAX_CONTENT_LENGTH = 2000
MAX_NAME_LENGTH = 100
MAX_USER_ID_LENGTH = 64


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


@contextmanager
def get_db(path=None, immediate=False):
    db_path = path or DB_PATH
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        if immediate:
            conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(path=None):
    """Initialize DB schema using a raw connection.

    Does NOT use get_db() because executescript() issues an implicit COMMIT
    before running, which bypasses get_db's transaction semantics.
    """
    db_path = path or DB_PATH
    schema = SCHEMA_PATH.read_text()
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(schema)
    finally:
        conn.close()


# ── Rooms ─────────────────────────────────────────────────────────────────────

def create_room(name, created_by, db_path=None):
    """Create a room. Returns room dict. Raises sqlite3.IntegrityError on duplicate name."""
    now = _now()
    with get_db(path=db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO rooms (name, created_by, created_at) VALUES (?, ?, ?)",
            (name, created_by, now),
        )
        row = conn.execute(
            "SELECT * FROM rooms WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        return dict(row)


def list_rooms(db_path=None):
    with get_db(path=db_path) as conn:
        rows = conn.execute("SELECT * FROM rooms ORDER BY id ASC").fetchall()
        return [dict(r) for r in rows]


def get_room(room_id, db_path=None):
    with get_db(path=db_path) as conn:
        row = conn.execute("SELECT * FROM rooms WHERE id = ?", (room_id,)).fetchone()
        return dict(row) if row else None


# ── Memberships ───────────────────────────────────────────────────────────────

def join_room(room_id, user_id, db_path=None):
    """Join a room. Returns True if newly joined, False if already a member.

    Raises sqlite3.IntegrityError (FK violation) if room_id does not exist.
    Callers should check room existence before calling if they need a clean error.
    """
    now = _now()
    with get_db(path=db_path) as conn:
        # Check if already a member first to distinguish FK error from duplicate
        existing = conn.execute(
            "SELECT 1 FROM memberships WHERE room_id = ? AND user_id = ?",
            (room_id, user_id),
        ).fetchone()
        if existing:
            return False
        # This will raise IntegrityError if room_id doesn't exist (FK constraint)
        conn.execute(
            "INSERT INTO memberships (room_id, user_id, joined_at) VALUES (?, ?, ?)",
            (room_id, user_id, now),
        )
        return True


def leave_room(room_id, user_id, db_path=None):
    """Leave a room. Returns True if was a member, False if was not."""
    with get_db(path=db_path) as conn:
        cursor = conn.execute(
            "DELETE FROM memberships WHERE room_id = ? AND user_id = ?",
            (room_id, user_id),
        )
        return cursor.rowcount > 0


def is_member(room_id, user_id, db_path=None):
    with get_db(path=db_path) as conn:
        row = conn.execute(
            "SELECT 1 FROM memberships WHERE room_id = ? AND user_id = ?",
            (room_id, user_id),
        ).fetchone()
        return row is not None


# ── Messages ──────────────────────────────────────────────────────────────────

def post_message(room_id, user_id, content, db_path=None):
    """Insert a message. Returns message dict."""
    now = _now()
    with get_db(path=db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO messages (room_id, user_id, content, created_at) VALUES (?, ?, ?, ?)",
            (room_id, user_id, content, now),
        )
        row = conn.execute(
            "SELECT * FROM messages WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        return dict(row)


def get_messages(room_id, after_id=None, limit=50, db_path=None):
    """Return (list_of_message_dicts, next_cursor_or_None).

    Fetch limit+1 rows to detect whether a next page exists without a COUNT query.
    next_cursor = id of the last returned message (index limit-1).
    Next call uses id > next_cursor, so it starts after the last returned row.
    """
    limit = max(1, min(int(limit), 200))
    params = [room_id]
    where_extra = ""
    if after_id is not None:
        where_extra = " AND id > ?"
        params.append(int(after_id))
    params.append(limit + 1)

    sql = f"SELECT * FROM messages WHERE room_id = ?{where_extra} ORDER BY id ASC LIMIT ?"
    with get_db(path=db_path) as conn:
        rows = conn.execute(sql, params).fetchall()

    messages = [dict(r) for r in rows]
    if len(messages) > limit:
        # messages[limit-1] is the last item on the current page.
        # Using its id as cursor means next call (id > cursor) returns the correct next page.
        next_cursor = messages[limit - 1]["id"]
        messages = messages[:limit]
    else:
        next_cursor = None

    return messages, next_cursor


# ── Rate limiting ─────────────────────────────────────────────────────────────

def check_rate_limit(
    user_id,
    window_seconds=WINDOW_SECONDS,
    max_count=MAX_MESSAGES_PER_WINDOW,
    db_path=None,
):
    """Check and increment the rate limit for a user.

    Returns True if the request is allowed (counter incremented).
    Returns False if the user has exceeded the window limit.

    Uses BEGIN IMMEDIATE to atomically: read window, reset if expired,
    check count, increment if under limit — all in one transaction.
    """
    now = _now()
    with get_db(path=db_path, immediate=True) as conn:
        row = conn.execute(
            "SELECT window_start, count FROM rate_limits WHERE user_id = ?",
            (user_id,),
        ).fetchone()

        if row is None:
            conn.execute(
                "INSERT INTO rate_limits (user_id, window_start, count) VALUES (?, ?, 1)",
                (user_id, now),
            )
            return True

        window_start = row["window_start"]
        count = row["count"]

        window_start_dt = datetime.strptime(window_start, "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=timezone.utc
        )
        now_dt = datetime.strptime(now, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        elapsed = (now_dt - window_start_dt).total_seconds()

        if elapsed >= window_seconds:
            conn.execute(
                "UPDATE rate_limits SET window_start = ?, count = 1 WHERE user_id = ?",
                (now, user_id),
            )
            return True

        if count >= max_count:
            return False

        conn.execute(
            "UPDATE rate_limits SET count = count + 1 WHERE user_id = ?",
            (user_id,),
        )
        return True


def rate_limit_and_post(
    room_id,
    user_id,
    content,
    window_seconds=WINDOW_SECONDS,
    max_count=MAX_MESSAGES_PER_WINDOW,
    db_path=None,
):
    """Atomically check rate limit and insert message in a single BEGIN IMMEDIATE transaction.

    Resolves the TOCTOU gap between check_rate_limit() and post_message() when called
    separately. Returns (message_dict, allowed): if allowed=False, message_dict is None.
    """
    now = _now()
    with get_db(path=db_path, immediate=True) as conn:
        # --- Rate limit check (same logic as check_rate_limit) ---
        row = conn.execute(
            "SELECT window_start, count FROM rate_limits WHERE user_id = ?",
            (user_id,),
        ).fetchone()

        if row is None:
            conn.execute(
                "INSERT INTO rate_limits (user_id, window_start, count) VALUES (?, ?, 1)",
                (user_id, now),
            )
        else:
            window_start = row["window_start"]
            count = row["count"]
            window_start_dt = datetime.strptime(window_start, "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=timezone.utc
            )
            now_dt = datetime.strptime(now, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            elapsed = (now_dt - window_start_dt).total_seconds()

            if elapsed >= window_seconds:
                conn.execute(
                    "UPDATE rate_limits SET window_start = ?, count = 1 WHERE user_id = ?",
                    (now, user_id),
                )
            elif count >= max_count:
                return None, False
            else:
                conn.execute(
                    "UPDATE rate_limits SET count = count + 1 WHERE user_id = ?",
                    (user_id,),
                )

        # --- Message insert (inside same transaction) ---
        cursor = conn.execute(
            "INSERT INTO messages (room_id, user_id, content, created_at) VALUES (?, ?, ?, ?)",
            (room_id, user_id, content, now),
        )
        msg_id = cursor.lastrowid
        msg_row = conn.execute(
            "SELECT * FROM messages WHERE id = ?", (msg_id,)
        ).fetchone()
        return dict(msg_row), True
