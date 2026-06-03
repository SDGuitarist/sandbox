from flask import Blueprint, abort, render_template

from app.database import get_db
from app.models.sharing_models import get_template_by_token
from app.models.component_models import get_all_components, get_components_grouped
from app.models.industry_models import get_industry, get_guidance_for_industry
from app.models.template_models import get_template, get_template_components

bp = Blueprint('sharing', __name__)


@bp.route('/<token>')
def view_share(token):
    """Public share link -- renders the wizard with template data pre-filled.
    No login required. CSRF exempt (GET-only, no form submission).
    Returns 404 for invalid or revoked tokens (never 403 -- don't confirm existence).
    """
    with get_db() as conn:
        template = get_template_by_token(conn, token)
        if template is None:
            abort(404)

        template_id = template['template_id']
        industry_id = template['industry_id']

        # Assemble the same context the wizard uses
        components = get_all_components(conn)
        clusters = get_components_grouped(conn)
        industry = get_industry(conn, industry_id)
        guidance = get_guidance_for_industry(conn, industry_id)
        template_components = get_template_components(conn, template_id)

        # Build prompt_data dict from template components (pre-fill the wizard)
        prompt_data = {}
        for tc in template_components:
            prompt_data[f'component_{tc["component_id"]}'] = tc['default_content']

        return render_template(
            'wizard/wizard.html',
            components=components,
            clusters=clusters,
            industry=industry,
            guidance=guidance,
            prompt=prompt_data,
            prompt_id=None,
            is_share=True,
            template_name=template['name']
        )
