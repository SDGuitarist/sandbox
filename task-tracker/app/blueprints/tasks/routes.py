from flask import render_template, request, redirect, url_for, flash, abort
from app.db import get_db
from app.models import (get_task, get_project, get_tasks_for_project, create_task,
                        update_task, delete_task, get_comments_for_task, create_comment,
                        TASK_STATUSES, TASK_PRIORITIES, STATUS_LABELS, PRIORITY_LABELS)
from app.blueprints.tasks import tasks_bp


@tasks_bp.route('/tasks/<int:task_id>')
def show_task(task_id):
    with get_db() as db:
        task = get_task(db, task_id)
        if task is None:
            abort(404)
        project = get_project(db, task['project_id'])
        if project is None:
            abort(404)
        comments = get_comments_for_task(db, task_id)
    return render_template('tasks/detail.html',
        task=task,
        project=project,
        comments=comments,
        STATUS_LABELS=STATUS_LABELS,
        PRIORITY_LABELS=PRIORITY_LABELS
    )


@tasks_bp.route('/projects/<int:project_id>/tasks/new')
def new_task(project_id):
    with get_db() as db:
        project = get_project(db, project_id)
    if project is None:
        abort(404)
    return render_template('tasks/form.html',
        task=None,
        project=project,
        action_url=url_for('tasks.create_task_route', project_id=project['id']),
        TASK_STATUSES=TASK_STATUSES,
        TASK_PRIORITIES=TASK_PRIORITIES,
        STATUS_LABELS=STATUS_LABELS,
        PRIORITY_LABELS=PRIORITY_LABELS
    )


@tasks_bp.route('/projects/<int:project_id>/tasks', methods=['POST'])
def create_task_route(project_id):
    with get_db() as db:
        project = get_project(db, project_id)
    if project is None:
        abort(404)

    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    priority = request.form.get('priority', '').strip()

    errors = []
    if not title:
        errors.append('Title is required.')
    if priority and priority not in TASK_PRIORITIES:
        errors.append('Invalid priority value.')

    if errors:
        for e in errors:
            flash(e, 'error')
        return render_template('tasks/form.html',
            task={'title': title, 'description': description, 'priority': priority},
            project=project,
            action_url=url_for('tasks.create_task_route', project_id=project['id']),
            TASK_STATUSES=TASK_STATUSES,
            TASK_PRIORITIES=TASK_PRIORITIES,
            STATUS_LABELS=STATUS_LABELS,
            PRIORITY_LABELS=PRIORITY_LABELS
        )

    if not priority:
        priority = 'medium'

    with get_db(immediate=True) as db:
        task_id = create_task(db, project_id, title, description, priority)
    return redirect(url_for('tasks.show_task', task_id=task_id))


@tasks_bp.route('/tasks/<int:task_id>/edit')
def edit_task(task_id):
    with get_db() as db:
        task = get_task(db, task_id)
        if task is None:
            abort(404)
        project = get_project(db, task['project_id'])
        if project is None:
            abort(404)
    return render_template('tasks/form.html',
        task=task,
        project=project,
        action_url=url_for('tasks.update_task_route', task_id=task['id']),
        TASK_STATUSES=TASK_STATUSES,
        TASK_PRIORITIES=TASK_PRIORITIES,
        STATUS_LABELS=STATUS_LABELS,
        PRIORITY_LABELS=PRIORITY_LABELS
    )


@tasks_bp.route('/tasks/<int:task_id>', methods=['POST'])
def update_task_route(task_id):
    with get_db() as db:
        task = get_task(db, task_id)
        if task is None:
            abort(404)
        project = get_project(db, task['project_id'])

    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    status = request.form.get('status', '').strip()
    priority = request.form.get('priority', '').strip()

    errors = []
    if not title:
        errors.append('Title is required.')
    if not status or status not in TASK_STATUSES:
        errors.append('Invalid status value.')
    if not priority or priority not in TASK_PRIORITIES:
        errors.append('Invalid priority value.')

    if errors:
        for e in errors:
            flash(e, 'error')
        return render_template('tasks/form.html',
            task={'id': task_id, 'title': title, 'description': description,
                  'status': status, 'priority': priority,
                  'project_id': task['project_id']},
            project=project,
            action_url=url_for('tasks.update_task_route', task_id=task_id),
            TASK_STATUSES=TASK_STATUSES,
            TASK_PRIORITIES=TASK_PRIORITIES,
            STATUS_LABELS=STATUS_LABELS,
            PRIORITY_LABELS=PRIORITY_LABELS
        )

    with get_db(immediate=True) as db:
        update_task(db, task_id, title, description, status, priority)
    return redirect(url_for('tasks.show_task', task_id=task_id))


@tasks_bp.route('/tasks/<int:task_id>/delete', methods=['POST'])
def delete_task_route(task_id):
    with get_db(immediate=True) as db:
        task = get_task(db, task_id)
        if task is None:
            abort(404)
        project_id = task['project_id']
        delete_task(db, task_id)
    return redirect(url_for('projects.show_project', project_id=project_id))


@tasks_bp.route('/tasks/<int:task_id>/comments', methods=['POST'])
def add_comment(task_id):
    content = request.form.get('content', '').strip()

    with get_db(immediate=True) as db:
        task = get_task(db, task_id)
        if task is None:
            abort(404)
        project = get_project(db, task['project_id'])

        if not content:
            flash('Comment cannot be empty.', 'error')
            comments = get_comments_for_task(db, task_id)
            return render_template('tasks/detail.html',
                task=task,
                project=project,
                comments=comments,
                STATUS_LABELS=STATUS_LABELS,
                PRIORITY_LABELS=PRIORITY_LABELS
            )

        create_comment(db, task_id, content)
    return redirect(url_for('tasks.show_task', task_id=task_id))
