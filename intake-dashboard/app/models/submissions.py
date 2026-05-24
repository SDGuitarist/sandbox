import sqlite3

VALID_STATUSES = [
    'new', 'reviewed', 'assessment-ready', 'audit-scheduled',
    'completed', 'declined', 'archived'
]
TERMINAL_STATUSES = ['completed', 'declined', 'archived']


def create_submission(conn: sqlite3.Connection, data: dict) -> int:
    """Insert a new submission. Commits internally.

    Usage:
        submission_id = create_submission(conn, {
            'contact_name': 'Jane Doe',
            'email': 'jane@example.com',
            'business_name': 'Acme Corp',
            'business_type': 'SaaS',
            'team_size': '10-50',
            'current_workflows': 'Manual spreadsheets',
            'pain_points': 'Data entry takes 4 hours/day',
            'tools_used': 'Excel, Google Docs',
            'goals': 'Automate data entry',
            'urgency': 'Next 30 days',
            'submitter_notes': 'Optional extra context'
        })
        # submission_id is an int, NOT a Row

    Returns: int (the new submission's ID)
    Transaction: commits internally
    """
    cursor = conn.execute(
        """INSERT INTO submissions
           (contact_name, email, business_name, business_type, team_size,
            current_workflows, pain_points, tools_used, goals, urgency,
            submitter_notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (data['contact_name'], data['email'], data['business_name'],
         data['business_type'], data['team_size'], data['current_workflows'],
         data['pain_points'], data['tools_used'], data['goals'],
         data['urgency'], data.get('submitter_notes', ''))
    )
    conn.commit()
    return cursor.lastrowid


def get_submission(conn: sqlite3.Connection, submission_id: int) -> sqlite3.Row | None:
    """Fetch a single submission by ID.

    Usage:
        submission = get_submission(conn, submission_id)
        if submission is None:
            abort(404)

    Returns: sqlite3.Row or None
    Transaction: does NOT commit (read-only)
    """
    return conn.execute(
        "SELECT * FROM submissions WHERE id = ?", (submission_id,)
    ).fetchone()


LIST_COLUMNS = "id, business_name, contact_name, email, status, created_at"
PER_PAGE = 50


def list_submissions(conn: sqlite3.Connection,
                     status_filter: str | None = None,
                     page: int = 1) -> list[sqlite3.Row]:
    """List submissions with column projection and pagination.

    Usage:
        submissions = list_submissions(conn)
        submissions = list_submissions(conn, status_filter='new', page=2)

    Returns: list of sqlite3.Row (6 columns only), ordered by created_at DESC
    Transaction: does NOT commit (read-only)
    """
    offset = (page - 1) * PER_PAGE
    if status_filter and status_filter in VALID_STATUSES:
        return conn.execute(
            f"SELECT {LIST_COLUMNS} FROM submissions"
            " WHERE status = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (status_filter, PER_PAGE + 1, offset)
        ).fetchall()
    return conn.execute(
        f"SELECT {LIST_COLUMNS} FROM submissions"
        " ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (PER_PAGE + 1, offset)
    ).fetchall()


def update_status(conn: sqlite3.Connection, submission_id: int,
                  new_status: str) -> bool:
    """Update submission status with terminal-state enforcement.
    Uses BEGIN IMMEDIATE to prevent TOCTOU race.

    Usage:
        success = update_status(conn, submission_id, 'reviewed')
        if not success:
            flash('Cannot change status of a terminal submission', 'error')

    Returns: bool (True if updated, False if in terminal state or not found)
    Transaction: commits internally with BEGIN IMMEDIATE + try/except/ROLLBACK
    """
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT status FROM submissions WHERE id = ?",
            (submission_id,)
        ).fetchone()
        if row is None or row['status'] in TERMINAL_STATUSES:
            conn.rollback()
            return False
        conn.execute(
            """UPDATE submissions
               SET status = ?, updated_at = datetime('now')
               WHERE id = ?""",
            (new_status, submission_id)
        )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise


def toggle_audit_fit(conn: sqlite3.Connection, submission_id: int) -> None:
    """Toggle the is_audit_fit flag. Commits internally.

    Usage:
        toggle_audit_fit(conn, submission_id)

    Returns: None
    Transaction: commits internally
    """
    conn.execute(
        """UPDATE submissions
           SET is_audit_fit = CASE WHEN is_audit_fit = 0 THEN 1 ELSE 0 END,
               updated_at = datetime('now')
           WHERE id = ?""",
        (submission_id,)
    )
    conn.commit()


def count_by_status(conn: sqlite3.Connection) -> dict:
    """Count submissions grouped by status.

    Usage:
        stats = count_by_status(conn)
        # stats = {'new': 3, 'reviewed': 1, 'assessment-ready': 0, ...}
        # Always includes all valid statuses (0 for missing)

    Returns: dict[str, int]
    Transaction: does NOT commit (read-only)
    """
    rows = conn.execute(
        "SELECT status, COUNT(*) as cnt FROM submissions GROUP BY status"
    ).fetchall()
    counts = {s: 0 for s in VALID_STATUSES}
    for row in rows:
        counts[row['status']] = row['cnt']
    return counts
