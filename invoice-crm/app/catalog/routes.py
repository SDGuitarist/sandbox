from flask import render_template, request, redirect, url_for, flash, session

from app.db import get_db
from app.helpers import login_required
from . import bp
from .forms import CatalogItemForm


@bp.route('/')
@login_required
def list_items():
    with get_db() as db:
        items = db.execute(
            "SELECT * FROM catalog_items WHERE user_id = ? ORDER BY name",
            (session['user_id'],)
        ).fetchall()
    return render_template('catalog/list.html', items=items)


@bp.route('/new', methods=['GET', 'POST'])
@login_required
def create_item():
    form = CatalogItemForm()
    if form.validate_on_submit():
        unit_price_cents = int(round(float(form.unit_price.data) * 100))
        with get_db() as db:
            db.execute(
                """INSERT INTO catalog_items (user_id, name, description, unit_price_cents, unit)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    session['user_id'],
                    form.name.data.strip(),
                    (form.description.data or '').strip(),
                    unit_price_cents,
                    form.unit.data,
                )
            )
            db.commit()
        flash('Catalog item created successfully.', 'success')
        return redirect(url_for('catalog.list_items'))
    return render_template('catalog/form.html', form=form, editing=False)


@bp.route('/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_item(item_id):
    with get_db() as db:
        item = db.execute(
            "SELECT * FROM catalog_items WHERE id = ? AND user_id = ?",
            (item_id, session['user_id'])
        ).fetchone()

        if not item:
            flash('Catalog item not found.', 'danger')
            return redirect(url_for('catalog.list_items'))

        form = CatalogItemForm()

        if form.validate_on_submit():
            unit_price_cents = int(round(float(form.unit_price.data) * 100))
            db.execute(
                """UPDATE catalog_items
                   SET name = ?, description = ?, unit_price_cents = ?, unit = ?
                   WHERE id = ? AND user_id = ?""",
                (
                    form.name.data.strip(),
                    (form.description.data or '').strip(),
                    unit_price_cents,
                    form.unit.data,
                    item_id,
                    session['user_id'],
                )
            )
            db.commit()
            flash('Catalog item updated successfully.', 'success')
            return redirect(url_for('catalog.list_items'))

        if request.method == 'GET':
            form.name.data = item['name']
            form.description.data = item['description']
            form.unit_price.data = item['unit_price_cents'] / 100
            form.unit.data = item['unit']

    return render_template('catalog/form.html', form=form, editing=True, item=item)


@bp.route('/<int:item_id>/delete', methods=['POST'])
@login_required
def delete_item(item_id):
    with get_db() as db:
        item = db.execute(
            "SELECT * FROM catalog_items WHERE id = ? AND user_id = ?",
            (item_id, session['user_id'])
        ).fetchone()

        if not item:
            flash('Catalog item not found.', 'danger')
            return redirect(url_for('catalog.list_items'))

        db.execute(
            "DELETE FROM catalog_items WHERE id = ? AND user_id = ?",
            (item_id, session['user_id'])
        )
        db.commit()

    flash('Catalog item deleted.', 'success')
    return redirect(url_for('catalog.list_items'))
