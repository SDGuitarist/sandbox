"""Auth model functions: user creation, authentication, lookup.

Transaction contracts (per plan):
- create_user: BEGIN IMMEDIATE, commits internally, try/except/ROLLBACK
- authenticate: read-only, constant-time password check
- get_user: read-only
"""
import sqlite3

from werkzeug.security import generate_password_hash, check_password_hash

# Constant-time guard: always run a hash comparison even when the user is
# missing, so login timing does not reveal whether a username exists.
DUMMY_HASH = generate_password_hash("dummy")


class DuplicateUsernameError(Exception):
    """Raised by create_user when the username already exists."""


def create_user(conn, username, password, display_name) -> int:
    """Create a user and return the new user_id.

    Commits internally (BEGIN IMMEDIATE). Raises DuplicateUsernameError if the
    username is already taken (the users.username UNIQUE constraint).
    """
    password_hash = generate_password_hash(password)
    conn.execute('BEGIN IMMEDIATE')
    try:
        cur = conn.execute(
            'INSERT INTO users (username, password_hash, display_name) '
            'VALUES (?, ?, ?)',
            (username, password_hash, display_name),
        )
        user_id = cur.lastrowid
        conn.execute('COMMIT')
    except sqlite3.IntegrityError as exc:
        conn.execute('ROLLBACK')
        raise DuplicateUsernameError(username) from exc
    except Exception:
        conn.execute('ROLLBACK')
        raise
    return user_id


def authenticate(conn, username, password) -> dict | None:
    """Return the user dict if credentials are valid, else None.

    Constant-time: always calls check_password_hash, even when the username is
    not found, to avoid leaking account existence via response timing.
    """
    user = conn.execute(
        'SELECT * FROM users WHERE username = ? AND is_active = 1',
        (username,),
    ).fetchone()
    if user is None:
        # Defeat timing attacks: do the same work as a real comparison.
        check_password_hash(DUMMY_HASH, password)
        return None
    if not check_password_hash(user['password_hash'], password):
        return None
    return dict(user)


def get_user(conn, user_id) -> dict | None:
    """Return the user dict for user_id, or None if not found/inactive."""
    user = conn.execute(
        'SELECT * FROM users WHERE id = ? AND is_active = 1',
        (user_id,),
    ).fetchone()
    return dict(user) if user is not None else None
