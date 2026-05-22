from flask import Blueprint, render_template, request, redirect, url_for, flash, abort

from app.db import get_db
from app.auth import login_required
from app.models import (
    create_trainer,
    get_trainer,
    get_all_trainers,
    update_trainer,
    delete_trainer,
)

bp = Blueprint('trainers', __name__)


@bp.route('/')
@login_required
def list_trainers():
    conn = get_db()
    trainers = get_all_trainers(conn)
    return render_template('trainers/list.html', trainers=trainers)


@bp.route('/new')
@login_required
def new_trainer():
    return render_template('trainers/form.html', trainer=None)


@bp.route('/', methods=['POST'], endpoint='create_trainer')
@login_required
def create_trainer_view():
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    specializations = request.form.get('specializations', '').strip()
    bio = request.form.get('bio', '').strip()

    if not name or len(name) > 100:
        flash('Name is required.', 'error')
        return redirect(url_for('trainers.new_trainer'))

    if not email or len(email) > 200 or '@' not in email:
        flash('Valid email is required.', 'error')
        return redirect(url_for('trainers.new_trainer'))

    if len(specializations) > 500:
        flash('Specializations too long.', 'error')
        return redirect(url_for('trainers.new_trainer'))

    conn = get_db()
    trainer_id = create_trainer(conn, name, email, phone, specializations, bio)
    flash('Trainer created successfully.', 'success')
    return redirect(url_for('trainers.detail', trainer_id=trainer_id))


@bp.route('/<int:trainer_id>')
@login_required
def detail(trainer_id):
    conn = get_db()
    trainer = get_trainer(conn, trainer_id)
    if trainer is None:
        abort(404)
    return render_template('trainers/detail.html', trainer=trainer)


@bp.route('/<int:trainer_id>/edit')
@login_required
def edit_trainer(trainer_id):
    conn = get_db()
    trainer = get_trainer(conn, trainer_id)
    if trainer is None:
        abort(404)
    return render_template('trainers/form.html', trainer=trainer)


@bp.route('/<int:trainer_id>/edit', methods=['POST'], endpoint='update_trainer')
@login_required
def update_trainer_view(trainer_id):
    conn = get_db()
    trainer = get_trainer(conn, trainer_id)
    if trainer is None:
        abort(404)

    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    specializations = request.form.get('specializations', '').strip()
    bio = request.form.get('bio', '').strip()
    status = request.form.get('status', '').strip()

    if not name or len(name) > 100:
        flash('Name is required.', 'error')
        return redirect(url_for('trainers.edit_trainer', trainer_id=trainer_id))

    if not email or len(email) > 200 or '@' not in email:
        flash('Valid email is required.', 'error')
        return redirect(url_for('trainers.edit_trainer', trainer_id=trainer_id))

    if len(specializations) > 500:
        flash('Specializations too long.', 'error')
        return redirect(url_for('trainers.edit_trainer', trainer_id=trainer_id))

    if status not in ('active', 'inactive'):
        flash('Invalid status.', 'error')
        return redirect(url_for('trainers.edit_trainer', trainer_id=trainer_id))

    update_trainer(conn, trainer_id, name, email, phone, specializations, bio, status)
    flash('Trainer updated successfully.', 'success')
    return redirect(url_for('trainers.detail', trainer_id=trainer_id))


@bp.route('/<int:trainer_id>/delete', methods=['POST'], endpoint='delete_trainer')
@login_required
def delete_trainer_view(trainer_id):
    conn = get_db()
    trainer = get_trainer(conn, trainer_id)
    if trainer is None:
        abort(404)

    delete_trainer(conn, trainer_id)
    flash('Trainer deleted successfully.', 'success')
    return redirect(url_for('trainers.list_trainers'))
