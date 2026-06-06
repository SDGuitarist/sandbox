from flask import Blueprint, render_template

from app import get_db, login_required
from app.gig_models import (
    count_played_gigs,
    total_revenue_cents,
    top_venues,
    recent_gigs,
    monthly_revenue,
)
from app.outcome_models import avg_audience_energy, total_tips_cents

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')


@dashboard_bp.route('/')
@login_required
def index():
    conn = get_db()
    return render_template(
        'dashboard/index.html',
        played_count=count_played_gigs(conn),
        total_revenue_cents=total_revenue_cents(conn),
        avg_audience_energy=avg_audience_energy(conn),
        total_tips_cents=total_tips_cents(conn),
        top_venues=top_venues(conn, 5),
        recent_gigs=recent_gigs(conn, 10),
        monthly_revenue=monthly_revenue(conn, 6),
    )
