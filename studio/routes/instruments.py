"""Instruments blueprint: instrument CRUD + checkout/return transaction surface.

Route agent for /instruments (spec: Route Table `instruments`, §3, §4, §5, §6).
Hosts the checkout/return actions; the availability guard is AUTHORITATIVE inside
`checkout_models.checkout_instrument`'s BEGIN IMMEDIATE (route does presence-only
checks — FC43/§3). Audit is recorded ONCE per successful mutation, post-commit (§4).
"""
from datetime import datetime

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from studio.auth import current_user, role_required
from studio.models import audit_models, checkout_models, instrument_models, student_models

bp = Blueprint('instruments', __name__, url_prefix='/instruments')

CONDITION_CHOICES = ('good', 'fair', 'needs_repair')


def _is_future_iso(value):
    """True when `value` parses as an ISO-8601 datetime strictly in the future."""
    if not value:
        return False
    try:
        parsed = datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return False
    return parsed > datetime.now()


@bp.route('/')
@role_required('admin', 'instructor')
def list_instruments():
    status = request.args.get('status') or None
    q = request.args.get('q') or None
    instruments = instrument_models.list_instruments(status=status, q=q)
    students = student_models.list_students(active_only=True)
    return render_template(
        'instruments/list.html', instruments=instruments, students=students, status=status, q=q
    )


@bp.route('/new', methods=['GET', 'POST'])
@role_required('admin')
def create_instrument():
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        category = (request.form.get('category') or '').strip()
        condition = request.form.get('condition') or 'good'
        serial_number = (request.form.get('serial_number') or '').strip() or None
        notes = (request.form.get('notes') or '').strip() or None

        if not name or not category or condition not in CONDITION_CHOICES:
            flash('Name and category are required and condition must be valid.', 'error')
            return render_template('instruments/new.html', form=request.form), 400

        iid = instrument_models.create_instrument(
            name, category, serial_number=serial_number, condition=condition, notes=notes
        )
        audit_models.record(current_user()['id'], 'create', 'instrument', iid, detail=name)
        flash('Instrument created.', 'success')
        return redirect(url_for('instruments.list_instruments'))

    return render_template('instruments/new.html', form={})


@bp.route('/<int:iid>/edit', methods=['GET', 'POST'])
@role_required('admin')
def edit_instrument(iid):
    instrument = instrument_models.get_instrument(iid) or abort(404)

    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        category = (request.form.get('category') or '').strip()
        condition = request.form.get('condition') or 'good'
        serial_number = (request.form.get('serial_number') or '').strip() or None
        notes = (request.form.get('notes') or '').strip() or None

        if not name or not category or condition not in CONDITION_CHOICES:
            flash('Name and category are required and condition must be valid.', 'error')
            return render_template('instruments/edit.html', instrument=instrument, form=request.form), 400

        instrument_models.update_instrument(
            iid,
            name=name,
            category=category,
            serial_number=serial_number,
            condition=condition,
            notes=notes,
        )
        audit_models.record(current_user()['id'], 'update', 'instrument', iid, detail=name)
        flash('Instrument updated.', 'success')
        return redirect(url_for('instruments.list_instruments'))

    return render_template('instruments/edit.html', instrument=instrument, form=instrument)


@bp.route('/checkouts')
@role_required('admin', 'instructor')
def list_checkouts():
    status = request.args.get('status') or None
    checkouts = checkout_models.list_checkouts(status=status)
    return render_template('instruments/checkouts.html', checkouts=checkouts, status=status)


@bp.route('/<int:iid>/checkout', methods=['POST'])
@role_required('admin', 'instructor')
def checkout_instrument(iid):
    if instrument_models.get_instrument(iid) is None:
        abort(404)

    student_id = request.form.get('student_id', type=int)
    due_at = (request.form.get('due_at') or '').strip()

    # Route-level checks are PRESENCE only (§3/FC43): student exists + due_at future ISO.
    # The status=='available' guard is AUTHORITATIVE inside the model's transaction.
    if student_id is None or student_models.get_student(student_id) is None or not _is_future_iso(due_at):
        flash('A valid student and a future due date are required.', 'error')
        return redirect(url_for('instruments.list_instruments')), 400

    try:
        cid = checkout_models.checkout_instrument(iid, student_id, due_at)
    except ValueError:
        flash('Instrument unavailable.', 'error')
        return redirect(url_for('instruments.list_instruments')), 400

    audit_models.record(current_user()['id'], 'checkout', 'instrument', iid, detail=str(cid))
    flash('Instrument checked out.', 'success')
    return redirect(url_for('instruments.list_checkouts'))


@bp.route('/checkouts/<int:cid>/return', methods=['POST'])
@role_required('admin', 'instructor')
def return_instrument(cid):
    checkout = checkout_models.get_checkout(cid)
    if checkout is None:
        abort(404)
    if checkout['status'] != 'out':
        flash('This checkout is not currently out.', 'error')
        return redirect(url_for('instruments.list_checkouts')), 400

    checkout_models.return_instrument(cid)
    audit_models.record(
        current_user()['id'], 'return', 'instrument', checkout['instrument_id'], detail=str(cid)
    )
    flash('Instrument returned.', 'success')
    return redirect(url_for('instruments.list_checkouts'))
