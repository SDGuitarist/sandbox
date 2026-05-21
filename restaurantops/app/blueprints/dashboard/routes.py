from datetime import date

from flask import Blueprint, render_template

from app.db import get_db
from app.models.dashboard_models import get_dashboard_stats, get_todays_specials
from app.models.inventory_models import get_low_stock_items
from app.models.order_models import get_all_orders
from app.models.reservation_models import get_all_reservations

bp = Blueprint('dashboard', __name__)


@bp.route('/')
def index():
    """Dashboard home -- summary cards, specials, pending orders, low stock, reservations."""
    conn = get_db()
    today_str = date.today().isoformat()

    return render_template(
        'dashboard/index.html',
        stats=get_dashboard_stats(conn),
        active_specials=get_todays_specials(conn),
        low_stock=get_low_stock_items(conn),
        pending_orders=get_all_orders(conn, status='pending'),
        todays_reservations=get_all_reservations(conn, date=today_str),
    )
