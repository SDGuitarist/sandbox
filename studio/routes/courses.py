"""Courses blueprint — catalog list/view (any logged-in) + create/edit (staff).

Owned by the route-course agent. Imports the course + instructor model modules
(SHADOWING pin: import MODULES, not names) and audit_models for post-commit records.
"""
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    abort,
)

from studio.auth import login_required, role_required, current_user
from studio.models import course_models, instructor_models
from studio.models import audit_models

bp = Blueprint('courses', __name__, url_prefix='/courses')

_LEVELS = ('beginner', 'intermediate', 'advanced')


def _parse_int(raw, minimum):
    """Return int(raw) if it parses and is >= minimum, else None."""
    if raw is None:
        return None
    raw = raw.strip()
    if raw == '':
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    if value < minimum:
        return None
    return value


def _validate_form(form):
    """Validate a create/edit course form.

    Returns (values, error). `values` is a dict of cleaned fields;
    `error` is a user-facing message or None.
    """
    name = (form.get('name') or '').strip()
    description = (form.get('description') or '').strip() or None
    level = (form.get('level') or '').strip()
    capacity_raw = form.get('capacity')
    price_raw = form.get('price_cents')
    instructor_raw = (form.get('instructor_id') or '').strip()

    values = {
        'name': name,
        'description': description,
        'level': level,
        'capacity': capacity_raw,
        'price_cents': price_raw,
        'instructor_id': instructor_raw,
    }

    if not name:
        return values, 'Name is required.'
    if level not in _LEVELS:
        return values, 'Level must be beginner, intermediate, or advanced.'

    capacity = _parse_int(capacity_raw, 1)
    if capacity is None:
        return values, 'Capacity must be a whole number of at least 1.'

    price_cents = _parse_int(price_raw, 0)
    if price_cents is None:
        return values, 'Price must be a whole number of cents (0 or more).'

    instructor_id = None
    if instructor_raw:
        instructor_id = _parse_int(instructor_raw, 1)
        if instructor_id is None or instructor_models.get_instructor(instructor_id) is None:
            return values, 'Selected instructor does not exist.'

    values['capacity'] = capacity
    values['price_cents'] = price_cents
    values['instructor_id'] = instructor_id
    return values, None


@bp.route('/')
@login_required
def list_courses():
    courses = course_models.list_courses()
    return render_template('courses/list.html', courses=courses)


@bp.route('/new', methods=('GET', 'POST'))
@role_required('admin', 'instructor')
def create_course():
    instructors = instructor_models.list_instructors(active_only=True)
    if request.method == 'POST':
        values, error = _validate_form(request.form)
        if error:
            flash(error, 'error')
            return render_template(
                'courses/new.html', instructors=instructors, values=values
            ), 400
        cid = course_models.create_course(
            name=values['name'],
            description=values['description'],
            instructor_id=values['instructor_id'],
            level=values['level'],
            capacity=values['capacity'],
            price_cents=values['price_cents'],
        )
        audit_models.record(
            current_user()['id'], 'create', 'course', cid, values['name']
        )
        flash('Course created.', 'success')
        return redirect(url_for('courses.view_course', cid=cid))
    return render_template('courses/new.html', instructors=instructors, values={})


@bp.route('/<int:cid>')
@login_required
def view_course(cid):
    course = course_models.get_course(cid)
    if course is None:
        abort(404)
    enrolled = course_models.count_enrolled(cid)
    return render_template('courses/view.html', course=course, enrolled=enrolled)


@bp.route('/<int:cid>/edit', methods=('GET', 'POST'))
@role_required('admin', 'instructor')
def edit_course(cid):
    course = course_models.get_course(cid)
    if course is None:
        abort(404)
    instructors = instructor_models.list_instructors(active_only=True)
    if request.method == 'POST':
        values, error = _validate_form(request.form)
        if error:
            flash(error, 'error')
            return render_template(
                'courses/edit.html',
                course=course,
                instructors=instructors,
                values=values,
            ), 400
        course_models.update_course(
            cid,
            name=values['name'],
            description=values['description'],
            instructor_id=values['instructor_id'],
            level=values['level'],
            capacity=values['capacity'],
            price_cents=values['price_cents'],
        )
        audit_models.record(
            current_user()['id'], 'update', 'course', cid, values['name']
        )
        flash('Course updated.', 'success')
        return redirect(url_for('courses.view_course', cid=cid))

    values = {
        'name': course.get('name'),
        'description': course.get('description'),
        'level': course.get('level'),
        'capacity': course.get('capacity'),
        'price_cents': course.get('price_cents'),
        'instructor_id': course.get('instructor_id'),
    }
    return render_template(
        'courses/edit.html', course=course, instructors=instructors, values=values
    )
