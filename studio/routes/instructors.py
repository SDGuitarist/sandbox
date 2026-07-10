"""Instructors blueprint — list, create (admin), view, edit (admin)."""
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    abort,
)

from studio.auth import role_required, current_user
from studio.models import instructor_models
from studio.models.audit_models import record

bp = Blueprint('instructors', __name__, url_prefix='/instructors')


def _validate_instructor_form(form):
    """Validate new/edit POST input.

    Returns (values, errors): values is a dict of cleaned fields, errors is a
    list of human-readable messages. hourly_rate_cents must be a non-negative
    integer; first_name + last_name must be non-empty.
    """
    first_name = (form.get('first_name') or '').strip()
    last_name = (form.get('last_name') or '').strip()
    email = (form.get('email') or '').strip() or None
    phone = (form.get('phone') or '').strip() or None
    bio = (form.get('bio') or '').strip() or None
    rate_raw = (form.get('hourly_rate_cents') or '').strip()

    errors = []
    if not first_name:
        errors.append('First name is required.')
    if not last_name:
        errors.append('Last name is required.')

    hourly_rate_cents = 0
    if rate_raw:
        try:
            hourly_rate_cents = int(rate_raw)
        except (TypeError, ValueError):
            errors.append('Hourly rate must be a whole number of cents.')
        else:
            if hourly_rate_cents < 0:
                errors.append('Hourly rate must be zero or greater.')

    values = {
        'first_name': first_name,
        'last_name': last_name,
        'email': email,
        'phone': phone,
        'bio': bio,
        'hourly_rate_cents': hourly_rate_cents,
    }
    return values, errors


@bp.route('/')
@role_required('admin', 'instructor')
def list_instructors():
    instructors = instructor_models.list_instructors()
    return render_template('instructors/list.html', instructors=instructors)


@bp.route('/new', methods=['GET', 'POST'])
@role_required('admin')
def create_instructor():
    if request.method == 'POST':
        values, errors = _validate_instructor_form(request.form)
        if errors:
            for message in errors:
                flash(message, 'error')
            return render_template('instructors/new.html', values=values), 400
        iid = instructor_models.create_instructor(
            first_name=values['first_name'],
            last_name=values['last_name'],
            email=values['email'],
            phone=values['phone'],
            bio=values['bio'],
            hourly_rate_cents=values['hourly_rate_cents'],
        )
        record(current_user()['id'], 'create', 'instructor', iid)
        flash('Instructor created.', 'success')
        return redirect(url_for('instructors.view_instructor', iid=iid))
    return render_template('instructors/new.html', values={})


@bp.route('/<int:iid>')
@role_required('admin', 'instructor')
def view_instructor(iid):
    instructor = instructor_models.get_instructor(iid) or abort(404)
    return render_template('instructors/view.html', instructor=instructor)


@bp.route('/<int:iid>/edit', methods=['GET', 'POST'])
@role_required('admin')
def edit_instructor(iid):
    instructor = instructor_models.get_instructor(iid) or abort(404)
    if request.method == 'POST':
        values, errors = _validate_instructor_form(request.form)
        if errors:
            for message in errors:
                flash(message, 'error')
            return (
                render_template(
                    'instructors/edit.html', instructor=instructor, values=values
                ),
                400,
            )
        instructor_models.update_instructor(
            iid,
            first_name=values['first_name'],
            last_name=values['last_name'],
            email=values['email'],
            phone=values['phone'],
            bio=values['bio'],
            hourly_rate_cents=values['hourly_rate_cents'],
        )
        record(current_user()['id'], 'update', 'instructor', iid)
        flash('Instructor updated.', 'success')
        return redirect(url_for('instructors.view_instructor', iid=iid))
    return render_template(
        'instructors/edit.html', instructor=instructor, values=instructor
    )
