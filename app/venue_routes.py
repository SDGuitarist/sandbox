import sqlite3

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from app import get_db, login_required
from app.venue_models import (
    create_venue,
    delete_venue,
    get_venue,
    list_venues,
    update_venue,
    venue_name_exists,
)
from app.gig_models import count_gigs_by_venue, list_gigs_by_venue
from app.outcome_models import avg_energy_by_venue

venues_bp = Blueprint('venues', __name__, url_prefix='/venues')

VENUE_TYPES = ('hotel', 'restaurant', 'private', 'corporate', 'festival', 'other')


def _parse_capacity(raw):
    """Parse capacity_estimate: empty -> None; non-empty -> int>=0.

    Returns (value, error_message). On success error_message is None; on
    failure value is None and error_message is the flash string.
    """
    raw = (raw or '').strip()
    if raw == '':
        return None, None
    try:
        value = int(raw)
    except ValueError:
        return None, 'Capacity must be a non-negative number'
    if value < 0:
        return None, 'Capacity must be a non-negative number'
    return value, None


@venues_bp.route('/')
@login_required
def list():
    conn = get_db()
    venues = list_venues(conn)
    return render_template('venues/list.html', venues=venues)


@venues_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    conn = get_db()
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        location = (request.form.get('location') or '').strip() or None
        venue_type = (request.form.get('venue_type') or '').strip() or None
        capacity_raw = request.form.get('capacity_estimate')
        vibe_notes = (request.form.get('vibe_notes') or '').strip() or None
        notes = (request.form.get('notes') or '').strip() or None

        form = {
            'id': None,
            'name': name,
            'location': location or '',
            'venue_type': venue_type or '',
            'capacity_estimate': (capacity_raw or '').strip(),
            'vibe_notes': vibe_notes or '',
            'notes': notes or '',
        }

        if not name:
            flash('Venue name is required', 'error')
            return render_template('venues/form.html', venue=form, venue_types=VENUE_TYPES, action=url_for('venues.new'))
        if venue_name_exists(conn, name):
            flash('Venue already exists', 'error')
            return render_template('venues/form.html', venue=form, venue_types=VENUE_TYPES, action=url_for('venues.new'))
        if venue_type is not None and venue_type not in VENUE_TYPES:
            flash('Invalid venue type', 'error')
            return render_template('venues/form.html', venue=form, venue_types=VENUE_TYPES, action=url_for('venues.new'))
        capacity, cap_err = _parse_capacity(capacity_raw)
        if cap_err:
            flash(cap_err, 'error')
            return render_template('venues/form.html', venue=form, venue_types=VENUE_TYPES, action=url_for('venues.new'))

        try:
            venue_id = create_venue(conn, name, location, venue_type, capacity, vibe_notes, notes)
        except sqlite3.IntegrityError:
            flash('Venue already exists', 'error')
            return render_template('venues/form.html', venue=form, venue_types=VENUE_TYPES, action=url_for('venues.new'))
        return redirect(url_for('venues.detail', id=venue_id))

    return render_template('venues/form.html', venue=None, venue_types=VENUE_TYPES, action=url_for('venues.new'))


@venues_bp.route('/<id>')
@login_required
def detail(id):
    conn = get_db()
    venue = get_venue(conn, id)
    if venue is None:
        flash('Venue not found', 'error')
        return redirect(url_for('venues.list'))
    gig_count = count_gigs_by_venue(conn, id)
    gigs = list_gigs_by_venue(conn, id)
    avg_energy = avg_energy_by_venue(conn, id)
    return render_template(
        'venues/detail.html',
        venue=venue,
        gig_count=gig_count,
        gigs=gigs,
        avg_energy=avg_energy,
    )


@venues_bp.route('/<id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    conn = get_db()
    venue = get_venue(conn, id)
    if venue is None:
        flash('Venue not found', 'error')
        return redirect(url_for('venues.list'))

    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        location = (request.form.get('location') or '').strip() or None
        venue_type = (request.form.get('venue_type') or '').strip() or None
        capacity_raw = request.form.get('capacity_estimate')
        vibe_notes = (request.form.get('vibe_notes') or '').strip() or None
        notes = (request.form.get('notes') or '').strip() or None

        form = {
            'id': id,
            'name': name,
            'location': location or '',
            'venue_type': venue_type or '',
            'capacity_estimate': (capacity_raw or '').strip(),
            'vibe_notes': vibe_notes or '',
            'notes': notes or '',
        }

        if not name:
            flash('Venue name is required', 'error')
            return render_template('venues/form.html', venue=form, venue_types=VENUE_TYPES, action=url_for('venues.edit', id=id))
        if venue_name_exists(conn, name, exclude_id=id):
            flash('Venue already exists', 'error')
            return render_template('venues/form.html', venue=form, venue_types=VENUE_TYPES, action=url_for('venues.edit', id=id))
        if venue_type is not None and venue_type not in VENUE_TYPES:
            flash('Invalid venue type', 'error')
            return render_template('venues/form.html', venue=form, venue_types=VENUE_TYPES, action=url_for('venues.edit', id=id))
        capacity, cap_err = _parse_capacity(capacity_raw)
        if cap_err:
            flash(cap_err, 'error')
            return render_template('venues/form.html', venue=form, venue_types=VENUE_TYPES, action=url_for('venues.edit', id=id))

        try:
            update_venue(conn, id, name, location, venue_type, capacity, vibe_notes, notes)
        except sqlite3.IntegrityError:
            flash('Venue already exists', 'error')
            return render_template('venues/form.html', venue=form, venue_types=VENUE_TYPES, action=url_for('venues.edit', id=id))
        return redirect(url_for('venues.detail', id=id))

    return render_template('venues/form.html', venue=venue, venue_types=VENUE_TYPES, action=url_for('venues.edit', id=id))


@venues_bp.route('/<id>/delete', methods=['POST'])
@login_required
def delete(id):
    conn = get_db()
    venue = get_venue(conn, id)
    if venue is None:
        flash('Venue not found', 'error')
        return redirect(url_for('venues.list'))
    try:
        delete_venue(conn, id)
    except sqlite3.IntegrityError:
        flash('Cannot delete venue with gig history', 'error')
        return redirect(url_for('venues.detail', id=id))
    flash('Venue deleted', 'success')
    return redirect(url_for('venues.list'))
