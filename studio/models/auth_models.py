"""Auth model functions: user creation and credential verification.

Owned by the auth-core agent. All getters convert sqlite3.Row -> plain dict
(never leak Row across a boundary -- FC2). Creators return the new int id.
"""
import sqlite3

from werkzeug.security import check_password_hash, generate_password_hash

from studio.database import get_db, query


def create_user(email, password, role, name):
    """Create a user with a hashed password. Returns the new int id.

    Raises ValueError('email exists') on the email-UNIQUE violation.
    Commits internally (class-A writer).
    """
    db = get_db()
    password_hash = generate_password_hash(password)
    try:
        cur = db.execute(
            "INSERT INTO users (email, password_hash, role, name) "
            "VALUES (?, ?, ?, ?)",
            (email, password_hash, role, name),
        )
        db.commit()
    except sqlite3.IntegrityError:
        # email UNIQUE constraint violated
        raise ValueError('email exists')
    return cur.lastrowid


def get_user(user_id):
    """Return the user row as a plain dict, or None."""
    return query("SELECT * FROM users WHERE id = ?", (user_id,), one=True)


def get_user_by_email(email):
    """Return the user row matching email as a plain dict, or None."""
    return query("SELECT * FROM users WHERE email = ?", (email,), one=True)


def verify_credentials(email, password):
    """Return the user dict if the password matches, else None."""
    user = get_user_by_email(email)
    if user is None:
        return None
    if not check_password_hash(user['password_hash'], password):
        return None
    return user
