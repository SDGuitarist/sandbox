from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.db import get_db
from app.models.purchase_order_models import (
    create_purchase_order,
    get_all_purchase_orders,
    get_purchase_order,
    get_purchase_order_items,
    set_purchase_order_items,
    update_purchase_order_total,
    submit_purchase_order,
    receive_purchase_order,
    close_purchase_order,
)
from app.models.supplier_models import get_all_suppliers
from app.models.ingredient_models import get_all_ingredients

bp = Blueprint('purchase_orders', __name__)


@bp.route('/')
def list_orders():
    conn = get_db()
    orders = get_all_purchase_orders(conn)
    return render_template('purchase_orders/list.html', orders=orders)


@bp.route('/create', methods=['GET'])
def create_form():
    conn = get_db()
    suppliers = get_all_suppliers(conn)
    ingredients = get_all_ingredients(conn)
    return render_template(
        'purchase_orders/form.html',
        order=None,
        items=[],
        suppliers=suppliers,
        ingredients=ingredients,
    )


@bp.route('/create', methods=['POST'])
def create():
    conn = get_db()

    # Validate supplier_id
    try:
        supplier_id = int(request.form.get('supplier_id', 0))
        if supplier_id < 1:
            raise ValueError
    except (ValueError, TypeError):
        flash('Please select a supplier.', 'error')
        return redirect(url_for('purchase_orders.create_form'))

    notes = request.form.get('notes', '').strip()[:500]

    # Parse parallel arrays
    ingredient_ids_raw = request.form.getlist('ingredient_ids[]')
    quantities_raw = request.form.getlist('quantities[]')
    unit_costs_raw = request.form.getlist('unit_costs[]')

    # FC4: Validate parallel array lengths before zip
    if not (len(ingredient_ids_raw) == len(quantities_raw) == len(unit_costs_raw)):
        flash('Form data mismatch. Please try again.', 'error')
        return redirect(url_for('purchase_orders.create_form'))

    # Parse and validate line items
    ingredient_ids = []
    quantities = []
    unit_costs = []
    for i in range(len(ingredient_ids_raw)):
        try:
            ing_id = int(ingredient_ids_raw[i])
            qty = float(quantities_raw[i])
            cost_cents = int(round(float(unit_costs_raw[i]) * 100))
            if ing_id < 1 or qty <= 0 or cost_cents < 0:
                raise ValueError
            ingredient_ids.append(ing_id)
            quantities.append(qty)
            unit_costs.append(cost_cents)
        except (ValueError, TypeError):
            flash('Invalid line item data. Please check quantities and costs.', 'error')
            return redirect(url_for('purchase_orders.create_form'))

    conn.execute("BEGIN")
    po_id = create_purchase_order(conn, supplier_id, notes)
    if ingredient_ids:
        set_purchase_order_items(conn, po_id, ingredient_ids, quantities, unit_costs)
        update_purchase_order_total(conn, po_id)
    conn.commit()

    flash('Purchase order created successfully.', 'success')
    return redirect(url_for('purchase_orders.detail', id=po_id))


@bp.route('/<int:id>')
def detail(id):
    conn = get_db()
    order = get_purchase_order(conn, id)
    if order is None:
        flash('Purchase order not found.', 'error')
        return redirect(url_for('purchase_orders.list_orders'))
    items = get_purchase_order_items(conn, id)
    return render_template('purchase_orders/detail.html', order=order, items=items)


@bp.route('/<int:id>/edit', methods=['GET'])
def edit_form(id):
    conn = get_db()
    order = get_purchase_order(conn, id)
    if order is None:
        flash('Purchase order not found.', 'error')
        return redirect(url_for('purchase_orders.list_orders'))
    if order['status'] != 'draft':
        flash('Only draft purchase orders can be edited.', 'error')
        return redirect(url_for('purchase_orders.detail', id=id))
    items = get_purchase_order_items(conn, id)
    suppliers = get_all_suppliers(conn)
    ingredients = get_all_ingredients(conn)
    return render_template(
        'purchase_orders/form.html',
        order=order,
        items=items,
        suppliers=suppliers,
        ingredients=ingredients,
    )


@bp.route('/<int:id>/edit', methods=['POST'])
def edit(id):
    conn = get_db()
    order = get_purchase_order(conn, id)
    if order is None:
        flash('Purchase order not found.', 'error')
        return redirect(url_for('purchase_orders.list_orders'))
    if order['status'] != 'draft':
        flash('Only draft purchase orders can be edited.', 'error')
        return redirect(url_for('purchase_orders.detail', id=id))

    # Validate supplier_id
    try:
        supplier_id = int(request.form.get('supplier_id', 0))
        if supplier_id < 1:
            raise ValueError
    except (ValueError, TypeError):
        flash('Please select a supplier.', 'error')
        return redirect(url_for('purchase_orders.edit_form', id=id))

    notes = request.form.get('notes', '').strip()[:500]

    # Parse parallel arrays
    ingredient_ids_raw = request.form.getlist('ingredient_ids[]')
    quantities_raw = request.form.getlist('quantities[]')
    unit_costs_raw = request.form.getlist('unit_costs[]')

    # FC4: Validate parallel array lengths before zip
    if not (len(ingredient_ids_raw) == len(quantities_raw) == len(unit_costs_raw)):
        flash('Form data mismatch. Please try again.', 'error')
        return redirect(url_for('purchase_orders.edit_form', id=id))

    # Parse and validate line items
    ingredient_ids = []
    quantities = []
    unit_costs = []
    for i in range(len(ingredient_ids_raw)):
        try:
            ing_id = int(ingredient_ids_raw[i])
            qty = float(quantities_raw[i])
            cost_cents = int(round(float(unit_costs_raw[i]) * 100))
            if ing_id < 1 or qty <= 0 or cost_cents < 0:
                raise ValueError
            ingredient_ids.append(ing_id)
            quantities.append(qty)
            unit_costs.append(cost_cents)
        except (ValueError, TypeError):
            flash('Invalid line item data. Please check quantities and costs.', 'error')
            return redirect(url_for('purchase_orders.edit_form', id=id))

    conn.execute("BEGIN")
    conn.execute(
        "UPDATE purchase_orders SET supplier_id = ?, notes = ?, updated_at = datetime('now') WHERE id = ?",
        (supplier_id, notes, id),
    )
    set_purchase_order_items(conn, id, ingredient_ids, quantities, unit_costs)
    update_purchase_order_total(conn, id)
    conn.commit()

    flash('Purchase order updated successfully.', 'success')
    return redirect(url_for('purchase_orders.detail', id=id))


@bp.route('/<int:id>/submit', methods=['POST'])
def submit(id):
    conn = get_db()
    order = get_purchase_order(conn, id)
    if order is None:
        flash('Purchase order not found.', 'error')
        return redirect(url_for('purchase_orders.list_orders'))
    if order['status'] != 'draft':
        flash('Only draft purchase orders can be submitted.', 'error')
        return redirect(url_for('purchase_orders.detail', id=id))

    conn.execute("BEGIN")
    submit_purchase_order(conn, id)
    conn.commit()

    flash('Purchase order submitted successfully.', 'success')
    return redirect(url_for('purchase_orders.detail', id=id))


@bp.route('/<int:id>/receive', methods=['POST'])
def receive(id):
    conn = get_db()
    order = get_purchase_order(conn, id)
    if order is None:
        flash('Purchase order not found.', 'error')
        return redirect(url_for('purchase_orders.list_orders'))
    if order['status'] != 'submitted':
        flash('Only submitted purchase orders can be received.', 'error')
        return redirect(url_for('purchase_orders.detail', id=id))

    # FC29: BEGIN IMMEDIATE for atomic multi-table operation (PO + stock movements)
    conn.execute("BEGIN IMMEDIATE")
    try:
        receive_purchase_order(conn, id)
        conn.commit()
    except Exception:
        conn.rollback()
        flash('Operation failed. Please try again.', 'error')
        return redirect(url_for('purchase_orders.detail', id=id))

    flash('Purchase order received. Stock updated.', 'success')
    return redirect(url_for('purchase_orders.detail', id=id))


@bp.route('/<int:id>/close', methods=['POST'])
def close(id):
    conn = get_db()
    order = get_purchase_order(conn, id)
    if order is None:
        flash('Purchase order not found.', 'error')
        return redirect(url_for('purchase_orders.list_orders'))
    if order['status'] != 'received':
        flash('Only received purchase orders can be closed.', 'error')
        return redirect(url_for('purchase_orders.detail', id=id))

    conn.execute("BEGIN")
    close_purchase_order(conn, id)
    conn.commit()

    flash('Purchase order closed.', 'success')
    return redirect(url_for('purchase_orders.detail', id=id))
