ITEMS_PER_PAGE = 20
MAX_SEARCH_TERMS = 10


def get_all_recipes(conn, limit, offset):
    return conn.execute(
        "SELECT * FROM recipes ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (limit, offset)
    ).fetchall()


def get_recipe_count(conn):
    return conn.execute("SELECT COUNT(*) FROM recipes").fetchone()[0]


def get_recipe(conn, recipe_id):
    return conn.execute(
        "SELECT * FROM recipes WHERE id = ?", (recipe_id,)
    ).fetchone()


def create_recipe(conn, title, description, instructions, servings,
                  prep_time_min, cook_time_min):
    cur = conn.execute(
        "INSERT INTO recipes (title, description, instructions, servings, "
        "prep_time_min, cook_time_min) VALUES (?, ?, ?, ?, ?, ?)",
        (title, description, instructions, servings, prep_time_min,
         cook_time_min)
    )
    return cur.lastrowid


def update_recipe(conn, recipe_id, title, description, instructions, servings,
                  prep_time_min, cook_time_min):
    conn.execute(
        "UPDATE recipes SET title = ?, description = ?, instructions = ?, "
        "servings = ?, prep_time_min = ?, cook_time_min = ?, "
        "updated_at = strftime('%Y-%m-%d %H:%M:%S', 'now') WHERE id = ?",
        (title, description, instructions, servings, prep_time_min,
         cook_time_min, recipe_id)
    )


def delete_recipe(conn, recipe_id):
    conn.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))


def get_all_ingredients(conn, limit, offset):
    return conn.execute(
        "SELECT i.*, "
        "(SELECT COUNT(*) FROM recipe_ingredients ri "
        "WHERE ri.ingredient_id = i.id) AS recipe_count "
        "FROM ingredients i ORDER BY name COLLATE NOCASE LIMIT ? OFFSET ?",
        (limit, offset)
    ).fetchall()


def get_ingredient_count(conn):
    return conn.execute("SELECT COUNT(*) FROM ingredients").fetchone()[0]


def get_ingredient(conn, ingredient_id):
    return conn.execute(
        "SELECT * FROM ingredients WHERE id = ?", (ingredient_id,)
    ).fetchone()


def create_ingredient(conn, name):
    cur = conn.execute(
        "INSERT INTO ingredients (name) VALUES (?)", (name,)
    )
    return cur.lastrowid


def update_ingredient(conn, ingredient_id, name):
    conn.execute(
        "UPDATE ingredients SET name = ? WHERE id = ?",
        (name, ingredient_id)
    )


def delete_ingredient(conn, ingredient_id):
    conn.execute("DELETE FROM ingredients WHERE id = ?", (ingredient_id,))


def set_recipe_ingredients(conn, recipe_id, ingredients_data):
    conn.execute(
        "DELETE FROM recipe_ingredients WHERE recipe_id = ?", (recipe_id,)
    )
    for item in ingredients_data:
        conn.execute(
            "INSERT INTO recipe_ingredients "
            "(recipe_id, ingredient_id, quantity, unit) VALUES (?, ?, ?, ?)",
            (recipe_id, item["ingredient_id"], item["quantity"], item["unit"])
        )


def get_ingredients_for_recipe(conn, recipe_id):
    return conn.execute(
        "SELECT ri.ingredient_id, i.name, ri.quantity, ri.unit "
        "FROM recipe_ingredients ri "
        "JOIN ingredients i ON i.id = ri.ingredient_id "
        "WHERE ri.recipe_id = ?",
        (recipe_id,)
    ).fetchall()


def get_ingredients_for_recipes(conn, recipe_ids):
    if not recipe_ids:
        return {}
    placeholders = ",".join("?" for _ in recipe_ids)
    rows = conn.execute(
        "SELECT ri.recipe_id, ri.ingredient_id, i.name, ri.quantity, ri.unit "
        "FROM recipe_ingredients ri "
        "JOIN ingredients i ON i.id = ri.ingredient_id "
        "WHERE ri.recipe_id IN (" + placeholders + ")",
        tuple(recipe_ids)
    ).fetchall()
    result = {rid: [] for rid in recipe_ids}
    for row in rows:
        result[row["recipe_id"]].append(row)
    return result


def _escape_like(term):
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _build_ingredient_search_where(query):
    terms = query.split()[:MAX_SEARCH_TERMS]
    if not terms:
        return "", []
    clauses = []
    params = []
    for term in terms:
        clauses.append(
            "EXISTS (SELECT 1 FROM recipe_ingredients ri "
            "JOIN ingredients i ON i.id = ri.ingredient_id "
            "WHERE ri.recipe_id = r.id AND i.name LIKE ? ESCAPE '\\')"
        )
        params.append("%" + _escape_like(term) + "%")
    where = " AND ".join(clauses)
    return where, params


def search_recipes_by_ingredients(conn, query, limit, offset):
    if not query or not query.strip():
        return get_all_recipes(conn, limit, offset)
    where, params = _build_ingredient_search_where(query)
    return conn.execute(
        "SELECT r.* FROM recipes r WHERE " + where +
        " ORDER BY r.created_at DESC LIMIT ? OFFSET ?",
        params + [limit, offset]
    ).fetchall()


def search_recipe_count(conn, query):
    if not query or not query.strip():
        return get_recipe_count(conn)
    where, params = _build_ingredient_search_where(query)
    return conn.execute(
        "SELECT COUNT(*) FROM recipes r WHERE " + where, params
    ).fetchone()[0]
