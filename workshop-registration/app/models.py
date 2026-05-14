import os


def register_attendee(conn, name, email, role):
    conn.execute("BEGIN IMMEDIATE")
    try:
        paid_count = conn.execute(
            "SELECT COUNT(*) FROM registrants WHERE status = 'paid'"
        ).fetchone()[0]

        capacity = int(os.environ.get("WORKSHOP_CAPACITY", 35))
        if paid_count >= capacity:
            conn.execute(
                "INSERT INTO registrants (name, email, role, status, queue_position) "
                "VALUES (?, ?, ?, 'waitlisted', "
                "(SELECT COALESCE(MAX(queue_position), 0) + 1 FROM registrants WHERE status = 'waitlisted'))",
                (name, email, role),
            )
        else:
            conn.execute(
                "INSERT INTO registrants (name, email, role, status) VALUES (?, ?, ?, 'pending_payment')",
                (name, email, role),
            )

        rid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()
        return rid
    except Exception:
        conn.rollback()
        raise


def get_registrant(conn, id):
    return conn.execute(
        "SELECT * FROM registrants WHERE id = ?", (id,)
    ).fetchone()


def get_registrant_by_email(conn, email):
    return conn.execute(
        "SELECT * FROM registrants WHERE email = ?", (email,)
    ).fetchone()


def update_status(conn, registrant_id, new_status, **kwargs):
    fields = ["status = ?"]
    values = [new_status]

    for key in ("square_order_id", "square_payment_id", "paid_at", "cancelled_at", "queue_position"):
        if key in kwargs:
            fields.append(f"{key} = ?")
            values.append(kwargs[key])

    values.append(registrant_id)
    conn.execute(
        f"UPDATE registrants SET {', '.join(fields)} WHERE id = ?",
        values,
    )
    conn.commit()


def get_paid_count(conn):
    return conn.execute(
        "SELECT COUNT(*) FROM registrants WHERE status = 'paid'"
    ).fetchone()[0]


def get_next_waitlisted(conn):
    return conn.execute(
        "SELECT * FROM registrants WHERE status = 'waitlisted' ORDER BY queue_position ASC LIMIT 1"
    ).fetchone()
