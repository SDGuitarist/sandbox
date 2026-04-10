import os
import sqlite3


def init_db(db):
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path) as f:
        db.executescript(f.read())


def get_all_contacts(db):
    return db.execute("SELECT * FROM contacts ORDER BY name").fetchall()


def get_contact(db, contact_id):
    return db.execute("SELECT * FROM contacts WHERE id = ?", (contact_id,)).fetchone()


def search_contacts(db, query):
    return db.execute(
        "SELECT * FROM contacts WHERE name LIKE ? COLLATE NOCASE ORDER BY name",
        (f"%{query}%",),
    ).fetchall()


def create_contact(db, name, email, phone, notes):
    cursor = db.execute(
        "INSERT INTO contacts (name, email, phone, notes) VALUES (?, ?, ?, ?)",
        (name, email, phone, notes),
    )
    db.commit()
    return cursor.lastrowid


def update_contact(db, contact_id, name, email, phone, notes):
    db.execute(
        "UPDATE contacts SET name = ?, email = ?, phone = ?, notes = ? WHERE id = ?",
        (name, email, phone, notes, contact_id),
    )
    db.commit()


def delete_contact(db, contact_id):
    db.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
    db.commit()
