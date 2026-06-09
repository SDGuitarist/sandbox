"""Call sheet routes: list, generate, detail, publish.

Blueprint name MUST be 'callsheets' and the variable MUST be named `bp`
(app factory does: from app.blueprints.callsheets.routes import bp as callsheets_bp).
Registered with url_prefix='/call-sheets'. Paths here are RELATIVE to that prefix.
"""

import re

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, g, abort,
)

from app.database import get_db
from app.blueprints.auth.routes import (
    login_required, require_project_member, require_role,
)
from app.models.callsheet_models import (
    generate_call_sheet,
    get_call_sheet,
    get_call_sheet_scenes,
    get_call_sheet_cast,
    publish_call_sheet,
)
# Cross-boundary imports (Cross-Boundary Wiring Table):
from app.models.crew_models import get_crew_by_department
from app.models.department_models import get_departments
from app.models.schedule_models import get_shoot_dates, get_schedule_entries

bp = Blueprint('callsheets', __name__)

# Shoot date format: YYYY-MM-DD (FC4 -- this exact validation bug shipped before).
DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')


@bp.route('/<int:project_id>', methods=['GET'])
@login_required
@require_project_member
def list(project_id):
    conn = get_db()
    call_sheets = conn.execute(
        '''SELECT id, sheet_number, shoot_date, status, created_at
           FROM call_sheets
           WHERE project_id = ?
           ORDER BY shoot_date''',
        (project_id,),
    ).fetchall()
    shoot_dates = get_shoot_dates(conn, project_id)
    return render_template(
        'callsheets/list.html',
        project=g.project,
        call_sheets=call_sheets,
        shoot_dates=shoot_dates,
    )


@bp.route('/<int:project_id>/generate', methods=['POST'])
@login_required
@require_project_member
@require_role('producer', 'ad')
def generate(project_id):
    conn = get_db()
    shoot_date = (request.form.get('shoot_date') or '').strip()

    if not DATE_RE.match(shoot_date):
        flash('Invalid shoot date', 'error')
        return redirect(url_for('callsheets.list', project_id=project_id))

    # Must have at least one scheduled scene for that day.
    entries = get_schedule_entries(conn, project_id, shoot_date)
    if not entries:
        flash('No scenes scheduled for that day', 'error')
        return redirect(url_for('callsheets.list', project_id=project_id))

    call_sheet_id = generate_call_sheet(conn, project_id, shoot_date)
    flash('Call sheet generated', 'success')
    return redirect(url_for(
        'callsheets.detail', project_id=project_id, call_sheet_id=call_sheet_id,
    ))


@bp.route('/<int:project_id>/<int:call_sheet_id>', methods=['GET'])
@login_required
@require_project_member
def detail(project_id, call_sheet_id):
    conn = get_db()
    call_sheet = get_call_sheet(conn, call_sheet_id)
    if call_sheet is None:
        abort(404)
    # IDOR prevention (FC35): resource must belong to the URL's project.
    if call_sheet['project_id'] != project_id:
        abort(404)

    scenes = get_call_sheet_scenes(conn, call_sheet_id)
    cast = get_call_sheet_cast(conn, call_sheet_id)
    crew = get_crew_by_department(conn, project_id)
    departments = get_departments(conn, project_id)

    return render_template(
        'callsheets/detail.html',
        project=g.project,
        call_sheet=call_sheet,
        scenes=scenes,
        cast=cast,
        crew=crew,
        departments=departments,
    )


@bp.route('/<int:project_id>/<int:call_sheet_id>/publish', methods=['POST'])
@login_required
@require_project_member
@require_role('producer', 'ad')
def publish(project_id, call_sheet_id):
    conn = get_db()
    call_sheet = get_call_sheet(conn, call_sheet_id)
    if call_sheet is None:
        abort(404)
    if call_sheet['project_id'] != project_id:
        abort(404)

    if call_sheet['status'] != 'draft':
        flash('Call sheet is already published', 'warning')
        return redirect(url_for(
            'callsheets.detail', project_id=project_id, call_sheet_id=call_sheet_id,
        ))

    publish_call_sheet(conn, call_sheet_id)
    flash('Call sheet published', 'success')
    return redirect(url_for(
        'callsheets.detail', project_id=project_id, call_sheet_id=call_sheet_id,
    ))
