from flask import Blueprint, render_template, g, abort
from app.db import get_db
from app.decorators import login_required, require_workspace
from app.models import get_lead, get_pipeline_notes, get_lead_tags
from app import PIPELINE_STAGES

pipeline_detail_bp = Blueprint('pipeline_detail', __name__)


@pipeline_detail_bp.route('/<int:id>')
@login_required
@require_workspace
def detail(id):
    conn = get_db()

    # Fetch lead
    lead = get_lead(conn, id)
    if lead is None:
        abort(404)

    # FC35: ownership check -- verify lead belongs to current workspace
    if lead['workspace_id'] != g.workspace['id']:
        abort(403)

    # Fetch tags for this lead
    tags = get_lead_tags(conn, id)

    # Fetch pipeline notes (activity history) for this lead
    notes = get_pipeline_notes(conn, id)

    return render_template(
        'pipeline_detail/detail.html',
        lead=lead,
        tags=tags,
        notes=notes,
        stages=PIPELINE_STAGES,
    )
