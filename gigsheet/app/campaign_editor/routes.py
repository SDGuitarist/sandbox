from flask import Blueprint, render_template, request, redirect, url_for, flash, g, abort

from app.db import get_db
from app.decorators import login_required, require_workspace
from app.models import (
    create_campaign,
    get_campaign,
    update_campaign,
    add_recipients,
    get_campaign_recipients,
    get_templates_by_workspace,
    get_leads_by_workspace,
    get_template,
    log_activity,
)

campaign_editor_bp = Blueprint(
    'campaign_editor',
    __name__,
    template_folder='../templates',
)


@campaign_editor_bp.route('/new')
@login_required
@require_workspace
def new():
    """Show the create-campaign form."""
    conn = get_db()
    templates = get_templates_by_workspace(conn, g.workspace['id'])
    return render_template(
        'campaign_editor/form.html',
        campaign=None,
        is_edit=False,
        templates=templates,
    )


@campaign_editor_bp.route('/new', methods=['POST'])
@login_required
@require_workspace
def create():
    """Handle campaign creation."""
    conn = get_db()

    name = request.form.get('name', '').strip()[:100]
    template_id = request.form.get('template_id', type=int)

    if not name:
        flash('Name is required.', 'error')
        return redirect(url_for('campaign_editor.new'))

    if template_id is None:
        flash('Please select a template.', 'error')
        return redirect(url_for('campaign_editor.new'))

    # Verify the selected template belongs to this workspace
    template = get_template(conn, template_id)
    if template is None or template['workspace_id'] != g.workspace['id']:
        flash('Invalid template selected.', 'error')
        return redirect(url_for('campaign_editor.new'))

    campaign_id = create_campaign(
        conn, g.workspace['id'], name, template_id, g.user['id']
    )
    log_activity(
        conn, g.workspace['id'], g.user['id'],
        'created_campaign', 'campaign', campaign_id, f'Campaign: {name}'
    )
    conn.commit()

    flash('Campaign created successfully.', 'success')
    return redirect(url_for('campaign_editor.detail', id=campaign_id))


@campaign_editor_bp.route('/<int:id>')
@login_required
@require_workspace
def detail(id):
    """Show campaign detail with recipients and available leads."""
    conn = get_db()

    campaign = get_campaign(conn, id)
    if campaign is None:
        abort(404)
    if campaign['workspace_id'] != g.workspace['id']:
        abort(403)

    template = get_template(conn, campaign['template_id']) if campaign['template_id'] else None
    recipients = get_campaign_recipients(conn, id)

    # Build set of lead IDs already in this campaign for exclusion
    recipient_lead_ids = {r['lead_id'] for r in recipients}

    # Get all workspace leads (no pagination -- need full list for checkbox selection)
    all_leads = get_leads_by_workspace(conn, g.workspace['id'], page=1, per_page=10000)
    available_leads = [lead for lead in all_leads if lead['id'] not in recipient_lead_ids]

    return render_template(
        'campaign_editor/detail.html',
        campaign=campaign,
        template=template,
        recipients=recipients,
        total_recipients=len(recipients),
        available_leads=available_leads,
    )


@campaign_editor_bp.route('/<int:id>/edit')
@login_required
@require_workspace
def edit(id):
    """Show the edit-campaign form."""
    conn = get_db()

    campaign = get_campaign(conn, id)
    if campaign is None:
        abort(404)
    if campaign['workspace_id'] != g.workspace['id']:
        abort(403)

    templates = get_templates_by_workspace(conn, g.workspace['id'])
    return render_template(
        'campaign_editor/form.html',
        campaign=campaign,
        is_edit=True,
        templates=templates,
    )


@campaign_editor_bp.route('/<int:id>/edit', methods=['POST'])
@login_required
@require_workspace
def update(id):
    """Handle campaign edit submission."""
    conn = get_db()

    campaign = get_campaign(conn, id)
    if campaign is None:
        abort(404)
    if campaign['workspace_id'] != g.workspace['id']:
        abort(403)

    name = request.form.get('name', '').strip()[:100]
    template_id = request.form.get('template_id', type=int)

    if not name:
        flash('Name is required.', 'error')
        return redirect(url_for('campaign_editor.edit', id=id))

    if template_id is None:
        flash('Please select a template.', 'error')
        return redirect(url_for('campaign_editor.edit', id=id))

    # Verify the selected template belongs to this workspace
    template = get_template(conn, template_id)
    if template is None or template['workspace_id'] != g.workspace['id']:
        flash('Invalid template selected.', 'error')
        return redirect(url_for('campaign_editor.edit', id=id))

    update_campaign(conn, id, name=name, template_id=template_id)
    log_activity(
        conn, g.workspace['id'], g.user['id'],
        'updated_campaign', 'campaign', id, f'Campaign: {name}'
    )
    conn.commit()

    flash('Campaign updated successfully.', 'success')
    return redirect(url_for('campaign_editor.detail', id=id))


@campaign_editor_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@require_workspace
def delete(id):
    """Delete a campaign (only drafts can be deleted)."""
    conn = get_db()

    campaign = get_campaign(conn, id)
    if campaign is None:
        abort(404)
    if campaign['workspace_id'] != g.workspace['id']:
        abort(403)

    if campaign['status'] != 'draft':
        flash('Only draft campaigns can be deleted.', 'error')
        return redirect(url_for('campaign_editor.detail', id=id))

    campaign_name = campaign['name']
    conn.execute('DELETE FROM campaigns WHERE id = ?', (id,))
    log_activity(
        conn, g.workspace['id'], g.user['id'],
        'deleted_campaign', 'campaign', id, f'Campaign: {campaign_name}'
    )
    conn.commit()

    flash('Campaign deleted.', 'success')
    return redirect(url_for('campaign_list.index'))


@campaign_editor_bp.route('/<int:id>/recipients', methods=['POST'])
@login_required
@require_workspace
def manage_recipients(id):
    """Add leads as recipients to a campaign."""
    conn = get_db()

    campaign = get_campaign(conn, id)
    if campaign is None:
        abort(404)
    if campaign['workspace_id'] != g.workspace['id']:
        abort(403)

    lead_ids = request.form.getlist('lead_ids[]', type=int)
    if not lead_ids:
        flash('No leads selected.', 'error')
        return redirect(url_for('campaign_editor.detail', id=id))

    # add_recipients does NOT commit -- we commit after
    add_recipients(conn, id, lead_ids)
    log_activity(
        conn, g.workspace['id'], g.user['id'],
        'added_recipients', 'campaign', id,
        f'Added {len(lead_ids)} recipients to campaign: {campaign["name"]}'
    )
    conn.commit()

    flash(f'{len(lead_ids)} recipient(s) added.', 'success')
    return redirect(url_for('campaign_editor.detail', id=id))
