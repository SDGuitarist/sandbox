from functools import wraps
from flask import session, redirect, url_for, flash


def dollars(cents):
    """Convert cents to dollar display: 15099 -> '$150.99'"""
    if cents is None:
        return '$0.00'
    return f'${cents / 100:,.2f}'


def format_date(date_str):
    """Format ISO date string: '2026-05-19' -> 'May 19, 2026'"""
    if not date_str:
        return ''
    from datetime import datetime
    try:
        dt = datetime.strptime(date_str[:10], '%Y-%m-%d')
        return dt.strftime('%b %d, %Y')
    except (ValueError, TypeError):
        return date_str


def register_filters(app):
    app.jinja_env.filters['dollars'] = dollars
    app.jinja_env.filters['format_date'] = format_date


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


def log_activity(db, client_id, user_id, activity_type, notes):
    """Log an activity. Does NOT commit."""
    if client_id:
        db.execute("""
            INSERT INTO activities (client_id, user_id, type, notes, activity_date)
            VALUES (?, ?, ?, ?, date('now'))
        """, (client_id, user_id, activity_type, notes))
