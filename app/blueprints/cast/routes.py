"""Cast blueprint routes.

url_prefix '/cast' is set in create_app(); paths here are RELATIVE to it.

Authorization (per Authorization Matrix):
- list / detail : login_required + require_project_member
- new / create / update : + require_role('producer', 'ad')

IDOR (FC35): every detail/edit route re-checks resource.project_id == project_id
and aborts 404 (not 403) on mismatch to avoid info leak.
"""

import sqlite3

from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, abort, g,
)

from app.database import get_db
from app.blueprints.auth.routes import (
    login_required, require_project_member, require_role,
)
from app.models.cast_models import (
    create_cast_member, update_cast_member,
    get_cast_members, get_cast_member,
)
from app.models.search_models import index_entity, remove_entity

bp = Blueprint('cast', __name__)


def _parse_cast_form():
    """Validate the cast create/edit form.

    Returns (name, character_name, cast_id_number, error_message).
    On success error_message is None.
    """
    name = (request.form.get('name') or '').strip()
    character_name = (request.form.get('character_name') or '').strip()
    cast_id_raw = (request.form.get('cast_id_number') or '').strip()

    if not name:
        return None, None, None, 'Name is required'
    if not character_name:
        return None, None, None, 'Character name is required'
    try:
        cast_id_number = int(cast_id_raw)
    except (ValueError, TypeError):
        return None, None, None, 'Cast ID number must be a whole number'
    if not (1 <= cast_id_number <= 99):
        return None, None, None, 'Cast ID number must be between 1 and 99'

    return name, character_name, cast_id_number, None


@bp.route('/<int:project_id>')
@login_required
@require_project_member
def list(project_id):
    conn = get_db()
    cast = get_cast_members(conn, project_id)
    return render_template('cast/list.html', project=g.project, cast=cast)


@bp.route('/<int:project_id>/new')
@login_required
@require_project_member
@require_role('producer', 'ad')
def new(project_id):
    return render_template('cast/new.html', project=g.project)


@bp.route('/<int:project_id>', methods=['POST'])
@login_required
@require_project_member
@require_role('producer', 'ad')
def create(project_id):
    conn = get_db()
    name, character_name, cast_id_number, error = _parse_cast_form()
    if error:
        flash(error, 'error')
        return redirect(url_for('cast.new', project_id=project_id))

    try:
        cast_member_id = create_cast_member(
            conn, project_id, name, character_name, cast_id_number
        )
    except sqlite3.IntegrityError:
        flash(f'Cast ID number {cast_id_number} is already in use', 'error')
        return redirect(url_for('cast.new', project_id=project_id))

    # Keep the search index in sync (index_entity does NOT commit; we commit).
    try:
        index_entity(conn, 'cast', cast_member_id, name, character_name)
        conn.commit()
    except Exception:
        conn.rollback()

    flash('Cast member added', 'success')
    return redirect(url_for('cast.detail', project_id=project_id, cast_member_id=cast_member_id))


@bp.route('/<int:project_id>/<int:cast_member_id>')
@login_required
@require_project_member
def detail(project_id, cast_member_id):
    conn = get_db()
    member = get_cast_member(conn, cast_member_id)
    if member is None:
        abort(404)
    if member['project_id'] != project_id:
        abort(404)
    return render_template('cast/detail.html', project=g.project, member=member)


@bp.route('/<int:project_id>/<int:cast_member_id>/edit', methods=['POST'])
@login_required
@require_project_member
@require_role('producer', 'ad')
def update(project_id, cast_member_id):
    conn = get_db()
    member = get_cast_member(conn, cast_member_id)
    if member is None:
        abort(404)
    if member['project_id'] != project_id:
        abort(404)

    name, character_name, cast_id_number, error = _parse_cast_form()
    if error:
        flash(error, 'error')
        return redirect(url_for('cast.detail', project_id=project_id, cast_member_id=cast_member_id))

    try:
        update_cast_member(conn, cast_member_id, name, character_name, cast_id_number)
    except sqlite3.IntegrityError:
        flash(f'Cast ID number {cast_id_number} is already in use', 'error')
        return redirect(url_for('cast.detail', project_id=project_id, cast_member_id=cast_member_id))

    # Refresh the search index entry.
    try:
        remove_entity(conn, 'cast', cast_member_id)
        index_entity(conn, 'cast', cast_member_id, name, character_name)
        conn.commit()
    except Exception:
        conn.rollback()

    flash('Cast member updated', 'success')
    return redirect(url_for('cast.detail', project_id=project_id, cast_member_id=cast_member_id))
