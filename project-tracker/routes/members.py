"""Routes for the members blueprint."""

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from app import get_db
from models.members import (get_all_members, get_member, create_member,
    update_member, delete_member)
from models.tasks import get_tasks_by_member
from models.activity import log_activity

bp = Blueprint('members', __name__)


@bp.route('/')
def list():
    db = get_db()
    members = get_all_members(db)
    return render_template('members/list.html', members=members)


@bp.route('/new')
def new():
    return render_template('members/form.html', member=None)


@bp.route('/new', methods=['POST'])
def create():
    name = request.form.get('name', '').strip()[:100]
    if not name:
        flash('Name is required', 'error')
        return redirect(request.url)

    role = request.form.get('role', '').strip()[:100]

    db = get_db()
    member_id = create_member(db, name, role)
    log_activity(db, 'member', member_id, 'created', f"Created member '{name}'")
    db.commit()

    return redirect(url_for('members.list'))


@bp.route('/<int:member_id>')
def detail(member_id):
    db = get_db()
    member = get_member(db, member_id)
    if member is None:
        abort(404)
    tasks = get_tasks_by_member(db, member_id)
    return render_template('members/detail.html', member=member, tasks=tasks)


@bp.route('/<int:member_id>/edit')
def edit_form(member_id):
    db = get_db()
    member = get_member(db, member_id)
    if member is None:
        abort(404)
    return render_template('members/form.html', member=member)


@bp.route('/<int:member_id>/edit', methods=['POST'])
def edit(member_id):
    db = get_db()
    member = get_member(db, member_id)
    if member is None:
        abort(404)

    name = request.form.get('name', '').strip()[:100]
    if not name:
        flash('Name is required', 'error')
        return redirect(request.url)

    role = request.form.get('role', '').strip()[:100]

    update_member(db, member_id, name, role)
    log_activity(db, 'member', member_id, 'updated', f"Updated member '{name}'")
    db.commit()

    return redirect(url_for('members.detail', member_id=member_id))


@bp.route('/<int:member_id>/delete', methods=['POST'])
def delete(member_id):
    db = get_db()
    member = get_member(db, member_id)
    if member is None:
        abort(404)

    name = member['name']
    delete_member(db, member_id)
    log_activity(db, 'member', member_id, 'deleted', f"Deleted member '{name}'")
    db.commit()

    return redirect(url_for('members.list'))
