import sqlite3


def create_note(conn: sqlite3.Connection, submission_id: int,
                content: str) -> int:
    """Add a note to a submission. Commits internally.

    Usage:
        note_id = create_note(conn, submission_id, 'Looks promising')
        # note_id is an int, NOT a Row

    Returns: int (the new note's ID)
    Transaction: commits internally
    """
    cursor = conn.execute(
        "INSERT INTO notes (submission_id, content) VALUES (?, ?)",
        (submission_id, content)
    )
    conn.commit()
    return cursor.lastrowid


def list_notes(conn: sqlite3.Connection,
               submission_id: int) -> list[sqlite3.Row]:
    """List all notes for a submission, newest first.

    Usage:
        notes = list_notes(conn, submission_id)

    Returns: list of sqlite3.Row, ordered by created_at DESC
    Transaction: does NOT commit (read-only)
    """
    return conn.execute(
        "SELECT * FROM notes WHERE submission_id = ? ORDER BY created_at DESC",
        (submission_id,)
    ).fetchall()
