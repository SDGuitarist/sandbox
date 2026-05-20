from flask import Blueprint, render_template, request, redirect, url_for, flash, g, abort

from app.db import get_db
from app.models import create_template, get_template, update_template, delete_template, log_activity
from app.decorators import login_required, require_workspace
from app import MERGE_FIELDS

template_editor_bp = Blueprint('template_editor', __name__)


@template_editor_bp.route('/new')
@login_required
@require_workspace
def new():
    return render_template('template_editor/form.html',
                           template=None,
                           is_edit=False,
                           merge_fields=MERGE_FIELDS)


@template_editor_bp.route('/new', methods=['POST'])
@login_required
@require_workspace
def create():
    name = request.form.get('name', '').strip()
    subject_line = request.form.get('subject_line', '').strip()
    html_body = request.form.get('html_body', '').strip()

    if not name:
        flash('Name is required.', 'error')
        return render_template('template_editor/form.html',
                               template={'name': name, 'subject_line': subject_line, 'html_body': html_body},
                               is_edit=False,
                               merge_fields=MERGE_FIELDS)

    if not subject_line:
        flash('Subject line is required.', 'error')
        return render_template('template_editor/form.html',
                               template={'name': name, 'subject_line': subject_line, 'html_body': html_body},
                               is_edit=False,
                               merge_fields=MERGE_FIELDS)

    conn = get_db()
    template_id = create_template(conn, g.workspace['id'], name, subject_line,
                                  html_body, g.user['id'])
    log_activity(conn, g.workspace['id'], g.user['id'],
                 'created_template', 'template', template_id, f'Template: {name}')
    conn.commit()
    flash('Template created successfully.', 'success')
    return redirect(url_for('template_editor.detail', id=template_id))


@template_editor_bp.route('/<int:id>')
@login_required
@require_workspace
def detail(id):
    conn = get_db()
    template = get_template(conn, id)
    if template is None:
        abort(404)
    if template['workspace_id'] != g.workspace['id']:
        abort(403)
    return render_template('template_editor/detail.html',
                           template=template,
                           merge_fields=MERGE_FIELDS)


@template_editor_bp.route('/<int:id>/edit')
@login_required
@require_workspace
def edit(id):
    conn = get_db()
    template = get_template(conn, id)
    if template is None:
        abort(404)
    if template['workspace_id'] != g.workspace['id']:
        abort(403)
    return render_template('template_editor/form.html',
                           template=template,
                           is_edit=True,
                           merge_fields=MERGE_FIELDS)


@template_editor_bp.route('/<int:id>/edit', methods=['POST'])
@login_required
@require_workspace
def update(id):
    conn = get_db()
    template = get_template(conn, id)
    if template is None:
        abort(404)
    if template['workspace_id'] != g.workspace['id']:
        abort(403)

    name = request.form.get('name', '').strip()
    subject_line = request.form.get('subject_line', '').strip()
    html_body = request.form.get('html_body', '').strip()

    if not name:
        flash('Name is required.', 'error')
        return render_template('template_editor/form.html',
                               template={'id': id, 'name': name, 'subject_line': subject_line, 'html_body': html_body},
                               is_edit=True,
                               merge_fields=MERGE_FIELDS)

    if not subject_line:
        flash('Subject line is required.', 'error')
        return render_template('template_editor/form.html',
                               template={'id': id, 'name': name, 'subject_line': subject_line, 'html_body': html_body},
                               is_edit=True,
                               merge_fields=MERGE_FIELDS)

    update_template(conn, id, name, subject_line, html_body)
    log_activity(conn, g.workspace['id'], g.user['id'],
                 'updated_template', 'template', id, f'Template: {name}')
    conn.commit()
    flash('Template updated successfully.', 'success')
    return redirect(url_for('template_editor.detail', id=id))


@template_editor_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@require_workspace
def delete(id):
    conn = get_db()
    template = get_template(conn, id)
    if template is None:
        abort(404)
    if template['workspace_id'] != g.workspace['id']:
        abort(403)

    template_name = template['name']
    delete_template(conn, id)
    log_activity(conn, g.workspace['id'], g.user['id'],
                 'deleted_template', 'template', id, f'Template: {template_name}')
    conn.commit()
    flash('Template deleted.', 'success')
    return redirect(url_for('template_list.index'))
