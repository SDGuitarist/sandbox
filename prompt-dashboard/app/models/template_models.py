from app.encryption import encrypt_field, decrypt_field


def create_template(conn, name, description, industry_id, created_by):
    """Returns: int (template_id). Commits internally.
    Usage:
        template_id = create_template(conn, 'Marketing Brief', 'For marketers', 1, admin_id)
    """
    cursor = conn.execute(
        'INSERT INTO prompt_templates (name, description, industry_id, created_by) VALUES (?, ?, ?, ?)',
        (name, description, industry_id, created_by)
    )
    # No conn.commit() -- autocommit=True
    return cursor.lastrowid


def get_template(conn, template_id):
    """Returns: sqlite3.Row or None
    Usage:
        template = get_template(conn, template_id)
        if template is None: abort(404)
    """
    return conn.execute('SELECT * FROM prompt_templates WHERE id = ?', (template_id,)).fetchone()


def get_all_templates(conn):
    """Returns: list[sqlite3.Row]
    Usage:
        templates = get_all_templates(conn)
    """
    return conn.execute(
        '''SELECT pt.*, i.name as industry_name, u.username as creator_name
           FROM prompt_templates pt
           JOIN industries i ON pt.industry_id = i.id
           JOIN users u ON pt.created_by = u.id
           ORDER BY pt.created_at DESC'''
    ).fetchall()


def get_template_components(conn, template_id):
    """Returns: list[dict] with decrypted content
    Usage:
        components = get_template_components(conn, template_id)
        # Returns: [{'component_id': 1, 'content': 'plaintext...'}, ...]
    """
    rows = conn.execute(
        'SELECT component_id, content FROM template_components WHERE template_id = ?',
        (template_id,)
    ).fetchall()
    return [{'component_id': r['component_id'],
             'content': decrypt_field(r['content'])} for r in rows]


def save_template_component(conn, template_id, component_id, content):
    """Save/update a template component. Encrypts before storing.
    Returns: None. Commits internally.
    Usage:
        save_template_component(conn, template_id, 1, 'You are a marketing expert...')
    """
    encrypted = encrypt_field(content)
    conn.execute(
        '''INSERT INTO template_components (template_id, component_id, content)
           VALUES (?, ?, ?)
           ON CONFLICT(template_id, component_id)
           DO UPDATE SET content = excluded.content''',
        (template_id, component_id, encrypted)
    )
    # No conn.commit() -- autocommit=True


def delete_template(conn, template_id):
    """Delete a template and all its components (CASCADE).
    Returns: None
    Usage:
        delete_template(conn, template_id)
    """
    conn.execute('DELETE FROM prompt_templates WHERE id = ?', (template_id,))
    # No conn.commit() -- autocommit=True
