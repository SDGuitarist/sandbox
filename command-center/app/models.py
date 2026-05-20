"""Model functions for all 21 tables. Plain functions, no classes.

Return type conventions:
- create_* returns int (the new row ID)
- get_* returns Row or None
- list_* returns list[Row]
- update_* returns None
- delete_* returns None
"""

from datetime import date, datetime, timedelta

# ---------------------------------------------------------------------------
# Pipeline stage configuration
# ---------------------------------------------------------------------------

PIPELINE_STAGES = [
    ('lead', 'Lead', 10),
    ('discovery', 'Discovery', 25),
    ('proposal_sent', 'Proposal Sent', 50),
    ('negotiation', 'Negotiation', 65),
    ('verbal_yes', 'Verbal Yes', 80),
    ('won', 'Won', 100),
    ('lost', 'Lost', 0),
]

STAGE_MAP = {s[0]: {'label': s[1], 'probability': s[2]} for s in PIPELINE_STAGES}

# ---------------------------------------------------------------------------
# Allowed sort columns (whitelist for ORDER BY — never interpolate user input)
# ---------------------------------------------------------------------------

_CONTACT_SORT_COLS = {'name', 'email', 'status', 'created_at', 'updated_at', 'company_id'}
_COMPANY_SORT_COLS = {'name', 'created_at'}
_DEAL_SORT_COLS = {'title', 'value', 'stage', 'created_at', 'updated_at', 'expected_close_date'}
_PROJECT_SORT_COLS = {'name', 'status', 'value', 'start_date', 'target_end_date', 'created_at'}
_TASK_SORT_COLS = {'title', 'priority', 'status', 'due_date', 'created_at'}
_TIME_ENTRY_SORT_COLS = {'date', 'minutes', 'created_at'}
_INCOME_SORT_COLS = {'date', 'amount', 'category', 'created_at'}
_EXPENSE_SORT_COLS = {'date', 'amount', 'category', 'created_at'}
_NOTE_SORT_COLS = {'title', 'created_at', 'updated_at'}

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _safe_order(sort, allowed, default='name'):
    """Return a safe ORDER BY column name from a whitelist."""
    if sort in allowed:
        return sort
    return default


def _safe_direction(order):
    """Return 'ASC' or 'DESC' only."""
    return 'DESC' if order.upper() == 'DESC' else 'ASC'


# ===========================================================================
# USER
# ===========================================================================


def create_user(db, email, password_hash, name=''):
    """Returns int -- the new user ID."""
    db.execute(
        "INSERT INTO user (email, password_hash, name) VALUES (?, ?, ?)",
        (email, password_hash, name),
    )
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def get_user(db, user_id):
    """Returns Row or None."""
    return db.execute("SELECT * FROM user WHERE id = ?", (user_id,)).fetchone()


def get_user_by_email(db, email):
    """Returns Row or None."""
    return db.execute("SELECT * FROM user WHERE email = ?", (email,)).fetchone()


def update_user(db, user_id, **kwargs):
    """Update user fields. Allowed keys: name, email, password_hash, setup_complete."""
    allowed = {'name', 'email', 'password_hash', 'setup_complete'}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return None
    set_clause = ', '.join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [user_id]
    db.execute(f"UPDATE user SET {set_clause} WHERE id = ?", values)
    return None


# ===========================================================================
# BUSINESS PROFILE
# ===========================================================================


def create_business_profile(db, user_id, **kwargs):
    """Returns int -- the new profile ID."""
    cols = ['user_id']
    vals = [user_id]
    allowed = {
        'business_name', 'owner_name', 'industry', 'currency_symbol',
        'fiscal_year_start', 'logo_url', 'tagline', 'email', 'phone',
        'website', 'address', 'tax_id', 'default_hourly_rate',
        'weekly_hours_target', 'monthly_revenue_target', 'quarterly_revenue_target',
    }
    for k, v in kwargs.items():
        if k in allowed:
            cols.append(k)
            vals.append(v)
    placeholders = ', '.join('?' for _ in cols)
    col_names = ', '.join(cols)
    db.execute(f"INSERT INTO business_profile ({col_names}) VALUES ({placeholders})", vals)
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def get_business_profile(db, user_id=None):
    """Returns Row or None. If user_id is None, returns the first profile (single-user app)."""
    if user_id is not None:
        return db.execute(
            "SELECT * FROM business_profile WHERE user_id = ?", (user_id,)
        ).fetchone()
    return db.execute("SELECT * FROM business_profile LIMIT 1").fetchone()


def update_business_profile(db, user_id, **kwargs):
    """Update business profile fields."""
    allowed = {
        'business_name', 'owner_name', 'industry', 'currency_symbol',
        'fiscal_year_start', 'logo_url', 'tagline', 'email', 'phone',
        'website', 'address', 'tax_id', 'default_hourly_rate',
        'weekly_hours_target', 'monthly_revenue_target', 'quarterly_revenue_target',
    }
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return None
    set_clause = ', '.join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [user_id]
    db.execute(f"UPDATE business_profile SET {set_clause} WHERE user_id = ?", values)
    return None


# ===========================================================================
# COMPANY
# ===========================================================================


def create_company(db, name, website='', industry='', address='', notes=''):
    """Returns int -- the new company ID."""
    db.execute(
        "INSERT INTO company (name, website, industry, address, notes) VALUES (?, ?, ?, ?, ?)",
        (name, website, industry, address, notes),
    )
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def get_company(db, company_id):
    """Returns Row or None."""
    return db.execute("SELECT * FROM company WHERE id = ?", (company_id,)).fetchone()


def list_companies(db, search='', sort='name', order='asc'):
    """Returns list[Row]."""
    col = _safe_order(sort, _COMPANY_SORT_COLS, 'name')
    direction = _safe_direction(order)
    if search:
        return db.execute(
            f"SELECT * FROM company WHERE name LIKE ? ORDER BY {col} {direction} LIMIT 1000",
            (f'%{search}%',),
        ).fetchall()
    return db.execute(
        f"SELECT * FROM company ORDER BY {col} {direction} LIMIT 1000"
    ).fetchall()


def update_company(db, company_id, name, website='', industry='', address='', notes=''):
    """Returns None."""
    db.execute(
        "UPDATE company SET name = ?, website = ?, industry = ?, address = ?, notes = ? WHERE id = ?",
        (name, website, industry, address, notes, company_id),
    )
    return None


def delete_company(db, company_id):
    """Returns None."""
    db.execute("DELETE FROM company WHERE id = ?", (company_id,))
    return None


# ===========================================================================
# CONTACT
# ===========================================================================


def create_contact(db, name, email='', phone='', company_id=None,
                   role_title='', tags='', source='other', notes='', status='lead'):
    """Returns int -- the new contact ID."""
    db.execute(
        """INSERT INTO contact (name, email, phone, company_id, role_title, tags, source, notes, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (name, email, phone, company_id, role_title, tags, source, notes, status),
    )
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def get_contact(db, contact_id):
    """Returns Row or None."""
    return db.execute("SELECT * FROM contact WHERE id = ?", (contact_id,)).fetchone()


def list_contacts(db, search='', status='', tag='', sort='name', order='asc'):
    """Returns list[Row]. Includes LEFT JOIN for company_name."""
    col = _safe_order(sort, _CONTACT_SORT_COLS, 'name')
    direction = _safe_direction(order)
    # Prefix with table alias for unambiguous ordering
    order_col = f"c.{col}" if col != 'company_id' else 'c.company_id'

    query = """SELECT c.*, co.name as company_name
               FROM contact c
               LEFT JOIN company co ON c.company_id = co.id
               WHERE 1=1"""
    params = []

    if search:
        query += " AND (c.name LIKE ? OR c.email LIKE ?)"
        params.extend([f'%{search}%', f'%{search}%'])
    if status:
        query += " AND c.status = ?"
        params.append(status)
    if tag:
        query += " AND c.tags LIKE ?"
        params.append(f'%{tag}%')

    query += f" ORDER BY {order_col} {direction} LIMIT 1000"
    return db.execute(query, params).fetchall()


def update_contact(db, contact_id, name, email='', phone='', company_id=None,
                   role_title='', tags='', source='other', notes='', status='lead'):
    """Returns None."""
    db.execute(
        """UPDATE contact SET name = ?, email = ?, phone = ?, company_id = ?,
           role_title = ?, tags = ?, source = ?, notes = ?, status = ?,
           updated_at = datetime('now')
           WHERE id = ?""",
        (name, email, phone, company_id, role_title, tags, source, notes, status, contact_id),
    )
    return None


def delete_contact(db, contact_id):
    """Returns None."""
    db.execute("DELETE FROM contact WHERE id = ?", (contact_id,))
    return None


# ===========================================================================
# INTERACTION
# ===========================================================================


def create_interaction(db, contact_id, date, type='email', notes=''):
    """Returns int -- the new interaction ID."""
    db.execute(
        "INSERT INTO interaction (contact_id, date, type, notes) VALUES (?, ?, ?, ?)",
        (contact_id, date, type, notes),
    )
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def list_interactions(db, contact_id):
    """Returns list[Row] ordered by date descending."""
    return db.execute(
        "SELECT * FROM interaction WHERE contact_id = ? ORDER BY date DESC LIMIT 1000",
        (contact_id,),
    ).fetchall()


def delete_interaction(db, interaction_id):
    """Returns None."""
    db.execute("DELETE FROM interaction WHERE id = ?", (interaction_id,))
    return None


# ===========================================================================
# DEAL
# ===========================================================================


def create_deal(db, title, contact_id=None, company_id=None, value=0,
                stage='lead', probability_pct=10, expected_close_date=None, notes='', source=''):
    """Returns int -- the new deal ID."""
    db.execute(
        """INSERT INTO deal (title, contact_id, company_id, value, stage,
           probability_pct, expected_close_date, notes, source)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (title, contact_id, company_id, value, stage, probability_pct,
         expected_close_date, notes, source),
    )
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def get_deal(db, deal_id):
    """Returns Row or None."""
    return db.execute("SELECT * FROM deal WHERE id = ?", (deal_id,)).fetchone()


def list_deals(db, stage='', contact_id=None, sort='created_at', order='desc'):
    """Returns list[Row]."""
    col = _safe_order(sort, _DEAL_SORT_COLS, 'created_at')
    direction = _safe_direction(order)
    query = "SELECT * FROM deal WHERE 1=1"
    params = []

    if stage:
        query += " AND stage = ?"
        params.append(stage)
    if contact_id is not None:
        query += " AND contact_id = ?"
        params.append(contact_id)

    query += f" ORDER BY {col} {direction} LIMIT 1000"
    return db.execute(query, params).fetchall()


def list_deals_by_stage(db, stage):
    """Returns list[Row] for a specific pipeline stage."""
    return db.execute(
        "SELECT * FROM deal WHERE stage = ? ORDER BY updated_at DESC LIMIT 1000",
        (stage,),
    ).fetchall()


def update_deal(db, deal_id, title, contact_id=None, company_id=None, value=0,
                stage='lead', probability_pct=10, expected_close_date=None,
                notes='', source='', loss_reason=None):
    """Returns None."""
    db.execute(
        """UPDATE deal SET title = ?, contact_id = ?, company_id = ?, value = ?,
           stage = ?, probability_pct = ?, expected_close_date = ?,
           notes = ?, source = ?, loss_reason = ?, updated_at = datetime('now')
           WHERE id = ?""",
        (title, contact_id, company_id, value, stage, probability_pct,
         expected_close_date, notes, source, loss_reason, deal_id),
    )
    return None


def update_deal_stage(db, deal_id, stage, probability_pct=None, loss_reason=None):
    """Update just the stage (and optionally probability/loss_reason). Returns None."""
    if probability_pct is None:
        probability_pct = STAGE_MAP.get(stage, {}).get('probability', 10)
    db.execute(
        """UPDATE deal SET stage = ?, probability_pct = ?, loss_reason = ?,
           updated_at = datetime('now') WHERE id = ?""",
        (stage, probability_pct, loss_reason, deal_id),
    )
    return None


def delete_deal(db, deal_id):
    """Returns None."""
    db.execute("DELETE FROM deal WHERE id = ?", (deal_id,))
    return None


# ===========================================================================
# PROJECT
# ===========================================================================


def create_project(db, name, contact_id=None, status='not_started', type='hourly',
                   value=0, hourly_rate=0, start_date=None, target_end_date=None,
                   description='', notes='', deal_id=None):
    """Returns int -- the new project ID."""
    db.execute(
        """INSERT INTO project (name, contact_id, status, type, value, hourly_rate,
           start_date, target_end_date, description, notes, deal_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (name, contact_id, status, type, value, hourly_rate,
         start_date, target_end_date, description, notes, deal_id),
    )
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def get_project(db, project_id):
    """Returns Row or None."""
    return db.execute("SELECT * FROM project WHERE id = ?", (project_id,)).fetchone()


def list_projects(db, status='', contact_id=None, sort='name', order='asc'):
    """Returns list[Row]."""
    col = _safe_order(sort, _PROJECT_SORT_COLS, 'name')
    direction = _safe_direction(order)
    query = "SELECT * FROM project WHERE 1=1"
    params = []

    if status:
        query += " AND status = ?"
        params.append(status)
    if contact_id is not None:
        query += " AND contact_id = ?"
        params.append(contact_id)

    query += f" ORDER BY {col} {direction} LIMIT 1000"
    return db.execute(query, params).fetchall()


def update_project(db, project_id, name, contact_id=None, status='not_started',
                   type='hourly', value=0, hourly_rate=0, start_date=None,
                   target_end_date=None, actual_end_date=None,
                   description='', notes='', deal_id=None):
    """Returns None."""
    db.execute(
        """UPDATE project SET name = ?, contact_id = ?, status = ?, type = ?,
           value = ?, hourly_rate = ?, start_date = ?, target_end_date = ?,
           actual_end_date = ?, description = ?, notes = ?, deal_id = ?,
           updated_at = datetime('now')
           WHERE id = ?""",
        (name, contact_id, status, type, value, hourly_rate, start_date,
         target_end_date, actual_end_date, description, notes, deal_id, project_id),
    )
    return None


def delete_project(db, project_id):
    """Returns None."""
    db.execute("DELETE FROM project WHERE id = ?", (project_id,))
    return None


# ===========================================================================
# MILESTONE
# ===========================================================================


def create_milestone(db, project_id, name, due_date=None, status='pending', description=''):
    """Returns int -- the new milestone ID."""
    db.execute(
        "INSERT INTO milestone (project_id, name, due_date, status, description) VALUES (?, ?, ?, ?, ?)",
        (project_id, name, due_date, status, description),
    )
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def get_milestone(db, milestone_id):
    """Returns Row or None."""
    return db.execute("SELECT * FROM milestone WHERE id = ?", (milestone_id,)).fetchone()


def list_milestones(db, project_id):
    """Returns list[Row] ordered by due_date."""
    return db.execute(
        "SELECT * FROM milestone WHERE project_id = ? ORDER BY due_date ASC LIMIT 1000",
        (project_id,),
    ).fetchall()


def update_milestone(db, milestone_id, name=None, due_date=None, status=None, description=None):
    """Returns None. Only updates fields that are not None."""
    fields = {}
    if name is not None:
        fields['name'] = name
    if due_date is not None:
        fields['due_date'] = due_date
    if status is not None:
        fields['status'] = status
    if description is not None:
        fields['description'] = description
    if not fields:
        return None
    set_clause = ', '.join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [milestone_id]
    db.execute(f"UPDATE milestone SET {set_clause} WHERE id = ?", values)
    return None


def complete_milestone(db, milestone_id):
    """Mark a milestone as complete. Returns None."""
    db.execute("UPDATE milestone SET status = 'completed' WHERE id = ?", (milestone_id,))
    return None


def delete_milestone(db, milestone_id):
    """Returns None."""
    db.execute("DELETE FROM milestone WHERE id = ?", (milestone_id,))
    return None


# ===========================================================================
# TASK
# ===========================================================================


def create_task(db, title, description='', project_id=None, priority='medium',
                status='todo', due_date=None, estimated_hours=0, tags='',
                is_recurring=0, recurrence_interval=None, recurrence_days=0):
    """Returns int -- the new task ID."""
    db.execute(
        """INSERT INTO task (title, description, project_id, priority, status,
           due_date, estimated_hours, tags, is_recurring, recurrence_interval, recurrence_days)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (title, description, project_id, priority, status, due_date,
         estimated_hours, tags, is_recurring, recurrence_interval, recurrence_days),
    )
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def get_task(db, task_id):
    """Returns Row or None."""
    return db.execute("SELECT * FROM task WHERE id = ?", (task_id,)).fetchone()


def list_tasks(db, project_id=None, priority='', status='', sort='due_date', order='asc'):
    """Returns list[Row]."""
    col = _safe_order(sort, _TASK_SORT_COLS, 'due_date')
    direction = _safe_direction(order)
    query = "SELECT * FROM task WHERE 1=1"
    params = []

    if project_id is not None:
        query += " AND project_id = ?"
        params.append(project_id)
    if priority:
        query += " AND priority = ?"
        params.append(priority)
    if status:
        query += " AND status = ?"
        params.append(status)

    query += f" ORDER BY {col} {direction} LIMIT 1000"
    return db.execute(query, params).fetchall()


def list_my_day_tasks(db):
    """Returns list[Row] -- tasks due today or overdue, ordered by priority."""
    today = date.today().isoformat()
    return db.execute(
        """SELECT t.*, p.name as project_name
           FROM task t
           LEFT JOIN project p ON t.project_id = p.id
           WHERE t.status != 'done'
             AND (t.due_date <= ? OR t.due_date IS NULL)
           ORDER BY
             CASE t.priority
               WHEN 'urgent' THEN 1
               WHEN 'high' THEN 2
               WHEN 'medium' THEN 3
               WHEN 'low' THEN 4
             END ASC
           LIMIT 1000""",
        (today,),
    ).fetchall()


def update_task(db, task_id, title, description='', project_id=None, priority='medium',
                status='todo', due_date=None, estimated_hours=0, tags='',
                is_recurring=0, recurrence_interval=None, recurrence_days=0):
    """Returns None."""
    db.execute(
        """UPDATE task SET title = ?, description = ?, project_id = ?, priority = ?,
           status = ?, due_date = ?, estimated_hours = ?, tags = ?,
           is_recurring = ?, recurrence_interval = ?, recurrence_days = ?,
           updated_at = datetime('now')
           WHERE id = ?""",
        (title, description, project_id, priority, status, due_date,
         estimated_hours, tags, is_recurring, recurrence_interval, recurrence_days, task_id),
    )
    return None


def complete_task(db, task_id):
    """Mark a task as done. Returns None."""
    db.execute(
        "UPDATE task SET status = 'done', updated_at = datetime('now') WHERE id = ?",
        (task_id,),
    )
    return None


def delete_task(db, task_id):
    """Returns None."""
    db.execute("DELETE FROM task WHERE id = ?", (task_id,))
    return None


# ===========================================================================
# TIME ENTRY
# ===========================================================================


def create_time_entry(db, date, project_id, task_id=None, minutes=0,
                      description='', billable=1):
    """Returns int -- the new time entry ID."""
    db.execute(
        """INSERT INTO time_entry (date, project_id, task_id, minutes, description, billable)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (date, project_id, task_id, minutes, description, billable),
    )
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def get_time_entry(db, entry_id):
    """Returns Row or None."""
    return db.execute("SELECT * FROM time_entry WHERE id = ?", (entry_id,)).fetchone()


def list_time_entries(db, project_id=None, date_from=None, date_to=None,
                      sort='date', order='desc'):
    """Returns list[Row] with project_name joined."""
    col = _safe_order(sort, _TIME_ENTRY_SORT_COLS, 'date')
    direction = _safe_direction(order)
    query = """SELECT te.*, p.name as project_name, t.title as task_title
               FROM time_entry te
               LEFT JOIN project p ON te.project_id = p.id
               LEFT JOIN task t ON te.task_id = t.id
               WHERE 1=1"""
    params = []

    if project_id is not None:
        query += " AND te.project_id = ?"
        params.append(project_id)
    if date_from:
        query += " AND te.date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND te.date <= ?"
        params.append(date_to)

    query += f" ORDER BY te.{col} {direction} LIMIT 1000"
    return db.execute(query, params).fetchall()


def update_time_entry(db, entry_id, date, project_id, task_id=None, minutes=0,
                      description='', billable=1):
    """Returns None."""
    db.execute(
        """UPDATE time_entry SET date = ?, project_id = ?, task_id = ?,
           minutes = ?, description = ?, billable = ?
           WHERE id = ?""",
        (date, project_id, task_id, minutes, description, billable, entry_id),
    )
    return None


def delete_time_entry(db, entry_id):
    """Returns None."""
    db.execute("DELETE FROM time_entry WHERE id = ?", (entry_id,))
    return None


# ===========================================================================
# INCOME
# ===========================================================================


def create_income(db, amount, date, contact_id=None, project_id=None,
                  category='other', payment_method='bank_transfer', notes=''):
    """Returns int -- the new income ID."""
    db.execute(
        """INSERT INTO income (amount, date, contact_id, project_id, category,
           payment_method, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (amount, date, contact_id, project_id, category, payment_method, notes),
    )
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def get_income(db, income_id):
    """Returns Row or None."""
    return db.execute("SELECT * FROM income WHERE id = ?", (income_id,)).fetchone()


def list_incomes(db, date_from=None, date_to=None, contact_id=None,
                 sort='date', order='desc'):
    """Returns list[Row] with contact_name and project_name joined."""
    col = _safe_order(sort, _INCOME_SORT_COLS, 'date')
    direction = _safe_direction(order)
    query = """SELECT i.*, c.name as contact_name, p.name as project_name
               FROM income i
               LEFT JOIN contact c ON i.contact_id = c.id
               LEFT JOIN project p ON i.project_id = p.id
               WHERE 1=1"""
    params = []

    if date_from:
        query += " AND i.date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND i.date <= ?"
        params.append(date_to)
    if contact_id is not None:
        query += " AND i.contact_id = ?"
        params.append(contact_id)

    query += f" ORDER BY i.{col} {direction} LIMIT 1000"
    return db.execute(query, params).fetchall()


def update_income(db, income_id, amount, date, contact_id=None, project_id=None,
                  category='other', payment_method='bank_transfer', notes=''):
    """Returns None."""
    db.execute(
        """UPDATE income SET amount = ?, date = ?, contact_id = ?, project_id = ?,
           category = ?, payment_method = ?, notes = ?
           WHERE id = ?""",
        (amount, date, contact_id, project_id, category, payment_method, notes, income_id),
    )
    return None


def delete_income(db, income_id):
    """Returns None."""
    db.execute("DELETE FROM income WHERE id = ?", (income_id,))
    return None


# ===========================================================================
# EXPENSE
# ===========================================================================


def create_expense(db, amount, date, category='other', vendor='', notes='',
                   tax_deductible=0):
    """Returns int -- the new expense ID."""
    db.execute(
        """INSERT INTO expense (amount, date, category, vendor, notes, tax_deductible)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (amount, date, category, vendor, notes, tax_deductible),
    )
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def get_expense(db, expense_id):
    """Returns Row or None."""
    return db.execute("SELECT * FROM expense WHERE id = ?", (expense_id,)).fetchone()


def list_expenses(db, date_from=None, date_to=None, category='',
                  sort='date', order='desc'):
    """Returns list[Row]."""
    col = _safe_order(sort, _EXPENSE_SORT_COLS, 'date')
    direction = _safe_direction(order)
    query = "SELECT * FROM expense WHERE 1=1"
    params = []

    if date_from:
        query += " AND date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND date <= ?"
        params.append(date_to)
    if category:
        query += " AND category = ?"
        params.append(category)

    query += f" ORDER BY {col} {direction} LIMIT 1000"
    return db.execute(query, params).fetchall()


def update_expense(db, expense_id, amount, date, category='other', vendor='',
                   notes='', tax_deductible=0):
    """Returns None."""
    db.execute(
        """UPDATE expense SET amount = ?, date = ?, category = ?, vendor = ?,
           notes = ?, tax_deductible = ?
           WHERE id = ?""",
        (amount, date, category, vendor, notes, tax_deductible, expense_id),
    )
    return None


def delete_expense(db, expense_id):
    """Returns None."""
    db.execute("DELETE FROM expense WHERE id = ?", (expense_id,))
    return None


# ===========================================================================
# INCOME CATEGORY
# ===========================================================================


def list_income_categories(db):
    """Returns list[Row]."""
    return db.execute("SELECT * FROM income_category ORDER BY name ASC").fetchall()


def create_income_category(db, name):
    """Returns int -- the new category ID."""
    db.execute("INSERT INTO income_category (name, is_default) VALUES (?, 0)", (name,))
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def delete_income_category(db, category_id):
    """Returns None. Only deletes non-default categories."""
    db.execute("DELETE FROM income_category WHERE id = ? AND is_default = 0", (category_id,))
    return None


# ===========================================================================
# EXPENSE CATEGORY
# ===========================================================================


def list_expense_categories(db):
    """Returns list[Row]."""
    return db.execute("SELECT * FROM expense_category ORDER BY name ASC").fetchall()


def create_expense_category(db, name):
    """Returns int -- the new category ID."""
    db.execute("INSERT INTO expense_category (name, is_default) VALUES (?, 0)", (name,))
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def delete_expense_category(db, category_id):
    """Returns None. Only deletes non-default categories."""
    db.execute("DELETE FROM expense_category WHERE id = ? AND is_default = 0", (category_id,))
    return None


# ===========================================================================
# GOAL
# ===========================================================================


def get_goal(db, month):
    """Returns Row or None. month is 'YYYY-MM' format."""
    return db.execute("SELECT * FROM goal WHERE month = ?", (month,)).fetchone()


def upsert_goal(db, month, revenue_target=0, hours_target=0,
                revenue_actual=0, hours_actual=0):
    """Insert or update a goal. Returns int -- the goal ID."""
    existing = get_goal(db, month)
    if existing:
        db.execute(
            """UPDATE goal SET revenue_target = ?, hours_target = ?,
               revenue_actual = ?, hours_actual = ?
               WHERE month = ?""",
            (revenue_target, hours_target, revenue_actual, hours_actual, month),
        )
        return existing['id']
    db.execute(
        """INSERT INTO goal (month, revenue_target, hours_target, revenue_actual, hours_actual)
           VALUES (?, ?, ?, ?, ?)""",
        (month, revenue_target, hours_target, revenue_actual, hours_actual),
    )
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def list_goals(db, limit=12):
    """Returns list[Row] ordered by month descending."""
    return db.execute(
        "SELECT * FROM goal ORDER BY month DESC LIMIT ?", (limit,)
    ).fetchall()


# ===========================================================================
# JOURNAL ENTRY
# ===========================================================================


def get_journal_entry(db, entry_date):
    """Returns Row or None. entry_date is 'YYYY-MM-DD' format."""
    return db.execute(
        "SELECT * FROM journal_entry WHERE date = ?", (entry_date,)
    ).fetchone()


def upsert_journal_entry(db, entry_date, content):
    """Insert or update a journal entry. Returns int -- the entry ID."""
    existing = get_journal_entry(db, entry_date)
    if existing:
        db.execute(
            "UPDATE journal_entry SET content = ?, updated_at = datetime('now') WHERE date = ?",
            (content, entry_date),
        )
        return existing['id']
    db.execute(
        "INSERT INTO journal_entry (date, content) VALUES (?, ?)",
        (entry_date, content),
    )
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def list_journal_entries(db, limit=30):
    """Returns list[Row] ordered by date descending."""
    return db.execute(
        "SELECT * FROM journal_entry ORDER BY date DESC LIMIT ?", (limit,)
    ).fetchall()


# ===========================================================================
# NOTE
# ===========================================================================


def create_note(db, title, content='', tags=''):
    """Returns int -- the new note ID."""
    db.execute(
        "INSERT INTO note (title, content, tags) VALUES (?, ?, ?)",
        (title, content, tags),
    )
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def get_note(db, note_id):
    """Returns Row or None."""
    return db.execute("SELECT * FROM note WHERE id = ?", (note_id,)).fetchone()


def list_notes(db, sort='updated_at', order='desc'):
    """Returns list[Row]."""
    col = _safe_order(sort, _NOTE_SORT_COLS, 'updated_at')
    direction = _safe_direction(order)
    return db.execute(
        f"SELECT * FROM note ORDER BY {col} {direction} LIMIT 1000"
    ).fetchall()


def update_note(db, note_id, title, content='', tags=''):
    """Returns None."""
    db.execute(
        "UPDATE note SET title = ?, content = ?, tags = ?, updated_at = datetime('now') WHERE id = ?",
        (title, content, tags, note_id),
    )
    return None


def delete_note(db, note_id):
    """Returns None."""
    db.execute("DELETE FROM note WHERE id = ?", (note_id,))
    return None


def search_notes_fts(db, query):
    """Search notes using FTS5. Returns list[Row]."""
    return db.execute(
        """SELECT n.* FROM note n
           JOIN notes_fts ON notes_fts.rowid = n.id
           WHERE notes_fts MATCH ?
           ORDER BY rank LIMIT 100""",
        (query,),
    ).fetchall()


def search_journal_fts(db, query):
    """Search journal entries using FTS5. Returns list[Row]."""
    return db.execute(
        """SELECT j.* FROM journal_entry j
           JOIN journal_fts ON journal_fts.rowid = j.id
           WHERE journal_fts MATCH ?
           ORDER BY rank LIMIT 100""",
        (query,),
    ).fetchall()


# ===========================================================================
# ACTIVITY LOG
# ===========================================================================


def create_activity(db, action, entity_type, entity_id, description):
    """Returns int -- the new activity log ID."""
    db.execute(
        """INSERT INTO activity_log (action, entity_type, entity_id, description)
           VALUES (?, ?, ?, ?)""",
        (action, entity_type, entity_id, description),
    )
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def list_activities(db, limit=20):
    """Returns list[Row] ordered by created_at descending."""
    return db.execute(
        "SELECT * FROM activity_log ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()


# ===========================================================================
# PROJECT TEMPLATE
# ===========================================================================


def create_project_template(db, name, description=''):
    """Returns int -- the new template ID."""
    db.execute(
        "INSERT INTO project_template (name, description) VALUES (?, ?)",
        (name, description),
    )
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def get_project_template(db, template_id):
    """Returns Row or None."""
    return db.execute(
        "SELECT * FROM project_template WHERE id = ?", (template_id,)
    ).fetchone()


def list_project_templates(db):
    """Returns list[Row]."""
    return db.execute(
        "SELECT * FROM project_template ORDER BY name ASC LIMIT 1000"
    ).fetchall()


def delete_project_template(db, template_id):
    """Returns None."""
    db.execute("DELETE FROM project_template WHERE id = ?", (template_id,))
    return None


# ===========================================================================
# TEMPLATE MILESTONE
# ===========================================================================


def create_template_milestone(db, template_id, name, offset_days=0, description=''):
    """Returns int -- the new template milestone ID."""
    db.execute(
        """INSERT INTO template_milestone (template_id, name, offset_days, description)
           VALUES (?, ?, ?, ?)""",
        (template_id, name, offset_days, description),
    )
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def list_template_milestones(db, template_id):
    """Returns list[Row] ordered by offset_days."""
    return db.execute(
        "SELECT * FROM template_milestone WHERE template_id = ? ORDER BY offset_days ASC",
        (template_id,),
    ).fetchall()


# ===========================================================================
# TEMPLATE TASK
# ===========================================================================


def create_template_task(db, template_id, title, description='', priority='medium',
                         estimated_hours=0):
    """Returns int -- the new template task ID."""
    db.execute(
        """INSERT INTO template_task (template_id, title, description, priority, estimated_hours)
           VALUES (?, ?, ?, ?, ?)""",
        (template_id, title, description, priority, estimated_hours),
    )
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def list_template_tasks(db, template_id):
    """Returns list[Row]."""
    return db.execute(
        "SELECT * FROM template_task WHERE template_id = ? ORDER BY id ASC",
        (template_id,),
    ).fetchall()


# ===========================================================================
# SEARCH (global)
# ===========================================================================


def search_contacts(db, query):
    """Search contacts by name or email. Returns list[Row]."""
    return db.execute(
        """SELECT * FROM contact
           WHERE name LIKE ? OR email LIKE ?
           ORDER BY name ASC LIMIT 20""",
        (f'%{query}%', f'%{query}%'),
    ).fetchall()


def search_projects(db, query):
    """Search projects by name. Returns list[Row]."""
    return db.execute(
        "SELECT * FROM project WHERE name LIKE ? ORDER BY name ASC LIMIT 20",
        (f'%{query}%',),
    ).fetchall()


def search_tasks(db, query):
    """Search tasks by title. Returns list[Row]."""
    return db.execute(
        "SELECT * FROM task WHERE title LIKE ? ORDER BY title ASC LIMIT 20",
        (f'%{query}%',),
    ).fetchall()


def search_deals(db, query):
    """Search deals by title. Returns list[Row]."""
    return db.execute(
        "SELECT * FROM deal WHERE title LIKE ? ORDER BY title ASC LIMIT 20",
        (f'%{query}%',),
    ).fetchall()


# ===========================================================================
# DASHBOARD QUERY FUNCTIONS
# ===========================================================================


def get_revenue_snapshot(db):
    """Returns dict with keys: this_month, last_month, ytd, target, pct_to_target.
    All monetary values in cents. No user_id needed (single-user app)."""
    today = date.today()
    this_month_start = today.replace(day=1).isoformat()
    if today.month == 12:
        next_month_start = date(today.year + 1, 1, 1).isoformat()
    else:
        next_month_start = date(today.year, today.month + 1, 1).isoformat()
    if today.month == 1:
        last_month_start = date(today.year - 1, 12, 1).isoformat()
    else:
        last_month_start = date(today.year, today.month - 1, 1).isoformat()
    year_start = date(today.year, 1, 1).isoformat()
    year_end = date(today.year + 1, 1, 1).isoformat()

    this_month = db.execute(
        "SELECT COALESCE(SUM(amount), 0) as total FROM income WHERE date >= ? AND date < ?",
        (this_month_start, next_month_start),
    ).fetchone()['total']

    last_month = db.execute(
        "SELECT COALESCE(SUM(amount), 0) as total FROM income WHERE date >= ? AND date < ?",
        (last_month_start, this_month_start),
    ).fetchone()['total']

    ytd = db.execute(
        "SELECT COALESCE(SUM(amount), 0) as total FROM income WHERE date >= ? AND date < ?",
        (year_start, year_end),
    ).fetchone()['total']

    profile = get_business_profile(db)
    target = profile['monthly_revenue_target'] if profile else 0

    pct_to_target = 0.0
    if target > 0:
        pct_to_target = round((this_month / target) * 100, 1)

    return {
        'this_month': this_month,
        'last_month': last_month,
        'ytd': ytd,
        'target': target,
        'pct_to_target': pct_to_target,
    }


def get_active_projects_summary(db):
    """Returns dict with keys: count, total_value."""
    row = db.execute(
        """SELECT COUNT(*) as count, COALESCE(SUM(value), 0) as total_value
           FROM project WHERE status IN ('not_started', 'in_progress')"""
    ).fetchone()
    return {
        'count': row['count'],
        'total_value': row['total_value'],
    }


def get_pipeline_summary(db):
    """Returns dict with keys: total_deals, total_value, closing_this_month."""
    today = date.today()
    month_end = date(today.year, today.month + 1, 1).isoformat() if today.month < 12 else date(today.year + 1, 1, 1).isoformat()
    this_month_start = today.replace(day=1).isoformat()

    active = db.execute(
        """SELECT COUNT(*) as cnt, COALESCE(SUM(value), 0) as val
           FROM deal WHERE stage NOT IN ('won', 'lost')"""
    ).fetchone()

    closing = db.execute(
        """SELECT COUNT(*) as cnt FROM deal
           WHERE stage NOT IN ('won', 'lost')
             AND expected_close_date >= ? AND expected_close_date < ?""",
        (this_month_start, month_end),
    ).fetchone()['cnt']

    return {
        'total_deals': active['cnt'],
        'total_value': active['val'],
        'closing_this_month': closing,
    }


def get_overdue_tasks(db, limit=5):
    """Returns list[Row] of tasks where due_date < today and status != 'done'."""
    today = date.today().isoformat()
    return db.execute(
        """SELECT t.*, p.name as project_name
           FROM task t
           LEFT JOIN project p ON t.project_id = p.id
           WHERE t.due_date < ? AND t.status != 'done'
           ORDER BY t.due_date ASC
           LIMIT ?""",
        (today, limit),
    ).fetchall()


def get_upcoming_deadlines(db, days=7):
    """Returns list[Row] of tasks + milestones due in next N days."""
    today = date.today()
    end_date = (today + timedelta(days=days)).isoformat()
    today_str = today.isoformat()

    tasks = db.execute(
        """SELECT t.title as name, t.due_date, 'task' as type, p.name as project_name
           FROM task t
           LEFT JOIN project p ON t.project_id = p.id
           WHERE t.due_date >= ? AND t.due_date <= ? AND t.status != 'done'
           ORDER BY t.due_date ASC LIMIT 20""",
        (today_str, end_date),
    ).fetchall()

    milestones = db.execute(
        """SELECT m.name, m.due_date, 'milestone' as type, p.name as project_name
           FROM milestone m
           JOIN project p ON m.project_id = p.id
           WHERE m.due_date >= ? AND m.due_date <= ? AND m.status != 'completed'
           ORDER BY m.due_date ASC LIMIT 20""",
        (today_str, end_date),
    ).fetchall()

    combined = list(tasks) + list(milestones)
    combined.sort(key=lambda r: r['due_date'] or '')
    return combined[:20]


def get_hours_this_week(db):
    """Returns dict with keys: logged (minutes), target (minutes)."""
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    monday_str = monday.isoformat()
    sunday_str = (monday + timedelta(days=6)).isoformat()

    logged = db.execute(
        "SELECT COALESCE(SUM(minutes), 0) as total FROM time_entry WHERE date >= ? AND date <= ?",
        (monday_str, sunday_str),
    ).fetchone()['total']

    profile = get_business_profile(db)
    target_hours = profile['weekly_hours_target'] if profile else 40
    target_minutes = target_hours * 60

    return {
        'logged': logged,
        'target': target_minutes,
    }


def get_cash_flow(db):
    """Returns dict with keys: income (cents), expenses (cents), net (cents).
    Current month only."""
    today = date.today()
    month_start = today.replace(day=1).isoformat()
    if today.month == 12:
        month_end = date(today.year + 1, 1, 1).isoformat()
    else:
        month_end = date(today.year, today.month + 1, 1).isoformat()

    income_total = db.execute(
        "SELECT COALESCE(SUM(amount), 0) as total FROM income WHERE date >= ? AND date < ?",
        (month_start, month_end),
    ).fetchone()['total']

    expense_total = db.execute(
        "SELECT COALESCE(SUM(amount), 0) as total FROM expense WHERE date >= ? AND date < ?",
        (month_start, month_end),
    ).fetchone()['total']

    return {
        'income': income_total,
        'expenses': expense_total,
        'net': income_total - expense_total,
    }


def get_recent_activity(db, limit=10):
    """Returns list[Row] from activity_log ORDER BY created_at DESC LIMIT N."""
    return db.execute(
        "SELECT * FROM activity_log ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()


# ===========================================================================
# REPORT HELPER FUNCTIONS
# ===========================================================================


def get_revenue_by_month(db, date_from=None, date_to=None):
    """Returns list of dicts: {month, income, expenses, profit, margin_pct}."""
    income_query = """SELECT strftime('%Y-%m', date) as month,
                      COALESCE(SUM(amount), 0) as total
                      FROM income WHERE 1=1"""
    expense_query = """SELECT strftime('%Y-%m', date) as month,
                       COALESCE(SUM(amount), 0) as total
                       FROM expense WHERE 1=1"""
    params_i = []
    params_e = []

    if date_from:
        income_query += " AND date >= ?"
        expense_query += " AND date >= ?"
        params_i.append(date_from)
        params_e.append(date_from)
    if date_to:
        income_query += " AND date <= ?"
        expense_query += " AND date <= ?"
        params_i.append(date_to)
        params_e.append(date_to)

    income_query += " GROUP BY month ORDER BY month DESC"
    expense_query += " GROUP BY month ORDER BY month DESC"

    income_rows = {r['month']: r['total'] for r in db.execute(income_query, params_i).fetchall()}
    expense_rows = {r['month']: r['total'] for r in db.execute(expense_query, params_e).fetchall()}

    all_months = sorted(set(list(income_rows.keys()) + list(expense_rows.keys())), reverse=True)
    result = []
    for m in all_months:
        inc = income_rows.get(m, 0)
        exp = expense_rows.get(m, 0)
        profit = inc - exp
        margin = round((profit / inc) * 100, 1) if inc > 0 else 0.0
        result.append({
            'month': m,
            'income': inc,
            'expenses': exp,
            'profit': profit,
            'margin_pct': margin,
        })
    return result


def get_revenue_by_client(db):
    """Returns list of dicts: {contact_name, total_revenue, project_count, avg_value}."""
    rows = db.execute(
        """SELECT c.name as contact_name,
                  COALESCE(SUM(i.amount), 0) as total_revenue,
                  COUNT(DISTINCT i.project_id) as project_count
           FROM income i
           JOIN contact c ON i.contact_id = c.id
           WHERE i.contact_id IS NOT NULL
           GROUP BY i.contact_id
           ORDER BY total_revenue DESC LIMIT 100"""
    ).fetchall()

    result = []
    for r in rows:
        total = r['total_revenue']
        count = r['project_count'] if r['project_count'] > 0 else 1
        result.append({
            'contact_name': r['contact_name'],
            'total_revenue': total,
            'project_count': r['project_count'],
            'avg_value': total // count,
        })
    return result


def get_time_by_project(db, date_from=None, date_to=None):
    """Returns list of dicts: {project_name, billable, non_billable, total}."""
    query = """SELECT p.name as project_name,
                      COALESCE(SUM(CASE WHEN te.billable = 1 THEN te.minutes ELSE 0 END), 0) as billable,
                      COALESCE(SUM(CASE WHEN te.billable = 0 THEN te.minutes ELSE 0 END), 0) as non_billable,
                      COALESCE(SUM(te.minutes), 0) as total
               FROM time_entry te
               JOIN project p ON te.project_id = p.id
               WHERE 1=1"""
    params = []
    if date_from:
        query += " AND te.date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND te.date <= ?"
        params.append(date_to)
    query += " GROUP BY te.project_id ORDER BY total DESC LIMIT 100"
    return db.execute(query, params).fetchall()


def get_time_by_week(db, date_from=None, date_to=None):
    """Returns list of dicts: {week, billable, non_billable, total}."""
    query = """SELECT strftime('%Y-W%W', date) as week,
                      COALESCE(SUM(CASE WHEN billable = 1 THEN minutes ELSE 0 END), 0) as billable,
                      COALESCE(SUM(CASE WHEN billable = 0 THEN minutes ELSE 0 END), 0) as non_billable,
                      COALESCE(SUM(minutes), 0) as total
               FROM time_entry WHERE 1=1"""
    params = []
    if date_from:
        query += " AND date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND date <= ?"
        params.append(date_to)
    query += " GROUP BY week ORDER BY week DESC LIMIT 52"
    return db.execute(query, params).fetchall()


def get_expense_by_category(db, date_from=None, date_to=None):
    """Returns list of dicts: {category, total, count, tax_deductible}."""
    query = """SELECT category,
                      COALESCE(SUM(amount), 0) as total,
                      COUNT(*) as count,
                      COALESCE(SUM(CASE WHEN tax_deductible = 1 THEN amount ELSE 0 END), 0) as tax_deductible
               FROM expense WHERE 1=1"""
    params = []
    if date_from:
        query += " AND date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND date <= ?"
        params.append(date_to)
    query += " GROUP BY category ORDER BY total DESC"
    return db.execute(query, params).fetchall()


def get_pipeline_stats(db):
    """Returns tuple: (stage_stats, total_weighted, closing_this_month, win_rate).
    stage_stats is list of dicts: {stage, label, count, total_value, weighted_value}.
    """
    today = date.today()
    month_end = date(today.year, today.month + 1, 1).isoformat() if today.month < 12 else date(today.year + 1, 1, 1).isoformat()
    this_month_start = today.replace(day=1).isoformat()

    stage_stats = []
    total_weighted = 0
    for key, label, prob in PIPELINE_STAGES:
        if key in ('won', 'lost'):
            continue
        row = db.execute(
            "SELECT COUNT(*) as cnt, COALESCE(SUM(value), 0) as val FROM deal WHERE stage = ?",
            (key,),
        ).fetchone()
        weighted = int(row['val'] * prob / 100)
        total_weighted += weighted
        stage_stats.append({
            'stage': key,
            'label': label,
            'count': row['cnt'],
            'total_value': row['val'],
            'weighted_value': weighted,
        })

    closing = db.execute(
        """SELECT * FROM deal
           WHERE stage NOT IN ('won', 'lost')
             AND expected_close_date >= ? AND expected_close_date < ?
           ORDER BY expected_close_date ASC""",
        (this_month_start, month_end),
    ).fetchall()

    won_count = db.execute("SELECT COUNT(*) as cnt FROM deal WHERE stage = 'won'").fetchone()['cnt']
    lost_count = db.execute("SELECT COUNT(*) as cnt FROM deal WHERE stage = 'lost'").fetchone()['cnt']
    total_closed = won_count + lost_count
    win_rate = round((won_count / total_closed) * 100, 1) if total_closed > 0 else 0.0

    return stage_stats, total_weighted, closing, win_rate


def get_utilization_by_week(db, weeks=12):
    """Returns list of dicts: {week_start, billable, total, rate, target}."""
    profile = get_business_profile(db)
    target_hours = profile['weekly_hours_target'] if profile else 40
    target_minutes = target_hours * 60

    today = date.today()
    monday = today - timedelta(days=today.weekday())

    result = []
    for i in range(weeks):
        week_start = monday - timedelta(weeks=i)
        week_end = week_start + timedelta(days=6)
        ws = week_start.isoformat()
        we = week_end.isoformat()

        row = db.execute(
            """SELECT COALESCE(SUM(CASE WHEN billable = 1 THEN minutes ELSE 0 END), 0) as billable,
                      COALESCE(SUM(minutes), 0) as total
               FROM time_entry WHERE date >= ? AND date <= ?""",
            (ws, we),
        ).fetchone()

        billable = row['billable']
        total = row['total']
        rate = round((billable / target_minutes) * 100, 1) if target_minutes > 0 else 0.0

        result.append({
            'week_start': ws,
            'billable': billable,
            'total': total,
            'rate': rate,
            'target': target_minutes,
        })

    result.reverse()
    return result


def get_contact_revenue(db, contact_id):
    """Returns int (cents) -- total income for a contact."""
    row = db.execute(
        "SELECT COALESCE(SUM(amount), 0) as total FROM income WHERE contact_id = ?",
        (contact_id,),
    ).fetchone()
    return row['total']


def get_contact_hours(db, contact_id):
    """Returns int (minutes) -- total hours for projects linked to a contact."""
    row = db.execute(
        """SELECT COALESCE(SUM(te.minutes), 0) as total
           FROM time_entry te
           JOIN project p ON te.project_id = p.id
           WHERE p.contact_id = ?""",
        (contact_id,),
    ).fetchone()
    return row['total']


def get_project_total_hours(db, project_id):
    """Returns int (minutes) -- total time entries for a project."""
    row = db.execute(
        "SELECT COALESCE(SUM(minutes), 0) as total FROM time_entry WHERE project_id = ?",
        (project_id,),
    ).fetchone()
    return row['total']


def get_project_billable_hours(db, project_id):
    """Returns int (minutes) -- billable time entries for a project."""
    row = db.execute(
        "SELECT COALESCE(SUM(minutes), 0) as total FROM time_entry WHERE project_id = ? AND billable = 1",
        (project_id,),
    ).fetchone()
    return row['total']


def get_project_budget_spent(db, project_id):
    """Returns int (cents) -- calculated from billable hours * hourly rate."""
    project = get_project(db, project_id)
    if not project or project['hourly_rate'] == 0:
        return 0
    billable_minutes = get_project_billable_hours(db, project_id)
    # hourly_rate is in cents, minutes / 60 = hours
    return int(billable_minutes / 60 * project['hourly_rate'])


def get_timesheet_data(db, week_start_str):
    """Returns dict: {project_name: {0: mins, 1: mins, ..., 6: mins}} for a given week.
    Keys 0-6 represent Monday through Sunday."""
    week_start = date.fromisoformat(week_start_str)
    week_end = week_start + timedelta(days=6)

    rows = db.execute(
        """SELECT te.date, p.name as project_name, te.minutes
           FROM time_entry te
           JOIN project p ON te.project_id = p.id
           WHERE te.date >= ? AND te.date <= ?
           ORDER BY p.name, te.date""",
        (week_start.isoformat(), week_end.isoformat()),
    ).fetchall()

    data = {}
    for r in rows:
        pname = r['project_name']
        entry_date = date.fromisoformat(r['date'])
        day_idx = (entry_date - week_start).days
        if pname not in data:
            data[pname] = {i: 0 for i in range(7)}
        data[pname][day_idx] = data[pname].get(day_idx, 0) + r['minutes']

    return data
