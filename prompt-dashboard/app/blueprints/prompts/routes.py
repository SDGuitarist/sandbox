import difflib
import html as html_module

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from markupsafe import Markup

from app.database import get_db
from app.models import (
    create_prompt,
    delete_prompt,
    get_all_tags,
    get_prompt,
    get_prompt_tags,
    get_prompt_version,
    get_prompt_versions,
    get_test_runs_for_prompt,
    update_prompt,
)

bp = Blueprint('prompts', __name__, url_prefix='/prompts')


def generate_diff_html(text1: str, text2: str, label1: str, label2: str) -> str:
    """Generate side-by-side HTML diff using difflib.

    Returns Markup()-wrapped HTML safe for |safe in templates.
    difflib.HtmlDiff escapes content lines internally in Python 3.
    Labels (fromdesc/todesc) are NOT escaped by difflib -- we escape them here.
    """
    differ = difflib.HtmlDiff(wrapcolumn=80)
    table = differ.make_table(
        text1.splitlines(), text2.splitlines(),
        fromdesc=html_module.escape(label1),
        todesc=html_module.escape(label2),
        context=True, numlines=3
    )
    return Markup(table)


@bp.route('/new')
def create_form():
    """GET /prompts/new -- render create form."""
    with get_db() as conn:
        return render_template('prompts/create.html',
            tags=get_all_tags(conn)
        )


@bp.route('/create', methods=['POST'])
def create():
    """POST /prompts/create -- create a new prompt, redirect to detail."""
    name = request.form.get('name', '').strip()
    if not name:
        flash('Name is required', 'error')
        return redirect(url_for('prompts.create_form'))
    if len(name) > 200:
        name = name[:200]

    description = request.form.get('description', '').strip()
    if len(description) > 1000:
        description = description[:1000]

    system_prompt = request.form.get('system_prompt', '').strip()
    user_prompt = request.form.get('user_prompt', '').strip()

    tags_raw = request.form.get('tags', '').strip()
    tag_names = []
    if tags_raw:
        for t in tags_raw.split(','):
            t = t.strip()[:50]
            if t:
                tag_names.append(t)

    with get_db() as conn:
        prompt_id = create_prompt(conn, name, description, system_prompt, user_prompt, tag_names)

    flash('Prompt created successfully', 'success')
    return redirect(url_for('prompts.detail', prompt_id=prompt_id))


@bp.route('/<int:prompt_id>')
def detail(prompt_id):
    """GET /prompts/<id> -- show prompt detail page."""
    with get_db() as conn:
        prompt = get_prompt(conn, prompt_id)
        if prompt is None:
            abort(404)
        return render_template('prompts/detail.html',
            prompt=prompt,
            tags=get_prompt_tags(conn, prompt_id),
            versions=get_prompt_versions(conn, prompt_id),
            recent_runs=get_test_runs_for_prompt(conn, prompt_id, limit=5)
        )


@bp.route('/<int:prompt_id>/edit')
def edit_form(prompt_id):
    """GET /prompts/<id>/edit -- render edit form."""
    with get_db() as conn:
        prompt = get_prompt(conn, prompt_id)
        if prompt is None:
            abort(404)
        return render_template('prompts/edit.html',
            prompt=prompt,
            tags=get_all_tags(conn),
            prompt_tags=[t['name'] for t in get_prompt_tags(conn, prompt_id)]
        )


@bp.route('/<int:prompt_id>/edit', methods=['POST'])
def update(prompt_id):
    """POST /prompts/<id>/edit -- update prompt, redirect to detail."""
    with get_db() as conn:
        prompt = get_prompt(conn, prompt_id)
        if prompt is None:
            abort(404)

    name = request.form.get('name', '').strip()
    if not name:
        flash('Name is required', 'error')
        return redirect(url_for('prompts.edit_form', prompt_id=prompt_id))
    if len(name) > 200:
        name = name[:200]

    description = request.form.get('description', '').strip()
    if len(description) > 1000:
        description = description[:1000]

    system_prompt = request.form.get('system_prompt', '').strip()
    user_prompt = request.form.get('user_prompt', '').strip()

    tags_raw = request.form.get('tags', '').strip()
    tag_names = []
    if tags_raw:
        for t in tags_raw.split(','):
            t = t.strip()[:50]
            if t:
                tag_names.append(t)

    with get_db() as conn:
        update_prompt(conn, prompt_id, name, description, system_prompt, user_prompt, tag_names)

    flash('Prompt updated successfully', 'success')
    return redirect(url_for('prompts.detail', prompt_id=prompt_id))


@bp.route('/<int:prompt_id>/delete', methods=['POST'])
def delete(prompt_id):
    """POST /prompts/<id>/delete -- delete prompt, redirect to dashboard."""
    with get_db() as conn:
        prompt = get_prompt(conn, prompt_id)
        if prompt is None:
            abort(404)
        delete_prompt(conn, prompt_id)

    flash('Prompt deleted successfully', 'success')
    return redirect(url_for('dashboard.index'))


@bp.route('/<int:prompt_id>/versions')
def versions(prompt_id):
    """GET /prompts/<id>/versions -- list all versions."""
    with get_db() as conn:
        prompt = get_prompt(conn, prompt_id)
        if prompt is None:
            abort(404)
        return render_template('prompts/versions.html',
            prompt=prompt,
            versions=get_prompt_versions(conn, prompt_id)
        )


@bp.route('/<int:prompt_id>/diff')
def diff(prompt_id):
    """GET /prompts/<id>/diff?v1=<version_id>&v2=<version_id> -- side-by-side diff.

    v1 and v2 are prompt_versions.id primary keys (NOT version numbers).
    Both must exist and belong to the given prompt_id.
    """
    with get_db() as conn:
        prompt = get_prompt(conn, prompt_id)
        if prompt is None:
            abort(404)

        # Validate v1 and v2 query params
        try:
            v1_id = int(request.args.get('v1', ''))
            v2_id = int(request.args.get('v2', ''))
        except (ValueError, TypeError):
            flash('Invalid version', 'error')
            return redirect(url_for('prompts.versions', prompt_id=prompt_id))

        version1 = get_prompt_version(conn, v1_id)
        version2 = get_prompt_version(conn, v2_id)

        if version1 is None or version2 is None:
            flash('Invalid version', 'error')
            return redirect(url_for('prompts.versions', prompt_id=prompt_id))

        # Both versions must belong to this prompt
        if version1['prompt_id'] != prompt_id or version2['prompt_id'] != prompt_id:
            flash('Invalid version', 'error')
            return redirect(url_for('prompts.versions', prompt_id=prompt_id))

        system_diff_html = generate_diff_html(
            version1['system_prompt'], version2['system_prompt'],
            f'Version {version1["version_number"]}',
            f'Version {version2["version_number"]}'
        )
        user_diff_html = generate_diff_html(
            version1['user_prompt'], version2['user_prompt'],
            f'Version {version1["version_number"]}',
            f'Version {version2["version_number"]}'
        )

        return render_template('prompts/diff.html',
            prompt=prompt,
            v1=version1,
            v2=version2,
            system_diff=system_diff_html,
            user_diff=user_diff_html
        )
