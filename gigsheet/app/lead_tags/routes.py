from flask import Blueprint, render_template, request, redirect, url_for, flash, g, abort
from app.db import get_db
from app.models import (
    create_tag, get_tags_by_workspace, assign_tag, remove_tag,
    delete_tag, get_lead, log_activity,
)
from app.decorators import login_required, require_workspace

lead_tags_bp = Blueprint('lead_tags', __name__)


@lead_tags_bp.route('/')
@login_required
@require_workspace
def index():
    conn = get_db()
    tags = get_tags_by_workspace(conn, g.workspace['id'])
    return render_template('lead_tags/index.html', tags=tags)


@lead_tags_bp.route('/', methods=['POST'])
@login_required
@require_workspace
def create():
    name = request.form.get('name', '').strip()[:100]
    color = request.form.get('color', '#6c757d').strip()[:20]

    if not name:
        flash('Name is required.', 'error')
        return redirect(url_for('lead_tags.index'))

    conn = get_db()
    tag_id = create_tag(conn, g.workspace['id'], name, color)
    log_activity(conn, g.workspace['id'], g.user['id'],
                 'created_tag', 'tag', tag_id, f'Tag: {name}')
    conn.commit()

    flash('Tag created successfully.', 'success')
    return redirect(url_for('lead_tags.index'))


@lead_tags_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@require_workspace
def delete(id):
    conn = get_db()

    # FC35: fetch tag and verify workspace ownership
    tag = conn.execute(
        'SELECT * FROM tags WHERE id = ?', (id,)
    ).fetchone()
    if tag is None:
        abort(404)
    if tag['workspace_id'] != g.workspace['id']:
        abort(403)

    delete_tag(conn, id)
    log_activity(conn, g.workspace['id'], g.user['id'],
                 'deleted_tag', 'tag', id, f'Tag: {tag["name"]}')
    conn.commit()

    flash('Tag deleted.', 'success')
    return redirect(url_for('lead_tags.index'))


@lead_tags_bp.route('/assign', methods=['POST'])
@login_required
@require_workspace
def assign():
    lead_id = request.form.get('lead_id', type=int)
    tag_id = request.form.get('tag_id', type=int)

    if not lead_id or not tag_id:
        flash('Lead and tag are required.', 'error')
        return redirect(request.referrer or url_for('lead_tags.index'))

    conn = get_db()

    # FC35: verify lead belongs to current workspace
    lead = get_lead(conn, lead_id)
    if lead is None:
        abort(404)
    if lead['workspace_id'] != g.workspace['id']:
        abort(403)

    # Verify tag belongs to current workspace
    tag = conn.execute(
        'SELECT * FROM tags WHERE id = ?', (tag_id,)
    ).fetchone()
    if tag is None:
        abort(404)
    if tag['workspace_id'] != g.workspace['id']:
        abort(403)

    assign_tag(conn, lead_id, tag_id)
    log_activity(conn, g.workspace['id'], g.user['id'],
                 'assigned_tag', 'tag', tag_id,
                 f'Tag "{tag["name"]}" assigned to lead {lead["venue_name"]}')
    conn.commit()

    flash('Tag assigned.', 'success')
    return redirect(request.referrer or url_for('lead_tags.index'))


@lead_tags_bp.route('/remove', methods=['POST'])
@login_required
@require_workspace
def remove():
    lead_id = request.form.get('lead_id', type=int)
    tag_id = request.form.get('tag_id', type=int)

    if not lead_id or not tag_id:
        flash('Lead and tag are required.', 'error')
        return redirect(request.referrer or url_for('lead_tags.index'))

    conn = get_db()

    # FC35: verify lead belongs to current workspace
    lead = get_lead(conn, lead_id)
    if lead is None:
        abort(404)
    if lead['workspace_id'] != g.workspace['id']:
        abort(403)

    # Verify tag belongs to current workspace
    tag = conn.execute(
        'SELECT * FROM tags WHERE id = ?', (tag_id,)
    ).fetchone()
    if tag is None:
        abort(404)
    if tag['workspace_id'] != g.workspace['id']:
        abort(403)

    remove_tag(conn, lead_id, tag_id)
    log_activity(conn, g.workspace['id'], g.user['id'],
                 'removed_tag', 'tag', tag_id,
                 f'Tag "{tag["name"]}" removed from lead {lead["venue_name"]}')
    conn.commit()

    flash('Tag removed.', 'success')
    return redirect(request.referrer or url_for('lead_tags.index'))
