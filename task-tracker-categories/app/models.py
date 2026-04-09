DEFAULT_COLOR = '#6366f1'


def get_all_projects(conn):
    return conn.execute("SELECT * FROM projects ORDER BY name").fetchall()


def get_project(conn, project_id):
    return conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()


def create_project(conn, name, color):
    cursor = conn.execute("INSERT INTO projects (name, color) VALUES (?, ?)", (name, color))
    return cursor.lastrowid


def update_project(conn, project_id, name, color):
    conn.execute("UPDATE projects SET name = ?, color = ? WHERE id = ?", (name, color, project_id))


def delete_project(conn, project_id):
    conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))


def get_tasks_for_project(conn, project_id):
    return conn.execute("SELECT * FROM tasks WHERE project_id = ? ORDER BY created_at DESC", (project_id,)).fetchall()


def get_task(conn, task_id):
    return conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()


def create_task(conn, project_id, title, description):
    cursor = conn.execute(
        "INSERT INTO tasks (project_id, title, description) VALUES (?, ?, ?)",
        (project_id, title, description)
    )
    return cursor.lastrowid


def update_task(conn, task_id, title, description):
    conn.execute("UPDATE tasks SET title = ?, description = ? WHERE id = ?", (title, description, task_id))


def toggle_task(conn, task_id):
    task = conn.execute("SELECT completed FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if task is None:
        return
    if task['completed']:
        conn.execute("UPDATE tasks SET completed = 0, completed_at = NULL WHERE id = ?", (task_id,))
    else:
        conn.execute("UPDATE tasks SET completed = 1, completed_at = datetime('now') WHERE id = ?", (task_id,))


def delete_task(conn, task_id):
    conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))


def get_dashboard_stats(conn):
    stats = conn.execute(
        "SELECT COUNT(*) AS total_tasks, "
        "SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) AS completed_tasks, "
        "SUM(CASE WHEN completed = 0 THEN 1 ELSE 0 END) AS pending_tasks "
        "FROM tasks"
    ).fetchone()

    projects = conn.execute(
        "SELECT p.id, p.name, p.color, "
        "COUNT(t.id) AS task_count, "
        "SUM(CASE WHEN t.completed = 1 THEN 1 ELSE 0 END) AS completed_count "
        "FROM projects p LEFT JOIN tasks t ON t.project_id = p.id "
        "GROUP BY p.id, p.name, p.color ORDER BY p.name"
    ).fetchall()

    return {
        "total_tasks": stats["total_tasks"] or 0,
        "completed_tasks": stats["completed_tasks"] or 0,
        "pending_tasks": stats["pending_tasks"] or 0,
        "projects": projects,
    }
