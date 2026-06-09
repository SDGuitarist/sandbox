"""Scene routes -- CRUD, element tagging, cast assignment, status transitions.

Blueprint: scenes (registered with url_prefix='/scenes' by the app factory).
Paths here are RELATIVE to that prefix (FC: do not duplicate the prefix).

Cross-boundary imports (per Cross-Boundary Wiring Table -- exact names/signatures):
  - location_models.get_locations            (form dropdown)
  - cast_models.add_cast_to_scene/remove_cast_from_scene/get_scene_cast
  - cast_models.get_cast_members             (assignment checkboxes)
  - search_models.index_entity               (FTS5 single-writer, in-txn)

Search index discipline (FC52/Negative Constraint 13): index_entity is called in the
SAME transaction as the source-row write. There is no scene-delete route in the Route
Table, so remove_entity is not called from here.
"""

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, g, abort
)

from app.database import get_db
from app.blueprints.auth.routes import (
    login_required, require_project_member, require_role
)
from app.models.scene_models import (
    VALID_SCENE_TRANSITIONS,
    create_scene, get_scenes, get_scene, transition_scene_status, update_scene,
    get_scene_elements, add_scene_element, remove_scene_element,
)
from app.models.location_models import get_locations
from app.models.cast_models import (
    add_cast_to_scene, remove_cast_from_scene, get_scene_cast, get_cast_members
)
from app.models.search_models import index_entity

bp = Blueprint('scenes', __name__)

# Allowed sets mirror the schema CHECK constraints exactly.
INT_EXT_VALUES = ('INT', 'EXT', 'INT/EXT')
DAY_NIGHT_VALUES = ('DAY', 'NIGHT', 'DAWN', 'DUSK')
ELEMENT_TYPES = ('prop', 'wardrobe', 'sfx', 'vehicle', 'animal', 'special_equipment')


def _scene_index_body(scene_number, description, int_ext, day_night, notes):
    """Build the FTS5 body text for a scene from its fields."""
    parts = [scene_number or '', description or '', int_ext or '',
             day_night or '', notes or '']
    return ' '.join(p for p in parts if p)


def _parse_location_id(raw):
    """Return (location_id, ok). Empty -> (None, True). Non-int -> (None, False)."""
    if raw is None or raw.strip() == '':
        return None, True
    try:
        return int(raw), True
    except (ValueError, TypeError):
        return None, False


def _validate_scene_fields(scene_number, int_ext, day_night, page_count_raw):
    """Shared create/edit field validation. Returns (page_count_eighths, error)."""
    if not scene_number:
        return None, 'Scene number is required'
    if int_ext not in INT_EXT_VALUES:
        return None, 'Invalid INT/EXT value'
    if day_night not in DAY_NIGHT_VALUES:
        return None, 'Invalid day/night value'
    try:
        page_count = int(page_count_raw)
    except (ValueError, TypeError):
        return None, 'Page count must be a whole number'
    if page_count <= 0:
        return None, 'Page count must be greater than zero'
    return page_count, None


@bp.route('/<int:project_id>')
@login_required
@require_project_member
def list(project_id):
    conn = get_db()
    return render_template('scenes/list.html',
                           project=g.project,
                           scenes=get_scenes(conn, project_id))


@bp.route('/<int:project_id>/new')
@login_required
@require_project_member
@require_role('producer', 'ad')
def new(project_id):
    conn = get_db()
    return render_template('scenes/new.html',
                           project=g.project,
                           locations=get_locations(conn, project_id),
                           int_ext_values=INT_EXT_VALUES,
                           day_night_values=DAY_NIGHT_VALUES)


@bp.route('/<int:project_id>', methods=['POST'])
@login_required
@require_project_member
@require_role('producer', 'ad')
def create(project_id):
    conn = get_db()
    scene_number = request.form.get('scene_number', '').strip()
    description = request.form.get('description', '').strip()
    int_ext = request.form.get('int_ext', '')
    day_night = request.form.get('day_night', '')
    page_count_raw = request.form.get('page_count_eighths', '')

    page_count, error = _validate_scene_fields(
        scene_number, int_ext, day_night, page_count_raw)
    if error:
        flash(error, 'error')
        return redirect(url_for('scenes.new', project_id=project_id))

    location_id, ok = _parse_location_id(request.form.get('location_id'))
    if not ok:
        flash('Invalid location', 'error')
        return redirect(url_for('scenes.new', project_id=project_id))
    if location_id is not None:
        loc = next((l for l in get_locations(conn, project_id)
                    if l['id'] == location_id), None)
        if loc is None:
            flash('Invalid location', 'error')
            return redirect(url_for('scenes.new', project_id=project_id))

    # create_scene commits internally; index_entity then runs in its own txn and
    # the route commits it (index_entity does NOT commit -- Transaction Contracts).
    try:
        scene_id = create_scene(conn, project_id, scene_number, description,
                                int_ext, day_night, page_count, location_id)
    except Exception:
        # UNIQUE(project_id, scene_number) or other integrity failure.
        flash('Scene number must be unique for this project', 'error')
        return redirect(url_for('scenes.new', project_id=project_id))

    try:
        conn.execute('BEGIN IMMEDIATE')
        index_entity(conn, 'scene', scene_id, scene_number,
                     _scene_index_body(scene_number, description, int_ext,
                                       day_night, None))
        conn.execute('COMMIT')
    except Exception:
        conn.execute('ROLLBACK')
        raise

    flash('Scene created', 'success')
    return redirect(url_for('scenes.detail', project_id=project_id,
                            scene_id=scene_id))


@bp.route('/<int:project_id>/<int:scene_id>')
@login_required
@require_project_member
def detail(project_id, scene_id):
    conn = get_db()
    scene = get_scene(conn, scene_id)
    if scene is None or scene['project_id'] != project_id:
        abort(404)
    return render_template('scenes/detail.html',
                           project=g.project,
                           scene=scene,
                           elements=get_scene_elements(conn, scene_id),
                           cast=get_scene_cast(conn, scene_id),
                           transitions=VALID_SCENE_TRANSITIONS.get(scene['status'], []))


@bp.route('/<int:project_id>/<int:scene_id>/edit')
@login_required
@require_project_member
@require_role('producer', 'ad')
def edit(project_id, scene_id):
    conn = get_db()
    scene = get_scene(conn, scene_id)
    if scene is None or scene['project_id'] != project_id:
        abort(404)
    assigned = {c['id'] for c in get_scene_cast(conn, scene_id)}
    return render_template('scenes/edit.html',
                           project=g.project,
                           scene=scene,
                           locations=get_locations(conn, project_id),
                           int_ext_values=INT_EXT_VALUES,
                           day_night_values=DAY_NIGHT_VALUES,
                           element_types=ELEMENT_TYPES,
                           elements=get_scene_elements(conn, scene_id),
                           all_cast=get_cast_members(conn, project_id),
                           assigned_cast_ids=assigned)


@bp.route('/<int:project_id>/<int:scene_id>/edit', methods=['POST'])
@login_required
@require_project_member
@require_role('producer', 'ad')
def update(project_id, scene_id):
    conn = get_db()
    scene = get_scene(conn, scene_id)
    if scene is None or scene['project_id'] != project_id:
        abort(404)

    scene_number = request.form.get('scene_number', '').strip()
    description = request.form.get('description', '').strip()
    int_ext = request.form.get('int_ext', '')
    day_night = request.form.get('day_night', '')
    page_count_raw = request.form.get('page_count_eighths', '')
    notes = request.form.get('notes', '').strip()

    page_count, error = _validate_scene_fields(
        scene_number, int_ext, day_night, page_count_raw)
    if error:
        flash(error, 'error')
        return redirect(url_for('scenes.edit', project_id=project_id,
                                scene_id=scene_id))

    location_id, ok = _parse_location_id(request.form.get('location_id'))
    if not ok:
        flash('Invalid location', 'error')
        return redirect(url_for('scenes.edit', project_id=project_id,
                                scene_id=scene_id))
    valid_location_ids = {l['id'] for l in get_locations(conn, project_id)}
    if location_id is not None and location_id not in valid_location_ids:
        flash('Invalid location', 'error')
        return redirect(url_for('scenes.edit', project_id=project_id,
                                scene_id=scene_id))

    # New element (optional). Validate before opening the transaction (fail closed).
    new_element_type = request.form.get('element_type', '').strip()
    new_element_desc = request.form.get('element_description', '').strip()
    if new_element_type or new_element_desc:
        if new_element_type not in ELEMENT_TYPES:
            flash('Invalid element type', 'error')
            return redirect(url_for('scenes.edit', project_id=project_id,
                                    scene_id=scene_id))
        if not new_element_desc:
            flash('Element description is required', 'error')
            return redirect(url_for('scenes.edit', project_id=project_id,
                                    scene_id=scene_id))

    # Cast assignment: checkbox set vs currently-assigned set.
    valid_cast_ids = {c['id'] for c in get_cast_members(conn, project_id)}
    selected_cast_ids = set()
    for raw in request.form.getlist('cast_ids'):
        try:
            cid = int(raw)
        except (ValueError, TypeError):
            flash('Invalid cast selection', 'error')
            return redirect(url_for('scenes.edit', project_id=project_id,
                                    scene_id=scene_id))
        if cid not in valid_cast_ids:
            flash('Invalid cast selection', 'error')
            return redirect(url_for('scenes.edit', project_id=project_id,
                                    scene_id=scene_id))
        selected_cast_ids.add(cid)

    # Element removal (optional).
    remove_element_ids = set()
    existing_element_ids = {e['id'] for e in get_scene_elements(conn, scene_id)}
    for raw in request.form.getlist('remove_element_ids'):
        try:
            eid = int(raw)
        except (ValueError, TypeError):
            flash('Invalid element selection', 'error')
            return redirect(url_for('scenes.edit', project_id=project_id,
                                    scene_id=scene_id))
        if eid not in existing_element_ids:
            abort(404)
        remove_element_ids.add(eid)

    currently_assigned = {c['id'] for c in get_scene_cast(conn, scene_id)}
    to_add = selected_cast_ids - currently_assigned
    to_remove = currently_assigned - selected_cast_ids

    # Compound write: update_scene + cast + elements + index_entity in ONE txn
    # (FC52: index in the same transaction as the source-row write).
    try:
        conn.execute('BEGIN IMMEDIATE')
        update_scene(conn, scene_id,
                     scene_number=scene_number, description=description,
                     int_ext=int_ext, day_night=day_night,
                     page_count_eighths=page_count, location_id=location_id,
                     notes=notes)
        for cid in to_add:
            add_cast_to_scene(conn, scene_id, cid)
        for cid in to_remove:
            remove_cast_from_scene(conn, scene_id, cid)
        for eid in remove_element_ids:
            remove_scene_element(conn, eid)
        if new_element_type and new_element_desc:
            add_scene_element(conn, scene_id, new_element_type, new_element_desc)
        index_entity(conn, 'scene', scene_id, scene_number,
                     _scene_index_body(scene_number, description, int_ext,
                                       day_night, notes))
        conn.execute('COMMIT')
    except Exception:
        conn.execute('ROLLBACK')
        flash('Scene number must be unique for this project', 'error')
        return redirect(url_for('scenes.edit', project_id=project_id,
                                scene_id=scene_id))

    flash('Scene updated', 'success')
    return redirect(url_for('scenes.detail', project_id=project_id,
                            scene_id=scene_id))


@bp.route('/<int:project_id>/<int:scene_id>/status', methods=['POST'])
@login_required
@require_project_member
@require_role('producer', 'ad')
def transition_status(project_id, scene_id):
    conn = get_db()
    scene = get_scene(conn, scene_id)
    if scene is None or scene['project_id'] != project_id:
        abort(404)

    new_status = request.form.get('new_status', '')
    # Route-level validation against the transition map (model re-checks in-lock).
    if new_status not in VALID_SCENE_TRANSITIONS.get(scene['status'], []):
        flash('Invalid transition', 'error')
        return redirect(url_for('scenes.detail', project_id=project_id,
                                scene_id=scene_id))

    if not transition_scene_status(conn, scene_id, new_status):
        flash('Invalid transition', 'error')
        return redirect(url_for('scenes.detail', project_id=project_id,
                                scene_id=scene_id))

    flash('Scene status updated', 'success')
    return redirect(url_for('scenes.detail', project_id=project_id,
                            scene_id=scene_id))
