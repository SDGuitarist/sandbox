from flask import render_template, request, redirect, url_for, flash, abort
from app.db import get_db
from app.models import (
    get_all_projects,
    get_project,
    create_project,
    update_project,
    delete_project,
    get_tasks_for_project,
    STATUS_LABELS,
)
from app.blueprints.projects import projects_bp


@projects_bp.route('/')
def list_projects():
    with get_db() as db:
        projects = get_all_projects(db)
    return render_template('projects/list.html', projects=projects)


@projects_bp.route('/<int:project_id>')
def show_project(project_id):
    with get_db() as db:
        project = get_project(db, project_id)
        if project is None:
            abort(404)
        tasks = get_tasks_for_project(db, project_id)
    return render_template(
        'projects/detail.html',
        project=project,
        tasks=tasks,
        STATUS_LABELS=STATUS_LABELS,
    )


@projects_bp.route('/new')
def new_project():
    return render_template(
        'projects/form.html',
        project=None,
        action_url=url_for('projects.create_project_route'),
    )


@projects_bp.route('/', methods=['POST'])
def create_project_route():
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()

    if not name:
        flash('Project name is required.', 'error')
        return redirect(url_for('projects.new_project'))

    with get_db(immediate=True) as db:
        project_id = create_project(db, name, description)
    return redirect(url_for('projects.show_project', project_id=project_id))


@projects_bp.route('/<int:project_id>/edit')
def edit_project(project_id):
    with get_db() as db:
        project = get_project(db, project_id)
    if project is None:
        abort(404)
    return render_template(
        'projects/form.html',
        project=project,
        action_url=url_for('projects.update_project_route', project_id=project['id']),
    )


@projects_bp.route('/<int:project_id>', methods=['POST'])
def update_project_route(project_id):
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()

    if not name:
        flash('Project name is required.', 'error')
        return redirect(url_for('projects.edit_project', project_id=project_id))

    with get_db(immediate=True) as db:
        project = get_project(db, project_id)
        if project is None:
            abort(404)
        update_project(db, project_id, name, description)
    return redirect(url_for('projects.show_project', project_id=project_id))


@projects_bp.route('/<int:project_id>/delete', methods=['POST'])
def delete_project_route(project_id):
    with get_db(immediate=True) as db:
        project = get_project(db, project_id)
        if project is None:
            abort(404)
        delete_project(db, project_id)
    return redirect(url_for('projects.list_projects'))
