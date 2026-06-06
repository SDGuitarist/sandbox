import sqlite3

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from app import get_db, login_required
from app.gig_models import get_gig
from app.outcome_models import (
    create_outcome,
    get_outcome_by_gig_id,
    update_outcome,
)

outcomes_bp = Blueprint('outcomes', __name__, url_prefix='/outcomes')


def _parse_optional_nonneg_int(value, field_error):
    """Parse an optional integer >= 0.

    Returns (parsed_value, error_message). Empty/whitespace input yields
    (0, None) so NOT NULL DEFAULT 0 columns receive a concrete default.
    """
    if value is None or value.strip() == '':
        return 0, None
    try:
        parsed = int(value)
    except ValueError:
        return None, field_error
    if parsed < 0:
        return None, field_error
    return parsed, None


def _parse_required_1_5(value, field_error):
    """Parse a required integer in the range 1-5.

    Returns (parsed_value, error_message).
    """
    if value is None or value.strip() == '':
        return None, field_error
    try:
        parsed = int(value)
    except ValueError:
        return None, field_error
    if parsed < 1 or parsed > 5:
        return None, field_error
    return parsed, None


def _collect_outcome_form():
    """Read all outcome fields from request.form into a dict of raw strings."""
    return {
        'audience_energy': request.form.get('audience_energy', ''),
        'audience_size_estimate': request.form.get('audience_size_estimate', ''),
        'song_highlights': request.form.get('song_highlights', ''),
        'song_struggles': request.form.get('song_struggles', ''),
        'audience_feedback': request.form.get('audience_feedback', ''),
        'staff_feedback': request.form.get('staff_feedback', ''),
        'personal_reflections': request.form.get('personal_reflections', ''),
        'tips_cents': request.form.get('tips_cents', ''),
        'leads_generated': request.form.get('leads_generated', ''),
        'overall_rating': request.form.get('overall_rating', ''),
    }


@outcomes_bp.route('/<gig_id>/new', methods=['GET', 'POST'])
@login_required
def new(gig_id):
    conn = get_db()

    gig = get_gig(conn, gig_id)
    if gig is None:
        flash('Gig not found', 'error')
        return redirect(url_for('gigs.list'))

    existing = get_outcome_by_gig_id(conn, gig_id)
    if existing is not None:
        flash('Outcome already exists for this gig', 'error')
        return redirect(url_for('outcomes.view', gig_id=gig_id))

    if request.method == 'POST':
        form = _collect_outcome_form()

        audience_energy, err = _parse_required_1_5(
            form['audience_energy'], 'Energy must be 1-5')
        if err:
            flash(err, 'error')
            return render_template(
                'outcomes/form.html', gig=gig, outcome=None, form=form)

        overall_rating, err = _parse_required_1_5(
            form['overall_rating'], 'Rating must be 1-5')
        if err:
            flash(err, 'error')
            return render_template(
                'outcomes/form.html', gig=gig, outcome=None, form=form)

        tips_cents, err = _parse_optional_nonneg_int(
            form['tips_cents'], 'Tips cannot be negative')
        if err:
            flash(err, 'error')
            return render_template(
                'outcomes/form.html', gig=gig, outcome=None, form=form)

        leads_generated, err = _parse_optional_nonneg_int(
            form['leads_generated'], 'Leads cannot be negative')
        if err:
            flash(err, 'error')
            return render_template(
                'outcomes/form.html', gig=gig, outcome=None, form=form)

        audience_size_estimate, err = _parse_optional_nonneg_int(
            form['audience_size_estimate'], 'Audience size cannot be negative')
        if err:
            flash(err, 'error')
            return render_template(
                'outcomes/form.html', gig=gig, outcome=None, form=form)

        song_highlights = form['song_highlights'].strip() or None
        song_struggles = form['song_struggles'].strip() or None
        audience_feedback = form['audience_feedback'].strip() or None
        staff_feedback = form['staff_feedback'].strip() or None
        personal_reflections = form['personal_reflections'].strip() or None

        try:
            create_outcome(
                conn,
                gig_id,
                audience_energy,
                audience_size_estimate,
                song_highlights,
                song_struggles,
                audience_feedback,
                staff_feedback,
                personal_reflections,
                tips_cents,
                leads_generated,
                overall_rating,
            )
        except sqlite3.IntegrityError:
            flash('Outcome already exists for this gig', 'error')
            return redirect(url_for('outcomes.view', gig_id=gig_id))

        flash('Outcome saved', 'success')
        return redirect(url_for('outcomes.view', gig_id=gig_id))

    return render_template(
        'outcomes/form.html', gig=gig, outcome=None, form=None)


@outcomes_bp.route('/<gig_id>', methods=['GET'])
@login_required
def view(gig_id):
    conn = get_db()

    gig = get_gig(conn, gig_id)
    if gig is None:
        flash('Gig not found', 'error')
        return redirect(url_for('gigs.list'))

    outcome = get_outcome_by_gig_id(conn, gig_id)
    if outcome is None:
        flash('No outcome yet for this gig', 'error')
        return redirect(url_for('outcomes.new', gig_id=gig_id))

    return render_template('outcomes/detail.html', gig=gig, outcome=outcome)


@outcomes_bp.route('/<gig_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(gig_id):
    conn = get_db()

    gig = get_gig(conn, gig_id)
    if gig is None:
        flash('Gig not found', 'error')
        return redirect(url_for('gigs.list'))

    outcome = get_outcome_by_gig_id(conn, gig_id)
    if outcome is None:
        flash('No outcome yet for this gig', 'error')
        return redirect(url_for('outcomes.new', gig_id=gig_id))

    if request.method == 'POST':
        form = _collect_outcome_form()

        audience_energy, err = _parse_required_1_5(
            form['audience_energy'], 'Energy must be 1-5')
        if err:
            flash(err, 'error')
            return render_template(
                'outcomes/form.html', gig=gig, outcome=outcome, form=form)

        overall_rating, err = _parse_required_1_5(
            form['overall_rating'], 'Rating must be 1-5')
        if err:
            flash(err, 'error')
            return render_template(
                'outcomes/form.html', gig=gig, outcome=outcome, form=form)

        tips_cents, err = _parse_optional_nonneg_int(
            form['tips_cents'], 'Tips cannot be negative')
        if err:
            flash(err, 'error')
            return render_template(
                'outcomes/form.html', gig=gig, outcome=outcome, form=form)

        leads_generated, err = _parse_optional_nonneg_int(
            form['leads_generated'], 'Leads cannot be negative')
        if err:
            flash(err, 'error')
            return render_template(
                'outcomes/form.html', gig=gig, outcome=outcome, form=form)

        audience_size_estimate, err = _parse_optional_nonneg_int(
            form['audience_size_estimate'], 'Audience size cannot be negative')
        if err:
            flash(err, 'error')
            return render_template(
                'outcomes/form.html', gig=gig, outcome=outcome, form=form)

        song_highlights = form['song_highlights'].strip() or None
        song_struggles = form['song_struggles'].strip() or None
        audience_feedback = form['audience_feedback'].strip() or None
        staff_feedback = form['staff_feedback'].strip() or None
        personal_reflections = form['personal_reflections'].strip() or None

        try:
            update_outcome(
                conn,
                gig_id,
                audience_energy,
                audience_size_estimate,
                song_highlights,
                song_struggles,
                audience_feedback,
                staff_feedback,
                personal_reflections,
                tips_cents,
                leads_generated,
                overall_rating,
            )
        except sqlite3.IntegrityError:
            flash('Energy must be 1-5', 'error')
            return render_template(
                'outcomes/form.html', gig=gig, outcome=outcome, form=form)

        flash('Outcome updated', 'success')
        return redirect(url_for('outcomes.view', gig_id=gig_id))

    return render_template(
        'outcomes/form.html', gig=gig, outcome=outcome, form=None)
