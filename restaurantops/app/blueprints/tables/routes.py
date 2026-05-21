from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.db import get_db
from app.models.table_models import (
    create_table,
    get_all_tables,
    get_table,
    update_table,
    delete_table,
    update_table_status,
    get_table_status_board,
)

bp = Blueprint('tables', __name__)

VALID_STATUSES = ('available', 'reserved', 'occupied', 'needs_cleaning')


@bp.route('/')
def list_tables():
    conn = get_db()
    tables = get_all_tables(conn)
    return render_template('tables/list.html', tables=tables)


@bp.route('/board')
def status_board():
    conn = get_db()
    tables = get_table_status_board(conn)
    return render_template('tables/board.html', tables=tables)


@bp.route('/create', methods=['GET'])
def create_form():
    return render_template('tables/form.html', table=None)


@bp.route('/create', methods=['POST'])
def create():
    table_number = request.form.get('table_number', '').strip()
    capacity_str = request.form.get('capacity', '').strip()
    zone = request.form.get('zone', '').strip()
    status = request.form.get('status', 'available').strip()

    if not table_number:
        flash('Table number is required.', 'error')
        return redirect(url_for('tables.create_form'))

    if not capacity_str:
        flash('Capacity is required.', 'error')
        return redirect(url_for('tables.create_form'))

    try:
        capacity = int(capacity_str)
    except ValueError:
        flash('Capacity must be a number.', 'error')
        return redirect(url_for('tables.create_form'))

    if capacity < 1:
        flash('Capacity must be at least 1.', 'error')
        return redirect(url_for('tables.create_form'))

    if not zone:
        zone = 'main'

    conn = get_db()
    conn.execute("BEGIN")
    try:
        create_table(conn, table_number, capacity, zone)
        conn.commit()
    except Exception:
        conn.rollback()
        flash('Failed to create table. The table number may already exist.', 'error')
        return redirect(url_for('tables.create_form'))

    flash('Table created successfully.', 'success')
    return redirect(url_for('tables.list_tables'))


@bp.route('/<int:id>/edit', methods=['GET'])
def edit_form(id):
    conn = get_db()
    table = get_table(conn, id)
    if table is None:
        flash('Table not found.', 'error')
        return redirect(url_for('tables.list_tables'))
    return render_template('tables/form.html', table=table)


@bp.route('/<int:id>/edit', methods=['POST'])
def edit(id):
    conn = get_db()
    table = get_table(conn, id)
    if table is None:
        flash('Table not found.', 'error')
        return redirect(url_for('tables.list_tables'))

    table_number = request.form.get('table_number', '').strip()
    capacity_str = request.form.get('capacity', '').strip()
    zone = request.form.get('zone', '').strip()

    if not table_number:
        flash('Table number is required.', 'error')
        return redirect(url_for('tables.edit_form', id=id))

    if not capacity_str:
        flash('Capacity is required.', 'error')
        return redirect(url_for('tables.edit_form', id=id))

    try:
        capacity = int(capacity_str)
    except ValueError:
        flash('Capacity must be a number.', 'error')
        return redirect(url_for('tables.edit_form', id=id))

    if capacity < 1:
        flash('Capacity must be at least 1.', 'error')
        return redirect(url_for('tables.edit_form', id=id))

    if not zone:
        zone = 'main'

    conn.execute("BEGIN")
    try:
        update_table(conn, id, table_number, capacity, zone)
        conn.commit()
    except Exception:
        conn.rollback()
        flash('Failed to update table. The table number may already exist.', 'error')
        return redirect(url_for('tables.edit_form', id=id))

    flash('Table updated successfully.', 'success')
    return redirect(url_for('tables.list_tables'))


@bp.route('/<int:id>/delete', methods=['POST'])
def delete(id):
    conn = get_db()
    table = get_table(conn, id)
    if table is None:
        flash('Table not found.', 'error')
        return redirect(url_for('tables.list_tables'))

    conn.execute("BEGIN")
    try:
        delete_table(conn, id)
        conn.commit()
    except Exception:
        conn.rollback()
        flash('Failed to delete table.', 'error')
        return redirect(url_for('tables.list_tables'))

    flash('Table deleted successfully.', 'success')
    return redirect(url_for('tables.list_tables'))


@bp.route('/<int:id>/status', methods=['POST'])
def update_status(id):
    conn = get_db()
    table = get_table(conn, id)
    if table is None:
        flash('Table not found.', 'error')
        return redirect(url_for('tables.status_board'))

    status = request.form.get('status', '').strip()
    if status not in VALID_STATUSES:
        flash('Invalid status.', 'error')
        return redirect(url_for('tables.status_board'))

    conn.execute("BEGIN")
    try:
        update_table_status(conn, id, status)
        conn.commit()
    except Exception:
        conn.rollback()
        flash('Failed to update table status.', 'error')
        return redirect(url_for('tables.status_board'))

    flash('Table status updated.', 'info')
    return redirect(url_for('tables.status_board'))
