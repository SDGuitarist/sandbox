"""Cast blueprint routes.

url_prefix=/cast (registered by scaffold agent in app factory).
Owns: cast list, cast new, cast detail, cast update.
Cross-boundary: calls index_entity from search_models on create.
IDOR: verify cast.project_id == project_id on detail/update.
"""
import sqlite3

from flask import Blueprint, render_template, request, redirect, url_for, flash, g, abort

from app.database import get_db
from app.blueprints.auth.routes import login_required, require_project_member, require_role
from app.models.cast_models import (
    create_cast_member,
    get_cast_members,
    get_cast_member,
)
from app.models.search_models import index_entity

bp = Blueprint('cast', __name__)


@bp.route('/<int:project_id>')
@login_required
@require_project_member
def list(project_id):
    """GET /cast/<project_id> -- list all cast members."""
    conn = get_db()
    members = get_cast_members(conn, project_id)
    return render_template('cast/list.html', project=g.project, members=members)


@bp.route('/<int:project_id>/new')
@login_required
@require_project_member
@require_role('producer', 'ad')
def new(project_id):
    """GET /cast/<project_id>/new -- show form to add a cast member."""
    return render_template('cast/new.html', project=g.project)


@bp.route('/<int:project_id>', methods=['POST'])
@login_required
@require_project_member
@require_role('producer', 'ad')
def create(project_id):
    """POST /cast/<project_id> -- create a new cast member."""
    conn = get_db()

    name = request.form.get('name', '').strip()
    character_name = request.form.get('character_name', '').strip()
    cast_id_number_raw = request.form.get('cast_id_number', '').strip()

    # Validation: name required
    if not name:
        flash('Name is required', 'error')
        return redirect(url_for('cast.new', project_id=project_id))

    # Validation: character_name required
    if not character_name:
        flash('Character name is required', 'error')
        return redirect(url_for('cast.new', project_id=project_id))

    # Validation: cast_id_number must be integer 1-99
    try:
        cast_id_number = int(cast_id_number_raw)
    except (ValueError, TypeError):
        flash('Cast ID must be a number between 1 and 99', 'error')
        return redirect(url_for('cast.new', project_id=project_id))

    if cast_id_number < 1 or cast_id_number > 99:
        flash('Cast ID must be between 1 and 99', 'error')
        return redirect(url_for('cast.new', project_id=project_id))

    # Attempt create -- IntegrityError means duplicate cast_id_number
    try:
        cast_member_id = create_cast_member(conn, project_id, name, character_name, cast_id_number)
    except sqlite3.IntegrityError:
        flash('Cast ID number is already in use for this project', 'error')
        return redirect(url_for('cast.new', project_id=project_id))

    # Index for search
    index_entity(conn, 'cast_member', cast_member_id, name, character_name)

    flash('Cast member added', 'success')
    return redirect(url_for('cast.detail', project_id=project_id, cast_member_id=cast_member_id))


@bp.route('/<int:project_id>/<int:cast_member_id>')
@login_required
@require_project_member
def detail(project_id, cast_member_id):
    """GET /cast/<project_id>/<cast_member_id> -- show cast member details."""
    conn = get_db()
    member = get_cast_member(conn, cast_member_id)

    # IDOR check: resource must exist and belong to this project
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
    """POST /cast/<project_id>/<cast_member_id>/edit -- update a cast member."""
    conn = get_db()
    member = get_cast_member(conn, cast_member_id)

    # IDOR check
    if member is None:
        abort(404)
    if member['project_id'] != project_id:
        abort(404)

    name = request.form.get('name', '').strip()
    character_name = request.form.get('character_name', '').strip()
    cast_id_number_raw = request.form.get('cast_id_number', '').strip()
    agent_name = request.form.get('agent_name', '').strip() or None
    agent_phone = request.form.get('agent_phone', '').strip() or None
    agent_email = request.form.get('agent_email', '').strip() or None
    notes = request.form.get('notes', '').strip() or None

    # Validation: name required
    if not name:
        flash('Name is required', 'error')
        return redirect(url_for('cast.detail', project_id=project_id, cast_member_id=cast_member_id))

    # Validation: character_name required
    if not character_name:
        flash('Character name is required', 'error')
        return redirect(url_for('cast.detail', project_id=project_id, cast_member_id=cast_member_id))

    # Validation: cast_id_number must be integer 1-99
    try:
        cast_id_number = int(cast_id_number_raw)
    except (ValueError, TypeError):
        flash('Cast ID must be a number between 1 and 99', 'error')
        return redirect(url_for('cast.detail', project_id=project_id, cast_member_id=cast_member_id))

    if cast_id_number < 1 or cast_id_number > 99:
        flash('Cast ID must be between 1 and 99', 'error')
        return redirect(url_for('cast.detail', project_id=project_id, cast_member_id=cast_member_id))

    # Update within a transaction
    try:
        conn.execute('BEGIN IMMEDIATE')
        conn.execute(
            '''UPDATE cast_members
               SET name = ?, character_name = ?, cast_id_number = ?,
                   agent_name = ?, agent_phone = ?, agent_email = ?, notes = ?
               WHERE id = ?''',
            (name, character_name, cast_id_number, agent_name, agent_phone, agent_email, notes, cast_member_id)
        )
        # Re-index for search
        index_entity(conn, 'cast_member', cast_member_id, name, character_name)
        conn.execute('COMMIT')
    except sqlite3.IntegrityError:
        conn.execute('ROLLBACK')
        flash('Cast ID number is already in use for this project', 'error')
        return redirect(url_for('cast.detail', project_id=project_id, cast_member_id=cast_member_id))
    except Exception:
        conn.execute('ROLLBACK')
        raise

    flash('Cast member updated', 'success')
    return redirect(url_for('cast.detail', project_id=project_id, cast_member_id=cast_member_id))
