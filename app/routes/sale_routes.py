import math
import sqlite3

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort

from app.db import get_db
from app.auth import login_required
from app.models.sale_models import get_all_sales, get_sale, create_sale
from app.models.tap_models import get_all_taps

bp = Blueprint('sales', __name__)

VALID_SALE_TYPES = ('pint', 'half_pint', 'growler', 'case')


@bp.route('/')
@login_required
def list():
    conn = get_db()
    sales = get_all_sales(conn)
    return render_template('sales/list.html', sales=sales)


@bp.route('/new')
@login_required
def new():
    conn = get_db()
    active_taps = get_all_taps(conn)
    return render_template('sales/form.html', active_taps=active_taps)


@bp.route('/', methods=['POST'])
@login_required
def create():
    conn = get_db()

    # Validate tap_id
    try:
        tap_id = int(request.form.get('tap_id', ''))
    except (ValueError, TypeError):
        flash('Invalid tap or no batch assigned', 'error')
        return redirect(url_for('sales.new'))

    # Validate quantity_oz
    try:
        quantity_oz = float(request.form.get('quantity_oz', ''))
        if not math.isfinite(quantity_oz) or quantity_oz <= 0:
            raise ValueError
    except (ValueError, TypeError):
        flash('Invalid quantity', 'error')
        return redirect(url_for('sales.new'))

    # Validate sale_type
    sale_type = request.form.get('sale_type', '')
    if sale_type not in VALID_SALE_TYPES:
        flash('Invalid sale type', 'error')
        return redirect(url_for('sales.new'))

    # Validate price (money parsing: dollars input -> cents integer)
    try:
        val = float(request.form.get('price', '0'))
        if not math.isfinite(val) or val < 0:
            raise ValueError
        price_cents = round(val * 100)
    except (ValueError, TypeError):
        flash('Invalid price', 'error')
        return redirect(url_for('sales.new'))

    # create_sale is NEEDS-BEGIN-IMMEDIATE -- do NOT call conn.commit()
    sale_id = create_sale(conn, tap_id, quantity_oz, sale_type, price_cents)
    if sale_id is None:
        flash('Insufficient remaining volume', 'error')
        return redirect(url_for('sales.new'))

    flash('Sale recorded successfully.', 'success')
    return redirect(url_for('sales.detail', sale_id=sale_id))


@bp.route('/<int:sale_id>')
@login_required
def detail(sale_id):
    conn = get_db()
    sale = get_sale(conn, sale_id)
    if sale is None:
        abort(404)
    return render_template('sales/detail.html', sale=sale)
