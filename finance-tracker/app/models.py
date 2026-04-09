from datetime import date

ITEMS_PER_PAGE = 20


def get_all_categories(conn):
    return conn.execute("SELECT * FROM categories ORDER BY name COLLATE NOCASE").fetchall()


def get_category(conn, category_id):
    return conn.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()


def create_category(conn, name, color):
    cur = conn.execute("INSERT INTO categories (name, color) VALUES (?, ?)", (name, color))
    return cur.lastrowid


def update_category(conn, category_id, name, color):
    conn.execute("UPDATE categories SET name = ?, color = ? WHERE id = ?", (name, color, category_id))


def delete_category(conn, category_id):
    if category_id == 1:
        return False
    conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))
    return True


def get_transactions(conn, year_month=None, category_id=None, limit=ITEMS_PER_PAGE, offset=0):
    conditions = []
    params = []
    if year_month:
        conditions.append("t.transaction_date >= ? AND t.transaction_date < ?")
        params.extend([f"{year_month}-01", f"{year_month}-32"])
    if category_id:
        conditions.append("t.category_id = ?")
        params.append(category_id)
    where = ""
    if conditions:
        where = "WHERE " + " AND ".join(conditions)
    sql = f"""
        SELECT t.*, c.name AS category_name, c.color AS category_color
        FROM transactions t
        JOIN categories c ON c.id = t.category_id
        {where}
        ORDER BY t.transaction_date DESC, t.id DESC
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])
    return conn.execute(sql, params).fetchall()


def get_transaction_count(conn, year_month=None, category_id=None):
    conditions = []
    params = []
    if year_month:
        conditions.append("transaction_date >= ? AND transaction_date < ?")
        params.extend([f"{year_month}-01", f"{year_month}-32"])
    if category_id:
        conditions.append("category_id = ?")
        params.append(category_id)
    where = ""
    if conditions:
        where = "WHERE " + " AND ".join(conditions)
    sql = f"SELECT COUNT(*) FROM transactions {where}"
    return conn.execute(sql, params).fetchone()[0]


def get_transaction(conn, transaction_id):
    return conn.execute("SELECT * FROM transactions WHERE id = ?", (transaction_id,)).fetchone()


def create_transaction(conn, category_id, amount, description, transaction_date):
    cur = conn.execute(
        "INSERT INTO transactions (category_id, amount, description, transaction_date) VALUES (?, ?, ?, ?)",
        (category_id, amount, description, transaction_date)
    )
    return cur.lastrowid


def update_transaction(conn, transaction_id, category_id, amount, description, transaction_date):
    conn.execute(
        "UPDATE transactions SET category_id = ?, amount = ?, description = ?, transaction_date = ? WHERE id = ?",
        (category_id, amount, description, transaction_date, transaction_id)
    )


def delete_transaction(conn, transaction_id):
    conn.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))


def get_budget(conn, category_id, year_month):
    return conn.execute(
        "SELECT * FROM budgets WHERE category_id = ? AND year_month = ?",
        (category_id, year_month)
    ).fetchone()


def set_budget(conn, category_id, year_month, amount):
    conn.execute(
        "INSERT INTO budgets (category_id, year_month, amount) VALUES (?, ?, ?) ON CONFLICT(category_id, year_month) DO UPDATE SET amount = excluded.amount",
        (category_id, year_month, amount)
    )


def delete_budget(conn, category_id, year_month):
    conn.execute("DELETE FROM budgets WHERE category_id = ? AND year_month = ?", (category_id, year_month))


def get_dashboard_data(conn, year_month):
    sql = """
        SELECT c.id AS category_id, c.name, c.color,
            COALESCE(SUM(t.amount), 0) AS spent,
            b.amount AS budget_amount
        FROM categories c
        LEFT JOIN transactions t ON t.category_id = c.id
            AND t.transaction_date >= ? AND t.transaction_date < ?
        LEFT JOIN budgets b ON b.category_id = c.id AND b.year_month = ?
        GROUP BY c.id ORDER BY c.name COLLATE NOCASE
    """
    return conn.execute(sql, (f"{year_month}-01", f"{year_month}-32", year_month)).fetchall()


def get_budgets_for_month(conn, year_month):
    rows = conn.execute("SELECT * FROM budgets WHERE year_month = ?", (year_month,)).fetchall()
    return {row["category_id"]: row for row in rows}


def get_available_months(conn):
    rows = conn.execute(
        "SELECT DISTINCT substr(transaction_date, 1, 7) AS month FROM transactions ORDER BY month DESC"
    ).fetchall()
    months = [row["month"] for row in rows]
    current = date.today().strftime("%Y-%m")
    if current not in months:
        months.insert(0, current)
    return months
