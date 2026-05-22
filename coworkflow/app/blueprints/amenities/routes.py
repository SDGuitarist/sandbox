from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, abort
)
from app.db import get_db
from app.auth import login_required
from app.models.amenity import (
    create_amenity, get_amenity, get_all_amenities, update_amenity,
    delete_amenity
)
import sqlite3

bp = Blueprint('amenities', __name__)


@bp.route('/')
@login_required
def list_amenities():
    conn = get_db()
    amenities = get_all_amenities(conn)
    return render_template('amenities/list.html', amenities=amenities)


@bp.route('/new')
@login_required
def new_amenity():
    return render_template('amenities/form.html', amenity=None)


@bp.route('/new', methods=['POST'])
@login_required
def create():
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()

    if not name or len(name) > 100:
        flash('Name is required.', 'error')
        return render_template('amenities/form.html', amenity=None)

    conn = get_db()
    try:
        create_amenity(conn, name, description)
    except sqlite3.IntegrityError:
        flash('An amenity with this name already exists.', 'error')
        return render_template('amenities/form.html', amenity=None)

    flash('Amenity created successfully.', 'success')
    return redirect(url_for('amenities.list_amenities'))


@bp.route('/<int:amenity_id>/edit')
@login_required
def edit_form(amenity_id):
    conn = get_db()
    amenity = get_amenity(conn, amenity_id)
    if amenity is None:
        abort(404)
    return render_template('amenities/form.html', amenity=amenity)


@bp.route('/<int:amenity_id>/edit', methods=['POST'])
@login_required
def update(amenity_id):
    conn = get_db()
    amenity = get_amenity(conn, amenity_id)
    if amenity is None:
        abort(404)

    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    is_available = 1 if request.form.get('is_available') else 0

    if not name or len(name) > 100:
        flash('Name is required.', 'error')
        return render_template('amenities/form.html', amenity=amenity)

    try:
        update_amenity(conn, amenity_id, name, description, is_available)
    except sqlite3.IntegrityError:
        flash('An amenity with this name already exists.', 'error')
        return render_template('amenities/form.html', amenity=amenity)

    flash('Amenity updated successfully.', 'success')
    return redirect(url_for('amenities.list_amenities'))


@bp.route('/<int:amenity_id>/delete', methods=['POST'])
@login_required
def delete(amenity_id):
    conn = get_db()
    amenity = get_amenity(conn, amenity_id)
    if amenity is None:
        abort(404)

    delete_amenity(conn, amenity_id)

    flash('Amenity deleted successfully.', 'success')
    return redirect(url_for('amenities.list_amenities'))
