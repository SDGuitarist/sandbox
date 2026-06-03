"""Wizard blueprint — guided 12-component prompt builder."""
from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from app.auth_helpers import login_required
from app.database import get_db
from app.models.component_models import get_all_components, get_components_grouped
from app.models.industry_models import get_all_industries, get_industry, get_guidance_for_industry
from app.models.template_models import get_template, get_all_templates, get_template_components
from app.models.prompt_models import (
    create_prompt, get_prompt, get_prompt_components, update_prompt,
    format_prompt, calculate_cluster_completeness,
)

bp = Blueprint('wizard', __name__)


def _parse_components(conn):
    """Parse component textareas from wizard form.
    Returns: list of (component_id, content) tuples.
    """
    components = get_all_components(conn)
    result = []
    for comp in components:
        raw = request.form.get(f'component_{comp["id"]}', '')
        content = raw.strip()[:5000]
        result.append((comp['id'], content))
    return result


@bp.route('/')
@login_required
def select_industry():
    conn = get_db()
    return render_template('wizard/select_industry.html',
        industries=get_all_industries(conn),
        templates=get_all_templates(conn),
    )


@bp.route('/new')
@login_required
def new_prompt():
    industry_id = request.args.get('industry_id', type=int)
    conn = get_db()
    if not industry_id:
        flash('Please select an industry', 'error')
        return redirect(url_for('wizard.select_industry'))
    industry = get_industry(conn, industry_id)
    if industry is None:
        flash('Invalid industry', 'error')
        return redirect(url_for('wizard.select_industry'))
    components = get_all_components(conn)
    clusters = get_components_grouped(conn)
    guidance_list = get_guidance_for_industry(conn, industry_id)
    guidance = {g['component_id']: g['guidance_text'] for g in guidance_list}
    return render_template('wizard/wizard.html',
        components=components,
        clusters=clusters,
        industry=industry,
        guidance=guidance,
        components_data={},
        prompt_id=None,
        is_share=False,
        template_name=None,
    )


@bp.route('/template/<int:template_id>')
@login_required
def from_template(template_id):
    conn = get_db()
    template = get_template(conn, template_id)
    if template is None:
        abort(404)
    template_comps = get_template_components(conn, template_id)
    industry = get_industry(conn, template['industry_id'])
    components = get_all_components(conn)
    clusters = get_components_grouped(conn)
    guidance_list = get_guidance_for_industry(conn, template['industry_id'])
    guidance = {g['component_id']: g['guidance_text'] for g in guidance_list}
    prompt_data = {tc['component_id']: tc['content'] for tc in template_comps}
    return render_template('wizard/wizard.html',
        components=components,
        clusters=clusters,
        industry=industry,
        guidance=guidance,
        components_data=prompt_data,
        prompt_id=None,
        is_share=False,
        template_name=template['name'],
    )


@bp.route('/save', methods=['POST'])
@login_required
def save_prompt():
    conn = get_db()
    title = request.form.get('title', '').strip()[:200]
    industry_id = request.form.get('industry_id', type=int)
    if not title:
        flash('Title is required', 'error')
        return redirect(url_for('wizard.new_prompt', industry_id=industry_id))
    if not industry_id or get_industry(conn, industry_id) is None:
        flash('Invalid industry', 'error')
        return redirect(url_for('wizard.select_industry'))
    component_data = _parse_components(conn)
    prompt_id = create_prompt(conn, title, industry_id, g.user['id'], component_data)
    flash('Prompt saved successfully', 'success')
    return redirect(url_for('library.detail', prompt_id=prompt_id))


@bp.route('/<int:prompt_id>/edit')
@login_required
def edit_prompt(prompt_id):
    conn = get_db()
    prompt = get_prompt(conn, prompt_id)
    if prompt is None or prompt['user_id'] != g.user['id']:
        abort(404)
    prompt_comps = get_prompt_components(conn, prompt_id)
    industry = get_industry(conn, prompt['industry_id'])
    components = get_all_components(conn)
    clusters = get_components_grouped(conn)
    guidance_list = get_guidance_for_industry(conn, prompt['industry_id'])
    guidance = {g['component_id']: g['guidance_text'] for g in guidance_list}
    prompt_data = {pc['component_id']: pc['content'] for pc in prompt_comps}
    return render_template('wizard/wizard.html',
        components=components,
        clusters=clusters,
        industry=industry,
        guidance=guidance,
        components_data=prompt_data,
        prompt_id=prompt_id,
        is_share=False,
        template_name=None,
    )


@bp.route('/<int:prompt_id>/update', methods=['POST'])
@login_required
def update_prompt_route(prompt_id):
    conn = get_db()
    prompt = get_prompt(conn, prompt_id)
    if prompt is None or prompt['user_id'] != g.user['id']:
        abort(404)
    title = request.form.get('title', '').strip()[:200]
    if not title:
        flash('Title is required', 'error')
        return redirect(url_for('wizard.edit_prompt', prompt_id=prompt_id))
    component_data = _parse_components(conn)
    update_prompt(conn, prompt_id, title, component_data)
    flash('Prompt updated', 'success')
    return redirect(url_for('library.detail', prompt_id=prompt_id))


@bp.route('/generate', methods=['POST'])
def generate_preview():
    conn = get_db()
    title = request.form.get('title', '').strip()[:200]
    industry_id = request.form.get('industry_id', type=int)
    industry = get_industry(conn, industry_id) if industry_id else None
    industry_name = industry['name'] if industry else 'General'

    components = get_all_components(conn)
    filled_components = []
    for comp in components:
        content = request.form.get(f'component_{comp["id"]}', '').strip()[:5000]
        filled_components.append({
            'component_id': comp['id'],
            'name': comp['name'],
            'cluster': comp['cluster'],
            'position': comp['position'],
            'content': content,
        })

    completeness = sum(1 for c in filled_components if c['content']) / 12.0
    cluster_completeness = calculate_cluster_completeness(filled_components)
    formatted_prompt = format_prompt(filled_components)

    return render_template('wizard/preview.html',
        title=title or 'Untitled Prompt',
        formatted_prompt=formatted_prompt,
        components=filled_components,
        completeness=completeness,
        cluster_completeness=cluster_completeness,
        industry_name=industry_name,
        prompt_id=None,
    )
