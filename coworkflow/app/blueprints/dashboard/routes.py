from flask import Blueprint, render_template, jsonify

from app.db import get_db
from app.auth import login_required
from app.models.member import count_active_members
from app.models.desk_booking import (
    get_desk_bookings_by_date,
    count_desk_bookings_today,
)
from app.models.room_booking import (
    get_room_bookings_by_date,
    count_room_bookings_today,
)
from app.models.invoice import get_pending_invoice_count
from app.models.payment import get_total_revenue_this_month
from app.models.amenity import count_amenities
from datetime import date

bp = Blueprint("dashboard", __name__)


@bp.route("/health")
def health():
    return jsonify({"status": "ok"}), 200


@bp.route("/")
@login_required
def index():
    conn = get_db()
    today = date.today().isoformat()
    return render_template(
        "dashboard/index.html",
        active_members=count_active_members(conn),
        revenue_cents=get_total_revenue_this_month(conn),
        desk_bookings_today=count_desk_bookings_today(conn),
        room_bookings_today=count_room_bookings_today(conn),
        pending_invoices=get_pending_invoice_count(conn),
        amenity_count=count_amenities(conn),
        today_desk_bookings=get_desk_bookings_by_date(conn, today),
        today_room_bookings=get_room_bookings_by_date(conn, today),
    )
