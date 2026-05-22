from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, abort
)
from app.db import get_db
from app.auth import login_required
from app.models.member import (
    create_member, get_member, get_all_members,
    update_member, delete_member, search_members
)
from app.models.plan import get_active_plans
import sqlite3

bp = Blueprint('members', __name__)


@bp.route('/')
@login_required
def list_members():
    conn = get_db()
    q = request.args.get('q', '').strip()
    if q:
        members = search_members(conn, q)
    else:
        members = get_all_members(conn)
    return render_template('members/list.html', members=members, q=q)


@bp.route('/new')
@login_required
def new_member():
    conn = get_db()
    plans = get_active_plans(conn)
    return render_template('members/form.html', member=None, plans=plans)


@bp.route('/new', methods=['POST'])
@login_required
def create():
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    company = request.form.get('company', '').strip()
    membership_plan_id_raw = request.form.get('membership_plan_id', '').strip()
    notes = request.form.get('notes', '').strip()

    if not name or len(name) > 100:
        flash('Name is required.', 'error')
        conn = get_db()
        plans = get_active_plans(conn)
        return render_template('members/form.html', member=None, plans=plans)

    if not email or len(email) > 200:
        flash('Email is required.', 'error')
        conn = get_db()
        plans = get_active_plans(conn)
        return render_template('members/form.html', member=None, plans=plans)

    if membership_plan_id_raw:
        try:
            membership_plan_id = int(membership_plan_id_raw)
        except ValueError:
            membership_plan_id = None
    else:
        membership_plan_id = None

    conn = get_db()
    try:
        member_id = create_member(
            conn, name, email, phone, company, membership_plan_id, notes
        )
    except sqlite3.IntegrityError:
        flash('A member with this email already exists.', 'error')
        plans = get_active_plans(conn)
        return render_template('members/form.html', member=None, plans=plans)

    flash('Member created successfully.', 'success')
    return redirect(url_for('members.detail', member_id=member_id))


@bp.route('/<int:member_id>')
@login_required
def detail(member_id):
    conn = get_db()
    member = get_member(conn, member_id)
    if member is None:
        abort(404)
    return render_template('members/detail.html', member=member)


@bp.route('/<int:member_id>/edit')
@login_required
def edit_form(member_id):
    conn = get_db()
    member = get_member(conn, member_id)
    if member is None:
        abort(404)
    plans = get_active_plans(conn)
    return render_template('members/form.html', member=member, plans=plans)


@bp.route('/<int:member_id>/edit', methods=['POST'])
@login_required
def update(member_id):
    conn = get_db()
    member = get_member(conn, member_id)
    if member is None:
        abort(404)

    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    company = request.form.get('company', '').strip()
    membership_plan_id_raw = request.form.get('membership_plan_id', '').strip()
    status = request.form.get('status', '').strip()
    notes = request.form.get('notes', '').strip()

    if not name or len(name) > 100:
        flash('Name is required.', 'error')
        plans = get_active_plans(conn)
        return render_template('members/form.html', member=member, plans=plans)

    if not email or len(email) > 200:
        flash('Email is required.', 'error')
        plans = get_active_plans(conn)
        return render_template('members/form.html', member=member, plans=plans)

    if status not in ('active', 'frozen', 'cancelled'):
        flash('Invalid status.', 'error')
        plans = get_active_plans(conn)
        return render_template('members/form.html', member=member, plans=plans)

    if membership_plan_id_raw:
        try:
            membership_plan_id = int(membership_plan_id_raw)
        except ValueError:
            membership_plan_id = None
    else:
        membership_plan_id = None

    try:
        update_member(
            conn, member_id, name, email, phone, company,
            membership_plan_id, status, notes
        )
    except sqlite3.IntegrityError:
        flash('A member with this email already exists.', 'error')
        plans = get_active_plans(conn)
        return render_template('members/form.html', member=member, plans=plans)

    flash('Member updated successfully.', 'success')
    return redirect(url_for('members.detail', member_id=member_id))


@bp.route('/<int:member_id>/delete', methods=['POST'])
@login_required
def delete(member_id):
    conn = get_db()
    member = get_member(conn, member_id)
    if member is None:
        abort(404)

    try:
        delete_member(conn, member_id)
    except sqlite3.IntegrityError:
        flash('Cannot delete: member has bookings or invoices.', 'error')
        return redirect(url_for('members.detail', member_id=member_id))

    flash('Member deleted successfully.', 'success')
    return redirect(url_for('members.list_members'))
