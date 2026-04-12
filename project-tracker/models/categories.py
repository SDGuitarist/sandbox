import re

COLOR_RE = re.compile(r'^#[0-9a-fA-F]{6}$')


def get_all_categories(db):
    """Return all categories ordered by name."""
    return db.execute(
        'SELECT * FROM categories ORDER BY name'
    ).fetchall()


def get_category(db, category_id):
    """Return a single category by ID, or None."""
    return db.execute(
        'SELECT * FROM categories WHERE id = ?', (category_id,)
    ).fetchone()


def create_category(db, name, color):
    """Insert a new category and return its ID. Does not commit."""
    cursor = db.execute(
        'INSERT INTO categories (name, color) VALUES (?, ?)',
        (name, color)
    )
    return cursor.lastrowid


def update_category(db, category_id, name, color):
    """Update a category's name and color. Does not commit."""
    db.execute(
        'UPDATE categories SET name = ?, color = ? WHERE id = ?',
        (name, color, category_id)
    )


def delete_category(db, category_id):
    """Delete a category. Raises ValueError if it still has tasks."""
    if category_has_tasks(db, category_id):
        raise ValueError('Cannot delete category with existing tasks')
    db.execute('DELETE FROM categories WHERE id = ?', (category_id,))


def category_has_tasks(db, category_id):
    """Return True if any tasks reference this category."""
    row = db.execute(
        'SELECT COUNT(*) FROM tasks WHERE category_id = ?', (category_id,)
    ).fetchone()
    return row[0] > 0
