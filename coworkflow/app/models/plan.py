import sqlite3


def create_plan(conn: sqlite3.Connection, name: str, price_cents: int,
                billing_cycle: str, description: str) -> int:
    cursor = conn.execute(
        "INSERT INTO membership_plans (name, price_cents, billing_cycle, description) VALUES (?, ?, ?, ?)",
        (name, price_cents, billing_cycle, description)
    )
    conn.commit()
    return cursor.lastrowid


def get_plan(conn: sqlite3.Connection, plan_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM membership_plans WHERE id=?", (plan_id,)).fetchone()


def get_all_plans(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM membership_plans ORDER BY name").fetchall()


def get_active_plans(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM membership_plans WHERE is_active=1 ORDER BY name").fetchall()


def update_plan(conn: sqlite3.Connection, plan_id: int, name: str,
                price_cents: int, billing_cycle: str,
                description: str, is_active: int) -> None:
    conn.execute(
        """UPDATE membership_plans SET name=?, price_cents=?, billing_cycle=?,
           description=?, is_active=?, updated_at=datetime('now') WHERE id=?""",
        (name, price_cents, billing_cycle, description, is_active, plan_id)
    )
    conn.commit()


def delete_plan(conn: sqlite3.Connection, plan_id: int) -> None:
    """FK constraint is SET NULL -- no IntegrityError raised."""
    conn.execute("DELETE FROM membership_plans WHERE id=?", (plan_id,))
    conn.commit()
