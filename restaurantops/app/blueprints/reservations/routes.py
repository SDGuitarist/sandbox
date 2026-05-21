from datetime import date, datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.db import get_db
from app.models.reservation_models import (
    create_reservation,
    get_all_reservations,
    get_reservation,
    update_reservation,
    seat_reservation,
    complete_reservation,
    cancel_reservation,
    no_show_reservation,
    is_table_available,
)
from app.models.table_models import get_all_tables

bp = Blueprint('reservations', __name__)


@bp.route('/')
def list_reservations():
    conn = get_db()
    filter_date = request.args.get('date')
    reservations = get_all_reservations(conn, date=filter_date)
    tables = get_all_tables(conn)
    return render_template(
        'reservations/list.html',
        reservations=reservations,
        tables=tables,
    )


@bp.route('/create', methods=['GET'])
def create_form():
    conn = get_db()
    tables = get_all_tables(conn)
    return render_template('reservations/form.html', reservation=None, tables=tables)


@bp.route('/create', methods=['POST'])
def create():
    conn = get_db()

    guest_name = request.form.get('guest_name', '').strip()[:200]
    if not guest_name:
        flash('Guest name is required.', 'error')
        return redirect(url_for('reservations.create_form'))

    guest_phone = request.form.get('guest_phone', '').strip()[:50]

    try:
        party_size = int(request.form.get('party_size', 2))
        if party_size < 1:
            party_size = 1
    except (ValueError, TypeError):
        party_size = 2

    reservation_date = request.form.get('reservation_date', '').strip()
    if not reservation_date:
        flash('Reservation date is required.', 'error')
        return redirect(url_for('reservations.create_form'))
    try:
        datetime.strptime(reservation_date, '%Y-%m-%d')
    except ValueError:
        flash('Invalid date format. Use YYYY-MM-DD.', 'error')
        return redirect(url_for('reservations.create_form'))

    reservation_time = request.form.get('reservation_time', '').strip()
    if not reservation_time:
        flash('Reservation time is required.', 'error')
        return redirect(url_for('reservations.create_form'))
    try:
        datetime.strptime(reservation_time, '%H:%M')
    except ValueError:
        flash('Invalid time format. Use HH:MM.', 'error')
        return redirect(url_for('reservations.create_form'))

    try:
        duration_minutes = int(request.form.get('duration_minutes', 90))
        if duration_minutes < 15:
            duration_minutes = 15
    except (ValueError, TypeError):
        duration_minutes = 90

    try:
        table_id = int(request.form.get('table_id', 0))
    except (ValueError, TypeError):
        flash('Please select a table.', 'error')
        return redirect(url_for('reservations.create_form'))

    notes = request.form.get('notes', '').strip()[:500]

    # FC4: validate table availability before creating
    if not is_table_available(conn, table_id, reservation_date, reservation_time, duration_minutes):
        flash('Table is not available at the requested date/time.', 'error')
        return redirect(url_for('reservations.create_form'))

    conn.execute("BEGIN")
    reservation_id = create_reservation(
        conn, table_id, guest_name, guest_phone, party_size,
        reservation_date, reservation_time, duration_minutes, notes,
    )
    conn.commit()

    flash('Reservation created successfully.', 'success')
    return redirect(url_for('reservations.detail', id=reservation_id))


@bp.route('/<int:id>')
def detail(id):
    conn = get_db()
    reservation = get_reservation(conn, id)
    if reservation is None:
        flash('Reservation not found.', 'error')
        return redirect(url_for('reservations.list_reservations'))
    return render_template('reservations/detail.html', reservation=reservation)


@bp.route('/<int:id>/edit', methods=['GET'])
def edit_form(id):
    conn = get_db()
    reservation = get_reservation(conn, id)
    if reservation is None:
        flash('Reservation not found.', 'error')
        return redirect(url_for('reservations.list_reservations'))
    tables = get_all_tables(conn)
    return render_template('reservations/form.html', reservation=reservation, tables=tables)


@bp.route('/<int:id>/edit', methods=['POST'])
def edit(id):
    conn = get_db()
    reservation = get_reservation(conn, id)
    if reservation is None:
        flash('Reservation not found.', 'error')
        return redirect(url_for('reservations.list_reservations'))

    guest_name = request.form.get('guest_name', '').strip()[:200]
    if not guest_name:
        flash('Guest name is required.', 'error')
        return redirect(url_for('reservations.edit_form', id=id))

    guest_phone = request.form.get('guest_phone', '').strip()[:50]

    try:
        party_size = int(request.form.get('party_size', 2))
        if party_size < 1:
            party_size = 1
    except (ValueError, TypeError):
        party_size = 2

    reservation_date = request.form.get('reservation_date', '').strip()
    if not reservation_date:
        flash('Reservation date is required.', 'error')
        return redirect(url_for('reservations.edit_form', id=id))
    try:
        datetime.strptime(reservation_date, '%Y-%m-%d')
    except ValueError:
        flash('Invalid date format. Use YYYY-MM-DD.', 'error')
        return redirect(url_for('reservations.edit_form', id=id))

    reservation_time = request.form.get('reservation_time', '').strip()
    if not reservation_time:
        flash('Reservation time is required.', 'error')
        return redirect(url_for('reservations.edit_form', id=id))
    try:
        datetime.strptime(reservation_time, '%H:%M')
    except ValueError:
        flash('Invalid time format. Use HH:MM.', 'error')
        return redirect(url_for('reservations.edit_form', id=id))

    try:
        duration_minutes = int(request.form.get('duration_minutes', 90))
        if duration_minutes < 15:
            duration_minutes = 15
    except (ValueError, TypeError):
        duration_minutes = 90

    try:
        table_id = int(request.form.get('table_id', 0))
    except (ValueError, TypeError):
        flash('Please select a table.', 'error')
        return redirect(url_for('reservations.edit_form', id=id))

    notes = request.form.get('notes', '').strip()[:500]

    # FC4: validate table availability before updating (exclude current reservation)
    if not is_table_available(conn, table_id, reservation_date, reservation_time, duration_minutes, exclude_reservation_id=id):
        flash('Table is not available at the requested date/time.', 'error')
        return redirect(url_for('reservations.edit_form', id=id))

    conn.execute("BEGIN")
    update_reservation(
        conn, id, table_id, guest_name, guest_phone, party_size,
        reservation_date, reservation_time, duration_minutes, notes,
    )
    conn.commit()

    flash('Reservation updated successfully.', 'success')
    return redirect(url_for('reservations.detail', id=id))


@bp.route('/<int:id>/seat', methods=['POST'])
def seat(id):
    conn = get_db()
    reservation = get_reservation(conn, id)
    if reservation is None:
        flash('Reservation not found.', 'error')
        return redirect(url_for('reservations.list_reservations'))

    conn.execute("BEGIN IMMEDIATE")
    try:
        seat_reservation(conn, id)
        conn.commit()
    except Exception:
        conn.rollback()
        flash('Could not seat reservation. Please try again.', 'error')
        return redirect(url_for('reservations.detail', id=id))

    flash('Reservation seated.', 'success')
    return redirect(url_for('reservations.detail', id=id))


@bp.route('/<int:id>/complete', methods=['POST'])
def complete(id):
    conn = get_db()
    reservation = get_reservation(conn, id)
    if reservation is None:
        flash('Reservation not found.', 'error')
        return redirect(url_for('reservations.list_reservations'))

    conn.execute("BEGIN IMMEDIATE")
    try:
        complete_reservation(conn, id)
        conn.commit()
    except Exception:
        conn.rollback()
        flash('Could not complete reservation. Please try again.', 'error')
        return redirect(url_for('reservations.detail', id=id))

    flash('Reservation completed.', 'success')
    return redirect(url_for('reservations.detail', id=id))


@bp.route('/<int:id>/cancel', methods=['POST'])
def cancel(id):
    conn = get_db()
    reservation = get_reservation(conn, id)
    if reservation is None:
        flash('Reservation not found.', 'error')
        return redirect(url_for('reservations.list_reservations'))

    conn.execute("BEGIN IMMEDIATE")
    try:
        cancel_reservation(conn, id)
        conn.commit()
    except Exception:
        conn.rollback()
        flash('Could not cancel reservation. Please try again.', 'error')
        return redirect(url_for('reservations.detail', id=id))

    flash('Reservation cancelled.', 'success')
    return redirect(url_for('reservations.detail', id=id))


@bp.route('/<int:id>/no-show', methods=['POST'])
def no_show(id):
    conn = get_db()
    reservation = get_reservation(conn, id)
    if reservation is None:
        flash('Reservation not found.', 'error')
        return redirect(url_for('reservations.list_reservations'))

    conn.execute("BEGIN IMMEDIATE")
    try:
        no_show_reservation(conn, id)
        conn.commit()
    except Exception:
        conn.rollback()
        flash('Could not mark reservation as no-show. Please try again.', 'error')
        return redirect(url_for('reservations.detail', id=id))

    flash('Reservation marked as no-show.', 'success')
    return redirect(url_for('reservations.detail', id=id))
