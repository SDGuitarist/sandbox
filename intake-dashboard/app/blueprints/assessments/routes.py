from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from app.db import get_db
from app.auth import login_required
from app.models.submissions import get_submission
from app.models.assessments import create_assessment, get_assessment_by_submission, update_assessment

assessments_bp = Blueprint('assessments', __name__)


@assessments_bp.route('/<int:submission_id>/assessment', methods=['GET', 'POST'])
@login_required
def assessment_form(submission_id):
    conn = get_db()
    submission = get_submission(conn, submission_id)
    if submission is None:
        abort(404)
    assessment = get_assessment_by_submission(conn, submission_id)

    if request.method == 'POST':
        data = {
            'summary': request.form.get('summary', '').strip()[:5000],
            'bottlenecks': request.form.get('bottlenecks', '').strip()[:5000],
            'root_causes': request.form.get('root_causes', '').strip()[:5000],
            'next_steps': request.form.get('next_steps', '').strip()[:5000],
            'audit_fit_recommendation': request.form.get('audit_fit_recommendation', '').strip()[:5000],
            'admin_notes': request.form.get('admin_notes', '').strip()[:5000],
        }
        if assessment:
            update_assessment(conn, assessment['id'], data)
            flash('Assessment updated', 'success')
        else:
            create_assessment(conn, submission_id, data)
            flash('Assessment created', 'success')
        return redirect(url_for('detail.view_submission', submission_id=submission_id))

    return render_template('assessments/form.html',
        submission=submission,
        assessment=assessment
    )
