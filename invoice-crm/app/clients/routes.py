from flask import (
    render_template, request, redirect, url_for, flash, session
)

from app.db import get_db
from app.helpers import login_required
from . import bp
from .forms import ClientForm


def _sync_tags(db, client_id, user_id, tag_names):
    """Upsert tags and update the client_tag_map. Does NOT commit."""
    for name in tag_names:
        db.execute(
            "INSERT OR IGNORE INTO client_tags (user_id, name) VALUES (?, ?)",
            (user_id, name)
        )
        tag = db.execute(
            "SELECT id FROM client_tags WHERE user_id = ? AND name = ?",
            (user_id, name)
        ).fetchone()
        db.execute(
            "INSERT OR IGNORE INTO client_tag_map (client_id, tag_id) VALUES (?, ?)",
            (client_id, tag['id'])
        )
    # Remove old tags not in the new list
    if tag_names:
        placeholders = ','.join('?' * len(tag_names))
        db.execute(
            f"""DELETE FROM client_tag_map WHERE client_id = ? AND tag_id NOT IN (
                SELECT id FROM client_tags WHERE user_id = ? AND name IN ({placeholders})
            )""",
            (client_id, user_id, *tag_names)
        )
    else:
        # No tags provided -- remove all mappings
        db.execute(
            "DELETE FROM client_tag_map WHERE client_id = ?",
            (client_id,)
        )


def _get_tags_for_client(db, client_id):
    """Return comma-separated tag string for a single client."""
    rows = db.execute(
        """SELECT ct.name FROM client_tags ct
           JOIN client_tag_map m ON m.tag_id = ct.id
           WHERE m.client_id = ?
           ORDER BY ct.name""",
        (client_id,)
    ).fetchall()
    return ', '.join(r['name'] for r in rows)


def _get_tags_for_clients(db, client_ids, user_id):
    """Batch-fetch tags for multiple clients. Returns dict {client_id: [tag_names]}."""
    if not client_ids:
        return {}
    placeholders = ','.join('?' * len(client_ids))
    rows = db.execute(
        f"""SELECT m.client_id, ct.name
            FROM client_tag_map m
            JOIN client_tags ct ON ct.id = m.tag_id
            WHERE m.client_id IN ({placeholders}) AND ct.user_id = ?
            ORDER BY ct.name""",
        (*client_ids, user_id)
    ).fetchall()
    result = {}
    for row in rows:
        result.setdefault(row['client_id'], []).append(row['name'])
    return result


@bp.route('/')
@login_required
def list_clients():
    user_id = session['user_id']
    q = request.args.get('q', '').strip()
    tag = request.args.get('tag', '').strip()
    status = request.args.get('status', '').strip()
    sort = request.args.get('sort', 'name').strip()

    with get_db() as db:
        # Build query dynamically
        sql = "SELECT c.* FROM clients c"
        params = []
        conditions = ["c.user_id = ?"]
        params.append(user_id)

        # Tag filter requires a join
        if tag:
            sql += """
                JOIN client_tag_map m ON m.client_id = c.id
                JOIN client_tags ct ON ct.id = m.tag_id
            """
            conditions.append("ct.user_id = ?")
            params.append(user_id)
            conditions.append("ct.name = ?")
            params.append(tag)

        # Search by name or email
        if q:
            conditions.append("(c.name LIKE ? OR c.email LIKE ?)")
            like_q = f'%{q}%'
            params.extend([like_q, like_q])

        # Status filter
        if status:
            conditions.append("c.status = ?")
            params.append(status)

        sql += " WHERE " + " AND ".join(conditions)

        # Sorting
        if sort == 'created_at':
            sql += " ORDER BY c.created_at DESC"
        else:
            sql += " ORDER BY c.name ASC"

        clients = db.execute(sql, params).fetchall()

        # Batch-fetch tags for all listed clients
        client_ids = [c['id'] for c in clients]
        tags_map = _get_tags_for_clients(db, client_ids, user_id)

        # Fetch all user tags for the filter sidebar
        all_tags = db.execute(
            "SELECT DISTINCT name FROM client_tags WHERE user_id = ? ORDER BY name",
            (user_id,)
        ).fetchall()

    return render_template(
        'clients/list.html',
        clients=clients,
        tags_map=tags_map,
        all_tags=all_tags,
        q=q,
        current_tag=tag,
        current_status=status,
        current_sort=sort
    )


@bp.route('/new', methods=['GET', 'POST'])
@login_required
def create_client():
    form = ClientForm()
    user_id = session['user_id']

    if form.validate_on_submit():
        with get_db() as db:
            cursor = db.execute(
                """INSERT INTO clients (user_id, name, email, phone, company, address, notes, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    user_id,
                    form.name.data.strip(),
                    form.email.data.strip() if form.email.data else '',
                    form.phone.data.strip() if form.phone.data else '',
                    form.company.data.strip() if form.company.data else '',
                    form.address.data.strip() if form.address.data else '',
                    form.notes.data.strip() if form.notes.data else '',
                    form.status.data
                )
            )
            client_id = cursor.lastrowid

            # Parse and sync tags
            tag_names = [
                t.strip() for t in form.tags.data.split(',') if t.strip()
            ] if form.tags.data else []
            _sync_tags(db, client_id, user_id, tag_names)

            db.commit()

        flash('Client created successfully.', 'success')
        return redirect(url_for('clients.list_clients'))

    return render_template('clients/form.html', form=form, client=None)


@bp.route('/<int:client_id>')
@login_required
def view_client(client_id):
    user_id = session['user_id']

    with get_db() as db:
        client = db.execute(
            "SELECT * FROM clients WHERE id = ? AND user_id = ?",
            (client_id, user_id)
        ).fetchone()

        if not client:
            flash('Client not found.', 'danger')
            return redirect(url_for('clients.list_clients'))

        # Tags for this client
        tags_str = _get_tags_for_client(db, client_id)

        # Recent invoices (last 10) via LEFT JOIN with payment totals
        invoices = db.execute(
            """SELECT i.*,
                      COALESCE(SUM(p.amount_cents), 0) AS paid_cents
               FROM invoices i
               LEFT JOIN payments p ON p.invoice_id = i.id
               WHERE i.client_id = ? AND i.user_id = ?
               GROUP BY i.id
               ORDER BY i.created_at DESC
               LIMIT 10""",
            (client_id, user_id)
        ).fetchall()

        # Total revenue from payments on this client's invoices
        revenue_row = db.execute(
            """SELECT COALESCE(SUM(p.amount_cents), 0) AS total_revenue
               FROM payments p
               JOIN invoices i ON i.id = p.invoice_id
               WHERE i.client_id = ? AND i.user_id = ?""",
            (client_id, user_id)
        ).fetchone()
        total_revenue = revenue_row['total_revenue']

        # Recent activities (last 10)
        activities = db.execute(
            """SELECT * FROM activities
               WHERE client_id = ? AND user_id = ?
               ORDER BY activity_date DESC, created_at DESC
               LIMIT 10""",
            (client_id, user_id)
        ).fetchall()

    return render_template(
        'clients/detail.html',
        client=client,
        tags_str=tags_str,
        invoices=invoices,
        total_revenue=total_revenue,
        activities=activities
    )


@bp.route('/<int:client_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_client(client_id):
    user_id = session['user_id']

    with get_db() as db:
        client = db.execute(
            "SELECT * FROM clients WHERE id = ? AND user_id = ?",
            (client_id, user_id)
        ).fetchone()

        if not client:
            flash('Client not found.', 'danger')
            return redirect(url_for('clients.list_clients'))

        form = ClientForm(obj=None)

        if form.validate_on_submit():
            db.execute(
                """UPDATE clients
                   SET name = ?, email = ?, phone = ?, company = ?,
                       address = ?, notes = ?, status = ?, updated_at = datetime('now')
                   WHERE id = ? AND user_id = ?""",
                (
                    form.name.data.strip(),
                    form.email.data.strip() if form.email.data else '',
                    form.phone.data.strip() if form.phone.data else '',
                    form.company.data.strip() if form.company.data else '',
                    form.address.data.strip() if form.address.data else '',
                    form.notes.data.strip() if form.notes.data else '',
                    form.status.data,
                    client_id,
                    user_id
                )
            )

            # Parse and sync tags
            tag_names = [
                t.strip() for t in form.tags.data.split(',') if t.strip()
            ] if form.tags.data else []
            _sync_tags(db, client_id, user_id, tag_names)

            db.commit()

            flash('Client updated successfully.', 'success')
            return redirect(url_for('clients.view_client', client_id=client_id))

        # Pre-fill form on GET
        if request.method == 'GET':
            form.name.data = client['name']
            form.email.data = client['email']
            form.phone.data = client['phone']
            form.company.data = client['company']
            form.address.data = client['address']
            form.notes.data = client['notes']
            form.status.data = client['status']
            form.tags.data = _get_tags_for_client(db, client_id)

    return render_template('clients/form.html', form=form, client=client)


@bp.route('/<int:client_id>/delete', methods=['POST'])
@login_required
def delete_client(client_id):
    user_id = session['user_id']

    with get_db() as db:
        client = db.execute(
            "SELECT * FROM clients WHERE id = ? AND user_id = ?",
            (client_id, user_id)
        ).fetchone()

        if not client:
            flash('Client not found.', 'danger')
            return redirect(url_for('clients.list_clients'))

        db.execute(
            "DELETE FROM clients WHERE id = ? AND user_id = ?",
            (client_id, user_id)
        )
        db.commit()

    flash('Client deleted.', 'success')
    return redirect(url_for('clients.list_clients'))
