from flask import render_template, redirect, url_for, flash, session, request
from werkzeug.security import generate_password_hash, check_password_hash

from app.db import get_db
from app.helpers import login_required
from . import bp
from .forms import LoginForm, RegisterForm, ProfileForm


@bp.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.strip()
        password = form.password.data
        with get_db() as db:
            user = db.execute(
                "SELECT * FROM users WHERE email = ?", (email,)
            ).fetchone()
            if user and check_password_hash(user['password_hash'], password):
                session.clear()  # Regenerate session to prevent fixation
                session['user_id'] = user['id']
                return redirect(url_for('dashboard.index'))
            flash('Invalid email or password.', 'danger')
    return render_template('auth/login.html', form=form)


@bp.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        email = form.email.data.strip()
        password = form.password.data
        with get_db() as db:
            existing = db.execute(
                "SELECT id FROM users WHERE email = ?", (email,)
            ).fetchone()
            if existing:
                flash('An account with that email already exists.', 'danger')
                return render_template('auth/register.html', form=form)
            db.execute(
                "INSERT INTO users (email, password_hash) VALUES (?, ?)",
                (email, generate_password_hash(password)),
            )
            db.commit()
        flash('Registration successful. Please log in.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('auth/register.html', form=form)


@bp.route('/logout', methods=['POST'])
@login_required
def logout():
    session.clear()
    return redirect(url_for('auth.login'))


@bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = ProfileForm()
    with get_db() as db:
        user = db.execute(
            "SELECT * FROM users WHERE id = ?", (session['user_id'],)
        ).fetchone()
        if not user:
            flash('User not found.', 'danger')
            return redirect(url_for('auth.login'))
        if form.validate_on_submit():
            db.execute(
                """UPDATE users SET company_name = ?, logo_url = ?, address = ?,
                   phone = ?, business_email = ?, tax_id = ?
                   WHERE id = ?""",
                (
                    form.company_name.data.strip(),
                    form.logo_url.data.strip(),
                    form.address.data.strip(),
                    form.phone.data.strip(),
                    form.business_email.data.strip(),
                    form.tax_id.data.strip(),
                    session['user_id'],
                ),
            )
            db.commit()
            flash('Profile updated successfully.', 'success')
            return redirect(url_for('auth.profile'))
        form.company_name.data = user['company_name']
        form.logo_url.data = user['logo_url']
        form.address.data = user['address']
        form.phone.data = user['phone']
        form.business_email.data = user['business_email']
        form.tax_id.data = user['tax_id']
    return render_template('auth/profile.html', form=form)
