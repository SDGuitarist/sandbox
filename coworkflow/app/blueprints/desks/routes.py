from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from app.db import get_db
from app.auth import login_required
from app.models.desk import create_desk, get_desk, get_all_desks, update_desk, delete_desk
import sqlite3

bp = Blueprint('desks', __name__)


@bp.route('/')
@login_required
def list_desks():
    conn = get_db()
    desks = get_all_desks(conn)
    return render_template('desks/list.html', desks=desks)


@bp.route('/new', methods=['GET'])
@login_required
def new_desk():
    return render_template('desks/form.html', desk=None)


@bp.route('/new', methods=['POST'])
@login_required
def create():
    name = request.form.get('name', '').strip()
    location = request.form.get('location', '').strip()

    if not name:
        flash('Name is required.', 'error')
        return redirect(url_for('desks.new_desk'))

    if len(name) > 100:
        flash('Name must be 100 characters or fewer.', 'error')
        return redirect(url_for('desks.new_desk'))

    conn = get_db()
    try:
        create_desk(conn, name, location)
    except sqlite3.IntegrityError:
        flash('A desk with this name already exists.', 'error')
        return redirect(url_for('desks.new_desk'))

    flash('Desk created successfully.', 'success')
    return redirect(url_for('desks.list_desks'))


@bp.route('/<int:desk_id>/edit', methods=['GET'])
@login_required
def edit_form(desk_id):
    conn = get_db()
    desk = get_desk(conn, desk_id)
    if desk is None:
        abort(404)
    return render_template('desks/form.html', desk=desk)


@bp.route('/<int:desk_id>/edit', methods=['POST'])
@login_required
def update(desk_id):
    conn = get_db()
    desk = get_desk(conn, desk_id)
    if desk is None:
        abort(404)

    name = request.form.get('name', '').strip()
    location = request.form.get('location', '').strip()
    is_active = 1 if 'is_active' in request.form else 0

    if not name:
        flash('Name is required.', 'error')
        return redirect(url_for('desks.edit_form', desk_id=desk_id))

    if len(name) > 100:
        flash('Name must be 100 characters or fewer.', 'error')
        return redirect(url_for('desks.edit_form', desk_id=desk_id))

    try:
        update_desk(conn, desk_id, name, location, is_active)
    except sqlite3.IntegrityError:
        flash('A desk with this name already exists.', 'error')
        return redirect(url_for('desks.edit_form', desk_id=desk_id))

    flash('Desk updated successfully.', 'success')
    return redirect(url_for('desks.list_desks'))


@bp.route('/<int:desk_id>/delete', methods=['POST'])
@login_required
def delete(desk_id):
    conn = get_db()
    desk = get_desk(conn, desk_id)
    if desk is None:
        abort(404)

    try:
        delete_desk(conn, desk_id)
    except sqlite3.IntegrityError:
        flash('Cannot delete: desk has bookings.', 'error')
        return redirect(url_for('desks.list_desks'))

    flash('Desk deleted successfully.', 'success')
    return redirect(url_for('desks.list_desks'))
