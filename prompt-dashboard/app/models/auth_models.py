"""Auth model functions for user management."""
import bcrypt


def create_user(conn, username, email, password):
    """Create a new user. Returns: int (user_id)
    Usage:
        user_id = create_user(conn, 'alex', 'alex@example.com', 'password123')
    """
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    cursor = conn.execute(
        'INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
        (username, email, password_hash)
    )
    # No conn.commit() -- autocommit=True handles single statements
    return cursor.lastrowid


def create_admin_user(conn, username, email, password):
    """Create an admin user. Returns: int (user_id)
    Usage:
        admin_id = create_admin_user(conn, 'admin', 'admin@amplifyai.com', 'pw')
    """
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    cursor = conn.execute(
        'INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)',
        (username, email, password_hash, 'admin')
    )
    # No conn.commit() -- autocommit=True handles single statements
    return cursor.lastrowid


def get_user_by_username(conn, username):
    """Returns: sqlite3.Row or None
    Usage:
        user = get_user_by_username(conn, 'alex')
        if user is None: flash('Invalid credentials')
    """
    return conn.execute(
        'SELECT * FROM users WHERE username = ?', (username,)
    ).fetchone()


def get_user_by_id(conn, user_id):
    """Returns: sqlite3.Row or None
    Usage:
        user = get_user_by_id(conn, session['user_id'])
        if user is None: abort(404)
    """
    return conn.execute(
        'SELECT * FROM users WHERE id = ?', (user_id,)
    ).fetchone()


def verify_password(plain_password, password_hash):
    """Returns: bool
    Usage:
        if not verify_password(form_password, user['password_hash']):
            flash('Invalid credentials')
    """
    return bcrypt.checkpw(plain_password.encode(), password_hash.encode())
