import re
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
from app.gig_models import (
    create_gig,
    delete_gig,
    get_gig,
    list_gigs,
    set_gig_status,
    update_gig,
)
from app.venue_models import get_venue, list_venues
from app.outcome_models import get_outcome_by_gig_id
from app.debrief_models import get_debrief_by_gig_id
from app.contact_models import list_contacts_by_gig_id

gigs_bp = Blueprint('gigs', __name__, url_prefix='/gigs')

DATE_RE = r'^\d{4}-\d{2}-\d{2}$'
EVENT_TYPES = ('wedding', 'corporate', 'restaurant', 'private_party', 'festival', 'public', 'other')
PAYMENT_STATUSES = ('unpaid', 'pending', 'paid')


@gigs_bp.route('/')
@login_required
def list():
    conn = get_db()
    status = request.args.get('status') or None
    if status not in ('upcoming', 'played', 'cancelled'):
        status = None
    gigs = list_gigs(conn, status)
    return render_template('gigs/list.html', gigs=gigs, status=status)


@gigs_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    conn = get_db()
    venues = list_venues(conn)
    if request.method == 'POST':
        date = (request.form.get('date') or '').strip()
        venue_id = (request.form.get('venue_id') or '').strip()
        event_type = (request.form.get('event_type') or '').strip()
        client_name = (request.form.get('client_name') or '').strip()
        client_email = (request.form.get('client_email') or '').strip()
        planned_set_summary = (request.form.get('planned_set_summary') or '').strip()
        expected_pay_raw = (request.form.get('expected_pay_cents') or '').strip()
        notes = (request.form.get('notes') or '').strip()

        form = {
            'date': date,
            'venue_id': venue_id,
            'event_type': event_type,
            'client_name': client_name,
            'client_email': client_email,
            'planned_set_summary': planned_set_summary,
            'expected_pay_cents': expected_pay_raw,
            'notes': notes,
        }

        if not re.match(DATE_RE, date):
            flash('Valid date required (YYYY-MM-DD)', 'error')
            return render_template('gigs/form.html', venues=venues, gig=form, mode='new')

        if not venue_id or get_venue(conn, venue_id) is None:
            flash('Venue not found', 'error')
            return render_template('gigs/form.html', venues=venues, gig=form, mode='new')

        if event_type and event_type not in EVENT_TYPES:
            flash('Invalid event type', 'error')
            return render_template('gigs/form.html', venues=venues, gig=form, mode='new')

        expected_pay_cents = None
        if expected_pay_raw:
            try:
                expected_pay_cents = int(expected_pay_raw)
            except ValueError:
                flash('Pay cannot be negative', 'error')
                return render_template('gigs/form.html', venues=venues, gig=form, mode='new')
            if expected_pay_cents < 0:
                flash('Pay cannot be negative', 'error')
                return render_template('gigs/form.html', venues=venues, gig=form, mode='new')

        try:
            gig_id = create_gig(
                conn,
                venue_id,
                date,
                event_type or None,
                client_name or None,
                client_email or None,
                planned_set_summary or None,
                expected_pay_cents,
                notes or None,
            )
        except sqlite3.IntegrityError:
            flash('Venue not found', 'error')
            return render_template('gigs/form.html', venues=venues, gig=form, mode='new')

        flash('Gig created', 'success')
        return redirect(url_for('gigs.detail', id=gig_id))

    return render_template('gigs/form.html', venues=venues, gig=None, mode='new')


@gigs_bp.route('/<id>')
@login_required
def detail(id):
    conn = get_db()
    gig = get_gig(conn, id)
    if gig is None:
        flash('Gig not found', 'error')
        return redirect(url_for('gigs.list'))
    venue = get_venue(conn, gig['venue_id'])
    outcome = get_outcome_by_gig_id(conn, id)
    debrief = get_debrief_by_gig_id(conn, id)
    contacts = list_contacts_by_gig_id(conn, id)
    can_delete = gig['status'] == 'upcoming' and outcome is None and debrief is None
    return render_template(
        'gigs/detail.html',
        gig=gig,
        venue=venue,
        outcome=outcome,
        debrief=debrief,
        contacts=contacts,
        can_delete=can_delete,
    )


@gigs_bp.route('/<id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    conn = get_db()
    gig = get_gig(conn, id)
    if gig is None:
        flash('Gig not found', 'error')
        return redirect(url_for('gigs.list'))
    venues = list_venues(conn)

    if request.method == 'POST':
        date = (request.form.get('date') or '').strip()
        event_type = (request.form.get('event_type') or '').strip()
        client_name = (request.form.get('client_name') or '').strip()
        client_email = (request.form.get('client_email') or '').strip()
        planned_set_summary = (request.form.get('planned_set_summary') or '').strip()
        expected_pay_raw = (request.form.get('expected_pay_cents') or '').strip()
        actual_pay_raw = (request.form.get('actual_pay_cents') or '').strip()
        payment_status = (request.form.get('payment_status') or '').strip()
        notes = (request.form.get('notes') or '').strip()

        form = {
            'id': id,
            'venue_id': gig['venue_id'],
            'date': date,
            'event_type': event_type,
            'client_name': client_name,
            'client_email': client_email,
            'planned_set_summary': planned_set_summary,
            'expected_pay_cents': expected_pay_raw,
            'actual_pay_cents': actual_pay_raw,
            'payment_status': payment_status,
            'notes': notes,
            'status': gig['status'],
        }

        def rerender():
            return render_template('gigs/form.html', venues=venues, gig=form, mode='edit')

        if not re.match(DATE_RE, date):
            flash('Valid date required (YYYY-MM-DD)', 'error')
            return rerender()

        if event_type and event_type not in EVENT_TYPES:
            flash('Invalid event type', 'error')
            return rerender()

        expected_pay_cents = None
        if expected_pay_raw:
            try:
                expected_pay_cents = int(expected_pay_raw)
            except ValueError:
                flash('Pay cannot be negative', 'error')
                return rerender()
            if expected_pay_cents < 0:
                flash('Pay cannot be negative', 'error')
                return rerender()

        actual_pay_cents = None
        if actual_pay_raw:
            try:
                actual_pay_cents = int(actual_pay_raw)
            except ValueError:
                flash('Pay cannot be negative', 'error')
                return rerender()
            if actual_pay_cents < 0:
                flash('Pay cannot be negative', 'error')
                return rerender()

        if payment_status and payment_status not in PAYMENT_STATUSES:
            flash('Invalid payment status', 'error')
            return rerender()

        actual_set = actual_pay_raw != ''
        status_set = payment_status != ''
        if actual_set != status_set:
            flash('Pay amount and status must be set together', 'error')
            return rerender()

        try:
            update_gig(
                conn,
                id,
                date,
                event_type or None,
                client_name or None,
                client_email or None,
                planned_set_summary or None,
                expected_pay_cents,
                actual_pay_cents,
                payment_status or None,
                notes or None,
            )
        except sqlite3.IntegrityError:
            flash('Pay amount and status must be set together', 'error')
            return rerender()

        flash('Gig updated', 'success')
        return redirect(url_for('gigs.detail', id=id))

    return render_template('gigs/form.html', venues=venues, gig=gig, mode='edit')


@gigs_bp.route('/<id>/delete', methods=['POST'])
@login_required
def delete(id):
    conn = get_db()
    gig = get_gig(conn, id)
    if gig is None:
        flash('Gig not found', 'error')
        return redirect(url_for('gigs.list'))

    if (
        gig['status'] != 'upcoming'
        or get_outcome_by_gig_id(conn, id) is not None
        or get_debrief_by_gig_id(conn, id) is not None
    ):
        flash('Can only delete upcoming gigs with no outcome or debrief', 'error')
        return redirect(url_for('gigs.detail', id=id))

    try:
        delete_gig(conn, id)
    except sqlite3.IntegrityError:
        flash('Can only delete upcoming gigs with no outcome or debrief', 'error')
        return redirect(url_for('gigs.detail', id=id))

    flash('Gig deleted', 'success')
    return redirect(url_for('gigs.list'))


@gigs_bp.route('/<id>/status', methods=['POST'])
@login_required
def status(id):
    conn = get_db()
    gig = get_gig(conn, id)
    if gig is None:
        flash('Gig not found', 'error')
        return redirect(url_for('gigs.list'))

    new_status = (request.form.get('new_status') or '').strip()
    valid_transitions = {
        ('upcoming', 'played'),
        ('upcoming', 'cancelled'),
    }
    if (gig['status'], new_status) not in valid_transitions:
        flash('Invalid status transition', 'error')
        return redirect(url_for('gigs.detail', id=id))

    set_gig_status(conn, id, new_status)
    flash('Gig status updated', 'success')
    return redirect(url_for('gigs.detail', id=id))
