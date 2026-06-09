"""Location routes (blueprint: locations, url_prefix=/locations).

Auth: all routes require login + project membership. Create/edit require
producer or ad role. IDOR-protected on detail/edit (loc.project_id == pid).
"""

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, g, abort,
)

from app.database import get_db
from app.blueprints.auth.routes import (
    login_required, require_project_member, require_role,
)
from app.models.location_models import (
    create_location, get_locations, get_location,
)
from app.models.search_models import index_entity

bp = Blueprint('locations', __name__)

VALID_PERMIT_STATUSES = ('pending', 'approved', 'denied')


@bp.route('/<int:project_id>')
@login_required
@require_project_member
def list(project_id):
    conn = get_db()
    locations = get_locations(conn, project_id)
    return render_template('locations/list.html',
                           project=g.project, locations=locations)


@bp.route('/<int:project_id>/new')
@login_required
@require_project_member
@require_role('producer', 'ad')
def new(project_id):
    return render_template('locations/new.html', project=g.project)


@bp.route('/<int:project_id>', methods=['POST'])
@login_required
@require_project_member
@require_role('producer', 'ad')
def create(project_id):
    conn = get_db()

    name = (request.form.get('name') or '').strip()
    if not name or len(name) > 200:
        flash('Name is required', 'error')
        return redirect(url_for('locations.new', project_id=project_id))

    address = (request.form.get('address') or '').strip() or None
    contact_name = (request.form.get('contact_name') or '').strip() or None
    contact_phone = (request.form.get('contact_phone') or '').strip() or None
    nearest_hospital = (request.form.get('nearest_hospital') or '').strip() or None

    location_id = create_location(
        conn, project_id, name,
        address=address, contact_name=contact_name,
        contact_phone=contact_phone, nearest_hospital=nearest_hospital,
    )

    index_entity(conn, 'location', location_id, name, address or '')

    flash('Location added', 'success')
    return redirect(url_for('locations.detail',
                            project_id=project_id, location_id=location_id))


@bp.route('/<int:project_id>/<int:location_id>')
@login_required
@require_project_member
def detail(project_id, location_id):
    conn = get_db()
    location = get_location(conn, location_id)
    if location is None:
        abort(404)
    if location['project_id'] != project_id:
        abort(404)
    return render_template('locations/detail.html',
                           project=g.project, location=location)


@bp.route('/<int:project_id>/<int:location_id>/edit', methods=['POST'])
@login_required
@require_project_member
@require_role('producer', 'ad')
def update(project_id, location_id):
    conn = get_db()

    location = get_location(conn, location_id)
    if location is None:
        abort(404)
    if location['project_id'] != project_id:
        abort(404)

    name = (request.form.get('name') or '').strip()
    if not name or len(name) > 200:
        flash('Name is required', 'error')
        return redirect(url_for('locations.detail',
                                project_id=project_id, location_id=location_id))

    permit_status = (request.form.get('permit_status') or '').strip()
    if permit_status and permit_status not in VALID_PERMIT_STATUSES:
        flash('Invalid permit status', 'error')
        return redirect(url_for('locations.detail',
                                project_id=project_id, location_id=location_id))
    if not permit_status:
        permit_status = location['permit_status']

    address = (request.form.get('address') or '').strip() or None
    contact_name = (request.form.get('contact_name') or '').strip() or None
    contact_phone = (request.form.get('contact_phone') or '').strip() or None
    nearest_hospital = (request.form.get('nearest_hospital') or '').strip() or None
    notes = (request.form.get('notes') or '').strip() or None

    # get_db() connections use autocommit=True; this UPDATE commits immediately.
    conn.execute(
        '''UPDATE locations
           SET name = ?, address = ?, contact_name = ?, contact_phone = ?,
               permit_status = ?, nearest_hospital = ?, notes = ?
           WHERE id = ?''',
        (name, address, contact_name, contact_phone,
         permit_status, nearest_hospital, notes, location_id),
    )

    index_entity(conn, 'location', location_id, name, address or '')

    flash('Location updated', 'success')
    return redirect(url_for('locations.detail',
                            project_id=project_id, location_id=location_id))
