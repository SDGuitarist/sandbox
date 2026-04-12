def get_all_bookmarks(db):
    return db.execute('SELECT * FROM bookmarks ORDER BY created_at DESC').fetchall()

def create_bookmark(db, url, title):
    cursor = db.execute('INSERT INTO bookmarks (url, title) VALUES (?, ?)', (url, title))
    db.commit()
    return cursor.lastrowid

def delete_bookmark(db, bookmark_id):
    db.execute('DELETE FROM bookmarks WHERE id = ?', (bookmark_id,))
    db.commit()
