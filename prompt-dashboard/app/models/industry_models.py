"""Industry and guidance queries — reads from industries and industry_guidance tables.

Note: industry_guidance.guidance_text is stored as plaintext (admin-authored, non-PII).
Only prompt_components, template_components, and prompt_grades fields are encrypted.
"""


def get_all_industries(conn):
    """Returns: list[sqlite3.Row]
    Usage:
        industries = get_all_industries(conn)
    """
    return conn.execute('SELECT * FROM industries ORDER BY name').fetchall()


def get_industry(conn, industry_id):
    """Returns: sqlite3.Row or None
    Usage:
        industry = get_industry(conn, industry_id)
        if industry is None: abort(404)
    """
    return conn.execute(
        'SELECT * FROM industries WHERE id = ?', (industry_id,)
    ).fetchone()


def get_guidance_for_industry(conn, industry_id):
    """Returns: list[dict] with guidance_text as plaintext (not encrypted).
    Usage:
        guidance = get_guidance_for_industry(conn, industry_id)
        # Returns: [{'component_id': 1, 'guidance_text': 'plaintext...'}, ...]
    """
    rows = conn.execute(
        'SELECT component_id, guidance_text FROM industry_guidance WHERE industry_id = ?',
        (industry_id,)
    ).fetchall()
    return [{'component_id': r['component_id'],
             'guidance_text': r['guidance_text']} for r in rows]


def save_guidance(conn, industry_id, component_id, guidance_text):
    """Save/update industry guidance. Stored as plaintext (admin-authored, non-PII).
    Returns: None
    Usage:
        save_guidance(conn, industry_id, component_id, 'Helpful tip...')
    """
    conn.execute(
        '''INSERT INTO industry_guidance (industry_id, component_id, guidance_text)
           VALUES (?, ?, ?)
           ON CONFLICT(industry_id, component_id)
           DO UPDATE SET guidance_text = excluded.guidance_text''',
        (industry_id, component_id, guidance_text)
    )
    # No conn.commit() -- autocommit=True
