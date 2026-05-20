from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, abort, g
)
from app.db import get_db
from app.decorators import login_required, role_required
from app.models import (
    create_venue, get_venue, get_venues_by_manager,
    update_venue, delete_venue, get_rooms_by_venue
)

venues_bp = Blueprint('venues', __name__)


@venues_bp.route('/')
@login_required
@role_required('venue_manager')
def list():
    conn = get_db()
    venues = get_venues_by_manager(conn, g.user['id'])
    return render_template('venues/list.html', venues=venues)


@venues_bp.route('/<int:venue_id>')
@login_required
@role_required('venue_manager')
def detail(venue_id):
    conn = get_db()
    venue = get_venue(conn, venue_id)
    if venue is None:
        abort(404)
    if venue['user_id'] != g.user['id']:
        abort(403)
    rooms = get_rooms_by_venue(conn, venue_id)
    return render_template('venues/detail.html', venue=venue, rooms=rooms)


@venues_bp.route('/new', methods=['GET', 'POST'])
@login_required
@role_required('venue_manager')
def create():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        location = request.form.get('location', '').strip()
        description = request.form.get('description', '').strip()
        capacity_raw = request.form.get('capacity', '').strip()
        genre_tags = request.form.get('genre_tags', '').strip()

        if not name:
            flash('Venue name is required.', 'error')
            return render_template('venues/form.html', venue=None)

        try:
            capacity = int(capacity_raw) if capacity_raw else 0
        except ValueError:
            flash('Capacity must be a number.', 'error')
            return render_template('venues/form.html', venue=None)

        if capacity < 0:
            flash('Capacity must be zero or positive.', 'error')
            return render_template('venues/form.html', venue=None)

        conn = get_db()
        venue_id = create_venue(
            conn, g.user['id'], name, location,
            description, capacity, genre_tags
        )
        conn.commit()
        flash('Venue created successfully.', 'success')
        return redirect(url_for('venues.detail', venue_id=venue_id))

    return render_template('venues/form.html', venue=None)


@venues_bp.route('/<int:venue_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('venue_manager')
def edit(venue_id):
    conn = get_db()
    venue = get_venue(conn, venue_id)
    if venue is None:
        abort(404)
    if venue['user_id'] != g.user['id']:
        abort(403)

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        location = request.form.get('location', '').strip()
        description = request.form.get('description', '').strip()
        capacity_raw = request.form.get('capacity', '').strip()
        genre_tags = request.form.get('genre_tags', '').strip()

        if not name:
            flash('Venue name is required.', 'error')
            return render_template('venues/form.html', venue=venue)

        try:
            capacity = int(capacity_raw) if capacity_raw else 0
        except ValueError:
            flash('Capacity must be a number.', 'error')
            return render_template('venues/form.html', venue=venue)

        if capacity < 0:
            flash('Capacity must be zero or positive.', 'error')
            return render_template('venues/form.html', venue=venue)

        update_venue(
            conn, venue_id, name, location,
            description, capacity, genre_tags
        )
        conn.commit()
        flash('Venue updated successfully.', 'success')
        return redirect(url_for('venues.detail', venue_id=venue_id))

    return render_template('venues/form.html', venue=venue)


@venues_bp.route('/<int:venue_id>/delete', methods=['POST'])
@login_required
@role_required('venue_manager')
def delete(venue_id):
    conn = get_db()
    venue = get_venue(conn, venue_id)
    if venue is None:
        abort(404)
    if venue['user_id'] != g.user['id']:
        abort(403)

    delete_venue(conn, venue_id)
    conn.commit()
    flash('Venue deleted successfully.', 'success')
    return redirect(url_for('venues.list'))
