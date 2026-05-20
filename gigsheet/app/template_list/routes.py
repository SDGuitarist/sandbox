from flask import Blueprint, render_template, g
from app.db import get_db
from app.models import get_templates_by_workspace
from app.decorators import login_required, require_workspace

template_list_bp = Blueprint('template_list', __name__)


@template_list_bp.route('/')
@login_required
@require_workspace
def index():
    conn = get_db()
    templates = get_templates_by_workspace(conn, g.workspace['id'])
    return render_template('template_list/index.html', templates=templates)
