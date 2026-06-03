"""Wizard blueprint routes.

Guides users through filling 12 prompt components grouped into 4 clusters.
Routes are RELATIVE to url_prefix /wizard (FC7).
"""

import json

from flask import (
    Blueprint,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
)

from app.database import get_db
from app.models.component_models import get_all_components, get_components_grouped
from app.models.industry_models import (
    get_all_industries,
    get_guidance_for_industry,
    get_industry,
)

bp = Blueprint('wizard', __name__, url_prefix='/wizard')


# ---------------------------------------------------------------------------
# Helper: validate component content from form
# ---------------------------------------------------------------------------

def _parse_component_form() -> dict[str, str]:
    """Parse component textareas from the wizard form.

    Each textarea has name="component_<id>".
    FC4: Validate each component content is 0-5000 chars.
    Returns: dict mapping component_id -> content string.
    """
    components = get_all_components()
    result: dict[str, str] = {}
    for comp in components:
        raw = request.form.get(f'component_{comp["id"]}', '')
        # FC4: content 0-5000 chars
        content = raw[:5000]
        result[comp['id']] = content
    return result


def _parse_title() -> str:
    """Parse and validate the prompt title from form.

    FC4: title 1-200 chars.
    Returns: stripped title string (may be empty — caller must check).
    """
    title = request.form.get('title', '').strip()
    if len(title) > 200:
        title = title[:200]
    return title


def _build_formatted_prompt(title: str, components_data: dict[str, str],
                            industry_id: str | None = None) -> str:
    """Assemble component content into a single formatted prompt string.

    Groups components by cluster and formats them with headers.
    Skips empty components.
    """
    from app.models.component_models import CLUSTERS, COMPONENTS

    lines: list[str] = []
    if title:
        lines.append(f'# {title}')
        lines.append('')

    if industry_id:
        industry = get_industry(industry_id)
        if industry:
            lines.append(f'**Industry:** {industry["name"]}')
            lines.append('')

    grouped = get_components_grouped()
    for cluster_id, cluster_components in grouped.items():
        cluster_meta = CLUSTERS[cluster_id]
        cluster_has_content = any(
            components_data.get(comp['id'], '').strip()
            for comp in cluster_components
        )
        if not cluster_has_content:
            continue

        lines.append(f'## {cluster_meta["name"]}')
        lines.append('')
        for comp in cluster_components:
            content = components_data.get(comp['id'], '').strip()
            if content:
                lines.append(f'### {comp["name"]}')
                lines.append(content)
                lines.append('')

    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@bp.route('/')
def select_industry():
    """GET /wizard/ -- choose an industry before starting the wizard."""
    industries = get_all_industries()
    return render_template('wizard/select_industry.html',
        industries=industries,
    )


@bp.route('/<industry_id>')
def wizard_form(industry_id):
    """GET /wizard/<industry_id> -- main wizard form with 12 textareas."""
    # FC4: validate industry_id exists
    industry = get_industry(industry_id)
    if industry is None:
        flash('Industry not found', 'error')
        return redirect(url_for('wizard.select_industry'))

    guidance = get_guidance_for_industry(industry_id)
    grouped = get_components_grouped()

    return render_template('wizard/wizard.html',
        industry=industry,
        grouped=grouped,
        guidance=guidance,
        components_data={},
        title='',
        is_share=False,
        is_edit=False,
        prompt_id=None,
    )


@bp.route('/generate', methods=['POST'])
def generate_preview():
    """POST /wizard/generate -- render preview of assembled prompt."""
    title = _parse_title()
    industry_id = request.form.get('industry_id', '').strip()
    components_data = _parse_component_form()

    # FC4: validate industry_id exists
    industry = get_industry(industry_id)
    if industry is None:
        flash('Invalid industry', 'error')
        return redirect(url_for('wizard.select_industry'))

    if not title:
        flash('Title is required', 'error')
        guidance = get_guidance_for_industry(industry_id)
        grouped = get_components_grouped()
        return render_template('wizard/wizard.html',
            industry=industry,
            grouped=grouped,
            guidance=guidance,
            components_data=components_data,
            title=title,
            is_share=False,
            is_edit=False,
            prompt_id=None,
        )

    formatted_prompt = _build_formatted_prompt(title, components_data, industry_id)

    # Calculate cluster completeness for the preview
    grouped = get_components_grouped()
    cluster_stats: dict[str, dict] = {}
    for cluster_id, cluster_components in grouped.items():
        filled = sum(
            1 for comp in cluster_components
            if components_data.get(comp['id'], '').strip()
        )
        total = len(cluster_components)
        cluster_stats[cluster_id] = {
            'filled': filled,
            'total': total,
            'percent': int((filled / total) * 100) if total > 0 else 0,
        }

    total_filled = sum(s['filled'] for s in cluster_stats.values())
    total_components = sum(s['total'] for s in cluster_stats.values())
    overall_percent = int((total_filled / total_components) * 100) if total_components > 0 else 0

    return render_template('wizard/preview.html',
        title=title,
        industry=industry,
        components_data=components_data,
        formatted_prompt=formatted_prompt,
        cluster_stats=cluster_stats,
        overall_percent=overall_percent,
        grouped=grouped,
    )


@bp.route('/save', methods=['POST'])
def save_prompt():
    """POST /wizard/save -- save assembled prompt. Requires login."""
    # Check if user is logged in
    if not hasattr(g, 'user') or g.user is None:
        flash('You must be logged in to save prompts', 'error')
        return redirect(url_for('wizard.select_industry'))

    title = _parse_title()
    industry_id = request.form.get('industry_id', '').strip()
    components_data = _parse_component_form()

    # FC4: validate industry_id exists
    industry = get_industry(industry_id)
    if industry is None:
        flash('Invalid industry', 'error')
        return redirect(url_for('wizard.select_industry'))

    # FC4: title 1-200 chars, required
    if not title:
        flash('Title is required', 'error')
        return redirect(url_for('wizard.wizard_form', industry_id=industry_id))

    formatted_prompt = _build_formatted_prompt(title, components_data, industry_id)

    # Save via the existing prompt CRUD (create_prompt from app.models)
    # The wizard stores the formatted prompt as user_prompt and
    # component data as JSON in the description field for reconstruction.
    with get_db() as conn:
        from app.models import create_prompt
        prompt_id = create_prompt(
            conn,
            name=title,
            description=json.dumps({
                'wizard': True,
                'industry_id': industry_id,
                'components': components_data,
            }),
            system_prompt='',
            user_prompt=formatted_prompt,
            tag_names=[industry['name'], 'wizard'],
        )

    flash('Prompt saved successfully', 'success')
    return redirect(url_for('prompts.detail', prompt_id=prompt_id))


@bp.route('/<int:prompt_id>/edit')
def edit_wizard(prompt_id):
    """GET /wizard/<int:prompt_id>/edit -- edit existing wizard prompt.

    FC35: Must check prompt['user_id'] == g.user['id'], else abort(404).
    """
    # Check if user is logged in
    if not hasattr(g, 'user') or g.user is None:
        flash('You must be logged in to edit prompts', 'error')
        return redirect(url_for('wizard.select_industry'))

    with get_db() as conn:
        from app.models import get_prompt
        prompt = get_prompt(conn, prompt_id)
        if prompt is None:
            abort(404)

        # FC35: ownership check
        user_id = dict(prompt).get('user_id')
        if user_id is not None and user_id != g.user['id']:
            abort(404)

        # Try to reconstruct wizard data from description JSON
        try:
            meta = json.loads(prompt['description'])
            if not isinstance(meta, dict) or not meta.get('wizard'):
                flash('This prompt was not created with the wizard', 'error')
                return redirect(url_for('prompts.detail', prompt_id=prompt_id))
            industry_id = meta.get('industry_id', 'general')
            components_data = meta.get('components', {})
        except (json.JSONDecodeError, TypeError):
            flash('This prompt was not created with the wizard', 'error')
            return redirect(url_for('prompts.detail', prompt_id=prompt_id))

    industry = get_industry(industry_id)
    if industry is None:
        industry = get_industry('general')
        industry_id = 'general'

    guidance = get_guidance_for_industry(industry_id)
    grouped = get_components_grouped()

    return render_template('wizard/wizard.html',
        industry=industry,
        grouped=grouped,
        guidance=guidance,
        components_data=components_data,
        title=prompt['name'],
        is_share=False,
        is_edit=True,
        prompt_id=prompt_id,
    )
