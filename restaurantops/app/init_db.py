"""Initialize the database schema. Run once: .venv/bin/python -m app.init_db"""
import os
import sqlite3

def get_db_path():
    """Return the database path (instance/restaurant.db)."""
    instance_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance')
    os.makedirs(instance_dir, exist_ok=True)
    return os.path.join(instance_dir, 'restaurant.db')

def init_db():
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    result = conn.execute("PRAGMA journal_mode=WAL").fetchone()
    if result[0] != 'wal':
        raise RuntimeError(f"Failed to enable WAL mode, got: {result[0]}")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
    with open(schema_path) as f:
        conn.executescript(f.read())
    conn.close()
    print(f"Database initialized at {db_path}")

if __name__ == '__main__':
    init_db()
