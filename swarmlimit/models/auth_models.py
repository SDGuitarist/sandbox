"""User model (auth-core).

Class-A writers: each write executes directly on the request connection. Because
the connection is opened with ``isolation_level=None`` (SQLite AUTOCOMMIT), the
single statement persists immediately -- these functions NEVER call
``conn.commit()`` and NEVER open ``transaction()`` (that is class-B only; see
spec §5).

Every function converts ``sqlite3.Row`` -> plain ``dict`` before returning so a
``sqlite3.Row`` never leaks across an agent boundary (FC63/FC2). The thin
``query`` helper from ``swarmlimit.database`` already returns plain dicts.
"""

import sqlite3

from werkzeug.security import check_password_hash, generate_password_hash

from swarmlimit.database import get_db, query


def create_user(email, password, role, name):
    """Create a user, returning the new user id.

    Hashes ``password`` with werkzeug. Persists immediately via SQLite
    autocommit (``isolation_level=None``) -- does NOT call ``conn.commit()`` and
    does NOT open a transaction (class-A writer, spec §5).

    Raises ``ValueError('email exists')`` on a UNIQUE(email) violation.

    Privilege pin (spec §Route Table / §6): the public ``POST /auth/register``
    route ALWAYS calls this with ``role='customer'`` (client-supplied role
    ignored). The ``role`` parameter stays variable ONLY for trusted
    seed/internal callers (e.g. ``init_db`` seeding ``admin@swarm.test``).
    """
    conn = get_db()
    password_hash = generate_password_hash(password)
    try:
        cursor = conn.execute(
            "INSERT INTO users (email, password_hash, role, name) "
            "VALUES (?, ?, ?, ?)",
            (email, password_hash, role, name),
        )
    except sqlite3.IntegrityError as exc:
        raise ValueError("email exists") from exc
    return cursor.lastrowid


def get_user(user_id):
    """Return the user row as a dict, or None if absent."""
    return query("SELECT * FROM users WHERE id = ?", (user_id,), one=True)


def get_user_by_email(email):
    """Return the user row matching ``email`` as a dict, or None if absent."""
    return query("SELECT * FROM users WHERE email = ?", (email,), one=True)


def verify_credentials(email, password):
    """Return the user dict if ``password`` matches the stored hash, else None."""
    user = get_user_by_email(email)
    if user is None:
        return None
    if not check_password_hash(user["password_hash"], password):
        return None
    return user
