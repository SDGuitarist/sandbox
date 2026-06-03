from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from app.auth_helpers import login_required
from app.database import get_db
from app.models.grading_models import save_grade as save_grade_model, get_grade
from app.models.prompt_models import get_prompt

bp = Blueprint('grading', __name__)


@bp.route('/<int:prompt_id>', methods=['GET'])
@login_required
def grade_form(prompt_id):
    """GET /grading/<prompt_id> -- show grading form, pre-filled if grade exists."""
    conn = get_db()
    prompt = get_prompt(conn, prompt_id)
    if prompt is None or prompt['user_id'] != g.user['id']:
        abort(404)
    return render_template('grading/form.html',
        prompt=prompt,
        grade=get_grade(conn, prompt_id)
    )


@bp.route('/<int:prompt_id>', methods=['POST'])
@login_required
def save_grade(prompt_id):
    """POST /grading/<prompt_id> -- validate and save grade, redirect to library detail."""
    conn = get_db()
    prompt = get_prompt(conn, prompt_id)
    if prompt is None or prompt['user_id'] != g.user['id']:
        abort(404)

    # Score validation: integer 1-5, required
    try:
        score = int(request.form.get('score', ''))
    except (ValueError, TypeError):
        flash('Score must be 1-5', 'error')
        return redirect(url_for('grading.grade_form', prompt_id=prompt_id))
    if score < 1 or score > 5:
        flash('Score must be 1-5', 'error')
        return redirect(url_for('grading.grade_form', prompt_id=prompt_id))

    # Text fields: strip, silently truncate to 2000 chars
    worked_well = request.form.get('worked_well', '').strip()[:2000]
    needs_improvement = request.form.get('needs_improvement', '').strip()[:2000]
    notes = request.form.get('notes', '').strip()[:2000]

    save_grade_model(conn, prompt_id, score, worked_well, needs_improvement, notes)
    flash('Grade saved', 'success')
    return redirect(url_for('library.detail', prompt_id=prompt_id))
