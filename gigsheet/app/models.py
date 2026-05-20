"""GigSheet model functions.

Every database operation goes through this module. Route agents import
individual functions -- they never write SQL directly.

Transaction boundaries are documented per-function:
  - "Does NOT commit" -- caller is responsible for conn.commit()
  - "COMMITS" -- function calls conn.commit() itself
"""
import re


# ---------------------------------------------------------------------------
# User Functions
# ---------------------------------------------------------------------------

# Returns: int (the new user's ID)
# Usage:
#   user_id = create_user(conn, email, password_hash, display_name)
#   session['user_id'] = user_id
def create_user(conn, email: str, password_hash: str, display_name: str) -> int:
    cur = conn.execute(
        'INSERT INTO users (email, password_hash, display_name) VALUES (?, ?, ?)',
        (email, password_hash, display_name)
    )
    return cur.lastrowid


# Returns: sqlite3.Row or None
# Usage:
#   user = get_user_by_email(conn, email)
#   if user is None: flash('Invalid credentials', 'error')
def get_user_by_email(conn, email: str):
    return conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()


# Returns: sqlite3.Row or None
# Usage:
#   user = get_user_by_id(conn, user_id)
#   if user is None: abort(404)
def get_user_by_id(conn, user_id: int):
    return conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()


# ---------------------------------------------------------------------------
# Workspace Functions
# ---------------------------------------------------------------------------

# Returns: int (the new workspace's ID)
# Usage:
#   workspace_id = create_workspace(conn, name, slug, owner_user_id)
#   add_workspace_member(conn, workspace_id, owner_user_id, 'owner')
# Does NOT commit -- caller commits after adding owner as member
def create_workspace(conn, name: str, slug: str, owner_user_id: int) -> int:
    cur = conn.execute(
        'INSERT INTO workspaces (name, slug, owner_user_id) VALUES (?, ?, ?)',
        (name, slug, owner_user_id)
    )
    return cur.lastrowid


# Returns: sqlite3.Row or None
def get_workspace_by_id(conn, workspace_id: int):
    return conn.execute('SELECT * FROM workspaces WHERE id = ?', (workspace_id,)).fetchone()


# Returns: list[sqlite3.Row]
# Usage:
#   workspaces = get_user_workspaces(conn, user_id)
#   for ws in workspaces: ...
def get_user_workspaces(conn, user_id: int):
    return conn.execute('''
        SELECT w.* FROM workspaces w
        JOIN workspace_members wm ON wm.workspace_id = w.id
        WHERE wm.user_id = ? AND wm.joined_at IS NOT NULL
        ORDER BY w.name
    ''', (user_id,)).fetchall()


# Returns: None
# Does NOT commit -- caller commits
def add_workspace_member(conn, workspace_id: int, user_id: int, role: str) -> None:
    conn.execute(
        'INSERT INTO workspace_members (workspace_id, user_id, role, joined_at) VALUES (?, ?, ?, datetime(\'now\'))',
        (workspace_id, user_id, role)
    )


# Returns: sqlite3.Row or None
def get_workspace_member(conn, workspace_id: int, user_id: int):
    return conn.execute(
        'SELECT * FROM workspace_members WHERE workspace_id = ? AND user_id = ?',
        (workspace_id, user_id)
    ).fetchone()


# Returns: list[sqlite3.Row]
def get_workspace_members(conn, workspace_id: int):
    return conn.execute('''
        SELECT wm.*, u.email, u.display_name FROM workspace_members wm
        JOIN users u ON u.id = wm.user_id
        WHERE wm.workspace_id = ? ORDER BY wm.role, u.display_name
    ''', (workspace_id,)).fetchall()


# Returns: None -- Does NOT commit
def remove_workspace_member(conn, workspace_id: int, user_id: int) -> None:
    conn.execute(
        'DELETE FROM workspace_members WHERE workspace_id = ? AND user_id = ?',
        (workspace_id, user_id)
    )


# Returns: None -- Does NOT commit
def update_member_role(conn, workspace_id: int, user_id: int, role: str) -> None:
    conn.execute(
        'UPDATE workspace_members SET role = ? WHERE workspace_id = ? AND user_id = ?',
        (role, workspace_id, user_id)
    )


# ---------------------------------------------------------------------------
# Lead Functions
# ---------------------------------------------------------------------------

# Returns: int (the new lead's ID)
# Does NOT commit -- caller commits
def create_lead(conn, workspace_id: int, email: str, contact_name: str,
                venue_name: str, capacity: int, location: str, genre_tags: str,
                phone: str, website: str, source: str, created_by_user_id: int) -> int:
    cur = conn.execute('''
        INSERT INTO leads (workspace_id, email, contact_name, venue_name, capacity,
            location, genre_tags, phone, website, source, created_by_user_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (workspace_id, email, contact_name, venue_name, capacity,
          location, genre_tags, phone, website, source, created_by_user_id))
    return cur.lastrowid


# Returns: sqlite3.Row or None
def get_lead(conn, lead_id: int):
    return conn.execute('SELECT * FROM leads WHERE id = ?', (lead_id,)).fetchone()


# Returns: list[sqlite3.Row]
# Paginated lead listing for a workspace with optional stage filter
def get_leads_by_workspace(conn, workspace_id: int, page: int = 1, per_page: int = 25,
                           stage: str = None, tag_id: int = None):
    query = 'SELECT l.* FROM leads l'
    params = []
    if tag_id:
        query += ' JOIN lead_tags lt ON lt.lead_id = l.id'
    query += ' WHERE l.workspace_id = ?'
    params.append(workspace_id)
    if stage:
        query += ' AND l.pipeline_stage = ?'
        params.append(stage)
    if tag_id:
        query += ' AND lt.tag_id = ?'
        params.append(tag_id)
    query += ' ORDER BY l.created_at DESC LIMIT ? OFFSET ?'
    params.extend([per_page, (page - 1) * per_page])
    return conn.execute(query, params).fetchall()


# Returns: int (count)
def count_leads_by_workspace(conn, workspace_id: int, stage: str = None, tag_id: int = None) -> int:
    query = 'SELECT COUNT(*) FROM leads l'
    params = []
    if tag_id:
        query += ' JOIN lead_tags lt ON lt.lead_id = l.id'
    query += ' WHERE l.workspace_id = ?'
    params.append(workspace_id)
    if stage:
        query += ' AND l.pipeline_stage = ?'
        params.append(stage)
    if tag_id:
        query += ' AND lt.tag_id = ?'
        params.append(tag_id)
    return conn.execute(query, params).fetchone()[0]


# Returns: None
# Does NOT commit -- caller commits
def update_lead(conn, lead_id: int, **kwargs) -> None:
    allowed = {'email', 'contact_name', 'venue_name', 'capacity', 'location',
               'genre_tags', 'phone', 'website', 'notes'}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return
    fields['updated_at'] = "datetime('now')"
    sets = ', '.join(f'{k} = ?' for k in fields if k != 'updated_at')
    sets += ", updated_at = datetime('now')"
    vals = [v for k, v in fields.items() if k != 'updated_at']
    vals.append(lead_id)
    conn.execute(f'UPDATE leads SET {sets} WHERE id = ?', vals)


# Returns: None
# Does NOT commit -- caller commits
def update_lead_stage(conn, lead_id: int, new_stage: str) -> None:
    conn.execute(
        "UPDATE leads SET pipeline_stage = ?, updated_at = datetime('now') WHERE id = ?",
        (new_stage, lead_id)
    )


# Returns: None
# Does NOT commit -- caller commits
def delete_lead(conn, lead_id: int) -> None:
    conn.execute('DELETE FROM leads WHERE id = ?', (lead_id,))


# FTS5 search -- sanitize input before MATCH (FC36 prevention)
# Returns: list[sqlite3.Row]
def search_leads(conn, workspace_id: int, query: str, limit: int = 50):
    cleaned = re.sub(r'[*"():^]', '', query).strip()
    if not cleaned:
        return []
    safe_query = f'"{cleaned}"'
    return conn.execute('''
        SELECT l.* FROM leads l
        JOIN leads_fts ON leads_fts.rowid = l.id
        WHERE l.workspace_id = ? AND leads_fts MATCH ?
        ORDER BY rank LIMIT ?
    ''', (workspace_id, safe_query, limit)).fetchall()


# Returns: list[sqlite3.Row] (leads grouped by pipeline_stage for kanban board)
def get_leads_by_stage(conn, workspace_id: int):
    return conn.execute('''
        SELECT * FROM leads WHERE workspace_id = ?
        ORDER BY pipeline_stage, updated_at DESC
    ''', (workspace_id,)).fetchall()


# ---------------------------------------------------------------------------
# Tag Functions
# ---------------------------------------------------------------------------

# Returns: int (the new tag's ID)
# Does NOT commit
def create_tag(conn, workspace_id: int, name: str, color: str) -> int:
    cur = conn.execute(
        'INSERT INTO tags (workspace_id, name, color) VALUES (?, ?, ?)',
        (workspace_id, name, color)
    )
    return cur.lastrowid


# Returns: list[sqlite3.Row]
def get_tags_by_workspace(conn, workspace_id: int):
    return conn.execute('SELECT * FROM tags WHERE workspace_id = ? ORDER BY name', (workspace_id,)).fetchall()


# Returns: None -- Does NOT commit
def assign_tag(conn, lead_id: int, tag_id: int) -> None:
    conn.execute('INSERT OR IGNORE INTO lead_tags (lead_id, tag_id) VALUES (?, ?)', (lead_id, tag_id))


# Returns: None -- Does NOT commit
def remove_tag(conn, lead_id: int, tag_id: int) -> None:
    conn.execute('DELETE FROM lead_tags WHERE lead_id = ? AND tag_id = ?', (lead_id, tag_id))


# Returns: None -- Does NOT commit
def delete_tag(conn, tag_id: int) -> None:
    conn.execute('DELETE FROM tags WHERE id = ?', (tag_id,))


# Returns: list[sqlite3.Row] (tags for a specific lead)
def get_lead_tags(conn, lead_id: int):
    return conn.execute('''
        SELECT t.* FROM tags t
        JOIN lead_tags lt ON lt.tag_id = t.id
        WHERE lt.lead_id = ? ORDER BY t.name
    ''', (lead_id,)).fetchall()


# ---------------------------------------------------------------------------
# Template Functions
# ---------------------------------------------------------------------------

# Returns: int (new template ID) -- Does NOT commit
def create_template(conn, workspace_id: int, name: str, subject_line: str,
                    html_body: str, created_by_user_id: int) -> int:
    cur = conn.execute('''
        INSERT INTO templates (workspace_id, name, subject_line, html_body, created_by_user_id)
        VALUES (?, ?, ?, ?, ?)
    ''', (workspace_id, name, subject_line, html_body, created_by_user_id))
    return cur.lastrowid


# Returns: sqlite3.Row or None
def get_template(conn, template_id: int):
    return conn.execute('SELECT * FROM templates WHERE id = ?', (template_id,)).fetchone()


# Returns: list[sqlite3.Row]
def get_templates_by_workspace(conn, workspace_id: int):
    return conn.execute(
        'SELECT * FROM templates WHERE workspace_id = ? ORDER BY updated_at DESC',
        (workspace_id,)
    ).fetchall()


# Returns: None -- Does NOT commit
def update_template(conn, template_id: int, name: str, subject_line: str, html_body: str) -> None:
    conn.execute('''
        UPDATE templates SET name = ?, subject_line = ?, html_body = ?, updated_at = datetime('now')
        WHERE id = ?
    ''', (name, subject_line, html_body, template_id))


# Returns: None -- Does NOT commit
def delete_template(conn, template_id: int) -> None:
    conn.execute('DELETE FROM templates WHERE id = ?', (template_id,))


# Render template with merge fields replaced
# Returns: tuple(str, str) -- (rendered_subject, rendered_body)
def render_template_with_lead(template_row, lead_row) -> tuple:
    from markupsafe import escape
    subject = template_row['subject_line']
    body = template_row['html_body']
    replacements = {
        '{{venue_name}}': str(escape(lead_row['venue_name'] or '')),
        '{{contact_name}}': str(escape(lead_row['contact_name'] or '')),
        '{{capacity}}': str(lead_row['capacity']),
        '{{location}}': str(escape(lead_row['location'] or '')),
        '{{genre}}': str(escape(lead_row['genre_tags'] or '')),
        '{{phone}}': str(escape(lead_row['phone'] or '')),
        '{{website}}': str(escape(lead_row['website'] or '')),
    }
    for placeholder, value in replacements.items():
        subject = subject.replace(placeholder, value)
        body = body.replace(placeholder, value)
    return subject, body


# ---------------------------------------------------------------------------
# Campaign Functions
# ---------------------------------------------------------------------------

# Returns: int (new campaign ID) -- Does NOT commit
def create_campaign(conn, workspace_id: int, name: str, template_id: int,
                    created_by_user_id: int) -> int:
    cur = conn.execute('''
        INSERT INTO campaigns (workspace_id, name, template_id, created_by_user_id)
        VALUES (?, ?, ?, ?)
    ''', (workspace_id, name, template_id, created_by_user_id))
    return cur.lastrowid


# Returns: sqlite3.Row or None
def get_campaign(conn, campaign_id: int):
    return conn.execute('SELECT * FROM campaigns WHERE id = ?', (campaign_id,)).fetchone()


# Returns: list[sqlite3.Row]
def get_campaigns_by_workspace(conn, workspace_id: int, status: str = None):
    if status:
        return conn.execute(
            'SELECT * FROM campaigns WHERE workspace_id = ? AND status = ? ORDER BY created_at DESC',
            (workspace_id, status)
        ).fetchall()
    return conn.execute(
        'SELECT * FROM campaigns WHERE workspace_id = ? ORDER BY created_at DESC',
        (workspace_id,)
    ).fetchall()


# Returns: None -- Does NOT commit
def update_campaign(conn, campaign_id: int, **kwargs) -> None:
    allowed = {'name', 'template_id'}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return
    sets = ', '.join(f'{k} = ?' for k in fields)
    sets += ", updated_at = datetime('now')"
    vals = list(fields.values())
    vals.append(campaign_id)
    conn.execute(f'UPDATE campaigns SET {sets} WHERE id = ?', vals)


# Returns: None -- COMMITS (independent status transition)
def update_campaign_status(conn, campaign_id: int, status: str) -> None:
    extra = ''
    if status == 'sending':
        extra = ", started_at = datetime('now')"
    elif status in ('sent', 'cancelled'):
        extra = ", completed_at = datetime('now')"
    conn.execute(f"UPDATE campaigns SET status = ?, updated_at = datetime('now'){extra} WHERE id = ?",
                 (status, campaign_id))
    conn.commit()


# Returns: None -- Does NOT commit
def delete_campaign(conn, campaign_id: int) -> None:
    conn.execute('DELETE FROM campaigns WHERE id = ?', (campaign_id,))


# Returns: None -- Does NOT commit
def update_campaign_schedule(conn, campaign_id: int, scheduled_at: str, timezone: str) -> None:
    conn.execute(
        "UPDATE campaigns SET scheduled_at = ?, timezone = ?, updated_at = datetime('now') WHERE id = ?",
        (scheduled_at, timezone, campaign_id)
    )


# Returns: None -- Does NOT commit
def update_workspace(conn, workspace_id: int, name: str, from_email: str, from_name: str) -> None:
    conn.execute(
        'UPDATE workspaces SET name = ?, from_email = ?, from_name = ? WHERE id = ?',
        (name, from_email, from_name, workspace_id)
    )


# Returns: None -- Does NOT commit
def add_recipients(conn, campaign_id: int, lead_ids: list) -> None:
    for lead_id in lead_ids:
        conn.execute(
            'INSERT OR IGNORE INTO campaign_recipients (campaign_id, lead_id) VALUES (?, ?)',
            (campaign_id, lead_id)
        )
    count = conn.execute(
        'SELECT COUNT(*) FROM campaign_recipients WHERE campaign_id = ?', (campaign_id,)
    ).fetchone()[0]
    conn.execute('UPDATE campaigns SET total_recipients = ? WHERE id = ?', (count, campaign_id))


# Returns: list[sqlite3.Row]
def get_campaign_recipients(conn, campaign_id: int):
    return conn.execute('''
        SELECT cr.*, l.email, l.contact_name, l.venue_name
        FROM campaign_recipients cr
        JOIN leads l ON l.id = cr.lead_id
        WHERE cr.campaign_id = ?
    ''', (campaign_id,)).fetchall()


# Returns: None -- Does NOT commit
def update_recipient_status(conn, recipient_id: int, status: str, message_id: str = None) -> None:
    if message_id:
        conn.execute(
            "UPDATE campaign_recipients SET status = ?, message_id = ?, sent_at = datetime('now') WHERE id = ?",
            (status, message_id, recipient_id)
        )
    else:
        conn.execute('UPDATE campaign_recipients SET status = ? WHERE id = ?', (status, recipient_id))


# Returns: None -- Does NOT commit
def increment_campaign_counter(conn, campaign_id: int, counter_name: str) -> None:
    allowed = {'sent_count', 'delivered_count', 'opened_count', 'clicked_count', 'bounced_count', 'failed_count'}
    if counter_name not in allowed:
        return
    conn.execute(f'UPDATE campaigns SET {counter_name} = {counter_name} + 1 WHERE id = ?', (campaign_id,))


# ---------------------------------------------------------------------------
# Job Queue Functions
# ---------------------------------------------------------------------------

# Returns: None -- Does NOT commit (caller commits after enqueuing all jobs)
# Called by campaign-sender (14)
def enqueue_send_jobs(conn, campaign_id: int, scheduled_at: str = None) -> None:
    recipients = conn.execute(
        'SELECT id FROM campaign_recipients WHERE campaign_id = ? AND status = ?',
        (campaign_id, 'pending')
    ).fetchall()
    sched = scheduled_at or "datetime('now')"
    for r in recipients:
        conn.execute('''
            INSERT INTO job_queue (campaign_id, recipient_id, scheduled_at)
            VALUES (?, ?, ?)
        ''', (campaign_id, r['id'], sched if scheduled_at else conn.execute("SELECT datetime('now')").fetchone()[0]))


# Returns: sqlite3.Row or None (the claimed job)
# Called ONLY by email-queue worker (26)
# COMMITS after claim (independent transaction)
def claim_next_job(conn, worker_id: str):
    conn.execute('BEGIN IMMEDIATE')
    job = conn.execute('''
        SELECT id FROM job_queue
        WHERE status = 'pending' AND scheduled_at <= datetime('now')
        ORDER BY created_at LIMIT 1
    ''').fetchone()
    if job is None:
        conn.rollback()
        return None
    updated = conn.execute('''
        UPDATE job_queue SET status = 'running', worker_id = ?, claimed_at = datetime('now')
        WHERE id = ? AND status = 'pending'
    ''', (worker_id, job['id']))
    if updated.rowcount != 1:
        conn.rollback()
        return None
    conn.commit()
    return conn.execute('SELECT * FROM job_queue WHERE id = ?', (job['id'],)).fetchone()


# Returns: None -- COMMITS (each job completion is independent)
def complete_job(conn, job_id: int, success: bool, error_message: str = '') -> None:
    status = 'completed' if success else 'failed'
    conn.execute('''
        UPDATE job_queue SET status = ?, completed_at = datetime('now'), error_message = ?
        WHERE id = ?
    ''', (status, error_message, job_id))
    conn.commit()


# Reclaim timed-out jobs (claimed_at older than 5 minutes, still running)
# Returns: int (number of jobs reclaimed)
# COMMITS
def reclaim_timed_out_jobs(conn) -> int:
    cur = conn.execute('''
        UPDATE job_queue SET status = 'pending', claimed_at = NULL, worker_id = '',
            attempt_count = attempt_count + 1
        WHERE status = 'running' AND claimed_at < datetime('now', '-5 minutes')
            AND attempt_count + 1 < max_attempts
    ''')
    failed = conn.execute('''
        UPDATE job_queue SET status = 'failed', error_message = 'max attempts exceeded',
            completed_at = datetime('now')
        WHERE status = 'running' AND claimed_at < datetime('now', '-5 minutes')
            AND attempt_count + 1 >= max_attempts
    ''')
    conn.commit()
    return cur.rowcount + failed.rowcount


# ---------------------------------------------------------------------------
# Campaign Progress Functions
# ---------------------------------------------------------------------------

# Returns: None -- COMMITS (called by email-queue worker after each job)
def update_campaign_progress(conn, campaign_id: int, sent_delta: int = 0,
                             delivered_delta: int = 0, failed_delta: int = 0) -> None:
    conn.execute('''
        INSERT INTO campaign_progress (campaign_id, total, sent, delivered, failed)
        VALUES (?, (SELECT total_recipients FROM campaigns WHERE id = ?), ?, ?, ?)
        ON CONFLICT(campaign_id) DO UPDATE SET
            sent = sent + excluded.sent,
            delivered = delivered + excluded.delivered,
            failed = failed + excluded.failed,
            updated_at = datetime('now')
    ''', (campaign_id, campaign_id, sent_delta, delivered_delta, failed_delta))
    # Check if campaign is complete
    progress = conn.execute('SELECT * FROM campaign_progress WHERE campaign_id = ?', (campaign_id,)).fetchone()
    if progress and (progress['sent'] + progress['failed']) >= progress['total']:
        conn.execute("UPDATE campaign_progress SET status = 'completed' WHERE campaign_id = ?", (campaign_id,))
        update_campaign_status(conn, campaign_id, 'sent')  # This also commits
    else:
        conn.commit()


# Returns: sqlite3.Row or None
def get_campaign_progress(conn, campaign_id: int):
    return conn.execute('SELECT * FROM campaign_progress WHERE campaign_id = ?', (campaign_id,)).fetchone()


# ---------------------------------------------------------------------------
# Email Event Functions
# ---------------------------------------------------------------------------

# Returns: int (event ID) -- Does NOT commit
def record_email_event(conn, campaign_id: int, recipient_id: int,
                       message_id: str, event_type: str, metadata_json: str = '{}') -> int:
    cur = conn.execute('''
        INSERT INTO email_events (campaign_id, recipient_id, message_id, event_type, metadata_json)
        VALUES (?, ?, ?, ?, ?)
    ''', (campaign_id, recipient_id, message_id, event_type, metadata_json))
    return cur.lastrowid


# ---------------------------------------------------------------------------
# Pipeline Note Functions
# ---------------------------------------------------------------------------

# Returns: int (note ID) -- Does NOT commit
def add_pipeline_note(conn, lead_id: int, user_id: int, content: str) -> int:
    cur = conn.execute(
        'INSERT INTO pipeline_notes (lead_id, user_id, content) VALUES (?, ?, ?)',
        (lead_id, user_id, content)
    )
    return cur.lastrowid


# Returns: list[sqlite3.Row]
def get_pipeline_notes(conn, lead_id: int):
    return conn.execute('''
        SELECT pn.*, u.display_name FROM pipeline_notes pn
        JOIN users u ON u.id = pn.user_id
        WHERE pn.lead_id = ? ORDER BY pn.created_at DESC
    ''', (lead_id,)).fetchall()


# ---------------------------------------------------------------------------
# Dashboard Stats
# ---------------------------------------------------------------------------

# Returns: dict (stage -> count)
# Usage:
#   stage_counts = get_stage_counts(conn, workspace_id)
#   # stage_counts = {'new': 12, 'contacted': 5, ...}
def get_stage_counts(conn, workspace_id: int) -> dict:
    rows = conn.execute(
        'SELECT pipeline_stage, COUNT(*) as cnt FROM leads WHERE workspace_id = ? GROUP BY pipeline_stage',
        (workspace_id,)
    ).fetchall()
    return {row['pipeline_stage']: row['cnt'] for row in rows}


# ---------------------------------------------------------------------------
# File Functions
# ---------------------------------------------------------------------------

# Returns: int (file ID) -- Does NOT commit
def create_file_record(conn, workspace_id: int, filename_original: str,
                       filename_stored: str, file_ext: str, file_size_bytes: int,
                       content_type: str, uploaded_by_user_id: int) -> int:
    cur = conn.execute('''
        INSERT INTO files (workspace_id, filename_original, filename_stored, file_ext,
            file_size_bytes, content_type, uploaded_by_user_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (workspace_id, filename_original, filename_stored, file_ext,
          file_size_bytes, content_type, uploaded_by_user_id))
    return cur.lastrowid


# Returns: sqlite3.Row or None
def get_file(conn, file_id: int):
    return conn.execute('SELECT * FROM files WHERE id = ?', (file_id,)).fetchone()


# Returns: list[sqlite3.Row]
def get_files_by_workspace(conn, workspace_id: int):
    return conn.execute(
        'SELECT * FROM files WHERE workspace_id = ? ORDER BY created_at DESC',
        (workspace_id,)
    ).fetchall()


# Returns: None -- Does NOT commit
def delete_file_record(conn, file_id: int) -> None:
    conn.execute('DELETE FROM files WHERE id = ?', (file_id,))


# ---------------------------------------------------------------------------
# Notification & Activity Functions
# ---------------------------------------------------------------------------

# Returns: int (notification ID) -- Does NOT commit
def create_notification(conn, workspace_id: int, user_id: int, message: str, link: str = '') -> int:
    cur = conn.execute(
        'INSERT INTO notifications (workspace_id, user_id, message, link) VALUES (?, ?, ?, ?)',
        (workspace_id, user_id, message, link)
    )
    return cur.lastrowid


# Returns: list[sqlite3.Row]
def get_unread_notifications(conn, user_id: int, limit: int = 20):
    return conn.execute(
        'SELECT * FROM notifications WHERE user_id = ? AND is_read = 0 ORDER BY created_at DESC LIMIT ?',
        (user_id, limit)
    ).fetchall()


# Returns: None -- Does NOT commit
def mark_notification_read(conn, notification_id: int) -> None:
    conn.execute('UPDATE notifications SET is_read = 1 WHERE id = ?', (notification_id,))


# Returns: None -- Does NOT commit
def log_activity(conn, workspace_id: int, user_id: int, action: str,
                 entity_type: str = '', entity_id: int = None, details: str = '') -> None:
    conn.execute('''
        INSERT INTO activity_log (workspace_id, user_id, action, entity_type, entity_id, details)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (workspace_id, user_id, action, entity_type, entity_id, details))
