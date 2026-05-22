from flask import Blueprint, render_template

from app.db import get_db
from app.auth import login_required
from app.models.batch_models import get_batches_by_statuses
from app.models.ingredient_models import get_low_stock_ingredients
from app.models.tap_models import get_all_taps
from app.models.sale_models import get_today_sales_total

bp = Blueprint('dashboard', __name__)


@bp.route('/')
@login_required
def index():
    conn = get_db()

    groups = get_batches_by_statuses(conn, ['brewing', 'fermenting', 'conditioning', 'ready', 'tapped'])
    active_batches = groups['brewing'] + groups['fermenting'] + groups['conditioning']
    ready_batches = groups['ready']
    tapped_batches = groups['tapped']
    low_stock = get_low_stock_ingredients(conn)
    taps = get_all_taps(conn)
    today_sales = get_today_sales_total(conn)

    return render_template(
        'dashboard/index.html',
        active_batches=active_batches,
        ready_batches=ready_batches,
        tapped_batches=tapped_batches,
        low_stock=low_stock,
        taps=taps,
        today_sales=today_sales,
    )
