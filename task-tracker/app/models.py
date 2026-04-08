TASK_STATUSES = ['todo', 'in_progress', 'done']
TASK_PRIORITIES = ['low', 'medium', 'high']
STATUS_LABELS = {'todo': 'To Do', 'in_progress': 'In Progress', 'done': 'Done'}
PRIORITY_LABELS = {'low': 'Low', 'medium': 'Medium', 'high': 'High'}


# --- Projects ---

def get_all_projects(conn):
    return conn.execute('SELECT * FROM projects ORDER BY name').fetchall()


def get_project(conn, project_id):
    return conn.execute('SELECT * FROM projects WHERE id = ?', (project_id,)).fetchone()


def create_project(conn, name, description):
    cursor = conn.execute(
        'INSERT INTO projects (name, description) VALUES (?, ?)',
        (name, description)
    )
    return cursor.lastrowid


def update_project(conn, project_id, name, description):
    conn.execute(
        "UPDATE projects SET name = ?, description = ?, updated_at = strftime('%Y-%m-%d %H:%M:%S', 'now') WHERE id = ?",
        (name, description, project_id)
    )


def delete_project(conn, project_id):
    conn.execute('DELETE FROM projects WHERE id = ?', (project_id,))


# --- Tasks ---

def get_tasks_for_project(conn, project_id):
    return conn.execute(
        'SELECT * FROM tasks WHERE project_id = ? ORDER BY created_at DESC',
        (project_id,)
    ).fetchall()


def get_task(conn, task_id):
    return conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()


def create_task(conn, project_id, title, description, priority):
    cursor = conn.execute(
        'INSERT INTO tasks (project_id, title, description, priority) VALUES (?, ?, ?, ?)',
        (project_id, title, description, priority)
    )
    return cursor.lastrowid


def update_task(conn, task_id, title, description, status, priority):
    conn.execute(
        "UPDATE tasks SET title = ?, description = ?, status = ?, priority = ?, updated_at = strftime('%Y-%m-%d %H:%M:%S', 'now') WHERE id = ?",
        (title, description, status, priority, task_id)
    )


def delete_task(conn, task_id):
    conn.execute('DELETE FROM tasks WHERE id = ?', (task_id,))


# --- Comments ---

def get_comments_for_task(conn, task_id):
    return conn.execute(
        'SELECT * FROM comments WHERE task_id = ? ORDER BY created_at ASC',
        (task_id,)
    ).fetchall()


def create_comment(conn, task_id, content):
    cursor = conn.execute(
        'INSERT INTO comments (task_id, content) VALUES (?, ?)',
        (task_id, content)
    )
    return cursor.lastrowid


# --- Dashboard ---

def get_dashboard_stats(conn):
    total_projects = conn.execute('SELECT COUNT(*) FROM projects').fetchone()[0]
    total_tasks = conn.execute('SELECT COUNT(*) FROM tasks').fetchone()[0]

    tasks_by_status = {'todo': 0, 'in_progress': 0, 'done': 0}
    rows = conn.execute(
        'SELECT status, COUNT(*) AS cnt FROM tasks GROUP BY status'
    ).fetchall()
    for row in rows:
        tasks_by_status[row['status']] = row['cnt']

    recent_tasks = conn.execute(
        'SELECT t.id, t.title, t.status, p.name AS project_name, t.created_at '
        'FROM tasks t JOIN projects p ON t.project_id = p.id '
        'ORDER BY t.created_at DESC LIMIT 5'
    ).fetchall()

    projects = conn.execute(
        'SELECT p.id, p.name, '
        'COUNT(t.id) AS task_count, '
        "SUM(CASE WHEN t.status = 'done' THEN 1 ELSE 0 END) AS done_count "
        'FROM projects p LEFT JOIN tasks t ON t.project_id = p.id '
        'GROUP BY p.id, p.name ORDER BY p.name'
    ).fetchall()

    return {
        'total_projects': total_projects,
        'total_tasks': total_tasks,
        'tasks_by_status': tasks_by_status,
        'recent_tasks': recent_tasks,
        'projects': projects,
    }
