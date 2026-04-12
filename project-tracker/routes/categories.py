import re

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from app import get_db
from models.categories import (get_all_categories, get_category, create_category,
    update_category, delete_category)
from models.tasks import get_tasks_by_category
from models.activity import log_activity

bp = Blueprint('categories', __name__)

COLOR_RE = re.compile(r'^#[0-9a-fA-F]{6}$')


@bp.route('/')
def list():
    db = get_db()
    categories = get_all_categories(db)
    return render_template('categories/list.html', categories=categories)


@bp.route('/new')
def new():
    return render_template('categories/form.html', category=None)


@bp.route('/new', methods=['POST'])
def create():
    db = get_db()

    name = request.form.get('name', '').strip()[:100]
    if not name:
        flash('Name is required', 'error')
        return redirect(request.url)

    color = request.form.get('color', '#6366f1').strip()
    if not COLOR_RE.match(color):
        color = '#6366f1'

    category_id = create_category(db, name, color)
    log_activity(db, 'category', category_id, 'created', f"Created category '{name}'")
    db.commit()
    flash('Category created', 'success')
    return redirect(url_for('categories.list'))


@bp.route('/<int:category_id>')
def detail(category_id):
    db = get_db()
    category = get_category(db, category_id)
    if category is None:
        abort(404)
    tasks = get_tasks_by_category(db, category_id)
    return render_template('categories/detail.html', category=category, tasks=tasks)


@bp.route('/<int:category_id>/edit')
def edit_form(category_id):
    db = get_db()
    category = get_category(db, category_id)
    if category is None:
        abort(404)
    return render_template('categories/form.html', category=category)


@bp.route('/<int:category_id>/edit', methods=['POST'])
def edit(category_id):
    db = get_db()
    category = get_category(db, category_id)
    if category is None:
        abort(404)

    name = request.form.get('name', '').strip()[:100]
    if not name:
        flash('Name is required', 'error')
        return redirect(request.url)

    color = request.form.get('color', '#6366f1').strip()
    if not COLOR_RE.match(color):
        color = '#6366f1'

    update_category(db, category_id, name, color)
    log_activity(db, 'category', category_id, 'updated', f"Updated category '{name}'")
    db.commit()
    flash('Category updated', 'success')
    return redirect(url_for('categories.detail', category_id=category_id))


@bp.route('/<int:category_id>/delete', methods=['POST'])
def delete(category_id):
    db = get_db()
    category = get_category(db, category_id)
    if category is None:
        abort(404)
    try:
        delete_category(db, category_id)
        log_activity(db, 'category', category_id, 'deleted', f"Deleted category '{category['name']}'")
        db.commit()
        flash('Category deleted', 'success')
    except ValueError:
        flash('Cannot delete category with existing tasks', 'error')
    return redirect(url_for('categories.list'))
