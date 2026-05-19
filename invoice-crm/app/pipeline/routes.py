from flask import render_template, request, redirect, url_for, flash, session, abort

from . import bp
from .forms import DealForm, MoveDealForm, STAGE_CHOICES
from app.db import get_db
from app.helpers import login_required, log_activity


VALID_STAGES = [s[0] for s in STAGE_CHOICES]


@bp.route('/')
@login_required
def list_deals():
    with get_db() as db:
        user_id = session['user_id']
        deals = db.execute("""
            SELECT d.*, c.name AS client_name
            FROM deals d
            LEFT JOIN clients c ON d.client_id = c.id
            WHERE d.user_id = ?
            ORDER BY d.updated_at DESC
        """, (user_id,)).fetchall()

        # Group deals by stage for kanban view
        stages = {}
        for stage_key, stage_label in STAGE_CHOICES:
            stages[stage_key] = {
                'label': stage_label,
                'deals': [],
                'total_cents': 0,
            }
        for deal in deals:
            stage = deal['stage']
            if stage in stages:
                stages[stage]['deals'].append(deal)
                stages[stage]['total_cents'] += deal['value_cents'] or 0

    return render_template('pipeline/kanban.html', stages=stages, stage_order=VALID_STAGES)


@bp.route('/new', methods=['GET', 'POST'])
@login_required
def create_deal():
    form = DealForm()
    with get_db() as db:
        user_id = session['user_id']
        clients = db.execute(
            "SELECT id, name FROM clients WHERE user_id = ? ORDER BY name",
            (user_id,)
        ).fetchall()
        form.client_id.choices = [(c['id'], c['name']) for c in clients]

        if form.validate_on_submit():
            value_cents = int(round(float(form.value.data) * 100))
            expected_close = form.expected_close_date.data.isoformat() if form.expected_close_date.data else None

            db.execute("""
                INSERT INTO deals (user_id, client_id, title, value_cents, stage,
                                   expected_close_date, probability, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, form.client_id.data, form.title.data, value_cents,
                  form.stage.data, expected_close, form.probability.data,
                  form.notes.data or ''))

            log_activity(db, form.client_id.data, user_id, 'note',
                         f"Deal '{form.title.data}' created")

            db.commit()
            flash('Deal created successfully.', 'success')
            return redirect(url_for('pipeline.list_deals'))

    return render_template('pipeline/form.html', form=form, editing=False)


@bp.route('/<int:deal_id>')
@login_required
def view_deal(deal_id):
    with get_db() as db:
        user_id = session['user_id']
        deal = db.execute("""
            SELECT d.*, c.name AS client_name
            FROM deals d
            LEFT JOIN clients c ON d.client_id = c.id
            WHERE d.id = ? AND d.user_id = ?
        """, (deal_id, user_id)).fetchone()

        if not deal:
            flash('Deal not found.', 'danger')
            return redirect(url_for('pipeline.list_deals'))

        move_form = MoveDealForm()

    return render_template('pipeline/detail.html', deal=deal, move_form=move_form,
                           stages=STAGE_CHOICES)


@bp.route('/<int:deal_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_deal(deal_id):
    with get_db() as db:
        user_id = session['user_id']
        deal = db.execute(
            "SELECT * FROM deals WHERE id = ? AND user_id = ?",
            (deal_id, user_id)
        ).fetchone()

        if not deal:
            flash('Deal not found.', 'danger')
            return redirect(url_for('pipeline.list_deals'))

        form = DealForm()
        clients = db.execute(
            "SELECT id, name FROM clients WHERE user_id = ? ORDER BY name",
            (user_id,)
        ).fetchall()
        form.client_id.choices = [(c['id'], c['name']) for c in clients]

        if form.validate_on_submit():
            value_cents = int(round(float(form.value.data) * 100))
            expected_close = form.expected_close_date.data.isoformat() if form.expected_close_date.data else None

            db.execute("""
                UPDATE deals
                SET client_id = ?, title = ?, value_cents = ?, stage = ?,
                    expected_close_date = ?, probability = ?, notes = ?,
                    updated_at = datetime('now')
                WHERE id = ? AND user_id = ?
            """, (form.client_id.data, form.title.data, value_cents,
                  form.stage.data, expected_close, form.probability.data,
                  form.notes.data or '', deal_id, user_id))

            db.commit()
            flash('Deal updated successfully.', 'success')
            return redirect(url_for('pipeline.view_deal', deal_id=deal_id))

        if request.method == 'GET':
            form.title.data = deal['title']
            form.client_id.data = deal['client_id']
            form.value.data = deal['value_cents'] / 100
            form.stage.data = deal['stage']
            if deal['expected_close_date']:
                from datetime import date as date_type
                form.expected_close_date.data = date_type.fromisoformat(deal['expected_close_date'][:10])
            form.probability.data = deal['probability']
            form.notes.data = deal['notes']

    return render_template('pipeline/form.html', form=form, editing=True, deal=deal)


@bp.route('/<int:deal_id>/move', methods=['POST'])
@login_required
def move_deal(deal_id):
    with get_db() as db:
        user_id = session['user_id']
        deal = db.execute(
            "SELECT * FROM deals WHERE id = ? AND user_id = ?",
            (deal_id, user_id)
        ).fetchone()

        if not deal:
            flash('Deal not found.', 'danger')
            return redirect(url_for('pipeline.list_deals'))

        form = MoveDealForm()
        if form.validate_on_submit():
            new_stage = form.new_stage.data
            if new_stage not in VALID_STAGES:
                flash('Invalid stage.', 'danger')
                return redirect(url_for('pipeline.view_deal', deal_id=deal_id))

            db.execute("""
                UPDATE deals SET stage = ?, updated_at = datetime('now')
                WHERE id = ? AND user_id = ?
            """, (new_stage, deal_id, user_id))

            log_activity(db, deal['client_id'], user_id, 'note',
                         f"Deal '{deal['title']}' moved to {new_stage}")

            if new_stage == 'won':
                db.commit()
                flash(f'Deal "{deal["title"]}" marked as Won! Create an invoice?', 'success')
                return redirect(url_for('invoices.create_invoice', from_deal=deal_id))

            db.commit()
            flash('Deal updated successfully.', 'success')

        return redirect(url_for('pipeline.view_deal', deal_id=deal_id))


@bp.route('/<int:deal_id>/delete', methods=['POST'])
@login_required
def delete_deal(deal_id):
    with get_db() as db:
        user_id = session['user_id']
        deal = db.execute(
            "SELECT * FROM deals WHERE id = ? AND user_id = ?",
            (deal_id, user_id)
        ).fetchone()

        if not deal:
            flash('Deal not found.', 'danger')
            return redirect(url_for('pipeline.list_deals'))

        db.execute("DELETE FROM deals WHERE id = ? AND user_id = ?", (deal_id, user_id))
        db.commit()
        flash('Deal deleted.', 'success')

    return redirect(url_for('pipeline.list_deals'))
