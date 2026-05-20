from flask import render_template, request, redirect, url_for, flash

from . import bp
from ..db import get_db
from ..decorators import setup_required


@bp.route('/')
@setup_required
def index():
    """List all contacts with optional search and status filter."""
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '').strip()

    with get_db() as db:
        # Build query with LEFT JOIN for company name
        query = """
            SELECT c.*, co.name AS company_name
            FROM contact c
            LEFT JOIN company co ON c.company_id = co.id
            WHERE 1=1
        """
        params = []

        if search:
            query += " AND (c.name LIKE ? OR c.email LIKE ? OR c.phone LIKE ?)"
            like = f'%{search}%'
            params.extend([like, like, like])

        if status_filter:
            query += " AND c.status = ?"
            params.append(status_filter)

        query += " ORDER BY c.name ASC LIMIT 1000"
        contacts = db.execute(query, params).fetchall()

        # Companies for the filter dropdown
        companies = db.execute("SELECT id, name FROM company ORDER BY name").fetchall()

    return render_template('contacts/list.html',
        contacts=contacts,
        search=search,
        status_filter=status_filter,
        statuses=['lead', 'active_client', 'past_client', 'partner'],
        companies=companies)


@bp.route('/<int:id>')
@setup_required
def detail(id):
    """Show a single contact with interactions, projects, and revenue summary."""
    with get_db() as db:
        contact = db.execute("SELECT * FROM contact WHERE id = ?", (id,)).fetchone()
        if not contact:
            flash("Contact not found.", "error")
            return redirect(url_for('contacts.index'))

        # Company info (may be None)
        company = None
        if contact['company_id']:
            company = db.execute("SELECT * FROM company WHERE id = ?",
                                 (contact['company_id'],)).fetchone()

        # Interactions for this contact
        interactions = db.execute(
            "SELECT * FROM interaction WHERE contact_id = ? ORDER BY date DESC",
            (id,)).fetchall()

        # Projects linked to this contact
        projects = db.execute(
            "SELECT * FROM project WHERE contact_id = ? ORDER BY created_at DESC",
            (id,)).fetchall()

        # Total revenue from income linked to this contact
        row = db.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total FROM income WHERE contact_id = ?",
            (id,)).fetchone()
        total_revenue = row['total'] if row else 0

        # Total hours from time entries on this contact's projects
        row = db.execute("""
            SELECT COALESCE(SUM(te.minutes), 0) AS total
            FROM time_entry te
            JOIN project p ON te.project_id = p.id
            WHERE p.contact_id = ?
        """, (id,)).fetchone()
        total_hours = row['total'] if row else 0

    return render_template('contacts/detail.html',
        contact=contact,
        company=company,
        interactions=interactions,
        projects=projects,
        total_revenue=total_revenue,
        total_hours=total_hours)


@bp.route('/new', methods=['GET', 'POST'])
@setup_required
def create():
    """Create a new contact."""
    with get_db() as db:
        companies = db.execute("SELECT id, name FROM company ORDER BY name").fetchall()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()

        if not name:
            flash("Name is required.", "error")
            return render_template('contacts/form.html',
                contact=None,
                companies=companies,
                statuses=['lead', 'active_client', 'past_client', 'partner'],
                sources=['referral', 'website', 'social', 'cold_outreach', 'other'])

        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        company_id = request.form.get('company_id', '').strip()
        company_id = int(company_id) if company_id else None
        role_title = request.form.get('role_title', '').strip()
        tags = request.form.get('tags', '').strip()
        source = request.form.get('source', 'other').strip()
        notes = request.form.get('notes', '').strip()
        status = request.form.get('status', 'lead').strip()

        with get_db(immediate=True) as db:
            db.execute("""
                INSERT INTO contact (name, email, phone, company_id, role_title, tags, source, notes, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, email, phone, company_id, role_title, tags, source, notes, status))
            contact_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

            db.execute(
                "INSERT INTO activity_log (action, entity_type, entity_id, description) VALUES (?, ?, ?, ?)",
                ('created', 'contact', contact_id, f"Created contact {name}"))

        flash("Contact created successfully.", "success")
        return redirect(url_for('contacts.detail', id=contact_id))

    return render_template('contacts/form.html',
        contact=None,
        companies=companies,
        statuses=['lead', 'active_client', 'past_client', 'partner'],
        sources=['referral', 'website', 'social', 'cold_outreach', 'other'])


@bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@setup_required
def edit(id):
    """Edit an existing contact."""
    with get_db() as db:
        contact = db.execute("SELECT * FROM contact WHERE id = ?", (id,)).fetchone()
        if not contact:
            flash("Contact not found.", "error")
            return redirect(url_for('contacts.index'))
        companies = db.execute("SELECT id, name FROM company ORDER BY name").fetchall()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()

        if not name:
            flash("Name is required.", "error")
            return render_template('contacts/form.html',
                contact=contact,
                companies=companies,
                statuses=['lead', 'active_client', 'past_client', 'partner'],
                sources=['referral', 'website', 'social', 'cold_outreach', 'other'])

        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        company_id = request.form.get('company_id', '').strip()
        company_id = int(company_id) if company_id else None
        role_title = request.form.get('role_title', '').strip()
        tags = request.form.get('tags', '').strip()
        source = request.form.get('source', 'other').strip()
        notes = request.form.get('notes', '').strip()
        status = request.form.get('status', 'lead').strip()

        with get_db(immediate=True) as db:
            db.execute("""
                UPDATE contact
                SET name = ?, email = ?, phone = ?, company_id = ?, role_title = ?,
                    tags = ?, source = ?, notes = ?, status = ?, updated_at = datetime('now')
                WHERE id = ?
            """, (name, email, phone, company_id, role_title, tags, source, notes, status, id))

            db.execute(
                "INSERT INTO activity_log (action, entity_type, entity_id, description) VALUES (?, ?, ?, ?)",
                ('updated', 'contact', id, f"Updated contact {name}"))

        flash("Contact updated successfully.", "success")
        return redirect(url_for('contacts.detail', id=id))

    return render_template('contacts/form.html',
        contact=contact,
        companies=companies,
        statuses=['lead', 'active_client', 'past_client', 'partner'],
        sources=['referral', 'website', 'social', 'cold_outreach', 'other'])


@bp.route('/<int:id>/delete', methods=['POST'])
@setup_required
def delete(id):
    """Delete a contact."""
    with get_db(immediate=True) as db:
        contact = db.execute("SELECT * FROM contact WHERE id = ?", (id,)).fetchone()
        if not contact:
            flash("Contact not found.", "error")
            return redirect(url_for('contacts.index'))

        name = contact['name']
        db.execute("DELETE FROM contact WHERE id = ?", (id,))

        db.execute(
            "INSERT INTO activity_log (action, entity_type, entity_id, description) VALUES (?, ?, ?, ?)",
            ('deleted', 'contact', id, f"Deleted contact {name}"))

    flash("Contact deleted successfully.", "success")
    return redirect(url_for('contacts.index'))


@bp.route('/<int:id>/interaction', methods=['POST'])
@setup_required
def add_interaction(id):
    """Add an interaction to a contact."""
    date = request.form.get('date', '').strip()
    interaction_type = request.form.get('type', 'email').strip()
    notes = request.form.get('notes', '').strip()

    if not date:
        flash("Date is required.", "error")
        return redirect(url_for('contacts.detail', id=id))

    with get_db(immediate=True) as db:
        contact = db.execute("SELECT * FROM contact WHERE id = ?", (id,)).fetchone()
        if not contact:
            flash("Contact not found.", "error")
            return redirect(url_for('contacts.index'))

        db.execute("""
            INSERT INTO interaction (contact_id, date, type, notes)
            VALUES (?, ?, ?, ?)
        """, (id, date, interaction_type, notes))

        # Update the contact's updated_at timestamp
        db.execute("UPDATE contact SET updated_at = datetime('now') WHERE id = ?", (id,))

        db.execute(
            "INSERT INTO activity_log (action, entity_type, entity_id, description) VALUES (?, ?, ?, ?)",
            ('interaction_added', 'contact', id, f"Added {interaction_type} interaction with {contact['name']}"),
        )

    flash("Interaction added successfully.", "success")
    return redirect(url_for('contacts.detail', id=id))


@bp.route('/quick-add', methods=['POST'])
@setup_required
def quick_add():
    """Quick-add a contact from the modal (minimal fields)."""
    name = request.form.get('name', '').strip()

    if not name:
        flash("Name is required.", "error")
        return redirect(url_for('contacts.index'))

    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    status = request.form.get('status', 'lead').strip()

    with get_db(immediate=True) as db:
        db.execute("""
            INSERT INTO contact (name, email, phone, status)
            VALUES (?, ?, ?, ?)
        """, (name, email, phone, status))
        contact_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        db.execute(
            "INSERT INTO activity_log (action, entity_type, entity_id, description) VALUES (?, ?, ?, ?)",
            ('created', 'contact', contact_id, f"Created contact {name}"))

    flash("Contact created successfully.", "success")
    return redirect(request.referrer or url_for('contacts.index'))
