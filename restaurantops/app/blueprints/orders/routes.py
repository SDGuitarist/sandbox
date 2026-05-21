from flask import Blueprint, render_template, request, redirect, url_for, flash

from app.db import get_db
from app.models.order_models import (
    create_order,
    get_all_orders,
    get_order,
    get_order_items,
    set_order_items,
    start_preparing_order,
    mark_order_ready,
    mark_order_served,
    close_order as close_order_model,
    cancel_order as cancel_order_model,
)
from app.models.menu_models import get_all_menu_items
from app.models.table_models import get_all_tables

bp = Blueprint('orders', __name__)


@bp.route('/')
def list_orders():
    conn = get_db()
    orders = get_all_orders(conn)
    return render_template('orders/list.html', orders=orders)


@bp.route('/kitchen')
def kitchen_board():
    conn = get_db()
    pending = get_all_orders(conn, status='pending')
    preparing = get_all_orders(conn, status='preparing')
    ready = get_all_orders(conn, status='ready')
    return render_template(
        'orders/kitchen.html',
        pending=pending,
        preparing=preparing,
        ready=ready,
    )


@bp.route('/create', methods=['GET'])
def create_form():
    conn = get_db()
    menu_items = get_all_menu_items(conn)
    tables = get_all_tables(conn)
    return render_template(
        'orders/form.html',
        order=None,
        items=[],
        menu_items=menu_items,
        tables=tables,
    )


@bp.route('/create', methods=['POST'])
def create():
    conn = get_db()

    table_id_raw = request.form.get('table_id', '')
    table_id = None
    if table_id_raw:
        try:
            table_id = int(table_id_raw)
        except (ValueError, TypeError):
            table_id = None

    notes = request.form.get('notes', '').strip()[:500]

    menu_item_ids = request.form.getlist('menu_item_ids[]')
    quantities = request.form.getlist('quantities[]')

    if len(menu_item_ids) != len(quantities):
        flash('Form data mismatch. Please try again.', 'error')
        return redirect(request.url)

    if not menu_item_ids:
        flash('At least one menu item is required.', 'error')
        return redirect(request.url)

    conn.execute("BEGIN")
    order_id = create_order(conn, table_id, notes)
    int_ids = []
    int_qtys = []
    for mid, qty in zip(menu_item_ids, quantities):
        try:
            int_ids.append(int(mid))
            q = int(qty)
            if q < 1:
                q = 1
            int_qtys.append(q)
        except (ValueError, TypeError):
            conn.rollback()
            flash('Invalid item data. Please try again.', 'error')
            return redirect(request.url)

    set_order_items(conn, order_id, int_ids, int_qtys)
    conn.commit()

    flash('Order created successfully.', 'success')
    return redirect(url_for('orders.detail', id=order_id))


@bp.route('/<int:id>')
def detail(id):
    conn = get_db()
    order = get_order(conn, id)
    if order is None:
        flash('Order not found.', 'error')
        return redirect(url_for('orders.list_orders'))
    items = get_order_items(conn, id)
    return render_template('orders/detail.html', order=order, items=items)


@bp.route('/<int:id>/edit', methods=['GET'])
def edit_form(id):
    conn = get_db()
    order = get_order(conn, id)
    if order is None:
        flash('Order not found.', 'error')
        return redirect(url_for('orders.list_orders'))
    items = get_order_items(conn, id)
    menu_items = get_all_menu_items(conn)
    tables = get_all_tables(conn)
    return render_template(
        'orders/form.html',
        order=order,
        items=items,
        menu_items=menu_items,
        tables=tables,
    )


@bp.route('/<int:id>/edit', methods=['POST'])
def edit(id):
    conn = get_db()
    order = get_order(conn, id)
    if order is None:
        flash('Order not found.', 'error')
        return redirect(url_for('orders.list_orders'))

    if order['status'] != 'pending':
        flash('Only pending orders can be edited.', 'error')
        return redirect(url_for('orders.detail', id=id))

    table_id_raw = request.form.get('table_id', '')
    table_id = None
    if table_id_raw:
        try:
            table_id = int(table_id_raw)
        except (ValueError, TypeError):
            table_id = None

    notes = request.form.get('notes', '').strip()[:500]

    menu_item_ids = request.form.getlist('menu_item_ids[]')
    quantities = request.form.getlist('quantities[]')

    if len(menu_item_ids) != len(quantities):
        flash('Form data mismatch. Please try again.', 'error')
        return redirect(request.url)

    if not menu_item_ids:
        flash('At least one menu item is required.', 'error')
        return redirect(request.url)

    conn.execute("BEGIN")
    conn.execute(
        "UPDATE orders SET table_id = ?, notes = ?, updated_at = datetime('now') WHERE id = ?",
        (table_id, notes, id),
    )

    int_ids = []
    int_qtys = []
    for mid, qty in zip(menu_item_ids, quantities):
        try:
            int_ids.append(int(mid))
            q = int(qty)
            if q < 1:
                q = 1
            int_qtys.append(q)
        except (ValueError, TypeError):
            conn.rollback()
            flash('Invalid item data. Please try again.', 'error')
            return redirect(request.url)

    set_order_items(conn, id, int_ids, int_qtys)
    conn.commit()

    flash('Order updated successfully.', 'success')
    return redirect(url_for('orders.detail', id=id))


@bp.route('/<int:id>/prepare', methods=['POST'])
def prepare(id):
    conn = get_db()
    order = get_order(conn, id)
    if order is None:
        flash('Order not found.', 'error')
        return redirect(url_for('orders.list_orders'))
    try:
        # start_preparing_order owns its own BEGIN IMMEDIATE + commit
        start_preparing_order(conn, id)
        flash('Order is now being prepared.', 'info')
    except Exception:
        flash('Could not start preparing order. Please try again.', 'error')
    return redirect(url_for('orders.detail', id=id))


@bp.route('/<int:id>/ready', methods=['POST'])
def ready(id):
    conn = get_db()
    order = get_order(conn, id)
    if order is None:
        flash('Order not found.', 'error')
        return redirect(url_for('orders.list_orders'))
    try:
        conn.execute("BEGIN")
        mark_order_ready(conn, id)
        conn.commit()
        flash('Order is ready for serving.', 'info')
    except Exception:
        conn.rollback()
        flash('Could not mark order as ready. Please try again.', 'error')
    return redirect(url_for('orders.detail', id=id))


@bp.route('/<int:id>/serve', methods=['POST'])
def serve(id):
    conn = get_db()
    order = get_order(conn, id)
    if order is None:
        flash('Order not found.', 'error')
        return redirect(url_for('orders.list_orders'))
    try:
        conn.execute("BEGIN")
        mark_order_served(conn, id)
        conn.commit()
        flash('Order has been served.', 'info')
    except Exception:
        conn.rollback()
        flash('Could not mark order as served. Please try again.', 'error')
    return redirect(url_for('orders.detail', id=id))


@bp.route('/<int:id>/close', methods=['POST'])
def close_order(id):
    conn = get_db()
    order = get_order(conn, id)
    if order is None:
        flash('Order not found.', 'error')
        return redirect(url_for('orders.list_orders'))
    try:
        conn.execute("BEGIN")
        close_order_model(conn, id)
        conn.commit()
        flash('Order closed.', 'success')
    except Exception:
        conn.rollback()
        flash('Could not close order. Please try again.', 'error')
    return redirect(url_for('orders.detail', id=id))


@bp.route('/<int:id>/cancel', methods=['POST'])
def cancel(id):
    conn = get_db()
    order = get_order(conn, id)
    if order is None:
        flash('Order not found.', 'error')
        return redirect(url_for('orders.list_orders'))
    try:
        # cancel_order owns its own BEGIN IMMEDIATE + commit
        cancel_order_model(conn, id)
        flash('Order cancelled.', 'warning')
    except Exception:
        flash('Could not cancel order. Please try again.', 'error')
    return redirect(url_for('orders.detail', id=id))
