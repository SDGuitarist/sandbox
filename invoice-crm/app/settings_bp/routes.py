from flask import render_template, request, session, flash, redirect, url_for

from app.db import get_db
from app.helpers import login_required
from app.settings_bp import bp
from app.settings_bp.forms import SettingsForm


@bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    """Display and update user business settings."""
    form = SettingsForm()

    if request.method == 'GET':
        with get_db() as db:
            user = db.execute(
                "SELECT * FROM users WHERE id = ?",
                (session['user_id'],)
            ).fetchone()

            if user:
                form.company_name.data = user['company_name']
                form.logo_url.data = user['logo_url']
                form.address.data = user['address']
                form.phone.data = user['phone']
                form.business_email.data = user['business_email']
                form.tax_id.data = user['tax_id']
                form.invoice_prefix.data = user['invoice_prefix']
                form.default_payment_terms.data = str(user['default_payment_terms'])
                form.default_tax_rate.data = user['default_tax_rate']
                form.currency.data = user['currency']

        return render_template('settings_bp/index.html', form=form)

    # POST
    if form.validate_on_submit():
        with get_db() as db:
            db.execute("""
                UPDATE users SET
                    company_name = ?,
                    logo_url = ?,
                    address = ?,
                    phone = ?,
                    business_email = ?,
                    tax_id = ?,
                    invoice_prefix = ?,
                    default_payment_terms = ?,
                    default_tax_rate = ?,
                    currency = ?
                WHERE id = ?
            """, (
                form.company_name.data or '',
                form.logo_url.data or '',
                form.address.data or '',
                form.phone.data or '',
                form.business_email.data or '',
                form.tax_id.data or '',
                form.invoice_prefix.data,
                int(form.default_payment_terms.data),
                float(form.default_tax_rate.data) if form.default_tax_rate.data is not None else 0.0,
                form.currency.data,
                session['user_id']
            ))
            db.commit()

        flash('Settings updated successfully.', 'success')
        return redirect(url_for('settings_bp.index'))

    # Form validation failed
    for field, errors in form.errors.items():
        for error in errors:
            flash(f'{getattr(form, field).label.text}: {error}', 'danger')

    return render_template('settings_bp/index.html', form=form)
