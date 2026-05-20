import uuid
import json
from flask import current_app

def send_email(to_email: str, from_email: str, subject: str, html_body: str,
               tracking_id: str = '') -> dict:
    """Send an email via SendGrid or mock.
    Returns: {"status": "accepted", "message_id": "sg-xxx" or "mock-xxx"}
    Does NOT write to DB. Pure function.
    """
    mode = current_app.config.get('SENDGRID_MODE', 'mock')
    if mode == 'live':
        return _send_live(to_email, from_email, subject, html_body, tracking_id)
    return _send_mock(to_email, from_email, subject, html_body, tracking_id)

def _send_mock(to_email, from_email, subject, html_body, tracking_id):
    message_id = f'mock-{uuid.uuid4().hex[:12]}'
    current_app.logger.info(f'[MOCK SEND] to={to_email} subject={subject} id={message_id}')
    return {'status': 'accepted', 'message_id': message_id}

def _send_live(to_email, from_email, subject, html_body, tracking_id):
    import urllib.request
    api_key = current_app.config['SENDGRID_API_KEY']
    payload = json.dumps({
        'personalizations': [{'to': [{'email': to_email}]}],
        'from': {'email': from_email},
        'subject': subject,
        'content': [{'type': 'text/html', 'value': html_body}],
        'custom_args': {'tracking_id': tracking_id}
    }).encode()
    req = urllib.request.Request(
        'https://api.sendgrid.com/v3/mail/send',
        data=payload,
        headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
        method='POST'
    )
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        message_id = resp.headers.get('X-Message-Id', f'sg-{uuid.uuid4().hex[:12]}')
        return {'status': 'accepted', 'message_id': message_id}
    except Exception as e:
        return {'status': 'failed', 'message_id': '', 'error': str(e)}
