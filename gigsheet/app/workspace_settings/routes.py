from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from app.db import get_db
from app.models import log_activity, update_workspace
from app.decorators import login_required, require_workspace, require_role

workspace_settings_bp = Blueprint('workspace_settings', __name__)

# Plan tiers mirror app/__init__.py PLAN_TIERS
PLAN_TIERS = {
    'solo':   {'price_cents': 2900,  'monthly_email_quota': 500},
    'pro':    {'price_cents': 5900,  'monthly_email_quota': 2000},
    'agency': {'price_cents': 9900,  'monthly_email_quota': 10000},
}


@workspace_settings_bp.route('/')
@login_required
@require_workspace
def index():
    workspace = g.workspace
    plan_tier = workspace['plan_tier']
    tier_info = PLAN_TIERS.get(plan_tier, PLAN_TIERS['solo'])
    return render_template('workspace_settings/index.html',
                           workspace=workspace,
                           plan_tier=plan_tier,
                           tier_info=tier_info)


@workspace_settings_bp.route('/', methods=['POST'])
@login_required
@require_workspace
@require_role('owner', 'admin')
def update():
    name = request.form.get('name', '').strip()[:100]
    from_email = request.form.get('from_email', '').strip()[:255]
    from_name = request.form.get('from_name', '').strip()[:100]

    if not name:
        flash('Workspace name is required.', 'error')
        return redirect(url_for('workspace_settings.index'))

    conn = get_db()
    update_workspace(conn, g.workspace['id'], name, from_email, from_name)
    log_activity(conn, g.workspace['id'], g.user['id'],
                 'updated_workspace', 'workspace', g.workspace['id'],
                 f'Updated workspace settings: {name}')
    conn.commit()

    flash('Workspace settings updated.', 'success')
    return redirect(url_for('workspace_settings.index'))
