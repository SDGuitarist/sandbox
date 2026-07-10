"""Invoices blueprint — ownership-scoped list, get-or-create draft, view, add item, status.

Route table (spec §Route Table, /invoices):
  GET       /                    list_invoices    role+own
  GET/POST  /new                 create_invoice   role:admin,instructor
  GET       /<int:iid>           view_invoice     role+own
  POST      /<int:iid>/items     add_item         role:admin,instructor
  POST      /<int:iid>/status    set_status       role:admin,instructor
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
from studio.models import invoice_models, student_models, audit_models

bp = Blueprint('invoices', __name__, url_prefix='/invoices')

# Allowed enum values (mirror schema CHECK constraints).
ITEM_SOURCE_TYPES = ('manual', 'enrollment', 'checkout_fee')
STATUS_TRANSITIONS = ('sent', 'paid', 'void')  # forward-only; never back to 'draft'


@bp.route('/')
@login_required
def list_invoices():
    """Ownership-scoped list: staff → all, student → own (powers 'my-invoices').

    The SQL predicate lives inside list_invoices_for; a non-owner simply gets
    an empty list. `status` is an optional filter passed straight through.
    """
    status = request.args.get('status') or None
    invoices = invoice_models.list_invoices_for(current_user(), status=status)
    return render_template('invoices/list.html', invoices=invoices, status=status)


@bp.route('/new', methods=('GET', 'POST'))
@role_required('admin', 'instructor')
def create_invoice():
    """Get-or-create the student's single open draft, then land on its view.

    create_invoice is get-or-create (index-safe): if the student already has a
    draft it is returned, otherwise one is inserted. Either way we redirect to
    the view so staff can add items.
    """
    students = student_models.list_students(active_only=False)
    if request.method == 'POST':
        student_id = _parse_int(request.form.get('student_id'))
        description = (request.form.get('description') or '').strip() or None
        due_at = (request.form.get('due_at') or '').strip() or None

        # Validation (§3): student must exist.
        if student_id is None or student_models.get_student(student_id) is None:
            flash('Please select a valid student.', 'error')
            return render_template('invoices/new.html', students=students), 400

        iid = invoice_models.create_invoice(
            student_id,
            description=description,
            due_at=due_at,
            created_by=current_user()['id'],
        )
        # Audit once, post-commit (§4). create_invoice commits internally.
        audit_models.record(
            current_user()['id'],
            'create',
            'invoice',
            entity_id=iid,
            detail='draft invoice for student %s' % student_id,
        )
        flash('Draft invoice ready — add line items below.', 'success')
        return redirect(url_for('invoices.view_invoice', iid=iid))

    return render_template('invoices/new.html', students=students)


@bp.route('/<int:iid>')
@login_required
def view_invoice(iid):
    """Ownership-scoped detail. Non-owner → None → 404 (no existence leak)."""
    invoice = invoice_models.get_invoice_for(iid, current_user()) or abort(404)
    return render_template(
        'invoices/view.html',
        invoice=invoice,
        source_types=ITEM_SOURCE_TYPES,
        statuses=STATUS_TRANSITIONS,
    )


@bp.route('/<int:iid>/items', methods=('POST',))
@role_required('admin', 'instructor')
def add_item(iid):
    """Add a manual line item to an existing invoice.

    Validation (§3): description non-empty; amount_cents int (may be negative
    for a credit); source_type ∈ enum (default 'manual').
    """
    # Confirm the invoice exists (staff caller → unscoped getter).
    if invoice_models.get_invoice(iid) is None:
        abort(404)

    description = (request.form.get('description') or '').strip()
    amount_cents = _parse_int(request.form.get('amount_cents'))
    source_type = (request.form.get('source_type') or 'manual').strip()

    if not description:
        flash('Item description is required.', 'error')
        return redirect(url_for('invoices.view_invoice', iid=iid)), 400
    if amount_cents is None:
        flash('Amount (in cents) must be a whole number.', 'error')
        return redirect(url_for('invoices.view_invoice', iid=iid)), 400
    if source_type not in ITEM_SOURCE_TYPES:
        flash('Invalid item source type.', 'error')
        return redirect(url_for('invoices.view_invoice', iid=iid)), 400

    invoice_models.add_item(
        iid,
        description,
        amount_cents,
        source_type=source_type,
    )
    audit_models.record(
        current_user()['id'],
        'update',
        'invoice',
        entity_id=iid,
        detail='added item: %s' % description,
    )
    flash('Line item added.', 'success')
    return redirect(url_for('invoices.view_invoice', iid=iid))


@bp.route('/<int:iid>/status', methods=('POST',))
@role_required('admin', 'instructor')
def set_status(iid):
    """Forward-only status transition. Only sent/paid/void accepted.

    set_invoice_status rejects any transition back to 'draft' with
    ValueError('cannot reopen to draft') — caught here as a 400.
    """
    if invoice_models.get_invoice(iid) is None:
        abort(404)

    status = (request.form.get('status') or '').strip()
    if status not in STATUS_TRANSITIONS:
        flash('Invalid status transition.', 'error')
        return redirect(url_for('invoices.view_invoice', iid=iid)), 400

    try:
        invoice_models.set_invoice_status(iid, status)
    except ValueError as exc:
        flash(str(exc), 'error')
        return redirect(url_for('invoices.view_invoice', iid=iid)), 400

    # 'paid' → action 'pay'; everything else → 'update' (§4/§audit rule).
    action = 'pay' if status == 'paid' else 'update'
    audit_models.record(
        current_user()['id'],
        action,
        'invoice',
        entity_id=iid,
        detail='status → %s' % status,
    )
    flash('Invoice marked %s.' % status, 'success')
    return redirect(url_for('invoices.view_invoice', iid=iid))


def _parse_int(raw):
    """Parse a form value as int, returning None on empty/invalid (not raising)."""
    if raw is None:
        return None
    raw = raw.strip()
    if raw == '':
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None
