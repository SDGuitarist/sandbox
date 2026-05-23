import sqlite3


def create_assessment(conn: sqlite3.Connection, submission_id: int,
                      data: dict) -> int:
    """Create a new assessment for a submission. Commits internally.

    Usage:
        assessment_id = create_assessment(conn, submission_id, {
            'summary': '...',
            'bottlenecks': '...',
            'root_causes': '...',
            'next_steps': '...',
            'audit_fit_recommendation': '...',
            'admin_notes': '...'
        })
        # assessment_id is an int, NOT a Row

    Returns: int (the new assessment's ID)
    Transaction: commits internally
    """
    cursor = conn.execute(
        """INSERT INTO assessments
           (submission_id, summary, bottlenecks, root_causes,
            next_steps, audit_fit_recommendation, admin_notes)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (submission_id, data.get('summary', ''),
         data.get('bottlenecks', ''), data.get('root_causes', ''),
         data.get('next_steps', ''),
         data.get('audit_fit_recommendation', ''),
         data.get('admin_notes', ''))
    )
    conn.commit()
    return cursor.lastrowid


def get_assessment_by_submission(conn: sqlite3.Connection,
                                 submission_id: int) -> sqlite3.Row | None:
    """Fetch the assessment for a submission (1:1 relationship).

    Usage:
        assessment = get_assessment_by_submission(conn, submission_id)
        if assessment is None:
            # No assessment yet -- show create form

    Returns: sqlite3.Row or None
    Transaction: does NOT commit (read-only)
    """
    return conn.execute(
        "SELECT * FROM assessments WHERE submission_id = ?",
        (submission_id,)
    ).fetchone()


def update_assessment(conn: sqlite3.Connection, assessment_id: int,
                      data: dict) -> None:
    """Update an existing assessment. Commits internally.

    Usage:
        update_assessment(conn, assessment['id'], {
            'summary': '...',
            'bottlenecks': '...',
            'root_causes': '...',
            'next_steps': '...',
            'audit_fit_recommendation': '...',
            'admin_notes': '...'
        })

    Returns: None
    Transaction: commits internally
    """
    conn.execute(
        """UPDATE assessments
           SET summary = ?, bottlenecks = ?, root_causes = ?,
               next_steps = ?, audit_fit_recommendation = ?,
               admin_notes = ?, updated_at = datetime('now')
           WHERE id = ?""",
        (data.get('summary', ''), data.get('bottlenecks', ''),
         data.get('root_causes', ''), data.get('next_steps', ''),
         data.get('audit_fit_recommendation', ''),
         data.get('admin_notes', ''), assessment_id)
    )
    conn.commit()
