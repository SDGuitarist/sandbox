import math
import sqlite3

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from app.auth import login_required
from app.db import get_db
from app.models import (
    create_assessment as model_create_assessment,
    delete_assessment as model_delete_assessment,
    get_active_trainers,
    get_all_assessments,
    get_all_members,
    get_assessment,
    get_assessments_by_member,
    update_assessment as model_update_assessment,
)

bp = Blueprint('assessments', __name__)


def _parse_optional_float(field_name, label):
    """Parse an optional float form field.

    Returns (value, error_message). value is float or None.
    If the field is empty or missing, returns (None, None).
    If present but invalid or negative, returns (None, error_message).
    """
    raw = request.form.get(field_name, '').strip()
    if raw == '':
        return None, None
    try:
        val = float(raw)
    except (ValueError, TypeError):
        return None, f'Invalid {label}.'
    if math.isnan(val) or math.isinf(val):
        return None, f'Invalid {label}.'
    if val < 0:
        return None, f'Invalid {label}.'
    return val, None


def _parse_optional_int(field_name, label):
    """Parse an optional int form field.

    Returns (value, error_message). value is int or None.
    """
    raw = request.form.get(field_name, '').strip()
    if raw == '':
        return None, None
    try:
        val = int(raw)
    except (ValueError, TypeError):
        return None, f'Invalid {label}.'
    if val < 0:
        return None, f'Invalid {label}.'
    return val, None


def _validate_assessment_form():
    """Validate and extract assessment form data.

    Returns (data_dict, error_message). On success error_message is None.
    """
    # member_id: required int
    member_id_raw = request.form.get('member_id', '').strip()
    if member_id_raw == '':
        return None, 'Member is required.'
    try:
        member_id = int(member_id_raw)
    except (ValueError, TypeError):
        return None, 'Member is required.'

    # trainer_id: optional int
    trainer_id_raw = request.form.get('trainer_id', '').strip()
    trainer_id = None
    if trainer_id_raw != '':
        try:
            trainer_id = int(trainer_id_raw)
        except (ValueError, TypeError):
            return None, 'Invalid trainer.'

    # assessment_date: required YYYY-MM-DD
    assessment_date = request.form.get('assessment_date', '').strip()
    if assessment_date == '':
        return None, 'Date is required.'

    # weight_kg: optional float >= 0
    weight_kg, err = _parse_optional_float('weight_kg', 'weight')
    if err:
        return None, err

    # height_cm: optional float >= 0
    height_cm, err = _parse_optional_float('height_cm', 'height')
    if err:
        return None, err

    # body_fat_pct: optional float 0-100
    body_fat_pct, err = _parse_optional_float('body_fat_pct', 'body fat %')
    if err:
        return None, err
    if body_fat_pct is not None and body_fat_pct > 100:
        return None, 'Body fat % must be 0-100.'

    # resting_heart_rate: optional int >= 0
    resting_heart_rate, err = _parse_optional_int('resting_heart_rate', 'heart rate')
    if err:
        return None, err

    # notes: optional text
    notes = request.form.get('notes', '').strip()

    return {
        'member_id': member_id,
        'trainer_id': trainer_id,
        'assessment_date': assessment_date,
        'weight_kg': weight_kg,
        'height_cm': height_cm,
        'body_fat_pct': body_fat_pct,
        'resting_heart_rate': resting_heart_rate,
        'notes': notes,
    }, None


@bp.route('/')
@login_required
def list_assessments():
    conn = get_db()
    member_id = request.args.get('member_id', '').strip()
    if member_id:
        try:
            member_id_int = int(member_id)
            assessments = get_assessments_by_member(conn, member_id_int)
        except (ValueError, TypeError):
            assessments = get_all_assessments(conn)
    else:
        assessments = get_all_assessments(conn)
    return render_template('assessments/list.html', assessments=assessments)


@bp.route('/new')
@login_required
def new_assessment():
    conn = get_db()
    return render_template(
        'assessments/form.html',
        assessment=None,
        members=get_all_members(conn),
        trainers=get_active_trainers(conn),
    )


@bp.route('/', methods=['POST'])
@login_required
def create_assessment():
    data, err = _validate_assessment_form()
    if err:
        flash(err, 'error')
        return redirect(url_for('assessments.new_assessment'))

    conn = get_db()
    assessment_id = model_create_assessment(
        conn,
        data['member_id'],
        data['trainer_id'],
        data['assessment_date'],
        data['weight_kg'],
        data['height_cm'],
        data['body_fat_pct'],
        data['resting_heart_rate'],
        data['notes'],
    )
    flash('Assessment created successfully.', 'success')
    return redirect(url_for('assessments.detail', assessment_id=assessment_id))


@bp.route('/<int:assessment_id>')
@login_required
def detail(assessment_id):
    conn = get_db()
    assessment = get_assessment(conn, assessment_id)
    if assessment is None:
        abort(404)
    return render_template('assessments/detail.html', assessment=assessment)


@bp.route('/<int:assessment_id>/edit')
@login_required
def edit_assessment(assessment_id):
    conn = get_db()
    assessment = get_assessment(conn, assessment_id)
    if assessment is None:
        abort(404)
    return render_template(
        'assessments/form.html',
        assessment=assessment,
        members=get_all_members(conn),
        trainers=get_active_trainers(conn),
    )


@bp.route('/<int:assessment_id>/edit', methods=['POST'])
@login_required
def update_assessment(assessment_id):
    conn = get_db()
    assessment = get_assessment(conn, assessment_id)
    if assessment is None:
        abort(404)

    data, err = _validate_assessment_form()
    if err:
        flash(err, 'error')
        return redirect(url_for('assessments.edit_assessment', assessment_id=assessment_id))

    model_update_assessment(
        conn,
        assessment_id,
        data['member_id'],
        data['trainer_id'],
        data['assessment_date'],
        data['weight_kg'],
        data['height_cm'],
        data['body_fat_pct'],
        data['resting_heart_rate'],
        data['notes'],
    )
    flash('Assessment updated successfully.', 'success')
    return redirect(url_for('assessments.detail', assessment_id=assessment_id))


@bp.route('/<int:assessment_id>/delete', methods=['POST'])
@login_required
def delete_assessment(assessment_id):
    conn = get_db()
    assessment = get_assessment(conn, assessment_id)
    if assessment is None:
        abort(404)

    try:
        model_delete_assessment(conn, assessment_id)
        flash('Assessment deleted successfully.', 'success')
    except sqlite3.IntegrityError:
        flash('Cannot delete: referenced by other records.', 'error')

    return redirect(url_for('assessments.list_assessments'))
