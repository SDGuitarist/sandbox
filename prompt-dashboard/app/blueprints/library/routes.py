from flask import Blueprint, render_template, redirect, url_for, flash, abort, g

from app.database import get_db
from app.auth_helpers import login_required
from app.models.prompt_models import (
    get_prompt, get_prompt_components, get_prompts_for_user,
    delete_prompt, format_prompt, calculate_cluster_completeness
)
from app.models.grading_models import get_grade
from app.models.audit_models import log_audit_event

bp = Blueprint('library', __name__, template_folder='../../templates/library')


@bp.route('/')
@login_required
def index():
    """Library index -- list all prompts for the current user."""
    conn = get_db()
    prompts = get_prompts_for_user(conn, g.user['id'])
    return render_template('library/index.html', prompts=prompts)


@bp.route('/<int:prompt_id>')
@login_required
def detail(prompt_id):
    """Prompt detail -- show formatted prompt, components by cluster, completeness, grade."""
    conn = get_db()
    prompt = get_prompt(conn, prompt_id)
    if prompt is None or prompt['user_id'] != g.user['id']:
        abort(404)
    components = get_prompt_components(conn, prompt_id)
    grade = get_grade(conn, prompt_id)
    formatted_prompt = format_prompt(components)
    cluster_completeness = calculate_cluster_completeness(components)
    return render_template('library/detail.html',
                           prompt=prompt,
                           components=components,
                           grade=grade,
                           formatted_prompt=formatted_prompt,
                           completeness=prompt['completeness'],
                           cluster_completeness=cluster_completeness)


@bp.route('/<int:prompt_id>/delete', methods=['POST'])
@login_required
def delete(prompt_id):
    """Delete a prompt. Requires ownership check (FC35)."""
    conn = get_db()
    prompt = get_prompt(conn, prompt_id)
    if prompt is None or prompt['user_id'] != g.user['id']:
        abort(404)
    delete_prompt(conn, prompt_id)
    log_audit_event(conn, g.user['id'], 'delete', 'prompt', prompt_id)
    flash('Prompt deleted.', 'success')
    return redirect(url_for('library.index'))
