import csv
import io

from flask import (
    Blueprint, abort, flash, redirect, render_template, request,
    session, url_for, g, Response,
)

from app.auth_helpers import admin_required
from app.database import get_db
from app.models.admin_models import get_dashboard_stats
from app.models.template_models import (
    create_template, get_template, get_all_templates,
    get_template_components, save_template_component, delete_template,
)
from app.models.component_models import (
    get_all_components, get_components_grouped, get_component,
)
from app.models.industry_models import (
    get_all_industries, get_industry, get_guidance_for_industry, save_guidance,
)
from app.models.prompt_models import get_all_prompts
from app.models.grading_models import get_all_grades
from app.models.sharing_models import generate_share_token, revoke_token, get_all_tokens
from app.models.export_models import export_all_prompts_json
from app.models.audit_models import log_audit_event

bp = Blueprint('admin', __name__)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@bp.route('/')
@admin_required
def dashboard():
    conn = get_db()
    stats = get_dashboard_stats(conn)
    return render_template(
        'admin/dashboard.html',
        total_users=stats['total_users'],
        total_prompts=stats['total_prompts'],
        total_templates=stats['total_templates'],
        avg_completeness=stats['avg_completeness'],
    )


# ---------------------------------------------------------------------------
# Template CRUD
# ---------------------------------------------------------------------------

@bp.route('/templates')
@admin_required
def templates_list():
    conn = get_db()
    templates = get_all_templates(conn)
    return render_template('admin/templates.html', templates=templates)


@bp.route('/templates/new')
@admin_required
def template_new():
    conn = get_db()
    return render_template(
        'admin/template_form.html',
        template=None,
        industries=get_all_industries(conn),
        components=get_all_components(conn),
        template_components=[],
    )


@bp.route('/templates', methods=['POST'])
@admin_required
def template_create():
    conn = get_db()

    name = request.form.get('name', '').strip()
    if not name or len(name) > 200:
        flash('Template name is required (1-200 characters).', 'error')
        return redirect(url_for('admin.template_new'))

    industry_id_str = request.form.get('industry_id', '')
    try:
        industry_id = int(industry_id_str)
    except (ValueError, TypeError):
        flash('Invalid industry.', 'error')
        return redirect(url_for('admin.template_new'))

    if get_industry(conn, industry_id) is None:
        flash('Industry not found.', 'error')
        return redirect(url_for('admin.template_new'))

    description = request.form.get('description', '').strip()

    template_id = create_template(conn, name, description, industry_id, g.user['id'])
    log_audit_event(conn, g.user['id'], 'create', 'template', template_id)

    # Save component content from form fields named component_<id>
    components = get_all_components(conn)
    for comp in components:
        content = request.form.get(f'component_{comp["id"]}', '').strip()
        if content:
            save_template_component(conn, template_id, comp['id'], content)

    flash('Template created successfully.', 'success')
    return redirect(url_for('admin.templates_list'))


@bp.route('/templates/<int:id>/edit')
@admin_required
def template_edit(id):
    conn = get_db()
    template = get_template(conn, id)
    if template is None:
        abort(404)
    return render_template(
        'admin/template_form.html',
        template=template,
        industries=get_all_industries(conn),
        components=get_all_components(conn),
        template_components=get_template_components(conn, id),
    )


@bp.route('/templates/<int:id>', methods=['POST'])
@admin_required
def template_update(id):
    conn = get_db()
    template = get_template(conn, id)
    if template is None:
        abort(404)

    name = request.form.get('name', '').strip()
    if not name or len(name) > 200:
        flash('Template name is required (1-200 characters).', 'error')
        return redirect(url_for('admin.template_edit', id=id))

    industry_id_str = request.form.get('industry_id', '')
    try:
        industry_id = int(industry_id_str)
    except (ValueError, TypeError):
        flash('Invalid industry.', 'error')
        return redirect(url_for('admin.template_edit', id=id))

    if get_industry(conn, industry_id) is None:
        flash('Industry not found.', 'error')
        return redirect(url_for('admin.template_edit', id=id))

    description = request.form.get('description', '').strip()

    # Update the template row directly (autocommit)
    conn.execute(
        'UPDATE prompt_templates SET name = ?, description = ?, industry_id = ? WHERE id = ?',
        (name, description, industry_id, id)
    )
    log_audit_event(conn, g.user['id'], 'update', 'template', id)

    # Save component content
    components = get_all_components(conn)
    for comp in components:
        content = request.form.get(f'component_{comp["id"]}', '').strip()
        if content:
            save_template_component(conn, id, comp['id'], content)

    flash('Template updated successfully.', 'success')
    return redirect(url_for('admin.templates_list'))


@bp.route('/templates/<int:id>/delete', methods=['POST'])
@admin_required
def template_delete(id):
    conn = get_db()
    template = get_template(conn, id)
    if template is None:
        abort(404)
    delete_template(conn, id)
    log_audit_event(conn, g.user['id'], 'delete', 'template', id)
    flash('Template deleted.', 'success')
    return redirect(url_for('admin.templates_list'))


# ---------------------------------------------------------------------------
# Guidance Editor
# ---------------------------------------------------------------------------

@bp.route('/guidance')
@admin_required
def guidance_list():
    conn = get_db()
    industries = get_all_industries(conn)
    components = get_all_components(conn)

    # Build guidance lookup dict keyed by (industry_id, component_id)
    all_guidance = {}
    for industry in industries:
        guidance_rows = get_guidance_for_industry(conn, industry['id'])
        for g_row in guidance_rows:
            all_guidance[(industry['id'], g_row['component_id'])] = g_row['guidance_text']

    return render_template(
        'admin/guidance.html',
        industries=industries,
        components=components,
        guidance=all_guidance,
    )


@bp.route('/guidance/<int:industry_id>/<int:component_id>', methods=['POST'])
@admin_required
def guidance_save(industry_id, component_id):
    conn = get_db()

    if get_industry(conn, industry_id) is None:
        abort(404)
    if get_component(conn, component_id) is None:
        abort(404)

    guidance_text = request.form.get('guidance_text', '').strip()
    # Silently truncate to 5000 chars per spec
    guidance_text = guidance_text[:5000]

    save_guidance(conn, industry_id, component_id, guidance_text)
    log_audit_event(conn, g.user['id'], 'update', 'guidance', None)
    flash('Guidance saved.', 'success')
    return redirect(url_for('admin.guidance_list'))


# ---------------------------------------------------------------------------
# All Prompts (filterable)
# ---------------------------------------------------------------------------

@bp.route('/prompts')
@admin_required
def all_prompts():
    conn = get_db()

    filter_industry = request.args.get('industry_id', type=int)
    filter_user = request.args.get('user_id', type=int)

    prompts = get_all_prompts(conn, industry_id=filter_industry, user_id=filter_user)
    industries = get_all_industries(conn)
    users = conn.execute('SELECT id, username FROM users ORDER BY username').fetchall()

    return render_template(
        'admin/prompts.html',
        prompts=prompts,
        industries=industries,
        users=users,
        filter_industry=filter_industry,
        filter_user=filter_user,
    )


# ---------------------------------------------------------------------------
# Grades View
# ---------------------------------------------------------------------------

@bp.route('/grades')
@admin_required
def all_grades():
    conn = get_db()
    grades = get_all_grades(conn)
    return render_template('admin/grades.html', grades=grades)


# ---------------------------------------------------------------------------
# Token Management
# ---------------------------------------------------------------------------

@bp.route('/tokens')
@admin_required
def tokens_list():
    conn = get_db()
    tokens = get_all_tokens(conn)
    templates = get_all_templates(conn)
    new_token = session.pop('new_token', None)
    return render_template(
        'admin/tokens.html',
        tokens=tokens,
        templates=templates,
        new_token=new_token,
    )


@bp.route('/tokens/generate', methods=['POST'])
@admin_required
def token_generate():
    conn = get_db()

    template_id_str = request.form.get('template_id', '')
    try:
        template_id = int(template_id_str)
    except (ValueError, TypeError):
        flash('Invalid template.', 'error')
        return redirect(url_for('admin.tokens_list'))

    if get_template(conn, template_id) is None:
        flash('Template not found.', 'error')
        return redirect(url_for('admin.tokens_list'))

    raw_token = generate_share_token(conn, template_id, g.user['id'])
    log_audit_event(conn, g.user['id'], 'create', 'share_token', template_id)

    # Store raw token in session so it can be shown ONCE on the next page load
    session['new_token'] = raw_token
    flash('Share token generated. Copy it now -- it will not be shown again.', 'success')
    return redirect(url_for('admin.tokens_list'))


@bp.route('/tokens/<int:id>/revoke', methods=['POST'])
@admin_required
def token_revoke(id):
    conn = get_db()

    # Verify token exists
    token = conn.execute('SELECT * FROM share_tokens WHERE id = ?', (id,)).fetchone()
    if token is None:
        abort(404)

    revoke_token(conn, id)
    log_audit_event(conn, g.user['id'], 'revoke', 'share_token', id)
    flash('Token revoked.', 'success')
    return redirect(url_for('admin.tokens_list'))


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

@bp.route('/export')
@admin_required
def export_page():
    return render_template('admin/export.html')


@bp.route('/export', methods=['POST'])
@admin_required
def export_data():
    conn = get_db()
    export_format = request.form.get('format', '').strip()

    if export_format not in ('csv', 'json'):
        flash('Invalid format.', 'error')
        return redirect(url_for('admin.export_page'))

    log_audit_event(conn, g.user['id'], 'export', 'all_prompts', None)

    if export_format == 'json':
        json_data = export_all_prompts_json(conn)
        return Response(
            json_data,
            mimetype='application/json',
            headers={'Content-Disposition': 'attachment; filename=prompts_export.json'},
        )

    # CSV export -- reuse the JSON data to build CSV
    import json
    data = json.loads(export_all_prompts_json(conn))
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Title', 'Industry', 'User', 'Completeness', 'Grade', 'Created'])
    for item in data:
        grade_score = item['grade']['score'] if item.get('grade') else ''
        writer.writerow([
            item['title'], item['industry'], item['user'],
            f"{item['completeness']:.0%}", grade_score, item['created_at'],
        ])
    csv_data = output.getvalue()
    return Response(
        csv_data,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=prompts_export.csv'},
    )
