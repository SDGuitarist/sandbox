from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from app.db import get_db
from app.auth import login_required
from app.models.room_booking import (
    create_room_booking, get_room_booking, get_all_room_bookings,
    get_room_bookings_by_member, get_available_slots,
    cancel_room_booking, VALID_SLOT_STARTS
)
from app.models.room import get_room, get_active_rooms
from app.models.member import get_member, get_all_members
from datetime import datetime

bp = Blueprint('room_bookings', __name__)


@bp.route('/')
@login_required
def list_bookings():
    conn = get_db()
    bookings = get_all_room_bookings(conn)
    return render_template('room_bookings/list.html', bookings=bookings)


@bp.route('/new')
@login_required
def new_booking():
    conn = get_db()
    rooms = get_active_rooms(conn)
    members = get_all_members(conn)
    return render_template(
        'room_bookings/form.html',
        rooms=rooms,
        members=members,
        slot_starts=VALID_SLOT_STARTS
    )


@bp.route('/new', methods=['POST'])
@login_required
def create():
    room_id_raw = request.form.get('room_id', '').strip()
    member_id_raw = request.form.get('member_id', '').strip()
    booking_date = request.form.get('booking_date', '').strip()
    slot_start = request.form.get('slot_start', '').strip()
    purpose = request.form.get('purpose', '').strip()

    # Validate room_id
    try:
        room_id = int(room_id_raw)
    except (ValueError, TypeError):
        flash('Invalid room.', 'error')
        return redirect(url_for('room_bookings.new_booking'))

    # Validate member_id
    try:
        member_id = int(member_id_raw)
    except (ValueError, TypeError):
        flash('Invalid member.', 'error')
        return redirect(url_for('room_bookings.new_booking'))

    # Validate booking_date
    if not booking_date:
        flash('Invalid date.', 'error')
        return redirect(url_for('room_bookings.new_booking'))
    try:
        datetime.strptime(booking_date, '%Y-%m-%d')
    except ValueError:
        flash('Invalid date.', 'error')
        return redirect(url_for('room_bookings.new_booking'))

    # Validate slot_start
    if slot_start not in VALID_SLOT_STARTS:
        flash('Invalid time slot.', 'error')
        return redirect(url_for('room_bookings.new_booking'))

    conn = get_db()

    # Validate room exists and is active
    room = get_room(conn, room_id)
    if room is None or not room['is_active']:
        flash('Invalid room.', 'error')
        return redirect(url_for('room_bookings.new_booking'))

    # Validate member exists
    member = get_member(conn, member_id)
    if member is None:
        flash('Invalid member.', 'error')
        return redirect(url_for('room_bookings.new_booking'))

    booking_id = create_room_booking(
        conn, room_id, member_id, booking_date, slot_start, purpose
    )
    if booking_id is None:
        flash('Room slot already booked.', 'error')
        return redirect(url_for('room_bookings.new_booking'))

    flash('Room booking created successfully.', 'success')
    return redirect(url_for('room_bookings.detail', booking_id=booking_id))


@bp.route('/<int:booking_id>')
@login_required
def detail(booking_id):
    conn = get_db()
    booking = get_room_booking(conn, booking_id)
    if booking is None:
        abort(404)
    return render_template('room_bookings/detail.html', booking=booking)


@bp.route('/<int:booking_id>/cancel', methods=['POST'])
@login_required
def cancel(booking_id):
    conn = get_db()
    booking = get_room_booking(conn, booking_id)
    if booking is None:
        abort(404)
    cancel_room_booking(conn, booking_id)
    flash('Room booking cancelled successfully.', 'success')
    return redirect(url_for('room_bookings.list_bookings'))
