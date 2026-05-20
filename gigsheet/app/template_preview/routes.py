from flask import Blueprint, request, jsonify, g, current_app, abort
from app.db import get_db
from app.models import get_template, render_template_with_lead, get_lead
from app.sendgrid_client import send_email
from app.decorators import login_required, require_workspace

template_preview_bp = Blueprint('template_preview', __name__)


@template_preview_bp.route('/render', methods=['POST'])
@login_required
@require_workspace
def render():
    """Render a template with a lead's merge fields.
    Accepts JSON: {"template_id": int, "lead_id": int}
    Returns JSON: {"subject": str, "body": str}
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Request must be JSON.'}), 400

    template_id = data.get('template_id')
    lead_id = data.get('lead_id')

    if not template_id or not lead_id:
        return jsonify({'error': 'template_id and lead_id are required.'}), 400

    conn = get_db()

    # Fetch template and verify workspace ownership (FC35)
    template = get_template(conn, template_id)
    if template is None:
        abort(404)
    if template['workspace_id'] != g.workspace['id']:
        abort(403)

    # Fetch lead and verify workspace ownership (FC35)
    lead = get_lead(conn, lead_id)
    if lead is None:
        abort(404)
    if lead['workspace_id'] != g.workspace['id']:
        abort(403)

    subject, body = render_template_with_lead(template, lead)

    return jsonify({'subject': subject, 'body': body})


@template_preview_bp.route('/send', methods=['POST'])
@login_required
@require_workspace
def send_test():
    """Send a test email with rendered template content.
    Accepts JSON: {"template_id": int, "to_email": str}
    Returns JSON: {"status": str, "message_id": str}
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Request must be JSON.'}), 400

    template_id = data.get('template_id')
    to_email = data.get('to_email', '').strip()

    if not template_id or not to_email:
        return jsonify({'error': 'template_id and to_email are required.'}), 400

    # Basic email format check
    if '@' not in to_email or '.' not in to_email:
        return jsonify({'error': 'Invalid email address.'}), 400

    conn = get_db()

    # Fetch template and verify workspace ownership (FC35)
    template = get_template(conn, template_id)
    if template is None:
        abort(404)
    if template['workspace_id'] != g.workspace['id']:
        abort(403)

    # For test send, use template subject/body as-is (merge fields stay as placeholders)
    subject = template['subject_line']
    body = template['html_body']

    from_email = current_app.config['SENDGRID_FROM_EMAIL']
    result = send_email(to_email, from_email, subject, body)

    return jsonify({
        'status': result.get('status', 'failed'),
        'message_id': result.get('message_id', ''),
    })
