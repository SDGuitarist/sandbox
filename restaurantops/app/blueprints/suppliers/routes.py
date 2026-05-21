from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.db import get_db
from app.models.supplier_models import (
    create_supplier,
    delete_supplier,
    get_all_suppliers,
    get_supplier,
    update_supplier,
)

bp = Blueprint('suppliers', __name__)


@bp.route('/')
def list_suppliers():
    conn = get_db()
    suppliers = get_all_suppliers(conn)
    return render_template('suppliers/list.html', suppliers=suppliers)


@bp.route('/create')
def create_form():
    return render_template('suppliers/form.html', supplier=None)


@bp.route('/', methods=['POST'])
def create():
    name = request.form.get('name', '').strip()
    contact_name = request.form.get('contact_name', '').strip()
    phone = request.form.get('phone', '').strip()
    email = request.form.get('email', '').strip()
    address = request.form.get('address', '').strip()
    notes = request.form.get('notes', '').strip()

    if not name:
        flash('Name is required.', 'error')
        return render_template('suppliers/form.html', supplier=None)

    conn = get_db()
    conn.execute("BEGIN")
    create_supplier(conn, name, contact_name, phone, email, address, notes)
    conn.commit()

    flash('Supplier created successfully.', 'success')
    return redirect(url_for('suppliers.list_suppliers'))


@bp.route('/<int:id>')
def detail(id):
    conn = get_db()
    supplier = get_supplier(conn, id)
    if supplier is None:
        flash('Supplier not found.', 'error')
        return redirect(url_for('suppliers.list_suppliers'))
    return render_template('suppliers/detail.html', supplier=supplier)


@bp.route('/<int:id>/edit')
def edit_form(id):
    conn = get_db()
    supplier = get_supplier(conn, id)
    if supplier is None:
        flash('Supplier not found.', 'error')
        return redirect(url_for('suppliers.list_suppliers'))
    return render_template('suppliers/form.html', supplier=supplier)


@bp.route('/<int:id>/edit', methods=['POST'])
def edit(id):
    conn = get_db()
    supplier = get_supplier(conn, id)
    if supplier is None:
        flash('Supplier not found.', 'error')
        return redirect(url_for('suppliers.list_suppliers'))

    name = request.form.get('name', '').strip()
    contact_name = request.form.get('contact_name', '').strip()
    phone = request.form.get('phone', '').strip()
    email = request.form.get('email', '').strip()
    address = request.form.get('address', '').strip()
    notes = request.form.get('notes', '').strip()

    if not name:
        flash('Name is required.', 'error')
        return render_template('suppliers/form.html', supplier=supplier)

    conn.execute("BEGIN")
    update_supplier(conn, id, name, contact_name, phone, email, address, notes)
    conn.commit()

    flash('Supplier updated successfully.', 'success')
    return redirect(url_for('suppliers.detail', id=id))


@bp.route('/<int:id>/delete', methods=['POST'])
def delete(id):
    conn = get_db()
    supplier = get_supplier(conn, id)
    if supplier is None:
        flash('Supplier not found.', 'error')
        return redirect(url_for('suppliers.list_suppliers'))

    conn.execute("BEGIN")
    delete_supplier(conn, id)
    conn.commit()

    flash('Supplier deleted successfully.', 'success')
    return redirect(url_for('suppliers.list_suppliers'))
