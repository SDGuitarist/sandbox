"""Invoice model — CRUD, in-tx enroll helpers, and the one-draft-per-student invariant.

The invoice total is NEVER stored: it is always computed at read time as
``SUM(invoice_items.amount_cents)`` (COALESCE to 0), the single source of truth
(schema §billing).

Writer classes (spec §5):
  (A) commit internally: create_invoice, add_item, set_invoice_status.
  (C) in-tx helpers (caller supplies ``conn``, do NOT commit, never open a
      transaction): add_item_in_tx, get_or_create_draft_invoice_in_tx — called
      ONLY by enrollment_models.enroll inside its BEGIN IMMEDIATE unit.

The one-open-draft-per-student invariant is schema-enforced by the partial unique
index ``ux_one_draft_per_student``. Every path here respects it: create_invoice is
get-or-create, get_or_create_draft_invoice_in_tx reuses the student's single draft,
and set_invoice_status is forward-only (never reopens to 'draft').
"""

from studio.database import get_db, query

# Forward-only status transitions (spec §5 / pitfalls #3). A 'draft' target is
# always rejected so we can never mint a second draft and collide with the index.
_ALLOWED_TRANSITIONS = {
    'draft': {'sent', 'void'},
    'sent': {'paid', 'void'},
}


def _now():
    """ISO-8601 UTC timestamp (matches schema datetime('now') convention)."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')


def _total_cents(invoice_id):
    """Computed total for one invoice = SUM(items.amount_cents), COALESCE 0."""
    row = query(
        "SELECT COALESCE(SUM(amount_cents), 0) AS total_cents "
        "FROM invoice_items WHERE invoice_id = ?",
        (invoice_id,),
        one=True,
    )
    return row['total_cents'] if row else 0


def list_invoices(student_id=None, status=None):
    """List invoices (unscoped; staff callers). Each row includes computed total_cents."""
    sql = (
        "SELECT i.*, COALESCE(SUM(it.amount_cents), 0) AS total_cents "
        "FROM invoices i "
        "LEFT JOIN invoice_items it ON it.invoice_id = i.id "
    )
    where = []
    params = []
    if student_id is not None:
        where.append("i.student_id = ?")
        params.append(student_id)
    if status is not None:
        where.append("i.status = ?")
        params.append(status)
    if where:
        sql += "WHERE " + " AND ".join(where) + " "
    sql += "GROUP BY i.id ORDER BY i.issued_at DESC, i.id DESC"
    return query(sql, tuple(params))


def list_invoices_for(actor, status=None):
    """Ownership-scoped list (spec §1b / FC35).

    Staff (admin OR instructor) → all invoices (optionally filtered by status);
    student → only their own via a SQL predicate. Predicate lives IN the SQL,
    never a fetch-then-compare. Non-owner student → [].
    """
    sql = (
        "SELECT i.*, COALESCE(SUM(it.amount_cents), 0) AS total_cents "
        "FROM invoices i "
        "LEFT JOIN invoice_items it ON it.invoice_id = i.id "
    )
    where = []
    params = []
    if actor and actor.get('role') in ('admin', 'instructor'):
        pass  # staff: no ownership restriction
    else:
        where.append(
            "i.student_id = (SELECT id FROM students WHERE user_id = ?)"
        )
        params.append(actor['id'] if actor else None)
    if status is not None:
        where.append("i.status = ?")
        params.append(status)
    if where:
        sql += "WHERE " + " AND ".join(where) + " "
    sql += "GROUP BY i.id ORDER BY i.issued_at DESC, i.id DESC"
    return query(sql, tuple(params))


def _items_for(invoice_id):
    """The invoice's line items as a list[dict]."""
    return query(
        "SELECT * FROM invoice_items WHERE invoice_id = ? ORDER BY id",
        (invoice_id,),
    )


def get_invoice(iid):
    """Unscoped single invoice (staff callers); includes items + total_cents, or None."""
    inv = query("SELECT * FROM invoices WHERE id = ?", (iid,), one=True)
    if inv is None:
        return None
    inv['items'] = _items_for(iid)
    inv['total_cents'] = sum(item['amount_cents'] for item in inv['items'])
    return inv


def get_invoice_for(iid, actor):
    """Ownership-scoped single invoice (spec §1b / FC35).

    Staff → any invoice; student → only their own (SQL predicate). Includes
    items + total_cents, else None (non-owner student → None → route abort(404)).
    """
    sql = "SELECT * FROM invoices WHERE id = ?"
    params = [iid]
    if actor and actor.get('role') in ('admin', 'instructor'):
        pass  # staff: no ownership restriction
    else:
        sql += " AND student_id = (SELECT id FROM students WHERE user_id = ?)"
        params.append(actor['id'] if actor else None)
    inv = query(sql, tuple(params), one=True)
    if inv is None:
        return None
    inv['items'] = _items_for(iid)
    inv['total_cents'] = sum(item['amount_cents'] for item in inv['items'])
    return inv


def create_invoice(student_id, description=None, due_at=None, created_by=None):
    """Get-or-create the student's single 'draft' (index-safe); returns its id (class-A, commits).

    If a draft already exists for the student, return it (updating description/due_at
    when supplied); else insert a new draft. This can NEVER violate
    ux_one_draft_per_student — it never blindly inserts a second draft.
    """
    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM invoices WHERE student_id = ? AND status = 'draft' "
        "ORDER BY id DESC LIMIT 1",
        (student_id,),
    ).fetchone()
    if existing is not None:
        invoice_id = existing['id']
        sets = []
        params = []
        if description is not None:
            sets.append("description = ?")
            params.append(description)
        if due_at is not None:
            sets.append("due_at = ?")
            params.append(due_at)
        if sets:
            params.append(invoice_id)
            conn.execute(
                "UPDATE invoices SET " + ", ".join(sets) + " WHERE id = ?",
                tuple(params),
            )
            conn.commit()
        return invoice_id
    cur = conn.execute(
        "INSERT INTO invoices (student_id, description, status, due_at, created_by) "
        "VALUES (?, ?, 'draft', ?, ?)",
        (student_id, description, due_at, created_by),
    )
    conn.commit()
    return cur.lastrowid


def add_item(invoice_id, description, amount_cents, source_type='manual', source_id=None):
    """Standalone line-item insert (class-A, commits). amount_cents may be negative (credit).

    source_type ∈ {manual, enrollment, checkout_fee}. No draft-index interaction
    (invoice_items is unconstrained by ux_one_draft_per_student).
    """
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO invoice_items "
        "(invoice_id, description, amount_cents, source_type, source_id) "
        "VALUES (?, ?, ?, ?, ?)",
        (invoice_id, description, amount_cents, source_type, source_id),
    )
    conn.commit()
    return cur.lastrowid


def add_item_in_tx(conn, invoice_id, description, amount_cents, source_type, source_id):
    """In-tx line-item insert (class-C). Writes on the CALLER-supplied conn; does NOT commit.

    Called ONLY by enrollment_models.enroll inside its BEGIN IMMEDIATE unit.
    """
    cur = conn.execute(
        "INSERT INTO invoice_items "
        "(invoice_id, description, amount_cents, source_type, source_id) "
        "VALUES (?, ?, ?, ?, ?)",
        (invoice_id, description, amount_cents, source_type, source_id),
    )
    return cur.lastrowid


def get_or_create_draft_invoice_in_tx(conn, student_id, created_by):
    """In-tx get-or-create of the student's single draft (class-C). Does NOT commit.

    Returns the student's most-recent 'draft' invoice id, or INSERTs one (recording
    created_by). NEVER creates a second draft — enroll-driven items always accrete
    onto the one open draft. Writes on the caller-supplied conn. Called ONLY by
    enrollment_models.enroll inside its transaction.
    """
    existing = conn.execute(
        "SELECT id FROM invoices WHERE student_id = ? AND status = 'draft' "
        "ORDER BY id DESC LIMIT 1",
        (student_id,),
    ).fetchone()
    if existing is not None:
        return existing['id']
    cur = conn.execute(
        "INSERT INTO invoices (student_id, status, created_by) "
        "VALUES (?, 'draft', ?)",
        (student_id, created_by),
    )
    return cur.lastrowid


def set_invoice_status(iid, status):
    """Forward-only status transition (class-A, commits). Does NOT audit.

    Allowed: draft→sent, sent→paid, draft|sent→void. Any transition BACK to 'draft'
    raises ValueError('cannot reopen to draft') so we can never mint a second draft.
    On 'paid', sets paid_at (ISO now). Raises ValueError for a missing invoice or an
    otherwise-illegal transition.
    """
    if status == 'draft':
        raise ValueError('cannot reopen to draft')
    conn = get_db()
    row = conn.execute(
        "SELECT status FROM invoices WHERE id = ?", (iid,)
    ).fetchone()
    if row is None:
        raise ValueError('invoice not found')
    current = row['status']
    if status not in _ALLOWED_TRANSITIONS.get(current, set()):
        raise ValueError(
            "illegal transition {0!r} -> {1!r}".format(current, status)
        )
    if status == 'paid':
        conn.execute(
            "UPDATE invoices SET status = ?, paid_at = ? WHERE id = ?",
            (status, _now(), iid),
        )
    else:
        conn.execute(
            "UPDATE invoices SET status = ? WHERE id = ?",
            (status, iid),
        )
    conn.commit()
