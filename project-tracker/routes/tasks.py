"""Task routes for the project tracker."""

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from app import get_db
from models.tasks import (
    get_all_tasks, get_task, create_task, update_task, delete_task,
    get_task_members, get_available_members, assign_member, unassign_member,
)
from models.categories import get_all_categories
from models.activity import log_activity

bp = Blueprint('tasks', __name__)


@bp.route('/')
def list():
    db = get_db()
    tasks = get_all_tasks(db)
    return render_template('tasks/list.html', tasks=tasks)


@bp.route('/new')
def new():
    db = get_db()
    categories = get_all_categories(db)
    return render_template('tasks/form.html', task=None, categories=categories)


@bp.route('/new', methods=['POST'])
def create():
    title = request.form.get('title', '').strip()[:100]
    if not title:
        flash('Title is required', 'error')
        return redirect(request.url)

    description = request.form.get('description', '').strip()

    status = request.form.get('status', 'todo')
    if status not in ('todo', 'in_progress', 'done'):
        status = 'todo'

    due_date = request.form.get('due_date', '').strip() or None

    try:
        category_id = int(request.form.get('category_id', 0))
    except (ValueError, TypeError):
        flash('Invalid category', 'error')
        return redirect(request.url)

    db = get_db()
    task_id = create_task(db, title, description, status, due_date, category_id)
    log_activity(db, 'task', task_id, 'created', f"Created task '{title}'")
    db.commit()

    return redirect(url_for('tasks.detail', task_id=task_id))


@bp.route('/<int:task_id>')
def detail(task_id):
    db = get_db()
    task = get_task(db, task_id)
    if task is None:
        abort(404)
    assigned = get_task_members(db, task_id)
    available = get_available_members(db, task_id)
    return render_template('tasks/detail.html', task=task, assigned=assigned, available=available)


@bp.route('/<int:task_id>/edit')
def edit_form(task_id):
    db = get_db()
    task = get_task(db, task_id)
    if task is None:
        abort(404)
    categories = get_all_categories(db)
    return render_template('tasks/form.html', task=task, categories=categories)


@bp.route('/<int:task_id>/edit', methods=['POST'])
def edit(task_id):
    db = get_db()
    task = get_task(db, task_id)
    if task is None:
        abort(404)

    title = request.form.get('title', '').strip()[:100]
    if not title:
        flash('Title is required', 'error')
        return redirect(request.url)

    description = request.form.get('description', '').strip()

    status = request.form.get('status', 'todo')
    if status not in ('todo', 'in_progress', 'done'):
        status = 'todo'

    due_date = request.form.get('due_date', '').strip() or None

    try:
        category_id = int(request.form.get('category_id', 0))
    except (ValueError, TypeError):
        flash('Invalid category', 'error')
        return redirect(request.url)

    update_task(db, task_id, title, description, status, due_date, category_id)
    log_activity(db, 'task', task_id, 'updated', f"Updated task '{title}'")
    db.commit()

    return redirect(url_for('tasks.detail', task_id=task_id))


@bp.route('/<int:task_id>/delete', methods=['POST'])
def delete(task_id):
    db = get_db()
    task = get_task(db, task_id)
    if task is None:
        abort(404)
    title = task['title']
    delete_task(db, task_id)
    log_activity(db, 'task', task_id, 'deleted', f"Deleted task '{title}'")
    db.commit()
    return redirect(url_for('tasks.list'))


@bp.route('/<int:task_id>/assign', methods=['POST'])
def assign(task_id):
    db = get_db()
    task = get_task(db, task_id)
    if task is None:
        abort(404)
    try:
        member_id = int(request.form.get('member_id', 0))
    except (ValueError, TypeError):
        flash('Invalid member', 'error')
        return redirect(url_for('tasks.detail', task_id=task_id))
    assign_member(db, task_id, member_id)
    db.commit()
    return redirect(url_for('tasks.detail', task_id=task_id))


@bp.route('/<int:task_id>/unassign', methods=['POST'])
def unassign(task_id):
    db = get_db()
    task = get_task(db, task_id)
    if task is None:
        abort(404)
    try:
        member_id = int(request.form.get('member_id', 0))
    except (ValueError, TypeError):
        flash('Invalid member', 'error')
        return redirect(url_for('tasks.detail', task_id=task_id))
    unassign_member(db, task_id, member_id)
    db.commit()
    return redirect(url_for('tasks.detail', task_id=task_id))
