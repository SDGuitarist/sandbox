from flask import Blueprint, flash, redirect, render_template, request, url_for
from app.db import get_db
from app import limiter
from app.models.submissions import create_submission
from email_validator import validate_email, EmailNotValidError

intake_bp = Blueprint('intake', __name__)


@intake_bp.route('/', methods=['GET', 'POST'])
@limiter.limit("5 per minute", methods=['POST'])
def intake_form():
    if request.method == 'POST':
        # Check honeypot BEFORE other validation
        website = request.form.get('website', '')
        if website:
            return redirect(url_for('intake.thank_you'))

        errors = []
        fields = {}

        # Short text fields (required)
        for field, label, max_len in [
            ('contact_name', 'Contact name', 100),
            ('business_name', 'Business name', 200),
            ('business_type', 'Business type / industry', 200),
            ('team_size', 'Team size', 100),
            ('urgency', 'Urgency / timeline', 200),
        ]:
            val = request.form.get(field, '').strip()[:max_len]
            if not val:
                errors.append(f'{label} is required')
            fields[field] = val

        # Long text fields (required)
        for field, label in [
            ('current_workflows', 'Current workflows description'),
            ('pain_points', 'Pain points description'),
            ('tools_used', 'Tools currently used'),
            ('goals', 'Goals / desired outcomes'),
        ]:
            val = request.form.get(field, '').strip()[:2000]
            if not val:
                errors.append(f'{label} is required')
            fields[field] = val

        # Email validation
        email = request.form.get('email', '').strip()[:254]
        try:
            valid = validate_email(email, check_deliverability=False)
            email = valid.normalized
        except EmailNotValidError:
            errors.append('Valid email is required')
        fields['email'] = email

        # Optional notes
        fields['submitter_notes'] = request.form.get(
            'submitter_notes', ''
        ).strip()[:2000]

        if errors:
            for e in errors:
                flash(e, 'error')
            return render_template('intake/form.html')

        conn = get_db()
        create_submission(conn, fields)
        return redirect(url_for('intake.thank_you'))

    return render_template('intake/form.html')


@intake_bp.route('/thank-you')
def thank_you():
    return render_template('intake/thank_you.html')
