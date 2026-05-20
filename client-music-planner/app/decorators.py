from functools import wraps
from flask import session, flash, redirect, url_for, abort, g
from .db import get_request_db
from .models import get_event_by_token


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


def require_portal_token(f):
    """Validates portal token and sets g.portal_event and g.portal_is_approved.
    Returns 404 for invalid/archived tokens (no information leak).
    Uses request-scoped connection (closed in teardown) to avoid double-open."""
    @wraps(f)
    def decorated_function(token, *args, **kwargs):
        db = get_request_db()
        event = get_event_by_token(db, token)
        if event is None:
            abort(404)
        if event['is_archived']:
            abort(404)
        g.portal_event = event
        g.portal_is_approved = bool(event['client_approved'])
        return f(token, *args, **kwargs)
    return decorated_function


def require_portal_writable(f):
    """Must be used AFTER @require_portal_token.
    Blocks all writes when event is approved."""
    @wraps(f)
    def decorated_function(token, *args, **kwargs):
        if g.portal_is_approved:
            flash("This event has been approved and is now locked.", "warning")
            return redirect(url_for('portal_browse.browse', token=token))
        return f(token, *args, **kwargs)
    return decorated_function
