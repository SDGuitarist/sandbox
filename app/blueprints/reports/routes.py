"""Reports blueprint: budget summary, DOOD grid, production progress."""

from flask import Blueprint, render_template, g

from app.blueprints.auth.routes import login_required, require_project_member, require_role
from app.database import get_db
from app.models.report_models import get_dood_grid, get_production_progress
from app.models.budget_models import get_budget_summary
from app.models.expense_models import get_expenses
from app.models.schedule_models import get_shoot_dates

bp = Blueprint('reports', __name__)


@bp.route('/<int:project_id>')
@login_required
@require_project_member
def index(project_id):
    """Reports landing page with links to each report."""
    return render_template('reports/index.html', project=g.project)


@bp.route('/<int:project_id>/budget-summary')
@login_required
@require_project_member
@require_role('producer')
def budget_summary(project_id):
    """Budget summary report -- producer only."""
    conn = get_db()
    summary = get_budget_summary(conn, project_id)
    expenses = get_expenses(conn, project_id)
    return render_template('reports/budget_summary.html',
                           project=g.project, summary=summary, expenses=expenses)


@bp.route('/<int:project_id>/dood')
@login_required
@require_project_member
def dood(project_id):
    """Day Out of Days grid."""
    conn = get_db()
    dood = get_dood_grid(conn, project_id)
    shoot_dates = get_shoot_dates(conn, project_id)
    return render_template('reports/dood.html',
                           project=g.project, dood=dood, shoot_dates=shoot_dates)


@bp.route('/<int:project_id>/progress')
@login_required
@require_project_member
def progress(project_id):
    """Production progress report."""
    conn = get_db()
    stats = get_production_progress(conn, project_id)
    return render_template('reports/progress.html',
                           project=g.project, stats=stats)
