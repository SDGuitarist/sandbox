"""
Notification helpers. create_notification() does NOT commit -- caller commits.
Used by booking_lifecycle.py and can be called directly from route handlers.
"""

def create_notification(conn, user_id, message, link=''):
    """
    Create a notification. Does NOT commit.
    Returns: int (notification_id)
    """
    cur = conn.execute(
        'INSERT INTO notifications (user_id, message, link) VALUES (?, ?, ?)',
        (user_id, message, link)
    )
    return cur.lastrowid

def get_notifications(conn, user_id, limit=20):
    """Returns: list[sqlite3.Row] ordered by newest first."""
    return conn.execute(
        'SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT ?',
        (user_id, limit)
    ).fetchall()

def get_unread_count(conn, user_id):
    """Returns: int"""
    row = conn.execute(
        'SELECT COUNT(*) AS cnt FROM notifications WHERE user_id = ? AND is_read = 0',
        (user_id,)
    ).fetchone()
    return row['cnt']

def mark_notification_read(conn, notification_id):
    """Does NOT commit."""
    conn.execute('UPDATE notifications SET is_read = 1 WHERE id = ?', (notification_id,))

def mark_all_read(conn, user_id):
    """Does NOT commit."""
    conn.execute('UPDATE notifications SET is_read = 1 WHERE user_id = ? AND is_read = 0',
                 (user_id,))
