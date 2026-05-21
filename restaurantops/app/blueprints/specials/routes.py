from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.db import get_db
from app.models.specials_models import (
    create_special,
    delete_special,
    get_all_specials,
    get_special,
    update_special,
)
from app.models.menu_models import get_all_menu_items

bp = Blueprint('specials', __name__)


@bp.route('/')
def list_specials():
    conn = get_db()
    specials = get_all_specials(conn)
    return render_template('specials/list.html', specials=specials)


@bp.route('/create', methods=['GET'])
def create_form():
    conn = get_db()
    menu_items = get_all_menu_items(conn)
    return render_template('specials/form.html', special=None, menu_items=menu_items)


@bp.route('/create', methods=['POST'])
def create():
    conn = get_db()

    name = request.form.get('name', '').strip()[:200]
    if not name:
        flash('Name is required.', 'error')
        return redirect(request.url)

    description = request.form.get('description', '').strip()[:2000]

    raw = request.form.get('price', '0')
    try:
        price_cents = int(round(float(raw) * 100))
        if price_cents < 0:
            price_cents = 0
    except (ValueError, TypeError):
        price_cents = 0

    menu_item_id_raw = request.form.get('menu_item_id', '')
    menu_item_id = None
    if menu_item_id_raw:
        try:
            menu_item_id = int(menu_item_id_raw)
        except (ValueError, TypeError):
            menu_item_id = None

    start_date = request.form.get('start_date', '').strip()
    end_date = request.form.get('end_date', '').strip()
    if not start_date or not end_date:
        flash('Start date and end date are required.', 'error')
        return redirect(request.url)

    conn.execute("BEGIN")
    create_special(conn, name, description, price_cents, menu_item_id, start_date, end_date)
    conn.commit()

    flash('Special created successfully.', 'success')
    return redirect(url_for('specials.list_specials'))


@bp.route('/<int:id>')
def detail(id):
    conn = get_db()
    special = get_special(conn, id)
    if special is None:
        flash('Special not found.', 'error')
        return redirect(url_for('specials.list_specials'))
    return render_template('specials/detail.html', special=special)


@bp.route('/<int:id>/edit', methods=['GET'])
def edit_form(id):
    conn = get_db()
    special = get_special(conn, id)
    if special is None:
        flash('Special not found.', 'error')
        return redirect(url_for('specials.list_specials'))
    menu_items = get_all_menu_items(conn)
    return render_template('specials/form.html', special=special, menu_items=menu_items)


@bp.route('/<int:id>/edit', methods=['POST'])
def edit(id):
    conn = get_db()
    special = get_special(conn, id)
    if special is None:
        flash('Special not found.', 'error')
        return redirect(url_for('specials.list_specials'))

    name = request.form.get('name', '').strip()[:200]
    if not name:
        flash('Name is required.', 'error')
        return redirect(request.url)

    description = request.form.get('description', '').strip()[:2000]

    raw = request.form.get('price', '0')
    try:
        price_cents = int(round(float(raw) * 100))
        if price_cents < 0:
            price_cents = 0
    except (ValueError, TypeError):
        price_cents = 0

    menu_item_id_raw = request.form.get('menu_item_id', '')
    menu_item_id = None
    if menu_item_id_raw:
        try:
            menu_item_id = int(menu_item_id_raw)
        except (ValueError, TypeError):
            menu_item_id = None

    start_date = request.form.get('start_date', '').strip()
    end_date = request.form.get('end_date', '').strip()
    if not start_date or not end_date:
        flash('Start date and end date are required.', 'error')
        return redirect(request.url)

    is_active = 1 if request.form.get('is_active') else 0

    conn.execute("BEGIN")
    update_special(conn, id, name, description, price_cents, menu_item_id, start_date, end_date, is_active)
    conn.commit()

    flash('Special updated successfully.', 'success')
    return redirect(url_for('specials.detail', id=id))


@bp.route('/<int:id>/delete', methods=['POST'])
def delete(id):
    conn = get_db()
    special = get_special(conn, id)
    if special is None:
        flash('Special not found.', 'error')
        return redirect(url_for('specials.list_specials'))

    conn.execute("BEGIN")
    delete_special(conn, id)
    conn.commit()

    flash('Special deleted successfully.', 'success')
    return redirect(url_for('specials.list_specials'))
