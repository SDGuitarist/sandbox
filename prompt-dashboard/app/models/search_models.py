"""Search models — FTS5 full-text search for prompts.

Provides search_prompts() which runs FTS5 MATCH queries against the
prompts_fts virtual table, filtered by user_id so users can only search
their own prompts. Uses _sanitize_fts_query() to strip FTS5 operators
and prevent injection (FC36).
"""

import re
import sqlite3


def _sanitize_fts_query(query: str) -> str | None:
    """Sanitize user input for FTS5 MATCH to prevent operator injection (FC36).

    Strips * " ( ) : ^ \\ characters, collapses whitespace, and wraps the
    cleaned text in double quotes so it is treated as a phrase search.

    Returns None if the query is empty or contains only stripped characters,
    signaling the caller to skip FTS5 MATCH entirely (return empty list).

    Examples:
        _sanitize_fts_query('hello world')      -> '"hello world"'
        _sanitize_fts_query('name:* OR "hack"') -> '"name OR hack"'
        _sanitize_fts_query('\\')               -> None
        _sanitize_fts_query('')                  -> None
        _sanitize_fts_query('   ')              -> None
    """
    cleaned = re.sub(r'[*"():^\\]', '', query).strip()
    if not cleaned:
        return None
    return f'"{cleaned}"'


def search_prompts(conn: sqlite3.Connection, query: str,
                   user_id: int) -> list[sqlite3.Row]:
    """Search prompts using FTS5 MATCH, filtered by user_id.

    Users can only search their own prompts. Admin search (all prompts)
    is handled in admin routes, not here.

    The query is sanitized via _sanitize_fts_query() before being passed
    to FTS5 MATCH with parameterized binding (never string interpolation).

    If the query is empty or sanitizes to empty, returns an empty list
    (not an error).

    Args:
        conn: SQLite database connection.
        query: Raw user search input.
        user_id: ID of the current logged-in user.

    Returns:
        List of matching prompt rows (sqlite3.Row), ordered by relevance
        then updated_at descending. Each row contains: id, name,
        description, system_prompt, user_prompt, variables, version_count,
        last_tested_at, created_at, updated_at.
    """
    if not query:
        return []

    safe_query = _sanitize_fts_query(query)
    if safe_query is None:
        return []

    # FTS5 MATCH with parameterized binding — never interpolate user input
    # into the SQL string, even after sanitization.
    sql = (
        'SELECT p.* FROM prompts p '
        'JOIN prompts_fts ON prompts_fts.rowid = p.id '
        'WHERE prompts_fts MATCH ? '
        'AND p.user_id = ? '
        'ORDER BY rank, p.updated_at DESC'
    )
    return conn.execute(sql, (safe_query, user_id)).fetchall()
