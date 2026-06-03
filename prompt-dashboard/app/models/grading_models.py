from app.encryption import encrypt_field, decrypt_field


def save_grade(conn, prompt_id, score, worked_well, needs_improvement, notes):
    """Save or update a grade. Encrypts text fields. Commits internally.
    Returns: int (grade_id)
    Usage:
        grade_id = save_grade(conn, prompt_id, 4, 'Great tone', 'Needs more detail', 'Notes here')
    """
    cursor = conn.execute(
        '''INSERT INTO prompt_grades (prompt_id, score, worked_well, needs_improvement, notes)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(prompt_id)
           DO UPDATE SET score = excluded.score,
                         worked_well = excluded.worked_well,
                         needs_improvement = excluded.needs_improvement,
                         notes = excluded.notes''',
        (prompt_id, score, encrypt_field(worked_well),
         encrypt_field(needs_improvement), encrypt_field(notes))
    )
    # No conn.commit() -- autocommit=True
    return cursor.lastrowid


def get_grade(conn, prompt_id):
    """Returns: dict with decrypted fields, or None
    Usage:
        grade = get_grade(conn, prompt_id)
        if grade: print(grade['score'], grade['worked_well'])
    """
    row = conn.execute(
        'SELECT * FROM prompt_grades WHERE prompt_id = ?', (prompt_id,)
    ).fetchone()
    if row is None:
        return None
    return {
        'id': row['id'], 'prompt_id': row['prompt_id'],
        'score': row['score'],
        'worked_well': decrypt_field(row['worked_well']),
        'needs_improvement': decrypt_field(row['needs_improvement']),
        'notes': decrypt_field(row['notes']),
        'created_at': row['created_at']
    }


def get_all_grades(conn):
    """Admin: all grades with prompt info. Returns: list[dict] with decrypted fields.
    Usage:
        grades = get_all_grades(conn)
    """
    rows = conn.execute(
        '''SELECT pg.*, p.title, p.user_id, u.username
           FROM prompt_grades pg
           JOIN prompts p ON pg.prompt_id = p.id
           JOIN users u ON p.user_id = u.id
           ORDER BY pg.created_at DESC'''
    ).fetchall()
    return [{
        'id': r['id'], 'prompt_id': r['prompt_id'], 'score': r['score'],
        'worked_well': decrypt_field(r['worked_well']),
        'needs_improvement': decrypt_field(r['needs_improvement']),
        'notes': decrypt_field(r['notes']),
        'title': r['title'], 'username': r['username'],
        'created_at': r['created_at']
    } for r in rows]
