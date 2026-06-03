import hashlib
import secrets


def generate_share_token(conn, template_id, created_by):
    """Generate a share token. Stores SHA-256 hash in DB.
    Returns: str (raw token -- shown ONCE to admin, never retrievable).
    Commits internally.
    Usage:
        raw_token = generate_share_token(conn, template_id, admin_id)
        # Display raw_token to admin. It cannot be retrieved later.
    """
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    conn.execute(
        'INSERT INTO share_tokens (template_id, token_hash, created_by) VALUES (?, ?, ?)',
        (template_id, token_hash, created_by)
    )
    # No conn.commit() -- autocommit=True
    return raw_token


def get_template_by_token(conn, raw_token):
    """Look up template by raw token. Returns: sqlite3.Row (template) or None.
    Usage:
        template = get_template_by_token(conn, raw_token)
        if template is None: abort(404)
    """
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    row = conn.execute(
        '''SELECT st.template_id, pt.*
           FROM share_tokens st
           JOIN prompt_templates pt ON st.template_id = pt.id
           WHERE st.token_hash = ? AND st.revoked_at IS NULL''',
        (token_hash,)
    ).fetchone()
    return row


def revoke_token(conn, token_id):
    """Revoke a share token.
    Returns: None
    Usage:
        revoke_token(conn, token_id)
    """
    conn.execute(
        "UPDATE share_tokens SET revoked_at = datetime('now') WHERE id = ?",
        (token_id,)
    )
    # No conn.commit() -- autocommit=True


def get_all_tokens(conn):
    """Admin: all share tokens with template info. Returns: list[sqlite3.Row]
    Usage:
        tokens = get_all_tokens(conn)
    """
    return conn.execute(
        '''SELECT st.*, pt.name as template_name, u.username as creator_name
           FROM share_tokens st
           JOIN prompt_templates pt ON st.template_id = pt.id
           JOIN users u ON st.created_by = u.id
           ORDER BY st.created_at DESC'''
    ).fetchall()
