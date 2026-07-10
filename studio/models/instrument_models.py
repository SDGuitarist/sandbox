"""Instrument model — CRUD + in-tx status helper.

Owns the `instruments` table. Two DISTINCT status paths (do not conflate):
  - `update_instrument(iid, **fields)` is class-A: whitelist INCLUDES `status`
    (admin maintenance toggle, standalone) and it COMMITS internally.
  - `set_instrument_status(conn, iid, status)` is class-C: writes on the
    CALLER-supplied `conn`, does NOT commit, opens no transaction. Called ONLY
    by checkout_models inside its BEGIN IMMEDIATE transaction.
"""

from studio.database import get_db, query

# Columns clients may set via update_instrument (class-A). `status` is included
# as an admin maintenance toggle (available/checked_out/maintenance); the DB
# CHECK constraint enforces the enum, so no value validation is needed here.
_UPDATE_FIELDS = ("name", "category", "serial_number", "condition", "notes", "status")


def list_instruments(status=None, q=None):
    """Return instruments, optionally filtered by status and/or a LIKE query.

    `q` LIKE-matches name / category / serial_number.
    """
    sql = "SELECT * FROM instruments"
    clauses = []
    params = []
    if status is not None:
        clauses.append("status = ?")
        params.append(status)
    if q:
        clauses.append(
            "(name LIKE ? OR category LIKE ? OR serial_number LIKE ?)"
        )
        like = f"%{q}%"
        params.extend([like, like, like])
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY name"
    return query(sql, tuple(params))


def get_instrument(iid):
    """Return one instrument as a plain dict, or None if absent."""
    return query("SELECT * FROM instruments WHERE id = ?", (iid,), one=True)


def create_instrument(name, category, serial_number=None, condition="good", notes=None):
    """Insert a new instrument (status defaults to 'available' per schema). Commits. Returns new id."""
    db = get_db()
    cur = db.execute(
        "INSERT INTO instruments (name, category, serial_number, condition, notes) "
        "VALUES (?, ?, ?, ?, ?)",
        (name, category, serial_number, condition, notes),
    )
    db.commit()
    return cur.lastrowid


def update_instrument(iid, **fields):
    """Update whitelisted fields (name, category, serial_number, condition, notes, status).

    Class-A: commits internally. Unknown keys are ignored; a no-op if no
    whitelisted field is supplied.
    """
    updates = {k: v for k, v in fields.items() if k in _UPDATE_FIELDS}
    if not updates:
        return
    assignments = ", ".join(f"{col} = ?" for col in updates)
    params = list(updates.values())
    params.append(iid)
    db = get_db()
    db.execute(f"UPDATE instruments SET {assignments} WHERE id = ?", params)
    db.commit()


def set_instrument_status(conn, iid, status):
    """Set an instrument's status on the CALLER-supplied connection.

    Class-C in-tx helper: writes on `conn`, does NOT commit, opens no
    transaction. Called ONLY by checkout_models inside its BEGIN IMMEDIATE
    transaction (checkout_instrument / return_instrument).
    """
    conn.execute("UPDATE instruments SET status = ? WHERE id = ?", (status, iid))
