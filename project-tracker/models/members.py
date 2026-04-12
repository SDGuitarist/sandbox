"""Member model functions for the project tracker."""


def get_all_members(db):
    """Return all members ordered by name."""
    return db.execute(
        'SELECT * FROM members ORDER BY name'
    ).fetchall()


def get_member(db, member_id):
    """Return a single member by ID, or None."""
    return db.execute(
        'SELECT * FROM members WHERE id = ?', (member_id,)
    ).fetchone()


def create_member(db, name, role):
    """Insert a new member and return its ID. Does not commit."""
    cursor = db.execute(
        'INSERT INTO members (name, role) VALUES (?, ?)',
        (name, role),
    )
    return cursor.lastrowid


def update_member(db, member_id, name, role):
    """Update a member's name and role. Does not commit."""
    db.execute(
        'UPDATE members SET name = ?, role = ? WHERE id = ?',
        (name, role, member_id),
    )


def delete_member(db, member_id):
    """Delete a member. CASCADE removes task_members rows. Does not commit."""
    db.execute('DELETE FROM members WHERE id = ?', (member_id,))


def count_tasks_for_member(db, member_id):
    """Return the number of tasks assigned to a member as a plain int."""
    row = db.execute(
        'SELECT COUNT(*) FROM task_members WHERE member_id = ?',
        (member_id,),
    ).fetchone()
    return row[0]
