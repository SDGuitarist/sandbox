from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.db import get_db
from app.models.inventory_models import (
    get_inventory_status,
    get_low_stock_items,
    get_stock_movements,
    record_stock_movement,
)
from app.models.ingredient_models import get_ingredient

bp = Blueprint('inventory', __name__)


@bp.route('/')
def index():
    """Show all inventory status."""
    conn = get_db()
    inventory = get_inventory_status(conn)
    return render_template('inventory/index.html', inventory=inventory)


@bp.route('/low-stock')
def low_stock():
    """Show ingredients below their low-stock threshold."""
    conn = get_db()
    items = get_low_stock_items(conn)
    return render_template('inventory/low_stock.html', items=items)


@bp.route('/<int:ingredient_id>/movements')
def movements(ingredient_id):
    """Show stock movement history for one ingredient."""
    conn = get_db()
    ingredient = get_ingredient(conn, ingredient_id)
    if ingredient is None:
        flash('Ingredient not found.', 'error')
        return redirect(url_for('inventory.index'))
    movements_list = get_stock_movements(conn, ingredient_id)
    return render_template(
        'inventory/movements.html',
        ingredient=ingredient,
        movements=movements_list,
    )


@bp.route('/<int:ingredient_id>/adjust', methods=['POST'])
def adjust(ingredient_id):
    """Create a manual adjustment or waste stock movement."""
    conn = get_db()
    ingredient = get_ingredient(conn, ingredient_id)
    if ingredient is None:
        flash('Ingredient not found.', 'error')
        return redirect(url_for('inventory.index'))

    # Validate movement_type
    movement_type = request.form.get('movement_type', '').strip()
    if movement_type not in ('adjustment', 'waste'):
        flash('Invalid movement type. Must be adjustment or waste.', 'error')
        return redirect(url_for('inventory.movements', ingredient_id=ingredient_id))

    # Validate quantity (can be negative for waste)
    raw_qty = request.form.get('quantity', '').strip()
    try:
        quantity = float(raw_qty)
    except (ValueError, TypeError):
        flash('Quantity must be a number.', 'error')
        return redirect(url_for('inventory.movements', ingredient_id=ingredient_id))

    if quantity == 0:
        flash('Quantity cannot be zero.', 'error')
        return redirect(url_for('inventory.movements', ingredient_id=ingredient_id))

    notes = request.form.get('notes', '').strip()[:500]

    conn.execute("BEGIN")
    try:
        record_stock_movement(
            conn,
            ingredient_id=ingredient_id,
            movement_type=movement_type,
            quantity=quantity,
            reference_type='manual',
            reference_id=None,
            notes=notes if notes else None,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        flash('Failed to record adjustment. Please try again.', 'error')
        return redirect(url_for('inventory.movements', ingredient_id=ingredient_id))

    flash('Stock adjustment recorded.', 'success')
    return redirect(url_for('inventory.movements', ingredient_id=ingredient_id))
