import sqlite3


def _escape_like(term: str) -> str:
    """Escape special LIKE characters."""
    return term.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


# --- Bookmarks ---

def create_bookmark(conn: sqlite3.Connection, url: str, title: str, description: str) -> int:
    """Insert a bookmark. Caller is responsible for committing."""
    cursor = conn.execute(
        'INSERT INTO bookmarks (url, title, description) VALUES (?, ?, ?)',
        (url, title, description),
    )
    return cursor.lastrowid


def delete_bookmark(conn: sqlite3.Connection, bookmark_id: int) -> None:
    conn.execute('DELETE FROM bookmarks WHERE id = ?', (bookmark_id,))
    cleanup_orphan_tags(conn)
    conn.commit()


def get_bookmark(conn: sqlite3.Connection, bookmark_id: int) -> sqlite3.Row | None:
    return conn.execute(
        'SELECT * FROM bookmarks WHERE id = ?', (bookmark_id,)
    ).fetchone()


# --- Tags ---

def get_or_create_tag(conn: sqlite3.Connection, name: str) -> int:
    name = name.lower().strip()
    conn.execute('INSERT OR IGNORE INTO tags (name) VALUES (?)', (name,))
    return conn.execute('SELECT id FROM tags WHERE name = ?', (name,)).fetchone()[0]


def set_bookmark_tags(conn: sqlite3.Connection, bookmark_id: int, tag_names: list[str]) -> None:
    conn.execute('DELETE FROM bookmark_tags WHERE bookmark_id = ?', (bookmark_id,))
    for name in tag_names:
        name = name.lower().strip()
        if not name:
            continue
        tag_id = get_or_create_tag(conn, name)
        conn.execute(
            'INSERT OR IGNORE INTO bookmark_tags (bookmark_id, tag_id) VALUES (?, ?)',
            (bookmark_id, tag_id),
        )


def get_tags_for_bookmarks(conn: sqlite3.Connection, bookmark_ids: list[int]) -> dict[int, list[sqlite3.Row]]:
    if not bookmark_ids:
        return {}
    placeholders = ','.join('?' * len(bookmark_ids))
    rows = conn.execute(
        f'SELECT bt.bookmark_id, t.id, t.name FROM bookmark_tags bt '
        f'JOIN tags t ON t.id = bt.tag_id WHERE bt.bookmark_id IN ({placeholders})',
        bookmark_ids,
    ).fetchall()
    result: dict[int, list[sqlite3.Row]] = {bid: [] for bid in bookmark_ids}
    for row in rows:
        result[row['bookmark_id']].append(row)
    return result


def cleanup_orphan_tags(conn: sqlite3.Connection) -> None:
    conn.execute('DELETE FROM tags WHERE id NOT IN (SELECT DISTINCT tag_id FROM bookmark_tags)')


# --- Search ---

def search_bookmarks(
    conn: sqlite3.Connection,
    query: str = '',
    tag: str = '',
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[sqlite3.Row], int]:
    """Search bookmarks by keyword and/or tag. Returns (rows, total_count)."""
    where_clauses: list[str] = []
    params: list = []

    if query:
        for term in query.split():
            escaped = f'%{_escape_like(term)}%'
            where_clauses.append(
                "(b.title LIKE ? ESCAPE '\\' COLLATE NOCASE "
                "OR b.url LIKE ? ESCAPE '\\' COLLATE NOCASE "
                "OR EXISTS (SELECT 1 FROM bookmark_tags bt2 JOIN tags t2 ON bt2.tag_id = t2.id "
                "WHERE bt2.bookmark_id = b.id AND t2.name LIKE ? ESCAPE '\\' COLLATE NOCASE))"
            )
            params.extend([escaped, escaped, escaped])

    if tag:
        where_clauses.append(
            "EXISTS (SELECT 1 FROM bookmark_tags bt3 JOIN tags t3 ON bt3.tag_id = t3.id "
            "WHERE bt3.bookmark_id = b.id AND t3.name = ?)"
        )
        params.append(tag.lower().strip())

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ''

    count = conn.execute(
        f'SELECT COUNT(*) FROM bookmarks b {where_sql}', params
    ).fetchone()[0]

    rows = conn.execute(
        f'SELECT b.* FROM bookmarks b {where_sql} ORDER BY b.created_at DESC LIMIT ? OFFSET ?',
        params + [limit, offset],
    ).fetchall()

    return rows, count
