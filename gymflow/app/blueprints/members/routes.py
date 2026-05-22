import re
import sqlite3

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from app.auth import login_required
from app.db import get_db
from app.models import (
    create_member,
    delete_member,
    get_active_membership_types,
    get_all_members,
    get_latest_assessment,
    get_member,
    get_members_by_status,
    search_members,
    update_member,
)

bp = Blueprint('members', __name__)

# Simple email regex: something@something.something
_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')

VALID_STATUSES = ('active', 'frozen', 'cancelled')


@bp.route('/')
@login_required
def list_members():
    conn = get_db()
    status_filter = request.args.get('status', '').strip()
    q = request.args.get('q', '').strip()

    if q:
        members = search_members(conn, q)
    elif status_filter in VALID_STATUSES:
        members = get_members_by_status(conn, status_filter)
    else:
        members = get_all_members(conn)

    return render_template('members/list.html', members=members)


@bp.route('/new')
@login_required
def new_member():
    conn = get_db()
    membership_types = get_active_membership_types(conn)
    return render_template(
        'members/form.html',
        member=None,
        membership_types=membership_types,
    )


@bp.route('/', methods=['POST'], endpoint='create_member')
@login_required
def create_member_route():
    conn = get_db()

    # Extract and strip form fields
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    emergency_contact = request.form.get('emergency_contact', '').strip()
    membership_type_id_raw = request.form.get('membership_type_id', '').strip()
    notes = request.form.get('notes', '').strip()

    # Validate name: required, 1-100 chars
    if not name or len(name) > 100:
        flash('Name is required.', 'error')
        return redirect(url_for('members.new_member'))

    # Validate email: required, 1-200 chars, basic format
    if not email or len(email) > 200 or not _EMAIL_RE.match(email):
        flash('Valid email is required.', 'error')
        return redirect(url_for('members.new_member'))

    # Validate phone: optional, max 50 chars
    if len(phone) > 50:
        flash('Phone number too long.', 'error')
        return redirect(url_for('members.new_member'))

    # Validate emergency_contact: optional, max 200 chars
    if len(emergency_contact) > 200:
        flash('Emergency contact too long.', 'error')
        return redirect(url_for('members.new_member'))

    # Validate membership_type_id: int or empty -> None
    membership_type_id = None
    if membership_type_id_raw:
        try:
            membership_type_id = int(membership_type_id_raw)
        except (ValueError, TypeError):
            flash('Invalid membership type.', 'error')
            return redirect(url_for('members.new_member'))

    # Validate notes: optional, max 1000 chars
    if len(notes) > 1000:
        flash('Notes too long.', 'error')
        return redirect(url_for('members.new_member'))

    member_id = create_member(
        conn, name, email, phone, emergency_contact,
        membership_type_id, notes,
    )
    flash('Member created successfully.', 'success')
    return redirect(url_for('members.detail', member_id=member_id))


@bp.route('/<int:member_id>')
@login_required
def detail(member_id):
    conn = get_db()
    member = get_member(conn, member_id)
    if member is None:
        abort(404)
    latest_assessment = get_latest_assessment(conn, member_id)
    return render_template(
        'members/detail.html',
        member=member,
        latest_assessment=latest_assessment,
    )


@bp.route('/<int:member_id>/edit')
@login_required
def edit_member(member_id):
    conn = get_db()
    member = get_member(conn, member_id)
    if member is None:
        abort(404)
    membership_types = get_active_membership_types(conn)
    return render_template(
        'members/form.html',
        member=member,
        membership_types=membership_types,
    )


@bp.route('/<int:member_id>/edit', methods=['POST'], endpoint='update_member')
@login_required
def update_member_route(member_id):
    conn = get_db()
    member = get_member(conn, member_id)
    if member is None:
        abort(404)

    # Extract and strip form fields
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    emergency_contact = request.form.get('emergency_contact', '').strip()
    membership_type_id_raw = request.form.get('membership_type_id', '').strip()
    status = request.form.get('status', '').strip()
    notes = request.form.get('notes', '').strip()

    # Validate name: required, 1-100 chars
    if not name or len(name) > 100:
        flash('Name is required.', 'error')
        return redirect(url_for('members.edit_member', member_id=member_id))

    # Validate email: required, 1-200 chars, basic format
    if not email or len(email) > 200 or not _EMAIL_RE.match(email):
        flash('Valid email is required.', 'error')
        return redirect(url_for('members.edit_member', member_id=member_id))

    # Validate phone: optional, max 50 chars
    if len(phone) > 50:
        flash('Phone number too long.', 'error')
        return redirect(url_for('members.edit_member', member_id=member_id))

    # Validate emergency_contact: optional, max 200 chars
    if len(emergency_contact) > 200:
        flash('Emergency contact too long.', 'error')
        return redirect(url_for('members.edit_member', member_id=member_id))

    # Validate membership_type_id: int or empty -> None
    membership_type_id = None
    if membership_type_id_raw:
        try:
            membership_type_id = int(membership_type_id_raw)
        except (ValueError, TypeError):
            flash('Invalid membership type.', 'error')
            return redirect(url_for('members.edit_member', member_id=member_id))

    # Validate status: must be one of the valid statuses
    if status not in VALID_STATUSES:
        flash('Invalid status.', 'error')
        return redirect(url_for('members.edit_member', member_id=member_id))

    # Validate notes: optional, max 1000 chars
    if len(notes) > 1000:
        flash('Notes too long.', 'error')
        return redirect(url_for('members.edit_member', member_id=member_id))

    update_member(
        conn, member_id, name, email, phone, emergency_contact,
        membership_type_id, status, notes,
    )
    flash('Member updated successfully.', 'success')
    return redirect(url_for('members.detail', member_id=member_id))


@bp.route('/<int:member_id>/delete', methods=['POST'], endpoint='delete_member')
@login_required
def delete_member_route(member_id):
    conn = get_db()
    member = get_member(conn, member_id)
    if member is None:
        abort(404)
    try:
        delete_member(conn, member_id)
        flash('Member deleted successfully.', 'success')
    except sqlite3.IntegrityError:
        flash('Cannot delete: referenced by other records.', 'error')
    return redirect(url_for('members.list_members'))
