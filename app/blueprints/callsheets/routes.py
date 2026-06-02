"""Call sheets blueprint — list, generate, detail, and publish call sheets.

url_prefix=/call-sheets (registered in app factory).
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request, g, abort
from app.database import get_db
from app.blueprints.auth.routes import login_required, require_project_member, require_role
from app.models.callsheet_models import (
    generate_call_sheet,
    get_call_sheet,
    get_call_sheet_scenes,
    get_call_sheet_cast,
    publish_call_sheet,
)
from app.models.crew_models import get_crew_by_department
from app.models.department_models import get_departments  # noqa: F401 — spec contract
from app.models.schedule_models import get_shoot_dates

bp = Blueprint('callsheets', __name__)


# ---------------------------------------------------------------------------
# GET /<project_id> — list all call sheets for the project
# ---------------------------------------------------------------------------
@bp.route('/<int:project_id>')
@login_required
@require_project_member
def list(project_id):
    conn = get_db()
    sheets = conn.execute(
        'SELECT * FROM call_sheets WHERE project_id = ? ORDER BY shoot_date DESC',
        (project_id,),
    ).fetchall()
    sheets = [dict(s) for s in sheets]

    # Shoot dates that do NOT yet have a call sheet (for the generate form)
    existing_dates = {s['shoot_date'] for s in sheets}
    all_dates = get_shoot_dates(conn, project_id)
    available_dates = [d for d in all_dates if d not in existing_dates]

    return render_template(
        'callsheets/list.html',
        project=g.project,
        sheets=sheets,
        available_dates=available_dates,
    )


# ---------------------------------------------------------------------------
# POST /<project_id>/generate — generate a call sheet for a shoot date
# ---------------------------------------------------------------------------
@bp.route('/<int:project_id>/generate', methods=['POST'])
@login_required
@require_project_member
@require_role('producer', 'ad')
def generate(project_id):
    conn = get_db()
    shoot_date = request.form.get('shoot_date', '').strip()

    if not shoot_date:
        flash('Please select a shoot date', 'error')
        return redirect(url_for('callsheets.list', project_id=project_id))

    # Validate that the date has schedule entries
    from app.models.schedule_models import get_schedule_entries
    entries = get_schedule_entries(conn, project_id, shoot_date)
    if not entries:
        flash('No scenes scheduled for that date', 'error')
        return redirect(url_for('callsheets.list', project_id=project_id))

    # Check if a call sheet already exists for this date
    existing = conn.execute(
        'SELECT id FROM call_sheets WHERE project_id = ? AND shoot_date = ?',
        (project_id, shoot_date),
    ).fetchone()
    if existing:
        flash('A call sheet already exists for that date', 'warning')
        return redirect(url_for('callsheets.detail', project_id=project_id, call_sheet_id=existing['id']))

    call_sheet_id = generate_call_sheet(conn, project_id, shoot_date)
    if call_sheet_id is None:
        flash('No scenes scheduled for that date', 'error')
        return redirect(url_for('callsheets.list', project_id=project_id))

    flash('Call sheet generated', 'success')
    return redirect(url_for('callsheets.detail', project_id=project_id, call_sheet_id=call_sheet_id))


# ---------------------------------------------------------------------------
# GET /<project_id>/<call_sheet_id> — call sheet detail
# ---------------------------------------------------------------------------
@bp.route('/<int:project_id>/<int:call_sheet_id>')
@login_required
@require_project_member
def detail(project_id, call_sheet_id):
    conn = get_db()
    call_sheet = get_call_sheet(conn, call_sheet_id)
    if call_sheet is None or call_sheet['project_id'] != project_id:
        abort(404)

    scenes = get_call_sheet_scenes(conn, call_sheet_id)
    cast = get_call_sheet_cast(conn, call_sheet_id)
    crew = get_crew_by_department(conn, project_id)

    return render_template(
        'callsheets/detail.html',
        project=g.project,
        call_sheet=call_sheet,
        scenes=scenes,
        cast=cast,
        crew=crew,
    )


# ---------------------------------------------------------------------------
# POST /<project_id>/<call_sheet_id>/publish — publish a draft call sheet
# ---------------------------------------------------------------------------
@bp.route('/<int:project_id>/<int:call_sheet_id>/publish', methods=['POST'])
@login_required
@require_project_member
@require_role('producer', 'ad')
def publish(project_id, call_sheet_id):
    conn = get_db()
    call_sheet = get_call_sheet(conn, call_sheet_id)
    if call_sheet is None or call_sheet['project_id'] != project_id:
        abort(404)

    if call_sheet['status'] != 'draft':
        flash('Already published', 'warning')
        return redirect(url_for('callsheets.detail', project_id=project_id, call_sheet_id=call_sheet_id))

    success = publish_call_sheet(conn, call_sheet_id)
    if success:
        flash('Call sheet published', 'success')
    else:
        flash('Could not publish call sheet', 'error')

    return redirect(url_for('callsheets.detail', project_id=project_id, call_sheet_id=call_sheet_id))
