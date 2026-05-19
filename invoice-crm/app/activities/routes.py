from flask import render_template, redirect, url_for, flash, session, abort
from . import bp
from .forms import ActivityForm
from app.db import get_db
from app.helpers import login_required


@bp.route('/<int:client_id>/activities')
@login_required
def list_activities(client_id):
    user_id = session['user_id']
    with get_db() as db:
        client = db.execute(
            "SELECT * FROM clients WHERE id = ? AND user_id = ?",
            (client_id, user_id),
        ).fetchone()
        if not client:
            flash('Client not found.', 'danger')
            return redirect(url_for('clients.list_clients'))

        activities = db.execute(
            "SELECT * FROM activities WHERE client_id = ? AND user_id = ? ORDER BY activity_date DESC, created_at DESC",
            (client_id, user_id),
        ).fetchall()

    return render_template(
        'activities/list.html',
        client=client,
        activities=activities,
    )


@bp.route('/<int:client_id>/activities/new', methods=['GET', 'POST'])
@login_required
def create_activity(client_id):
    user_id = session['user_id']
    with get_db() as db:
        client = db.execute(
            "SELECT * FROM clients WHERE id = ? AND user_id = ?",
            (client_id, user_id),
        ).fetchone()
        if not client:
            flash('Client not found.', 'danger')
            return redirect(url_for('clients.list_clients'))

    form = ActivityForm()
    if form.validate_on_submit():
        with get_db() as db:
            db.execute(
                """INSERT INTO activities (client_id, user_id, type, notes, activity_date)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    client_id,
                    user_id,
                    form.type.data,
                    form.notes.data,
                    form.activity_date.data.strftime('%Y-%m-%d'),
                ),
            )
            db.commit()
        flash('Activity created successfully.', 'success')
        return redirect(url_for('activities.list_activities', client_id=client_id))

    return render_template(
        'activities/form.html',
        form=form,
        client=client,
    )


@bp.route('/<int:client_id>/activities/<int:activity_id>/delete', methods=['POST'])
@login_required
def delete_activity(client_id, activity_id):
    user_id = session['user_id']
    with get_db() as db:
        client = db.execute(
            "SELECT * FROM clients WHERE id = ? AND user_id = ?",
            (client_id, user_id),
        ).fetchone()
        if not client:
            flash('Client not found.', 'danger')
            return redirect(url_for('clients.list_clients'))

        activity = db.execute(
            "SELECT * FROM activities WHERE id = ? AND client_id = ? AND user_id = ?",
            (activity_id, client_id, user_id),
        ).fetchone()
        if not activity:
            flash('Activity not found.', 'danger')
            return redirect(url_for('activities.list_activities', client_id=client_id))

        db.execute("DELETE FROM activities WHERE id = ?", (activity_id,))
        db.commit()

    flash('Activity deleted.', 'success')
    return redirect(url_for('activities.list_activities', client_id=client_id))
