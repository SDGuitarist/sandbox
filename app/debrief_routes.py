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
from app.debrief_models import (
    create_debrief,
    get_debrief_by_gig_id,
    update_debrief,
    search_debriefs,
)

debriefs_bp = Blueprint('debriefs', __name__, url_prefix='/debriefs')


@debriefs_bp.route('/search', methods=['GET'])
@login_required
def search():
    query = request.args.get('q', '').strip()
    if not query:
        results = []
    else:
        conn = get_db()
        results = search_debriefs(conn, query)
    return render_template('debriefs/search.html', query=query, results=results)


@debriefs_bp.route('/<gig_id>/new', methods=['GET', 'POST'])
@login_required
def new(gig_id):
    conn = get_db()
    gig = get_gig(conn, gig_id)
    if gig is None:
        flash('Gig not found', 'error')
        return redirect(url_for('gigs.list'))

    existing = get_debrief_by_gig_id(conn, gig_id)
    if existing is not None:
        flash('Debrief already exists for this gig', 'error')
        return redirect(url_for('debriefs.view', gig_id=gig_id))

    if request.method == 'POST':
        raw_text = request.form.get('raw_text', '').strip()
        key_takeaways = request.form.get('key_takeaways', '').strip()
        lessons_learned = request.form.get('lessons_learned', '').strip()

        if not raw_text:
            flash('Debrief text is required', 'error')
            return render_template(
                'debriefs/form.html',
                gig=gig,
                debrief=None,
                form=request.form,
            )

        try:
            create_debrief(conn, gig_id, raw_text, key_takeaways, lessons_learned)
        except sqlite3.IntegrityError:
            flash('Debrief already exists for this gig', 'error')
            return redirect(url_for('debriefs.view', gig_id=gig_id))

        flash('Debrief created', 'success')
        return redirect(url_for('debriefs.view', gig_id=gig_id))

    return render_template(
        'debriefs/form.html',
        gig=gig,
        debrief=None,
        form=None,
    )


@debriefs_bp.route('/<gig_id>', methods=['GET'])
@login_required
def view(gig_id):
    conn = get_db()
    gig = get_gig(conn, gig_id)
    if gig is None:
        flash('Gig not found', 'error')
        return redirect(url_for('gigs.list'))

    debrief = get_debrief_by_gig_id(conn, gig_id)
    if debrief is None:
        flash('Debrief not found', 'error')
        return redirect(url_for('gigs.detail', id=gig_id))

    return render_template('debriefs/detail.html', gig=gig, debrief=debrief)


@debriefs_bp.route('/<gig_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(gig_id):
    conn = get_db()
    gig = get_gig(conn, gig_id)
    if gig is None:
        flash('Gig not found', 'error')
        return redirect(url_for('gigs.list'))

    debrief = get_debrief_by_gig_id(conn, gig_id)
    if debrief is None:
        flash('Debrief not found', 'error')
        return redirect(url_for('gigs.detail', id=gig_id))

    if request.method == 'POST':
        raw_text = request.form.get('raw_text', '').strip()
        key_takeaways = request.form.get('key_takeaways', '').strip()
        lessons_learned = request.form.get('lessons_learned', '').strip()

        if not raw_text:
            flash('Debrief text is required', 'error')
            return render_template(
                'debriefs/form.html',
                gig=gig,
                debrief=debrief,
                form=request.form,
            )

        try:
            update_debrief(conn, gig_id, raw_text, key_takeaways, lessons_learned)
        except sqlite3.IntegrityError:
            flash('Debrief text is required', 'error')
            return render_template(
                'debriefs/form.html',
                gig=gig,
                debrief=debrief,
                form=request.form,
            )

        flash('Debrief updated', 'success')
        return redirect(url_for('debriefs.view', gig_id=gig_id))

    return render_template(
        'debriefs/form.html',
        gig=gig,
        debrief=debrief,
        form=None,
    )
