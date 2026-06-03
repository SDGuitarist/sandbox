"""Sharing blueprint — public share link for templates."""
from flask import Blueprint, abort, render_template

from app.database import get_db
from app.models.sharing_models import get_template_by_token
from app.models.component_models import get_all_components, get_components_grouped
from app.models.industry_models import get_industry, get_guidance_for_industry
from app.models.template_models import get_template_components

bp = Blueprint('sharing', __name__)


@bp.route('/<token>')
def view_share(token):
    """Public share link — renders wizard with template data pre-filled.
    No login required. Returns 404 for invalid/revoked tokens (never 403).
    """
    conn = get_db()
    template = get_template_by_token(conn, token)
    if template is None:
        abort(404)

    template_id = template['template_id']
    industry_id = template['industry_id']

    components = get_all_components(conn)
    clusters = get_components_grouped(conn)
    industry = get_industry(conn, industry_id)
    guidance = get_guidance_for_industry(conn, industry_id)
    template_comps = get_template_components(conn, template_id)

    prompt_data = {tc['component_id']: tc['content'] for tc in template_comps}

    guidance = {g_item['component_id']: g_item['guidance_text'] for g_item in guidance}

    return render_template('wizard/wizard.html',
        components=components,
        clusters=clusters,
        industry=industry,
        guidance=guidance,
        components_data=prompt_data,
        prompt_id=None,
        is_share=True,
        template_name=template['name'],
    )
