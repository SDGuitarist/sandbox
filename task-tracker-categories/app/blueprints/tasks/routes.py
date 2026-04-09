from flask import render_template, request, redirect, url_for, flash, abort

from app.db import get_db
from app.models import (get_task, get_project, create_task, update_task,
                        toggle_task, delete_task)
from app.blueprints.tasks import tasks_bp


@tasks_bp.route('/projects/<int:project_id>/tasks', methods=['POST'])
def create_task_route(project_id):
    title = request.form.get('title', '').strip()
    if not title:
        flash('Task title is required', 'error')
        return redirect(url_for('projects.show_project', project_id=project_id))
    description = request.form.get('description', '').strip()
    with get_db(immediate=True) as conn:
        create_task(conn, project_id, title, description)
    return redirect(url_for('projects.show_project', project_id=project_id))


@tasks_bp.route('/tasks/<int:task_id>/toggle', methods=['POST'])
def toggle_task_route(task_id):
    with get_db(immediate=True) as conn:
        task = get_task(conn, task_id)
        if task is None:
            abort(404)
        toggle_task(conn, task_id)
    return redirect(url_for('projects.show_project', project_id=task['project_id']))


@tasks_bp.route('/tasks/<int:task_id>/edit')
def edit_task(task_id):
    with get_db() as conn:
        task = get_task(conn, task_id)
        if task is None:
            abort(404)
        project = get_project(conn, task['project_id'])
        if project is None:
            abort(404)
    return render_template('tasks/form.html',
                           task=task,
                           project=project,
                           action_url=url_for('tasks.update_task_route', task_id=task['id']))


@tasks_bp.route('/tasks/<int:task_id>', methods=['POST'])
def update_task_route(task_id):
    title = request.form.get('title', '').strip()
    if not title:
        flash('Task title is required', 'error')
        return redirect(url_for('tasks.edit_task', task_id=task_id))
    description = request.form.get('description', '').strip()
    with get_db(immediate=True) as conn:
        task = get_task(conn, task_id)
        if task is None:
            abort(404)
        update_task(conn, task_id, title, description)
    return redirect(url_for('projects.show_project', project_id=task['project_id']))


@tasks_bp.route('/tasks/<int:task_id>/delete', methods=['POST'])
def delete_task_route(task_id):
    with get_db(immediate=True) as conn:
        task = get_task(conn, task_id)
        if task is None:
            abort(404)
        delete_task(conn, task_id)
    return redirect(url_for('projects.show_project', project_id=task['project_id']))
