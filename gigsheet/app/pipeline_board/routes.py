from flask import render_template, g

from app.pipeline_board import pipeline_board_bp
from app.db import get_db
from app.decorators import login_required, require_workspace
from app.models import get_leads_by_stage
from app import PIPELINE_STAGES


@pipeline_board_bp.route('/')
@login_required
@require_workspace
def index():
    """Kanban board with one column per pipeline stage."""
    conn = get_db()
    all_leads = get_leads_by_stage(conn, g.workspace['id'])

    # Group leads by pipeline_stage into a dict
    leads_by_stage = {stage: [] for stage in PIPELINE_STAGES}
    for lead in all_leads:
        stage = lead['pipeline_stage']
        if stage in leads_by_stage:
            leads_by_stage[stage].append(lead)

    return render_template(
        'pipeline_board/index.html',
        stages=PIPELINE_STAGES,
        leads_by_stage=leads_by_stage,
    )
