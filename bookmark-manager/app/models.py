import sqlite3
from typing import Final

ITEMS_PER_PAGE: Final[int] = 20
SORT_OPTIONS: Final[list[str]] = ['newest', 'oldest', 'a-z']
SORT_LABELS: Final[dict[str, str]] = {'newest': 'Newest First', 'oldest': 'Oldest First', 'a-z': 'A-Z by Title'}
SORT_MAP: Final[dict[str, str]] = {'newest': 'created_at DESC', 'oldest': 'created_at ASC', 'a-z': 'title ASC'}

def _sort_clause(sort_order: str) -> str:
    if sort_order not in SORT_MAP:
        raise ValueError(f"Unknown sort order: {sort_order}")
    return f"ORDER BY {SORT_MAP[sort_order]}"

def _escape_like(term: str) -> str:
    return term.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')

# --- Bookmarks ---

def get_all_bookmarks(conn: sqlite3.Connection, sort_order: str = 'newest', limit: int = 20, offset: int = 0) -> list[sqlite3.Row]:
    order = _sort_clause(sort_order)
    return conn.execute(f'SELECT * FROM bookmarks {order} LIMIT ? OFFSET ?', (limit, offset)).fetchall()

def get_bookmark(conn: sqlite3.Connection, bookmark_id: int) -> sqlite3.Row | None:
    return conn.execute('SELECT * FROM bookmarks WHERE id = ?', (bookmark_id,)).fetchone()

def get_bookmark_count(conn: sqlite3.Connection) -> int:
    return conn.execute('SELECT COUNT(*) FROM bookmarks').fetchone()[0]

def get_bookmarks_by_url(conn: sqlite3.Connection, url: str) -> list[sqlite3.Row]:
    return conn.execute('SELECT * FROM bookmarks WHERE url = ?', (url,)).fetchall()

def create_bookmark(conn: sqlite3.Connection, url: str, title: str, description: str) -> int:
    cursor = conn.execute('INSERT INTO bookmarks (url, title, description) VALUES (?, ?, ?)', (url, title, description))
    return cursor.lastrowid

def update_bookmark(conn: sqlite3.Connection, bookmark_id: int, url: str, title: str, description: str) -> None:
    conn.execute("UPDATE bookmarks SET url = ?, title = ?, description = ?, updated_at = strftime('%Y-%m-%d %H:%M:%S', 'now') WHERE id = ?", (url, title, description, bookmark_id))

def delete_bookmark(conn: sqlite3.Connection, bookmark_id: int) -> None:
    conn.execute('DELETE FROM bookmarks WHERE id = ?', (bookmark_id,))

# --- Tags ---

def get_all_tags(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute('SELECT t.id, t.name, COUNT(bt.bookmark_id) AS bookmark_count FROM tags t LEFT JOIN bookmark_tags bt ON t.id = bt.tag_id GROUP BY t.id, t.name ORDER BY t.name').fetchall()

def get_tag_by_name(conn: sqlite3.Connection, name: str) -> sqlite3.Row | None:
    return conn.execute('SELECT * FROM tags WHERE name = ?', (name,)).fetchone()

def get_or_create_tag(conn: sqlite3.Connection, name: str) -> int:
    name = name.lower().strip()
    conn.execute('INSERT OR IGNORE INTO tags (name) VALUES (?)', (name,))
    return conn.execute('SELECT id FROM tags WHERE name = ?', (name,)).fetchone()[0]

def get_tags_for_bookmark(conn: sqlite3.Connection, bookmark_id: int) -> list[sqlite3.Row]:
    return conn.execute('SELECT t.id, t.name FROM tags t JOIN bookmark_tags bt ON t.id = bt.tag_id WHERE bt.bookmark_id = ?', (bookmark_id,)).fetchall()

def get_tags_for_bookmarks(conn: sqlite3.Connection, bookmark_ids: list[int]) -> dict[int, list[sqlite3.Row]]:
    if not bookmark_ids:
        return {}
    placeholders = ','.join('?' * len(bookmark_ids))
    rows = conn.execute(f'SELECT bt.bookmark_id, t.id, t.name FROM bookmark_tags bt JOIN tags t ON t.id = bt.tag_id WHERE bt.bookmark_id IN ({placeholders})', bookmark_ids).fetchall()
    result: dict[int, list[sqlite3.Row]] = {bid: [] for bid in bookmark_ids}
    for row in rows:
        result[row['bookmark_id']].append(row)
    return result

def set_bookmark_tags(conn: sqlite3.Connection, bookmark_id: int, tag_names: list[str]) -> None:
    conn.execute('DELETE FROM bookmark_tags WHERE bookmark_id = ?', (bookmark_id,))
    for name in tag_names:
        name = name.lower().strip()
        if not name:
            continue
        tag_id = get_or_create_tag(conn, name)
        conn.execute('INSERT OR IGNORE INTO bookmark_tags (bookmark_id, tag_id) VALUES (?, ?)', (bookmark_id, tag_id))
    cleanup_orphan_tags(conn)

def cleanup_orphan_tags(conn: sqlite3.Connection) -> None:
    conn.execute('DELETE FROM tags WHERE id NOT IN (SELECT DISTINCT tag_id FROM bookmark_tags)')

# --- Search ---

def search_bookmarks(conn: sqlite3.Connection, query: str, sort_order: str = 'newest', limit: int = 20, offset: int = 0) -> list[sqlite3.Row]:
    terms = query.split()
    if not terms:
        return get_all_bookmarks(conn, sort_order, limit, offset)
    where_clauses = []
    params: list[str] = []
    for term in terms:
        escaped = f'%{_escape_like(term)}%'
        where_clauses.append(
            "(b.title LIKE ? ESCAPE '\\' OR b.url LIKE ? ESCAPE '\\'"
            " OR EXISTS (SELECT 1 FROM bookmark_tags bt JOIN tags t ON bt.tag_id = t.id"
            " WHERE bt.bookmark_id = b.id AND t.name LIKE ? ESCAPE '\\'))"
        )
        params.extend([escaped, escaped, escaped])
    order = _sort_clause(sort_order)
    sql = f"SELECT b.* FROM bookmarks b WHERE {' AND '.join(where_clauses)} {order} LIMIT ? OFFSET ?"
    params.extend([str(limit), str(offset)])
    return conn.execute(sql, params).fetchall()

def search_bookmark_count(conn: sqlite3.Connection, query: str) -> int:
    terms = query.split()
    if not terms:
        return get_bookmark_count(conn)
    where_clauses = []
    params: list[str] = []
    for term in terms:
        escaped = f'%{_escape_like(term)}%'
        where_clauses.append(
            "(b.title LIKE ? ESCAPE '\\' OR b.url LIKE ? ESCAPE '\\'"
            " OR EXISTS (SELECT 1 FROM bookmark_tags bt JOIN tags t ON bt.tag_id = t.id"
            " WHERE bt.bookmark_id = b.id AND t.name LIKE ? ESCAPE '\\'))"
        )
        params.extend([escaped, escaped, escaped])
    sql = f"SELECT COUNT(*) FROM bookmarks b WHERE {' AND '.join(where_clauses)}"
    return conn.execute(sql, params).fetchone()[0]

# --- Bookmarks by Tag ---

def get_bookmarks_by_tag(conn: sqlite3.Connection, tag_name: str, sort_order: str = 'newest', limit: int = 20, offset: int = 0) -> list[sqlite3.Row]:
    order = _sort_clause(sort_order)
    return conn.execute(f'SELECT b.* FROM bookmarks b JOIN bookmark_tags bt ON b.id = bt.bookmark_id JOIN tags t ON bt.tag_id = t.id WHERE t.name = ? {order} LIMIT ? OFFSET ?', (tag_name, limit, offset)).fetchall()

def get_bookmarks_by_tag_count(conn: sqlite3.Connection, tag_name: str) -> int:
    return conn.execute('SELECT COUNT(*) FROM bookmarks b JOIN bookmark_tags bt ON b.id = bt.bookmark_id JOIN tags t ON bt.tag_id = t.id WHERE t.name = ?', (tag_name,)).fetchone()[0]
