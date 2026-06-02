"""Location routes for the Film Production PM tool."""

from flask import Blueprint, render_template, request, redirect, url_for, flash, g, abort
from app.database import get_db
from app.blueprints.auth.routes import login_required, require_project_member, require_role
from app.models.location_models import create_location, get_locations, get_location
from app.models.search_models import index_entity

bp = Blueprint('locations', __name__)


@bp.route('/<int:project_id>')
@login_required
@require_project_member
def list(project_id):
    """List all locations for a project."""
    conn = get_db()
    locations = get_locations(conn, project_id)
    return render_template('locations/list.html',
                           project=g.project, locations=locations)


@bp.route('/<int:project_id>/new')
@login_required
@require_project_member
@require_role('producer', 'ad')
def new(project_id):
    """Show form to create a new location."""
    return render_template('locations/new.html', project=g.project)


@bp.route('/<int:project_id>', methods=['POST'])
@login_required
@require_project_member
@require_role('producer', 'ad')
def create(project_id):
    """Create a new location."""
    conn = get_db()

    name = request.form.get('name', '').strip()
    if not name or len(name) > 200:
        flash('Name is required', 'error')
        return redirect(url_for('locations.new', project_id=project_id))

    address = request.form.get('address', '').strip() or None
    contact_name = request.form.get('contact_name', '').strip() or None
    contact_phone = request.form.get('contact_phone', '').strip() or None
    nearest_hospital = request.form.get('nearest_hospital', '').strip() or None

    location_id = create_location(conn, project_id, name, address=address,
                                  contact_name=contact_name,
                                  contact_phone=contact_phone,
                                  nearest_hospital=nearest_hospital)

    # Index for search
    index_entity(conn, 'location', location_id, name,
                 ' '.join(filter(None, [address, contact_name])))

    flash('Location added', 'success')
    return redirect(url_for('locations.detail', project_id=project_id,
                            location_id=location_id))


@bp.route('/<int:project_id>/<int:location_id>')
@login_required
@require_project_member
def detail(project_id, location_id):
    """Show location detail."""
    conn = get_db()
    loc = get_location(conn, location_id)
    if loc is None:
        abort(404)
    if loc['project_id'] != project_id:
        abort(404)
    return render_template('locations/detail.html',
                           project=g.project, location=loc)


@bp.route('/<int:project_id>/<int:location_id>/edit', methods=['POST'])
@login_required
@require_project_member
@require_role('producer', 'ad')
def update(project_id, location_id):
    """Update an existing location."""
    conn = get_db()

    loc = get_location(conn, location_id)
    if loc is None:
        abort(404)
    if loc['project_id'] != project_id:
        abort(404)

    name = request.form.get('name', '').strip()
    if not name or len(name) > 200:
        flash('Name is required', 'error')
        return redirect(url_for('locations.detail', project_id=project_id,
                                location_id=location_id))

    address = request.form.get('address', '').strip() or None
    contact_name = request.form.get('contact_name', '').strip() or None
    contact_phone = request.form.get('contact_phone', '').strip() or None
    nearest_hospital = request.form.get('nearest_hospital', '').strip() or None
    permit_status = request.form.get('permit_status', '').strip()
    notes = request.form.get('notes', '').strip() or None

    # Validate permit_status
    valid_statuses = ('pending', 'approved', 'denied')
    if permit_status not in valid_statuses:
        permit_status = loc['permit_status']

    try:
        conn.execute('BEGIN IMMEDIATE')
        conn.execute(
            '''UPDATE locations
               SET name = ?, address = ?, contact_name = ?, contact_phone = ?,
                   nearest_hospital = ?, permit_status = ?, notes = ?
               WHERE id = ?''',
            (name, address, contact_name, contact_phone,
             nearest_hospital, permit_status, notes, location_id)
        )
        # Re-index for search
        index_entity(conn, 'location', location_id, name,
                     ' '.join(filter(None, [address, contact_name])))
        conn.execute('COMMIT')
    except Exception:
        conn.execute('ROLLBACK')
        raise

    flash('Location updated', 'success')
    return redirect(url_for('locations.detail', project_id=project_id,
                            location_id=location_id))
