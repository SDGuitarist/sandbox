"""Contact routes: list, follow-ups, new, detail, edit, delete."""
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
from app.gig_models import get_gig, list_gigs
from app.venue_models import get_venue, list_venues
from app.contact_models import (
    create_contact,
    get_contact,
    list_contacts,
    update_contact,
    delete_contact,
    list_follow_ups,
)

contacts_bp = Blueprint('contacts', __name__, url_prefix='/contacts')

DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')


def _validate_contact_form(conn, form):
    """Validate contact create/edit inputs.

    Returns (data_dict, error_message). If error_message is not None the
    caller must re-render the form. Validates every input in this handler
    (name required; met_at_gig_id/venue_id existence; follow_up_date format).
    """
    name = (form.get('name') or '').strip()
    if not name:
        return None, 'Contact name is required'

    role = (form.get('role') or '').strip() or None
    organization = (form.get('organization') or '').strip() or None
    phone = (form.get('phone') or '').strip() or None
    email = (form.get('email') or '').strip() or None
    follow_up_notes = (form.get('follow_up_notes') or '').strip() or None
    notes = (form.get('notes') or '').strip() or None

    met_at_gig_id = (form.get('met_at_gig_id') or '').strip() or None
    if met_at_gig_id is not None and get_gig(conn, met_at_gig_id) is None:
        return None, 'Gig not found'

    venue_id = (form.get('venue_id') or '').strip() or None
    if venue_id is not None and get_venue(conn, venue_id) is None:
        return None, 'Venue not found'

    follow_up_needed = 1 if form.get('follow_up_needed') else 0

    follow_up_date = (form.get('follow_up_date') or '').strip() or None
    if follow_up_date is not None and not DATE_RE.match(follow_up_date):
        return None, 'Valid date required for follow-up'

    data = {
        'name': name,
        'role': role,
        'organization': organization,
        'phone': phone,
        'email': email,
        'met_at_gig_id': met_at_gig_id,
        'venue_id': venue_id,
        'follow_up_needed': follow_up_needed,
        'follow_up_date': follow_up_date,
        'follow_up_notes': follow_up_notes,
        'notes': notes,
    }
    return data, None


@contacts_bp.route('/')
@login_required
def list():
    conn = get_db()
    contacts = list_contacts(conn)
    return render_template('contacts/list.html', contacts=contacts)


@contacts_bp.route('/follow-ups')
@login_required
def follow_ups():
    conn = get_db()
    contacts = list_follow_ups(conn)
    return render_template('contacts/follow_ups.html', contacts=contacts)


@contacts_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    conn = get_db()
    if request.method == 'POST':
        data, error = _validate_contact_form(conn, request.form)
        if error is not None:
            flash(error, 'error')
            return render_template(
                'contacts/form.html',
                contact=request.form,
                gigs=list_gigs(conn),
                venues=list_venues(conn),
            )
        try:
            contact_id = create_contact(
                conn,
                data['name'],
                data['role'],
                data['organization'],
                data['phone'],
                data['email'],
                data['met_at_gig_id'],
                data['venue_id'],
                data['follow_up_needed'],
                data['follow_up_date'],
                data['follow_up_notes'],
                data['notes'],
            )
        except sqlite3.IntegrityError:
            flash('Gig not found', 'error')
            return render_template(
                'contacts/form.html',
                contact=request.form,
                gigs=list_gigs(conn),
                venues=list_venues(conn),
            )
        flash('Contact created', 'success')
        return redirect(url_for('contacts.detail', id=contact_id))
    return render_template(
        'contacts/form.html',
        contact=None,
        gigs=list_gigs(conn),
        venues=list_venues(conn),
    )


@contacts_bp.route('/<id>')
@login_required
def detail(id):
    conn = get_db()
    contact = get_contact(conn, id)
    if contact is None:
        flash('Contact not found', 'error')
        return redirect(url_for('contacts.list'))
    met_at_gig = get_gig(conn, contact['met_at_gig_id']) if contact['met_at_gig_id'] else None
    venue = get_venue(conn, contact['venue_id']) if contact['venue_id'] else None
    return render_template(
        'contacts/detail.html',
        contact=contact,
        met_at_gig=met_at_gig,
        venue=venue,
    )


@contacts_bp.route('/<id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    conn = get_db()
    contact = get_contact(conn, id)
    if contact is None:
        flash('Contact not found', 'error')
        return redirect(url_for('contacts.list'))
    if request.method == 'POST':
        data, error = _validate_contact_form(conn, request.form)
        if error is not None:
            flash(error, 'error')
            return render_template(
                'contacts/form.html',
                contact=request.form,
                gigs=list_gigs(conn),
                venues=list_venues(conn),
            )
        try:
            update_contact(
                conn,
                id,
                data['name'],
                data['role'],
                data['organization'],
                data['phone'],
                data['email'],
                data['met_at_gig_id'],
                data['venue_id'],
                data['follow_up_needed'],
                data['follow_up_date'],
                data['follow_up_notes'],
                data['notes'],
            )
        except sqlite3.IntegrityError:
            flash('Gig not found', 'error')
            return render_template(
                'contacts/form.html',
                contact=request.form,
                gigs=list_gigs(conn),
                venues=list_venues(conn),
            )
        flash('Contact updated', 'success')
        return redirect(url_for('contacts.detail', id=id))
    return render_template(
        'contacts/form.html',
        contact=contact,
        gigs=list_gigs(conn),
        venues=list_venues(conn),
    )


@contacts_bp.route('/<id>/delete', methods=['POST'])
@login_required
def delete(id):
    conn = get_db()
    contact = get_contact(conn, id)
    if contact is None:
        flash('Contact not found', 'error')
        return redirect(url_for('contacts.list'))
    delete_contact(conn, id)
    flash('Contact deleted', 'success')
    return redirect(url_for('contacts.list'))
