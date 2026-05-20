from flask import Blueprint, render_template, request, g

from app.db import get_db
from app.decorators import login_required, require_workspace
from app.models import (
    get_leads_by_workspace,
    count_leads_by_workspace,
    search_leads,
    get_tags_by_workspace,
)
from app import PIPELINE_STAGES

lead_list_bp = Blueprint('lead_list', __name__)


@lead_list_bp.route('/')
@login_required
@require_workspace
def index():
    conn = get_db()
    workspace_id = g.workspace['id']

    page = request.args.get('page', 1, type=int)
    per_page = 25
    stage = request.args.get('stage', None, type=str)
    tag_id = request.args.get('tag_id', None, type=int)
    q = request.args.get('q', '', type=str).strip()

    # FTS5 search takes priority when a query is provided
    if q:
        leads = search_leads(conn, workspace_id, q)
        total = len(leads)
    else:
        leads = get_leads_by_workspace(
            conn, workspace_id, page=page, per_page=per_page,
            stage=stage, tag_id=tag_id,
        )
        total = count_leads_by_workspace(
            conn, workspace_id, stage=stage, tag_id=tag_id,
        )

    tags = get_tags_by_workspace(conn, workspace_id)

    return render_template(
        'lead_list/index.html',
        leads=leads,
        tags=tags,
        total=total,
        page=page,
        per_page=per_page,
        stage=stage,
        tag_id=tag_id,
        stages=PIPELINE_STAGES,
    )
