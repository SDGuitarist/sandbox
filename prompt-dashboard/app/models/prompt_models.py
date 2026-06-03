from app.encryption import encrypt_field, decrypt_field


def create_prompt(conn, title, industry_id, user_id, component_data):
    """Create a prompt with all 12 component answers.
    component_data: list of (component_id, content) tuples.
    Encrypts content before storing. Calculates completeness.
    Returns: int (prompt_id). Commits internally.
    Usage:
        component_data = [(1, 'I am a marketer'), (2, ''), (3, 'Agency background'), ...]
        prompt_id = create_prompt(conn, 'My Prompt', 1, user_id, component_data)
    """
    completeness = sum(1 for _, content in component_data if content.strip()) / 12.0
    # Use 'with conn:' context manager for atomicity. This is the correct pattern
    # for Python 3.12+ with autocommit=True -- explicit BEGIN/commit() silently
    # fails to persist data after conn.close() in Python 3.14 (in_transaction
    # stays True even after commit, write is lost on close).
    with conn:
        cursor = conn.execute(
            'INSERT INTO prompts (title, industry_id, user_id, completeness) VALUES (?, ?, ?, ?)',
            (title, industry_id, user_id, completeness)
        )
        prompt_id = cursor.lastrowid
        for component_id, content in component_data:
            encrypted = encrypt_field(content)
            conn.execute(
                'INSERT INTO prompt_components (prompt_id, component_id, content) VALUES (?, ?, ?)',
                (prompt_id, component_id, encrypted)
            )
    return prompt_id


def get_prompt(conn, prompt_id):
    """Returns: sqlite3.Row or None
    Usage:
        prompt = get_prompt(conn, prompt_id)
        if prompt is None: abort(404)
    """
    return conn.execute(
        '''SELECT p.*, i.name as industry_name, u.username
           FROM prompts p
           JOIN industries i ON p.industry_id = i.id
           JOIN users u ON p.user_id = u.id
           WHERE p.id = ?''',
        (prompt_id,)
    ).fetchone()


def get_prompt_components(conn, prompt_id):
    """Returns: list[dict] with decrypted content, joined with component definitions.
    Usage:
        components = get_prompt_components(conn, prompt_id)
        # Returns: [{'component_id': 1, 'name': 'Role', 'cluster': 'Your Reality',
        #            'position': 1, 'content': 'decrypted text...'}, ...]
    """
    rows = conn.execute(
        '''SELECT pc.component_id, pc.content, cd.name, cd.cluster, cd.position
           FROM prompt_components pc
           JOIN component_definitions cd ON pc.component_id = cd.id
           WHERE pc.prompt_id = ?
           ORDER BY cd.position''',
        (prompt_id,)
    ).fetchall()
    return [{'component_id': r['component_id'], 'name': r['name'],
             'cluster': r['cluster'], 'position': r['position'],
             'content': decrypt_field(r['content'])} for r in rows]


def get_prompts_for_user(conn, user_id):
    """Returns: list[sqlite3.Row]
    Usage:
        prompts = get_prompts_for_user(conn, user_id)
    """
    return conn.execute(
        '''SELECT p.*, i.name as industry_name,
                  pg.score as grade_score
           FROM prompts p
           JOIN industries i ON p.industry_id = i.id
           LEFT JOIN prompt_grades pg ON p.id = pg.prompt_id
           WHERE p.user_id = ?
           ORDER BY p.updated_at DESC''',
        (user_id,)
    ).fetchall()


def get_all_prompts(conn, industry_id=None, user_id=None):
    """Admin: get all prompts with optional filters. Returns: list[sqlite3.Row]
    Usage:
        all_prompts = get_all_prompts(conn)
        filtered = get_all_prompts(conn, industry_id=1)
    """
    query = '''SELECT p.*, i.name as industry_name, u.username,
                      pg.score as grade_score
               FROM prompts p
               JOIN industries i ON p.industry_id = i.id
               JOIN users u ON p.user_id = u.id
               LEFT JOIN prompt_grades pg ON p.id = pg.prompt_id
               WHERE 1=1'''
    params = []
    if industry_id:
        query += ' AND p.industry_id = ?'
        params.append(industry_id)
    if user_id:
        query += ' AND p.user_id = ?'
        params.append(user_id)
    query += ' ORDER BY p.updated_at DESC'
    return conn.execute(query, params).fetchall()


def update_prompt(conn, prompt_id, title, component_data):
    """Update a prompt's title and all components. Recalculates completeness.
    component_data: list of (component_id, content) tuples.
    Returns: None. Commits internally.
    Usage:
        update_prompt(conn, prompt_id, 'New Title', [(1, 'updated text'), ...])
    """
    completeness = sum(1 for _, content in component_data if content.strip()) / 12.0
    # Use 'with conn:' context manager for atomicity (same fix as create_prompt).
    # Python 3.14 autocommit=True + explicit BEGIN/commit() silently loses writes.
    with conn:
        conn.execute(
            "UPDATE prompts SET title = ?, completeness = ?, updated_at = datetime('now') WHERE id = ?",
            (title, completeness, prompt_id)
        )
        for component_id, content in component_data:
            encrypted = encrypt_field(content)
            conn.execute(
                '''INSERT INTO prompt_components (prompt_id, component_id, content)
                   VALUES (?, ?, ?)
                   ON CONFLICT(prompt_id, component_id)
                   DO UPDATE SET content = excluded.content''',
                (prompt_id, component_id, encrypted)
            )


def delete_prompt(conn, prompt_id):
    """Delete a prompt and all components/grades (CASCADE).
    Returns: None
    Usage:
        delete_prompt(conn, prompt_id)
    """
    conn.execute('DELETE FROM prompts WHERE id = ?', (prompt_id,))
    # No conn.commit() -- autocommit=True


def format_prompt(components):
    """Format filled components into a clean, copy-ready prompt string.
    components: list[dict] with 'name', 'cluster', 'content' keys.
    Returns: str
    Usage:
        formatted = format_prompt(get_prompt_components(conn, prompt_id))
    """
    lines = []
    current_cluster = None
    for comp in components:
        if not comp['content'].strip():
            continue
        if comp['cluster'] != current_cluster:
            if current_cluster is not None:
                lines.append('')
            lines.append(f"## {comp['cluster']}")
            current_cluster = comp['cluster']
        lines.append(f"**{comp['name']}:** {comp['content']}")
    return '\n'.join(lines)


def calculate_cluster_completeness(components):
    """Calculate completeness per cluster.
    Returns: dict[str, float] -- e.g., {'Your Reality': 0.67, 'Your Assignment': 1.0, ...}
    Usage:
        cluster_scores = calculate_cluster_completeness(components)
    """
    clusters = {}
    for comp in components:
        cluster = comp['cluster']
        if cluster not in clusters:
            clusters[cluster] = {'filled': 0, 'total': 0}
        clusters[cluster]['total'] += 1
        if comp['content'].strip():
            clusters[cluster]['filled'] += 1
    return {k: v['filled'] / v['total'] for k, v in clusters.items()}
