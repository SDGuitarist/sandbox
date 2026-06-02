"""Auth model functions: create_user, authenticate, get_user."""

from werkzeug.security import generate_password_hash, check_password_hash

# Constant-time comparison: always hash-check even when user not found
DUMMY_HASH = generate_password_hash("dummy")


def create_user(conn, username, password, display_name):
    """Create a new user. Returns user id.

    Commits internally via BEGIN IMMEDIATE.
    """
    password_hash = generate_password_hash(password)
    try:
        conn.execute('BEGIN IMMEDIATE')
        cursor = conn.execute(
            'INSERT INTO users (username, password_hash, display_name) VALUES (?, ?, ?)',
            (username, password_hash, display_name),
        )
        user_id = cursor.lastrowid
        conn.execute('COMMIT')
        return user_id
    except Exception:
        conn.execute('ROLLBACK')
        raise


def authenticate(conn, username, password):
    """Authenticate a user by username and password.

    Returns dict with user data on success, None on failure.
    Uses DUMMY_HASH pattern to prevent timing attacks.
    """
    user = conn.execute(
        'SELECT * FROM users WHERE username = ?',
        (username,),
    ).fetchone()

    if user is None:
        # Constant-time: always run hash comparison to prevent timing attack
        check_password_hash(DUMMY_HASH, password)
        return None

    if not check_password_hash(user['password_hash'], password):
        return None

    return dict(user)


def get_user(conn, user_id):
    """Get a user by id. Returns dict or None."""
    row = conn.execute(
        'SELECT * FROM users WHERE id = ?',
        (user_id,),
    ).fetchone()

    if row is None:
        return None

    return dict(row)
