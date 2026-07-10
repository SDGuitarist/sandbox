"""Students blueprint — list, create, view (ownership-scoped), edit, deactivate.

Owned by the student route agent. Imports model MODULES (not names) to avoid
shadowing the view functions that share names with the model functions.
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
from studio.models import student_models
from studio.models import audit_models

bp = Blueprint('students', __name__, url_prefix='/students')

SKILL_LEVELS = ('beginner', 'intermediate', 'advanced')


def _clean(value):
    """Trim a form value; return '' for missing."""
    return (value or '').strip()


def _validate_student_form(form):
    """Return (fields_dict, error_message_or_None) for new/edit POST bodies."""
    first_name = _clean(form.get('first_name'))
    last_name = _clean(form.get('last_name'))
    email = _clean(form.get('email'))
    phone = _clean(form.get('phone'))
    skill_level = _clean(form.get('skill_level')) or 'beginner'
    notes = _clean(form.get('notes'))

    fields = {
        'first_name': first_name,
        'last_name': last_name,
        'email': email,
        'phone': phone,
        'skill_level': skill_level,
        'notes': notes,
    }

    if not first_name or not last_name:
        return fields, 'First name and last name are required.'
    if skill_level not in SKILL_LEVELS:
        return fields, 'Skill level must be beginner, intermediate, or advanced.'
    return fields, None


@bp.route('/')
@role_required('admin', 'instructor')
def list_students():
    q = _clean(request.args.get('q')) or None
    active_only = request.args.get('active_only') == '1'
    students = student_models.list_students(active_only=active_only, q=q)
    return render_template(
        'students/list.html',
        students=students,
        q=q or '',
        active_only=active_only,
    )


@bp.route('/new', methods=['GET', 'POST'])
@role_required('admin', 'instructor')
def create_student():
    if request.method == 'POST':
        fields, error = _validate_student_form(request.form)
        if error:
            flash(error, 'error')
            return render_template(
                'students/new.html',
                skill_levels=SKILL_LEVELS,
                student=fields,
            ), 400
        sid = student_models.create_student(
            first_name=fields['first_name'],
            last_name=fields['last_name'],
            email=fields['email'] or None,
            phone=fields['phone'] or None,
            skill_level=fields['skill_level'],
        )
        audit_models.record(
            current_user()['id'], 'create', 'student', sid,
            detail=fields['first_name'] + ' ' + fields['last_name'],
        )
        flash('Student created.', 'success')
        return redirect(url_for('students.view_student', sid=sid))
    return render_template(
        'students/new.html',
        skill_levels=SKILL_LEVELS,
        student=None,
    )


@bp.route('/<int:sid>')
@login_required
def view_student(sid):
    student = student_models.get_student_for(sid, current_user()) or abort(404)
    return render_template('students/view.html', student=student)


@bp.route('/<int:sid>/edit', methods=['GET', 'POST'])
@role_required('admin', 'instructor')
def edit_student(sid):
    student = student_models.get_student(sid) or abort(404)
    if request.method == 'POST':
        fields, error = _validate_student_form(request.form)
        if error:
            flash(error, 'error')
            merged = dict(student)
            merged.update(fields)
            return render_template(
                'students/edit.html',
                skill_levels=SKILL_LEVELS,
                student=merged,
            ), 400
        student_models.update_student(
            sid,
            first_name=fields['first_name'],
            last_name=fields['last_name'],
            email=fields['email'] or None,
            phone=fields['phone'] or None,
            skill_level=fields['skill_level'],
            notes=fields['notes'] or None,
        )
        audit_models.record(current_user()['id'], 'update', 'student', sid)
        flash('Student updated.', 'success')
        return redirect(url_for('students.view_student', sid=sid))
    return render_template(
        'students/edit.html',
        skill_levels=SKILL_LEVELS,
        student=student,
    )


@bp.route('/<int:sid>/deactivate', methods=['POST'])
@role_required('admin')
def deactivate_student(sid):
    student = student_models.get_student(sid) or abort(404)
    student_models.set_student_active(sid, 0)
    audit_models.record(current_user()['id'], 'update', 'student', sid, detail='deactivated')
    flash('Student deactivated.', 'warning')
    return redirect(url_for('students.list_students'))
