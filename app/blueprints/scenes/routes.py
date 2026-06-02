"""Scenes blueprint — CRUD, element tagging, status transitions, cast assignment."""

import sqlite3
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, g
from markupsafe import escape, Markup

from app.blueprints.auth.routes import login_required, require_project_member, require_role
from app.database import get_db
from app.models.scene_models import (
    create_scene, get_scenes, get_scene, update_scene,
    transition_scene_status, get_scene_elements, add_scene_element,
    remove_scene_element, VALID_INT_EXT, VALID_DAY_NIGHT, VALID_TRANSITIONS,
    VALID_ELEMENT_TYPES,
)
from app.models.location_models import get_locations
from app.models.cast_models import add_cast_to_scene, remove_cast_from_scene, get_scene_cast
from app.models.search_models import index_entity, remove_entity

bp = Blueprint('scenes', __name__)


def _status_badge(status):
    """Return a Bootstrap badge for a scene status string."""
    colors = {
        'not_started': 'secondary',
        'in_prep': 'info',
        'ready': 'primary',
        'shooting': 'warning',
        'wrapped': 'success',
        'on_hold': 'danger',
    }
    color = colors.get(status, 'secondary')
    safe_status = escape(status.replace('_', ' ').title())
    return Markup(f'<span class="badge bg-{color}">{safe_status}</span>')


# ─── LIST ────────────────────────────────────────────────────────────────────

@bp.route('/<int:project_id>')
@login_required
@require_project_member
def list(project_id):
    conn = get_db()
    scenes = get_scenes(conn, project_id)
    return render_template('scenes/list.html',
                           project=g.project, scenes=scenes,
                           status_badge=_status_badge)


# ─── NEW ─────────────────────────────────────────────────────────────────────

@bp.route('/<int:project_id>/new')
@login_required
@require_project_member
@require_role('producer', 'ad')
def new(project_id):
    conn = get_db()
    locations = get_locations(conn, project_id)
    return render_template('scenes/new.html',
                           project=g.project, locations=locations)


# ─── CREATE ──────────────────────────────────────────────────────────────────

@bp.route('/<int:project_id>', methods=['POST'])
@login_required
@require_project_member
@require_role('producer', 'ad')
def create(project_id):
    scene_number = request.form.get('scene_number', '').strip()
    description = request.form.get('description', '').strip()
    int_ext = request.form.get('int_ext', '').strip()
    day_night = request.form.get('day_night', '').strip()
    page_count_raw = request.form.get('page_count_eighths', '').strip()
    location_id_raw = request.form.get('location_id', '').strip()

    # Validation
    if not scene_number:
        flash('Scene number is required', 'error')
        return redirect(url_for('scenes.new', project_id=project_id))

    if int_ext not in VALID_INT_EXT:
        flash('Invalid INT/EXT value', 'error')
        return redirect(url_for('scenes.new', project_id=project_id))

    if day_night not in VALID_DAY_NIGHT:
        flash('Invalid Day/Night value', 'error')
        return redirect(url_for('scenes.new', project_id=project_id))

    try:
        page_count_eighths = int(page_count_raw)
    except (ValueError, TypeError):
        flash('Page count must be a number', 'error')
        return redirect(url_for('scenes.new', project_id=project_id))

    if page_count_eighths <= 0:
        flash('Page count must be greater than 0', 'error')
        return redirect(url_for('scenes.new', project_id=project_id))

    location_id = None
    if location_id_raw:
        try:
            location_id = int(location_id_raw)
        except (ValueError, TypeError):
            flash('Invalid location', 'error')
            return redirect(url_for('scenes.new', project_id=project_id))

    conn = get_db()
    try:
        scene_id = create_scene(conn, project_id, scene_number, description,
                                int_ext, day_night, page_count_eighths, location_id)
    except sqlite3.IntegrityError:
        flash('Scene number already exists in this project', 'error')
        return redirect(url_for('scenes.new', project_id=project_id))

    # Index for search
    index_entity(conn, 'scene', scene_id,
                 f'Scene {scene_number}',
                 f'{description} {int_ext} {day_night}')

    flash('Scene created', 'success')
    return redirect(url_for('scenes.detail', project_id=project_id, scene_id=scene_id))


# ─── DETAIL ──────────────────────────────────────────────────────────────────

@bp.route('/<int:project_id>/<int:scene_id>')
@login_required
@require_project_member
def detail(project_id, scene_id):
    conn = get_db()
    scene = get_scene(conn, scene_id)
    if scene is None:
        abort(404)
    if scene['project_id'] != project_id:
        abort(404)

    elements = get_scene_elements(conn, scene_id)
    cast = get_scene_cast(conn, scene_id)
    transitions = VALID_TRANSITIONS.get(scene['status'], [])

    return render_template('scenes/detail.html',
                           project=g.project, scene=scene,
                           elements=elements, cast=cast,
                           transitions=transitions,
                           status_badge=_status_badge,
                           element_types=sorted(VALID_ELEMENT_TYPES))


# ─── EDIT (GET) ──────────────────────────────────────────────────────────────

@bp.route('/<int:project_id>/<int:scene_id>/edit')
@login_required
@require_project_member
@require_role('producer', 'ad')
def edit(project_id, scene_id):
    conn = get_db()
    scene = get_scene(conn, scene_id)
    if scene is None:
        abort(404)
    if scene['project_id'] != project_id:
        abort(404)

    locations = get_locations(conn, project_id)
    elements = get_scene_elements(conn, scene_id)
    cast = get_scene_cast(conn, scene_id)
    from app.models.cast_models import get_cast_members
    all_cast = get_cast_members(conn, project_id)

    return render_template('scenes/edit.html',
                           project=g.project, scene=scene,
                           locations=locations, elements=elements,
                           cast=cast, all_cast=all_cast,
                           element_types=sorted(VALID_ELEMENT_TYPES))


# ─── UPDATE (POST) ──────────────────────────────────────────────────────────

@bp.route('/<int:project_id>/<int:scene_id>/edit', methods=['POST'])
@login_required
@require_project_member
@require_role('producer', 'ad')
def update(project_id, scene_id):
    conn = get_db()
    scene = get_scene(conn, scene_id)
    if scene is None:
        abort(404)
    if scene['project_id'] != project_id:
        abort(404)

    scene_number = request.form.get('scene_number', '').strip()
    description = request.form.get('description', '').strip()
    int_ext = request.form.get('int_ext', '').strip()
    day_night = request.form.get('day_night', '').strip()
    page_count_raw = request.form.get('page_count_eighths', '').strip()
    location_id_raw = request.form.get('location_id', '').strip()
    notes = request.form.get('notes', '').strip()

    # Validation
    if not scene_number:
        flash('Scene number is required', 'error')
        return redirect(url_for('scenes.edit', project_id=project_id, scene_id=scene_id))

    if int_ext not in VALID_INT_EXT:
        flash('Invalid INT/EXT value', 'error')
        return redirect(url_for('scenes.edit', project_id=project_id, scene_id=scene_id))

    if day_night not in VALID_DAY_NIGHT:
        flash('Invalid Day/Night value', 'error')
        return redirect(url_for('scenes.edit', project_id=project_id, scene_id=scene_id))

    try:
        page_count_eighths = int(page_count_raw)
    except (ValueError, TypeError):
        flash('Page count must be a number', 'error')
        return redirect(url_for('scenes.edit', project_id=project_id, scene_id=scene_id))

    if page_count_eighths <= 0:
        flash('Page count must be greater than 0', 'error')
        return redirect(url_for('scenes.edit', project_id=project_id, scene_id=scene_id))

    location_id = None
    if location_id_raw:
        try:
            location_id = int(location_id_raw)
        except (ValueError, TypeError):
            flash('Invalid location', 'error')
            return redirect(url_for('scenes.edit', project_id=project_id, scene_id=scene_id))

    # Handle cast assignments
    cast_ids_raw = request.form.getlist('cast_ids')
    cast_ids = set()
    for cid in cast_ids_raw:
        try:
            cast_ids.add(int(cid))
        except (ValueError, TypeError):
            pass

    current_cast = get_scene_cast(conn, scene_id)
    current_cast_ids = {c['id'] for c in current_cast}

    to_add = cast_ids - current_cast_ids
    to_remove = current_cast_ids - cast_ids

    # Compound write: update_scene + cast changes + index_entity in one transaction
    conn.execute('BEGIN IMMEDIATE')
    try:
        update_scene(conn, scene_id,
                     scene_number=scene_number,
                     description=description,
                     int_ext=int_ext,
                     day_night=day_night,
                     page_count_eighths=page_count_eighths,
                     location_id=location_id,
                     notes=notes)

        for cid in to_add:
            add_cast_to_scene(conn, scene_id, cid)

        for cid in to_remove:
            remove_cast_from_scene(conn, scene_id, cid)

        index_entity(conn, 'scene', scene_id,
                     f'Scene {scene_number}',
                     f'{description} {int_ext} {day_night}')

        conn.execute('COMMIT')
    except sqlite3.IntegrityError:
        conn.execute('ROLLBACK')
        flash('Scene number already exists in this project', 'error')
        return redirect(url_for('scenes.edit', project_id=project_id, scene_id=scene_id))
    except Exception:
        conn.execute('ROLLBACK')
        raise

    flash('Scene updated', 'success')
    return redirect(url_for('scenes.detail', project_id=project_id, scene_id=scene_id))


# ─── ADD ELEMENT ─────────────────────────────────────────────────────────────

@bp.route('/<int:project_id>/<int:scene_id>/elements', methods=['POST'])
@login_required
@require_project_member
@require_role('producer', 'ad')
def add_element(project_id, scene_id):
    conn = get_db()
    scene = get_scene(conn, scene_id)
    if scene is None:
        abort(404)
    if scene['project_id'] != project_id:
        abort(404)

    element_type = request.form.get('element_type', '').strip()
    description = request.form.get('element_description', '').strip()

    if element_type not in VALID_ELEMENT_TYPES:
        flash('Invalid element type', 'error')
        return redirect(url_for('scenes.detail', project_id=project_id, scene_id=scene_id))

    if not description:
        flash('Element description is required', 'error')
        return redirect(url_for('scenes.detail', project_id=project_id, scene_id=scene_id))

    add_scene_element(conn, scene_id, element_type, description)
    flash('Element added', 'success')
    return redirect(url_for('scenes.detail', project_id=project_id, scene_id=scene_id))


# ─── REMOVE ELEMENT ──────────────────────────────────────────────────────────

@bp.route('/<int:project_id>/<int:scene_id>/elements/<int:element_id>/delete', methods=['POST'])
@login_required
@require_project_member
@require_role('producer', 'ad')
def remove_element(project_id, scene_id, element_id):
    conn = get_db()
    scene = get_scene(conn, scene_id)
    if scene is None:
        abort(404)
    if scene['project_id'] != project_id:
        abort(404)

    # Verify element belongs to this scene
    elem = conn.execute(
        'SELECT id FROM scene_elements WHERE id = ? AND scene_id = ?',
        (element_id, scene_id)
    ).fetchone()
    if elem is None:
        abort(404)

    remove_scene_element(conn, element_id)
    flash('Element removed', 'success')
    return redirect(url_for('scenes.detail', project_id=project_id, scene_id=scene_id))


# ─── STATUS TRANSITION ──────────────────────────────────────────────────────

@bp.route('/<int:project_id>/<int:scene_id>/status', methods=['POST'])
@login_required
@require_project_member
@require_role('producer', 'ad')
def transition_status(project_id, scene_id):
    conn = get_db()
    scene = get_scene(conn, scene_id)
    if scene is None:
        abort(404)
    if scene['project_id'] != project_id:
        abort(404)

    new_status = request.form.get('new_status', '').strip()
    success = transition_scene_status(conn, scene_id, new_status)
    if not success:
        flash('Invalid status transition', 'error')
    else:
        flash(f'Scene status changed to {new_status.replace("_", " ").title()}', 'success')

    return redirect(url_for('scenes.detail', project_id=project_id, scene_id=scene_id))
