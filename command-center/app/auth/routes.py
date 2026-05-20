from flask import flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from ..db import get_db
from . import bp

INDUSTRIES = [
    'consulting', 'design', 'development', 'coaching', 'marketing', 'other',
]


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('auth/login.html')

    # POST -- validate email + password
    email = (request.form.get('email') or '').strip()
    password = request.form.get('password') or ''

    if not email or not password:
        flash('Email and password are required.', 'error')
        return render_template('auth/login.html')

    with get_db() as db:
        user = db.execute(
            "SELECT * FROM user WHERE email = ?", (email,)
        ).fetchone()

    if user is None or not check_password_hash(user['password_hash'], password):
        flash('Invalid email or password.', 'error')
        return render_template('auth/login.html')

    session.clear()  # Prevent session fixation
    session['user_id'] = user['id']
    return redirect(url_for('dashboard.index'))


@bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('auth/register.html')

    # POST -- validate and create account
    email = (request.form.get('email') or '').strip()
    password = request.form.get('password') or ''
    confirm_password = request.form.get('confirm_password') or ''

    if not email or not password:
        flash('Email and password are required.', 'error')
        return render_template('auth/register.html')

    if password != confirm_password:
        flash('Passwords do not match.', 'error')
        return render_template('auth/register.html')

    if len(password) < 8:
        flash('Password must be at least 8 characters.', 'error')
        return render_template('auth/register.html')

    # Check + insert in single transaction to prevent race condition
    with get_db(immediate=True) as db:
        existing = db.execute(
            "SELECT id FROM user WHERE email = ?", (email,)
        ).fetchone()

        if existing is not None:
            flash('An account with that email already exists.', 'error')
            return render_template('auth/register.html')

        db.execute(
            "INSERT INTO user (email, password_hash, setup_complete) VALUES (?, ?, 0)",
            (email, generate_password_hash(password)),
        )
        user_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

    session['user_id'] = user_id
    return redirect(url_for('auth.setup'))


@bp.route('/setup', methods=['GET', 'POST'])
def setup():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    if request.method == 'GET':
        return render_template('auth/setup.html', industries=INDUSTRIES)

    # POST -- validate and save business profile
    business_name = (request.form.get('business_name') or '').strip()
    owner_name = (request.form.get('owner_name') or '').strip()
    industry = (request.form.get('industry') or '').strip()
    currency_symbol = (request.form.get('currency_symbol') or '').strip()
    fiscal_year_start = (request.form.get('fiscal_year_start') or '').strip()

    if not business_name or not owner_name:
        flash('Business name and owner name are required.', 'error')
        return render_template('auth/setup.html', industries=INDUSTRIES)

    if industry not in INDUSTRIES:
        flash('Please select a valid industry.', 'error')
        return render_template('auth/setup.html', industries=INDUSTRIES)

    if not currency_symbol:
        currency_symbol = '$'

    if not fiscal_year_start:
        fiscal_year_start = '1'

    # Validate fiscal_year_start is 1-12
    try:
        month = int(fiscal_year_start)
        if month < 1 or month > 12:
            raise ValueError
    except ValueError:
        flash('Fiscal year start must be a month (1-12).', 'error')
        return render_template('auth/setup.html', industries=INDUSTRIES)

    user_id = session['user_id']

    with get_db(immediate=True) as db:
        db.execute(
            "INSERT INTO business_profile "
            "(user_id, business_name, owner_name, industry, currency_symbol, fiscal_year_start) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, business_name, owner_name, industry, currency_symbol, fiscal_year_start),
        )
        profile_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Log setup activity
        db.execute(
            "INSERT INTO activity_log (action, entity_type, entity_id, description) "
            "VALUES (?, ?, ?, ?)",
            ('updated', 'business_profile', profile_id, 'Updated business profile'),
        )

        # Mark user setup as complete
        db.execute(
            "UPDATE user SET setup_complete = 1 WHERE id = ?",
            (user_id,),
        )

    flash('Business profile saved!', 'success')
    return redirect(url_for('dashboard.index'))


@bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
