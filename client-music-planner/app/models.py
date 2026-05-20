GENRES = [
    'rock', 'pop', 'jazz', 'blues', 'country', 'r_and_b',
    'classical', 'latin', 'folk', 'funk', 'soul', 'reggae',
    'electronic', 'hip_hop', 'other'
]

EVENT_TYPES = ['wedding', 'corporate', 'birthday', 'private_party', 'concert', 'other']


# --- User Functions ---

def get_user_by_email(db, email):
    """Returns: Row or None"""
    return db.execute("SELECT * FROM user WHERE email = ?", (email,)).fetchone()


def get_user_by_id(db, user_id):
    """Returns: Row or None"""
    return db.execute("SELECT * FROM user WHERE id = ?", (user_id,)).fetchone()


def create_user(db, email, password_hash, display_name):
    """Returns: int (user_id). Does NOT commit."""
    cursor = db.execute(
        "INSERT INTO user (email, password_hash, display_name) VALUES (?, ?, ?)",
        (email, password_hash, display_name)
    )
    return cursor.lastrowid


# --- Song Functions ---

def get_songs_by_user(db, user_id, genre=None, energy=None, search=None):
    """Returns: list[Row]. Supports optional filtering."""
    query = "SELECT * FROM song WHERE user_id = ?"
    params = [user_id]
    if genre:
        query += " AND genre = ?"
        params.append(genre)
    if energy:
        query += " AND energy = ?"
        params.append(int(energy))
    if search:
        query += " AND (title LIKE ? OR artist LIKE ?)"
        term = f"%{search}%"
        params.extend([term, term])
    query += " ORDER BY title ASC"
    return db.execute(query, params).fetchall()


def get_song(db, song_id, user_id):
    """Returns: Row or None. Enforces ownership via user_id."""
    return db.execute(
        "SELECT * FROM song WHERE id = ? AND user_id = ?",
        (song_id, user_id)
    ).fetchone()


def get_song_for_portal(db, song_id, user_id):
    """Returns: Row or None. Used by portal agents to read musician's song.
    Same as get_song but named distinctly for clarity."""
    return db.execute(
        "SELECT * FROM song WHERE id = ? AND user_id = ?",
        (song_id, user_id)
    ).fetchone()


def create_song(db, user_id, title, artist, genre, musical_key, tempo, energy, duration_seconds, notes):
    """Returns: int (song_id). Does NOT commit."""
    cursor = db.execute(
        """INSERT INTO song (user_id, title, artist, genre, musical_key, tempo, energy, duration_seconds, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, title, artist, genre, musical_key, tempo, int(energy), duration_seconds, notes)
    )
    return cursor.lastrowid


def update_song(db, song_id, user_id, title, artist, genre, musical_key, tempo, energy, duration_seconds, notes):
    """Returns: None. Does NOT commit. Enforces ownership."""
    db.execute(
        """UPDATE song SET title=?, artist=?, genre=?, musical_key=?, tempo=?, energy=?,
           duration_seconds=?, notes=?, updated_at=datetime('now')
           WHERE id=? AND user_id=?""",
        (title, artist, genre, musical_key, tempo, int(energy), duration_seconds, notes, song_id, user_id)
    )


def delete_song(db, song_id, user_id):
    """Returns: None. Does NOT commit. Cascades to playlist_items."""
    db.execute("DELETE FROM song WHERE id = ? AND user_id = ?", (song_id, user_id))


def bulk_create_songs(db, user_id, songs_list):
    """Returns: int (count of songs created). Does NOT commit.
    songs_list is list[dict] with keys: title, artist, genre, musical_key, tempo, energy, duration_seconds, notes"""
    count = 0
    for s in songs_list:
        db.execute(
            """INSERT INTO song (user_id, title, artist, genre, musical_key, tempo, energy, duration_seconds, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, s['title'], s.get('artist', ''), s.get('genre', 'other'),
             s.get('musical_key', ''), s.get('tempo'), int(s.get('energy', 3)),
             s.get('duration_seconds'), s.get('notes', ''))
        )
        count += 1
    return count


# --- Event Functions ---

def get_events_by_user(db, user_id, include_archived=False):
    """Returns: list[Row]."""
    if include_archived:
        return db.execute(
            "SELECT * FROM event WHERE user_id = ? ORDER BY event_date DESC",
            (user_id,)
        ).fetchall()
    return db.execute(
        "SELECT * FROM event WHERE user_id = ? AND is_archived = 0 ORDER BY event_date DESC",
        (user_id,)
    ).fetchall()


def get_event(db, event_id, user_id):
    """Returns: Row or None. Enforces ownership."""
    return db.execute(
        "SELECT * FROM event WHERE id = ? AND user_id = ?",
        (event_id, user_id)
    ).fetchone()


def get_event_by_token(db, token):
    """Returns: Row or None. Used by @require_portal_token decorator."""
    return db.execute(
        "SELECT * FROM event WHERE portal_token = ?",
        (token,)
    ).fetchone()


def create_event(db, user_id, name, event_date, event_type, venue, client_name, client_email, portal_token, notes=''):
    """Returns: int (event_id). Does NOT commit."""
    cursor = db.execute(
        """INSERT INTO event (user_id, name, event_date, event_type, venue, client_name, client_email, portal_token, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, name, event_date, event_type, venue, client_name, client_email, portal_token, notes)
    )
    return cursor.lastrowid


def update_event(db, event_id, user_id, name, event_date, event_type, venue, client_name, client_email, notes):
    """Returns: None. Does NOT commit."""
    db.execute(
        """UPDATE event SET name=?, event_date=?, event_type=?, venue=?, client_name=?,
           client_email=?, notes=?, updated_at=datetime('now')
           WHERE id=? AND user_id=?""",
        (name, event_date, event_type, venue, client_name, client_email, notes, event_id, user_id)
    )


def delete_event(db, event_id, user_id):
    """Returns: None. Does NOT commit. Cascades to playlist_items, song_requests."""
    db.execute("DELETE FROM event WHERE id = ? AND user_id = ?", (event_id, user_id))


def archive_event(db, event_id, user_id):
    """Returns: None. Does NOT commit. Toggles is_archived."""
    db.execute(
        "UPDATE event SET is_archived = 1 - is_archived, updated_at=datetime('now') WHERE id = ? AND user_id = ?",
        (event_id, user_id)
    )


def regenerate_token(db, event_id, user_id, new_token):
    """Returns: None. Does NOT commit."""
    db.execute(
        "UPDATE event SET portal_token = ?, updated_at=datetime('now') WHERE id = ? AND user_id = ?",
        (new_token, event_id, user_id)
    )


def approve_event(db, event_id):
    """Returns: None. Does NOT commit. Sets client_approved=1 and approved_at."""
    db.execute(
        "UPDATE event SET client_approved = 1, approved_at = datetime('now'), updated_at=datetime('now') WHERE id = ?",
        (event_id,)
    )


# --- Playlist Functions ---

def get_playlist_items(db, event_id):
    """Returns: list[Row] ordered by position. Joins song table for display data."""
    return db.execute(
        """SELECT pi.*, s.title, s.artist, s.genre, s.musical_key, s.tempo,
                  s.energy, s.duration_seconds
           FROM playlist_item pi
           JOIN song s ON pi.song_id = s.id
           WHERE pi.event_id = ?
           ORDER BY pi.position ASC""",
        (event_id,)
    ).fetchall()


def get_playlist_song_ids(db, event_id):
    """Returns: list[int]. Used by portal-browse to mark songs already in playlist."""
    rows = db.execute(
        "SELECT song_id FROM playlist_item WHERE event_id = ?",
        (event_id,)
    ).fetchall()
    return [row['song_id'] for row in rows]


def get_next_position(db, event_id):
    """Returns: int. Next position value for new playlist item."""
    row = db.execute(
        "SELECT COALESCE(MAX(position), -1) + 1 as next_pos FROM playlist_item WHERE event_id = ?",
        (event_id,)
    ).fetchone()
    return row['next_pos']


def add_playlist_item(db, event_id, song_id, position):
    """Returns: int (item_id). Does NOT commit.
    Raises IntegrityError if song already in playlist (UNIQUE constraint)."""
    cursor = db.execute(
        "INSERT INTO playlist_item (event_id, song_id, position) VALUES (?, ?, ?)",
        (event_id, song_id, position)
    )
    return cursor.lastrowid


def remove_playlist_item(db, event_id, song_id):
    """Returns: None. Does NOT commit."""
    db.execute(
        "DELETE FROM playlist_item WHERE event_id = ? AND song_id = ?",
        (event_id, song_id)
    )


def update_playlist_positions(db, event_id, item_ids_in_order):
    """Returns: None. Does NOT commit.
    item_ids_in_order is list[int] of playlist_item.id values in new order.
    IMPORTANT: Caller MUST validate len(item_ids_in_order) matches actual count."""
    for position, item_id in enumerate(item_ids_in_order):
        db.execute(
            "UPDATE playlist_item SET position = ? WHERE id = ? AND event_id = ?",
            (position, item_id, event_id)
        )


def toggle_playlist_flag(db, event_id, song_id, flag_type):
    """Returns: dict with keys 'is_must_play', 'is_do_not_play'.
    Does NOT commit.
    flag_type must be 'must_play' or 'do_not_play'.
    Toggling must_play clears do_not_play and vice versa."""
    item = db.execute(
        "SELECT * FROM playlist_item WHERE event_id = ? AND song_id = ?",
        (event_id, song_id)
    ).fetchone()
    if item is None:
        return None
    if flag_type == 'must_play':
        new_must = 0 if item['is_must_play'] else 1
        db.execute(
            "UPDATE playlist_item SET is_must_play = ?, is_do_not_play = 0 WHERE event_id = ? AND song_id = ?",
            (new_must, event_id, song_id)
        )
        return {'is_must_play': new_must, 'is_do_not_play': 0}
    elif flag_type == 'do_not_play':
        new_dnp = 0 if item['is_do_not_play'] else 1
        db.execute(
            "UPDATE playlist_item SET is_do_not_play = ?, is_must_play = 0 WHERE event_id = ? AND song_id = ?",
            (new_dnp, event_id, song_id)
        )
        return {'is_must_play': 0, 'is_do_not_play': new_dnp}
    return None


def get_playlist_stats(db, event_id):
    """Returns: dict with keys 'total', 'must_play', 'do_not_play'."""
    row = db.execute(
        """SELECT COUNT(*) as total,
                  SUM(CASE WHEN is_must_play = 1 THEN 1 ELSE 0 END) as must_play,
                  SUM(CASE WHEN is_do_not_play = 1 THEN 1 ELSE 0 END) as do_not_play
           FROM playlist_item WHERE event_id = ?""",
        (event_id,)
    ).fetchone()
    return {'total': row['total'], 'must_play': row['must_play'] or 0, 'do_not_play': row['do_not_play'] or 0}


# --- Song Request Functions ---

def get_song_requests(db, event_id):
    """Returns: list[Row]."""
    return db.execute(
        "SELECT * FROM song_request WHERE event_id = ? ORDER BY created_at DESC",
        (event_id,)
    ).fetchall()


def add_song_request(db, event_id, title, artist, notes):
    """Returns: int (request_id). Does NOT commit."""
    cursor = db.execute(
        "INSERT INTO song_request (event_id, title, artist, notes) VALUES (?, ?, ?, ?)",
        (event_id, title, artist, notes)
    )
    return cursor.lastrowid


def delete_song_request(db, request_id, event_id):
    """Returns: None. Does NOT commit. Enforces event scope."""
    db.execute(
        "DELETE FROM song_request WHERE id = ? AND event_id = ?",
        (request_id, event_id)
    )


def get_song_request_count(db, event_id):
    """Returns: int."""
    row = db.execute(
        "SELECT COUNT(*) as cnt FROM song_request WHERE event_id = ?",
        (event_id,)
    ).fetchone()
    return row['cnt']
