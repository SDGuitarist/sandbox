from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from app.auth import login_required
from app.db import get_db
from app.models.desk import get_active_desks
from app.models.desk_booking import (
    cancel_desk_booking,
    create_desk_booking,
    get_all_desk_bookings,
    get_desk_booking,
    get_desk_bookings_by_member,
)
from app.models.member import get_all_members

bp = Blueprint('desk_bookings', __name__)


@bp.route('/')
@login_required
def list_bookings():
    conn = get_db()
    bookings = get_all_desk_bookings(conn)
    return render_template('desk_bookings/list.html', bookings=bookings)


@bp.route('/new', methods=['GET'])
@login_required
def new_booking():
    conn = get_db()
    desks = get_active_desks(conn)
    members = get_all_members(conn)
    return render_template(
        'desk_bookings/form.html',
        desks=desks,
        members=members,
    )


@bp.route('/new', methods=['POST'])
@login_required
def create():
    conn = get_db()

    # Validate desk_id: required, valid int, desk must exist and be active
    try:
        desk_id = int(request.form.get('desk_id', ''))
    except (ValueError, TypeError):
        flash('Invalid desk.', 'error')
        return redirect(url_for('desk_bookings.new_booking'))

    active_desks = get_active_desks(conn)
    if not any(d['id'] == desk_id for d in active_desks):
        flash('Invalid desk.', 'error')
        return redirect(url_for('desk_bookings.new_booking'))

    # Validate member_id: required, valid int, member must exist
    try:
        member_id = int(request.form.get('member_id', ''))
    except (ValueError, TypeError):
        flash('Invalid member.', 'error')
        return redirect(url_for('desk_bookings.new_booking'))

    members = get_all_members(conn)
    if not any(m['id'] == member_id for m in members):
        flash('Invalid member.', 'error')
        return redirect(url_for('desk_bookings.new_booking'))

    # Validate booking_date: required, valid ISO date (YYYY-MM-DD)
    booking_date = request.form.get('booking_date', '').strip()
    if not booking_date:
        flash('Invalid date.', 'error')
        return redirect(url_for('desk_bookings.new_booking'))
    try:
        datetime.strptime(booking_date, '%Y-%m-%d')
    except ValueError:
        flash('Invalid date.', 'error')
        return redirect(url_for('desk_bookings.new_booking'))

    # Validate block: must be in ('am', 'pm', 'full')
    block = request.form.get('block', '')
    if block not in ('am', 'pm', 'full'):
        flash('Invalid block.', 'error')
        return redirect(url_for('desk_bookings.new_booking'))

    # Create the booking (handles BEGIN IMMEDIATE internally)
    booking_id = create_desk_booking(conn, desk_id, member_id, booking_date, block)
    if booking_id is None:
        flash('Desk already booked for that block.', 'error')
        return redirect(url_for('desk_bookings.new_booking'))

    flash('Desk booking created successfully.', 'success')
    return redirect(url_for('desk_bookings.detail', booking_id=booking_id))


@bp.route('/<int:booking_id>')
@login_required
def detail(booking_id):
    conn = get_db()
    booking = get_desk_booking(conn, booking_id)
    if booking is None:
        abort(404)
    return render_template('desk_bookings/detail.html', booking=booking)


@bp.route('/<int:booking_id>/cancel', methods=['POST'])
@login_required
def cancel(booking_id):
    conn = get_db()
    booking = get_desk_booking(conn, booking_id)
    if booking is None:
        abort(404)
    cancel_desk_booking(conn, booking_id)
    flash('Desk booking cancelled successfully.', 'success')
    return redirect(url_for('desk_bookings.detail', booking_id=booking_id))
