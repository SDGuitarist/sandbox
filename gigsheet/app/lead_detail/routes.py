from flask import (
    Blueprint, render_template, request, redirect, url_for,
    flash, g, abort
)
from app.db import get_db
from app.decorators import login_required, require_workspace
from app.models import (
    create_lead, get_lead, update_lead, delete_lead,
    get_tags_by_workspace, get_lead_tags, log_activity
)
from app import PIPELINE_STAGES

lead_detail_bp = Blueprint('lead_detail', __name__)


@lead_detail_bp.route('/new')
@login_required
@require_workspace
def new():
    return render_template('lead_detail/form.html', lead=None, is_edit=False)


@lead_detail_bp.route('/new', methods=['POST'])
@login_required
@require_workspace
def create():
    email = request.form.get('email', '').strip()[:200]
    contact_name = request.form.get('contact_name', '').strip()[:200]
    venue_name = request.form.get('venue_name', '').strip()[:200]
    location = request.form.get('location', '').strip()[:200]
    genre_tags = request.form.get('genre_tags', '').strip()[:200]
    phone = request.form.get('phone', '').strip()[:50]
    website = request.form.get('website', '').strip()[:500]
    notes = request.form.get('notes', '').strip()[:2000]

    # capacity: convert to int, default 0
    try:
        capacity = int(request.form.get('capacity', '0') or '0')
    except (ValueError, TypeError):
        capacity = 0
    if capacity < 0:
        capacity = 0

    if not venue_name:
        flash('Venue name is required.', 'error')
        return redirect(request.referrer or url_for('lead_detail.new'))

    conn = get_db()
    lead_id = create_lead(
        conn,
        workspace_id=g.workspace['id'],
        email=email,
        contact_name=contact_name,
        venue_name=venue_name,
        capacity=capacity,
        location=location,
        genre_tags=genre_tags,
        phone=phone,
        website=website,
        source='manual',
        created_by_user_id=g.user['id'],
    )
    # Notes are not part of create_lead -- update separately if provided
    if notes:
        update_lead(conn, lead_id, notes=notes)
    log_activity(
        conn, g.workspace['id'], g.user['id'],
        'created_lead', 'lead', lead_id, f'Lead: {venue_name}'
    )
    conn.commit()
    flash('Lead created successfully.', 'success')
    return redirect(url_for('lead_detail.detail', id=lead_id))


@lead_detail_bp.route('/<int:id>')
@login_required
@require_workspace
def detail(id):
    conn = get_db()
    lead = get_lead(conn, id)
    if lead is None:
        abort(404)
    if lead['workspace_id'] != g.workspace['id']:
        abort(403)

    lead_tags = get_lead_tags(conn, id)
    all_tags = get_tags_by_workspace(conn, g.workspace['id'])

    return render_template(
        'lead_detail/detail.html',
        lead=lead,
        tags=lead_tags,
        all_tags=all_tags,
        stages=PIPELINE_STAGES,
    )


@lead_detail_bp.route('/<int:id>/edit')
@login_required
@require_workspace
def edit(id):
    conn = get_db()
    lead = get_lead(conn, id)
    if lead is None:
        abort(404)
    if lead['workspace_id'] != g.workspace['id']:
        abort(403)

    return render_template('lead_detail/form.html', lead=lead, is_edit=True)


@lead_detail_bp.route('/<int:id>/edit', methods=['POST'])
@login_required
@require_workspace
def update(id):
    conn = get_db()
    lead = get_lead(conn, id)
    if lead is None:
        abort(404)
    if lead['workspace_id'] != g.workspace['id']:
        abort(403)

    email = request.form.get('email', '').strip()[:200]
    contact_name = request.form.get('contact_name', '').strip()[:200]
    venue_name = request.form.get('venue_name', '').strip()[:200]
    location = request.form.get('location', '').strip()[:200]
    genre_tags = request.form.get('genre_tags', '').strip()[:200]
    phone = request.form.get('phone', '').strip()[:50]
    website = request.form.get('website', '').strip()[:500]
    notes = request.form.get('notes', '').strip()[:2000]

    try:
        capacity = int(request.form.get('capacity', '0') or '0')
    except (ValueError, TypeError):
        capacity = 0
    if capacity < 0:
        capacity = 0

    if not venue_name:
        flash('Venue name is required.', 'error')
        return redirect(url_for('lead_detail.edit', id=id))

    update_lead(
        conn, id,
        email=email,
        contact_name=contact_name,
        venue_name=venue_name,
        capacity=capacity,
        location=location,
        genre_tags=genre_tags,
        phone=phone,
        website=website,
        notes=notes,
    )
    log_activity(
        conn, g.workspace['id'], g.user['id'],
        'updated_lead', 'lead', id, f'Lead: {venue_name}'
    )
    conn.commit()
    flash('Lead updated successfully.', 'success')
    return redirect(url_for('lead_detail.detail', id=id))


@lead_detail_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@require_workspace
def delete(id):
    conn = get_db()
    lead = get_lead(conn, id)
    if lead is None:
        abort(404)
    if lead['workspace_id'] != g.workspace['id']:
        abort(403)

    venue_name = lead['venue_name']
    delete_lead(conn, id)
    log_activity(
        conn, g.workspace['id'], g.user['id'],
        'deleted_lead', 'lead', id, f'Lead: {venue_name}'
    )
    conn.commit()
    flash('Lead deleted.', 'success')
    return redirect(url_for('lead_list.index'))
