"""FTS5 search model functions for full-text search across project entities."""

import re


def _sanitize_query(query):
    """Strip FTS5 operators and wrap in quotes as phrase search.

    FTS5 operators (* " ( ) : ^) can cause query parse errors or injection.
    We strip them all, then wrap the cleaned text in double quotes so FTS5
    treats the entire input as a phrase search -- safe and predictable.
    """
    cleaned = re.sub(r'[*"():^]', '', query).strip()
    if not cleaned:
        return None
    return f'"{cleaned}"'


def search(conn, query, project_id):
    """Search the FTS5 index for entities belonging to a project.

    Args:
        conn: Database connection (row_factory already set by get_db).
        query: Raw user search string (will be sanitized).
        project_id: Integer project ID to scope results.

    Returns:
        list[dict] with keys: entity_type, entity_id, title, snippet.
        Empty list if query is empty or sanitizes to nothing.
    """
    sanitized = _sanitize_query(query)
    if sanitized is None:
        return []

    rows = conn.execute(
        """SELECT entity_type, entity_id, title,
                  snippet(search_index, 3, '<mark>', '</mark>', '...', 32) AS snippet
           FROM search_index
           WHERE search_index MATCH ?
           ORDER BY rank""",
        (sanitized,)
    ).fetchall()

    # Filter to only entities that belong to the given project.
    # FTS5 contentless mode doesn't store project_id, so we filter in Python
    # by looking up each entity in its source table.
    results = []
    for row in rows:
        entity_type = row['entity_type']
        entity_id = row['entity_id']

        # Verify entity belongs to this project
        if entity_type == 'scene':
            check = conn.execute(
                'SELECT id FROM scenes WHERE id = ? AND project_id = ?',
                (entity_id, project_id)
            ).fetchone()
        elif entity_type == 'cast':
            check = conn.execute(
                'SELECT id FROM cast_members WHERE id = ? AND project_id = ?',
                (entity_id, project_id)
            ).fetchone()
        elif entity_type == 'crew':
            check = conn.execute(
                'SELECT id FROM crew_members WHERE id = ? AND project_id = ?',
                (entity_id, project_id)
            ).fetchone()
        elif entity_type == 'location':
            check = conn.execute(
                'SELECT id FROM locations WHERE id = ? AND project_id = ?',
                (entity_id, project_id)
            ).fetchone()
        else:
            check = None

        if check is not None:
            results.append({
                'entity_type': entity_type,
                'entity_id': entity_id,
                'title': row['title'],
                'snippet': row['snippet'],
            })

    return results


def index_entity(conn, entity_type, entity_id, title, body):
    """Insert or replace an entity in the FTS5 search index.

    Fire-and-forget: caller manages the transaction. Does NOT commit.

    Args:
        conn: Database connection.
        entity_type: One of 'scene', 'cast', 'crew', 'location'.
        entity_id: Integer ID of the entity in its source table.
        title: Searchable title text (e.g. scene number, person name).
        body: Searchable body text (e.g. description, role, notes).
    """
    # Remove any existing entry first to avoid duplicates
    conn.execute(
        'DELETE FROM search_index WHERE entity_type = ? AND entity_id = ?',
        (entity_type, entity_id)
    )
    conn.execute(
        'INSERT INTO search_index (entity_type, entity_id, title, body) VALUES (?, ?, ?, ?)',
        (entity_type, entity_id, title, body or '')
    )


def remove_entity(conn, entity_type, entity_id):
    """Remove an entity from the FTS5 search index.

    Fire-and-forget: caller manages the transaction. Does NOT commit.

    Args:
        conn: Database connection.
        entity_type: One of 'scene', 'cast', 'crew', 'location'.
        entity_id: Integer ID of the entity in its source table.
    """
    conn.execute(
        'DELETE FROM search_index WHERE entity_type = ? AND entity_id = ?',
        (entity_type, entity_id)
    )
