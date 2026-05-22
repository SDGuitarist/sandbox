import sqlite3

from flask import Blueprint, flash, redirect, render_template, request, url_for, abort

from app.auth import login_required
from app.db import get_db
from app.models import (
    create_class_type,
    get_class_type,
    get_all_class_types,
    update_class_type,
    delete_class_type,
)

bp = Blueprint('class_types', __name__)


@bp.route('/')
@login_required
def list_types():
    conn = get_db()
    types = get_all_class_types(conn)
    return render_template('class_types/list.html', types=types)


@bp.route('/new')
@login_required
def new_type():
    return render_template('class_types/form.html', ctype=None)


@bp.route('/', methods=['POST'])
@login_required
def create_type():
    conn = get_db()

    name = request.form.get('name', '').strip()
    if not name or len(name) > 100:
        flash('Name is required (max 100 characters).', 'error')
        return redirect(url_for('class_types.new_type'))

    description = request.form.get('description', '').strip()

    try:
        duration_minutes = int(request.form.get('duration_minutes', '0'))
        if duration_minutes < 1:
            raise ValueError
    except (ValueError, TypeError):
        flash('Duration must be at least 1 minute.', 'error')
        return redirect(url_for('class_types.new_type'))

    try:
        default_capacity = int(request.form.get('default_capacity', '0'))
        if default_capacity < 1:
            raise ValueError
    except (ValueError, TypeError):
        flash('Capacity must be at least 1.', 'error')
        return redirect(url_for('class_types.new_type'))

    try:
        create_class_type(conn, name, description, duration_minutes, default_capacity)
    except sqlite3.IntegrityError:
        flash('A class type with that name already exists.', 'error')
        return redirect(url_for('class_types.new_type'))

    flash('Class type created successfully.', 'success')
    return redirect(url_for('class_types.list_types'))


@bp.route('/<int:type_id>/edit')
@login_required
def edit_type(type_id):
    conn = get_db()
    ctype = get_class_type(conn, type_id)
    if ctype is None:
        abort(404)
    return render_template('class_types/form.html', ctype=ctype)


@bp.route('/<int:type_id>/edit', methods=['POST'])
@login_required
def update_type(type_id):
    conn = get_db()
    ctype = get_class_type(conn, type_id)
    if ctype is None:
        abort(404)

    name = request.form.get('name', '').strip()
    if not name or len(name) > 100:
        flash('Name is required (max 100 characters).', 'error')
        return redirect(url_for('class_types.edit_type', type_id=type_id))

    description = request.form.get('description', '').strip()

    try:
        duration_minutes = int(request.form.get('duration_minutes', '0'))
        if duration_minutes < 1:
            raise ValueError
    except (ValueError, TypeError):
        flash('Duration must be at least 1 minute.', 'error')
        return redirect(url_for('class_types.edit_type', type_id=type_id))

    try:
        default_capacity = int(request.form.get('default_capacity', '0'))
        if default_capacity < 1:
            raise ValueError
    except (ValueError, TypeError):
        flash('Capacity must be at least 1.', 'error')
        return redirect(url_for('class_types.edit_type', type_id=type_id))

    try:
        update_class_type(conn, type_id, name, description, duration_minutes, default_capacity)
    except sqlite3.IntegrityError:
        flash('A class type with that name already exists.', 'error')
        return redirect(url_for('class_types.edit_type', type_id=type_id))

    flash('Class type updated successfully.', 'success')
    return redirect(url_for('class_types.list_types'))


@bp.route('/<int:type_id>/delete', methods=['POST'])
@login_required
def delete_type(type_id):
    conn = get_db()
    ctype = get_class_type(conn, type_id)
    if ctype is None:
        abort(404)

    try:
        delete_class_type(conn, type_id)
    except sqlite3.IntegrityError:
        flash('Cannot delete: referenced by other records.', 'error')
        return redirect(url_for('class_types.list_types'))

    flash('Class type deleted successfully.', 'success')
    return redirect(url_for('class_types.list_types'))
