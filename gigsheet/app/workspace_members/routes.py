from flask import Blueprint, render_template, request, redirect, url_for, flash, g, abort
from app.db import get_db
from app.models import (
    get_workspace_members,
    add_workspace_member,
    remove_workspace_member,
    update_member_role,
    get_user_by_email,
    create_notification,
    log_activity,
    get_workspace_member,
)
from app.decorators import login_required, require_workspace, require_role
from app import WORKSPACE_ROLES

workspace_members_bp = Blueprint('workspace_members', __name__)


@workspace_members_bp.route('/')
@login_required
@require_workspace
def index():
    """List all members of the current workspace."""
    conn = get_db()
    members = get_workspace_members(conn, g.workspace['id'])
    return render_template(
        'workspace_members/index.html',
        members=members,
        roles=WORKSPACE_ROLES,
    )


@workspace_members_bp.route('/invite', methods=['POST'])
@login_required
@require_workspace
@require_role('owner', 'admin')
def invite():
    """Invite a user to the workspace by email."""
    email = request.form.get('email', '').strip()
    role = request.form.get('role', '').strip()

    if not email:
        flash('Email is required.', 'error')
        return redirect(url_for('workspace_members.index'))

    if role not in WORKSPACE_ROLES:
        flash('Invalid role.', 'error')
        return redirect(url_for('workspace_members.index'))

    # Owners cannot be invited -- only the workspace creator is owner
    if role == 'owner':
        flash('Cannot invite as owner.', 'error')
        return redirect(url_for('workspace_members.index'))

    conn = get_db()

    # Look up the user by email
    user = get_user_by_email(conn, email)
    if user is None:
        flash('No user found with that email.', 'error')
        return redirect(url_for('workspace_members.index'))

    # Check if user is already a member
    existing = get_workspace_member(conn, g.workspace['id'], user['id'])
    if existing is not None:
        flash('User is already a member of this workspace.', 'error')
        return redirect(url_for('workspace_members.index'))

    add_workspace_member(conn, g.workspace['id'], user['id'], role)
    create_notification(
        conn, g.workspace['id'], user['id'],
        f"You were invited to workspace '{g.workspace['name']}' as {role}.",
        link=url_for('workspace_members.index'),
    )
    log_activity(
        conn, g.workspace['id'], g.user['id'],
        'invited_member', 'workspace_member', user['id'],
        f'Invited {email} as {role}',
    )
    conn.commit()

    flash(f'{email} has been invited as {role}.', 'success')
    return redirect(url_for('workspace_members.index'))


@workspace_members_bp.route('/<int:id>/remove', methods=['POST'])
@login_required
@require_workspace
@require_role('owner', 'admin')
def remove(id):
    """Remove a member from the workspace. Cannot remove the owner."""
    conn = get_db()

    # Verify the member exists in this workspace
    member = get_workspace_member(conn, g.workspace['id'], id)
    if member is None:
        abort(404)

    # Cannot remove the owner
    if member['role'] == 'owner':
        flash('Cannot remove the workspace owner.', 'error')
        return redirect(url_for('workspace_members.index'))

    remove_workspace_member(conn, g.workspace['id'], id)
    log_activity(
        conn, g.workspace['id'], g.user['id'],
        'removed_member', 'workspace_member', id,
        f'Removed user {id}',
    )
    conn.commit()

    flash('Member removed.', 'success')
    return redirect(url_for('workspace_members.index'))


@workspace_members_bp.route('/<int:id>/role', methods=['POST'])
@login_required
@require_workspace
@require_role('owner', 'admin')
def change_role(id):
    """Change a member's role. Cannot change the owner's role."""
    role = request.form.get('role', '').strip()

    if role not in WORKSPACE_ROLES:
        flash('Invalid role.', 'error')
        return redirect(url_for('workspace_members.index'))

    # Cannot assign owner role
    if role == 'owner':
        flash('Cannot assign owner role.', 'error')
        return redirect(url_for('workspace_members.index'))

    conn = get_db()

    # Verify the member exists in this workspace
    member = get_workspace_member(conn, g.workspace['id'], id)
    if member is None:
        abort(404)

    # Cannot change the owner's role
    if member['role'] == 'owner':
        flash('Cannot change the owner\'s role.', 'error')
        return redirect(url_for('workspace_members.index'))

    update_member_role(conn, g.workspace['id'], id, role)
    log_activity(
        conn, g.workspace['id'], g.user['id'],
        'changed_role', 'workspace_member', id,
        f'Changed role to {role}',
    )
    conn.commit()

    flash(f'Role updated to {role}.', 'success')
    return redirect(url_for('workspace_members.index'))
