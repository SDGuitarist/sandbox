"""Menu blueprint: CRUD for menu items and categories."""
from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.db import get_db
from app.models.menu_models import (
    create_menu_item,
    delete_menu_item,
    get_all_menu_items,
    get_menu_item,
    get_menu_item_allergens,
    get_menu_item_cost,
    update_menu_item,
)
from app.models.category_models import (
    create_category as model_create_category,
    delete_category as model_delete_category,
    get_all_categories,
    get_category,
    update_category as model_update_category,
)
from app.models.recipe_models import get_all_recipes
from app.models.review_models import get_menu_item_avg_rating

bp = Blueprint('menu', __name__)


# ---------------------------------------------------------------------------
# Menu Items
# ---------------------------------------------------------------------------

@bp.route('/')
def list_items():
    """GET /menu -- list all menu items."""
    conn = get_db()
    items = get_all_menu_items(conn)
    categories = get_all_categories(conn)
    return render_template('menu/list.html', items=items, categories=categories)


@bp.route('/create', methods=['GET'])
def create_form():
    """GET /menu/create -- show create form."""
    conn = get_db()
    categories = get_all_categories(conn)
    recipes = get_all_recipes(conn)
    return render_template('menu/form.html', item=None, categories=categories, recipes=recipes)


@bp.route('/create', methods=['POST'])
def create():
    """POST /menu/create -- create a new menu item."""
    conn = get_db()

    name = request.form.get('name', '').strip()[:200]
    if not name:
        flash('Name is required.', 'error')
        return redirect(url_for('menu.create_form'))

    description = request.form.get('description', '').strip()[:2000]

    # Price: accept decimal dollars, convert to integer cents
    raw_price = request.form.get('price', '0')
    try:
        price_cents = int(round(float(raw_price) * 100))
        if price_cents < 0:
            price_cents = 0
    except (ValueError, TypeError):
        price_cents = 0

    # Category (optional)
    raw_cat = request.form.get('category_id', '')
    try:
        category_id = int(raw_cat) if raw_cat else None
    except (ValueError, TypeError):
        category_id = None

    # Recipe (optional)
    raw_recipe = request.form.get('recipe_id', '')
    try:
        recipe_id = int(raw_recipe) if raw_recipe else None
    except (ValueError, TypeError):
        recipe_id = None

    # Availability checkbox
    is_available = 1 if request.form.get('is_available') else 0

    conn.execute("BEGIN")
    create_menu_item(conn, name, description, price_cents, category_id, recipe_id, is_available)
    conn.commit()

    flash('Menu item created successfully.', 'success')
    return redirect(url_for('menu.list_items'))


@bp.route('/<int:id>')
def detail(id):
    """GET /menu/<id> -- show menu item detail."""
    conn = get_db()
    item = get_menu_item(conn, id)
    if item is None:
        flash('Item not found.', 'error')
        return redirect(url_for('menu.list_items'))

    allergens = get_menu_item_allergens(conn, id)
    cost_cents = get_menu_item_cost(conn, id)
    avg_rating = get_menu_item_avg_rating(conn, id)

    return render_template(
        'menu/detail.html',
        item=item,
        allergens=allergens,
        cost_cents=cost_cents,
        avg_rating=avg_rating,
    )


@bp.route('/<int:id>/edit', methods=['GET'])
def edit_form(id):
    """GET /menu/<id>/edit -- show edit form."""
    conn = get_db()
    item = get_menu_item(conn, id)
    if item is None:
        flash('Item not found.', 'error')
        return redirect(url_for('menu.list_items'))

    categories = get_all_categories(conn)
    recipes = get_all_recipes(conn)
    return render_template('menu/form.html', item=item, categories=categories, recipes=recipes)


@bp.route('/<int:id>/edit', methods=['POST'])
def edit(id):
    """POST /menu/<id>/edit -- update a menu item."""
    conn = get_db()
    item = get_menu_item(conn, id)
    if item is None:
        flash('Item not found.', 'error')
        return redirect(url_for('menu.list_items'))

    name = request.form.get('name', '').strip()[:200]
    if not name:
        flash('Name is required.', 'error')
        return redirect(url_for('menu.edit_form', id=id))

    description = request.form.get('description', '').strip()[:2000]

    raw_price = request.form.get('price', '0')
    try:
        price_cents = int(round(float(raw_price) * 100))
        if price_cents < 0:
            price_cents = 0
    except (ValueError, TypeError):
        price_cents = 0

    raw_cat = request.form.get('category_id', '')
    try:
        category_id = int(raw_cat) if raw_cat else None
    except (ValueError, TypeError):
        category_id = None

    raw_recipe = request.form.get('recipe_id', '')
    try:
        recipe_id = int(raw_recipe) if raw_recipe else None
    except (ValueError, TypeError):
        recipe_id = None

    is_available = 1 if request.form.get('is_available') else 0

    conn.execute("BEGIN")
    update_menu_item(conn, id, name, description, price_cents, category_id, recipe_id, is_available)
    conn.commit()

    flash('Menu item updated successfully.', 'success')
    return redirect(url_for('menu.detail', id=id))


@bp.route('/<int:id>/delete', methods=['POST'])
def delete(id):
    """POST /menu/<id>/delete -- delete a menu item."""
    conn = get_db()
    item = get_menu_item(conn, id)
    if item is None:
        flash('Item not found.', 'error')
        return redirect(url_for('menu.list_items'))

    conn.execute("BEGIN")
    try:
        delete_menu_item(conn, id)
        conn.commit()
    except Exception:
        conn.rollback()
        flash('Cannot delete this menu item because it has existing orders.', 'error')
        return redirect(url_for('menu.detail', id=id))

    flash('Menu item deleted successfully.', 'success')
    return redirect(url_for('menu.list_items'))


# ---------------------------------------------------------------------------
# Categories (inline management on /menu/categories)
# ---------------------------------------------------------------------------

@bp.route('/categories')
def list_categories():
    """GET /menu/categories -- list and manage categories."""
    conn = get_db()
    categories = get_all_categories(conn)
    return render_template('menu/categories.html', categories=categories)


@bp.route('/categories', methods=['POST'])
def create_category():
    """POST /menu/categories -- create a new category."""
    conn = get_db()

    name = request.form.get('name', '').strip()[:200]
    if not name:
        flash('Category name is required.', 'error')
        return redirect(url_for('menu.list_categories'))

    raw_sort = request.form.get('sort_order', '0')
    try:
        sort_order = int(raw_sort)
    except (ValueError, TypeError):
        sort_order = 0

    conn.execute("BEGIN")
    model_create_category(conn, name, sort_order)
    conn.commit()

    flash('Category created successfully.', 'success')
    return redirect(url_for('menu.list_categories'))


@bp.route('/categories/<int:id>/edit', methods=['POST'])
def edit_category(id):
    """POST /menu/categories/<id>/edit -- update a category."""
    conn = get_db()
    cat = get_category(conn, id)
    if cat is None:
        flash('Category not found.', 'error')
        return redirect(url_for('menu.list_categories'))

    name = request.form.get('name', '').strip()[:200]
    if not name:
        flash('Category name is required.', 'error')
        return redirect(url_for('menu.list_categories'))

    raw_sort = request.form.get('sort_order', '0')
    try:
        sort_order = int(raw_sort)
    except (ValueError, TypeError):
        sort_order = 0

    conn.execute("BEGIN")
    model_update_category(conn, id, name, sort_order)
    conn.commit()

    flash('Category updated successfully.', 'success')
    return redirect(url_for('menu.list_categories'))


@bp.route('/categories/<int:id>/delete', methods=['POST'])
def delete_category(id):
    """POST /menu/categories/<id>/delete -- delete a category."""
    conn = get_db()
    cat = get_category(conn, id)
    if cat is None:
        flash('Category not found.', 'error')
        return redirect(url_for('menu.list_categories'))

    conn.execute("BEGIN")
    model_delete_category(conn, id)
    conn.commit()

    flash('Category deleted successfully.', 'success')
    return redirect(url_for('menu.list_categories'))
