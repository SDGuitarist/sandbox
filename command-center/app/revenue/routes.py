from flask import render_template, request, redirect, url_for, flash
from . import bp
from ..db import get_db
from ..decorators import setup_required


@bp.route('/')
@setup_required
def index():
    """Revenue index -- redirects to P&L view."""
    return redirect(url_for('revenue.pl'))


# ---------------------------------------------------------------------------
# Income CRUD
# ---------------------------------------------------------------------------

@bp.route('/income/new', methods=['GET', 'POST'])
@setup_required
def add_income():
    if request.method == 'POST':
        amount_str = request.form.get('amount', '0')
        try:
            amount = int(float(amount_str) * 100)
        except (ValueError, TypeError):
            amount = 0

        date = request.form.get('date', '').strip()
        if not date:
            flash("Date is required.", "error")
            return _render_income_form(None)

        if amount <= 0:
            flash("Amount must be greater than zero.", "error")
            return _render_income_form(None)

        contact_id = request.form.get('contact_id') or None
        project_id = request.form.get('project_id') or None
        category = request.form.get('category', 'other').strip()
        payment_method = request.form.get('payment_method', 'bank_transfer').strip()
        notes = request.form.get('notes', '').strip()

        with get_db(immediate=True) as db:
            db.execute(
                "INSERT INTO income (amount, date, contact_id, project_id, category, payment_method, notes) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (amount, date, contact_id, project_id, category, payment_method, notes),
            )
            income_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

            # Look up contact name for activity log
            contact_name = "unknown"
            if contact_id:
                row = db.execute("SELECT name FROM contact WHERE id = ?", (contact_id,)).fetchone()
                if row:
                    contact_name = row['name']

            db.execute(
                "INSERT INTO activity_log (action, entity_type, entity_id, description) VALUES (?, ?, ?, ?)",
                ('income_added', 'income', income_id, f"Added income ${amount / 100:.2f} from {contact_name}"),
            )

        flash("Income added successfully.", "success")
        return redirect(url_for('revenue.pl'))

    return _render_income_form(None)


@bp.route('/income/<int:id>/edit', methods=['GET', 'POST'])
@setup_required
def edit_income(id):
    if request.method == 'POST':
        amount_str = request.form.get('amount', '0')
        try:
            amount = int(float(amount_str) * 100)
        except (ValueError, TypeError):
            amount = 0

        date = request.form.get('date', '').strip()
        if not date:
            flash("Date is required.", "error")
            with get_db() as db:
                income = db.execute("SELECT * FROM income WHERE id = ?", (id,)).fetchone()
            return _render_income_form(income)

        if amount <= 0:
            flash("Amount must be greater than zero.", "error")
            with get_db() as db:
                income = db.execute("SELECT * FROM income WHERE id = ?", (id,)).fetchone()
            return _render_income_form(income)

        contact_id = request.form.get('contact_id') or None
        project_id = request.form.get('project_id') or None
        category = request.form.get('category', 'other').strip()
        payment_method = request.form.get('payment_method', 'bank_transfer').strip()
        notes = request.form.get('notes', '').strip()

        with get_db(immediate=True) as db:
            db.execute(
                "UPDATE income SET amount = ?, date = ?, contact_id = ?, project_id = ?, "
                "category = ?, payment_method = ?, notes = ? WHERE id = ?",
                (amount, date, contact_id, project_id, category, payment_method, notes, id),
            )
            db.execute(
                "INSERT INTO activity_log (action, entity_type, entity_id, description) VALUES (?, ?, ?, ?)",
                ('updated', 'income', id, f"Updated income ${amount / 100:.2f}"),
            )

        flash("Income updated successfully.", "success")
        return redirect(url_for('revenue.pl'))

    with get_db() as db:
        income = db.execute("SELECT * FROM income WHERE id = ?", (id,)).fetchone()
    if not income:
        flash("Income record not found.", "error")
        return redirect(url_for('revenue.pl'))
    return _render_income_form(income)


@bp.route('/income/<int:id>/delete', methods=['POST'])
@setup_required
def delete_income(id):
    with get_db(immediate=True) as db:
        db.execute("DELETE FROM income WHERE id = ?", (id,))
        db.execute(
            "INSERT INTO activity_log (action, entity_type, entity_id, description) VALUES (?, ?, ?, ?)",
            ('deleted', 'income', id, "Deleted income record"),
        )
    flash("Income deleted.", "success")
    return redirect(url_for('revenue.pl'))


# ---------------------------------------------------------------------------
# Expense CRUD
# ---------------------------------------------------------------------------

@bp.route('/expense/new', methods=['GET', 'POST'])
@setup_required
def add_expense():
    if request.method == 'POST':
        amount_str = request.form.get('amount', '0')
        try:
            amount = int(float(amount_str) * 100)
        except (ValueError, TypeError):
            amount = 0

        date = request.form.get('date', '').strip()
        if not date:
            flash("Date is required.", "error")
            return _render_expense_form(None)

        if amount <= 0:
            flash("Amount must be greater than zero.", "error")
            return _render_expense_form(None)

        category = request.form.get('category', 'other').strip()
        vendor = request.form.get('vendor', '').strip()
        notes = request.form.get('notes', '').strip()
        tax_deductible = 1 if request.form.get('tax_deductible') else 0

        with get_db(immediate=True) as db:
            db.execute(
                "INSERT INTO expense (amount, date, category, vendor, notes, tax_deductible) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (amount, date, category, vendor, notes, tax_deductible),
            )
            expense_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

            db.execute(
                "INSERT INTO activity_log (action, entity_type, entity_id, description) VALUES (?, ?, ?, ?)",
                ('expense_added', 'expense', expense_id, f"Added expense ${amount / 100:.2f} for {category}"),
            )

        flash("Expense added successfully.", "success")
        return redirect(url_for('revenue.pl'))

    return _render_expense_form(None)


@bp.route('/expense/<int:id>/edit', methods=['GET', 'POST'])
@setup_required
def edit_expense(id):
    if request.method == 'POST':
        amount_str = request.form.get('amount', '0')
        try:
            amount = int(float(amount_str) * 100)
        except (ValueError, TypeError):
            amount = 0

        date = request.form.get('date', '').strip()
        if not date:
            flash("Date is required.", "error")
            with get_db() as db:
                expense = db.execute("SELECT * FROM expense WHERE id = ?", (id,)).fetchone()
            return _render_expense_form(expense)

        if amount <= 0:
            flash("Amount must be greater than zero.", "error")
            with get_db() as db:
                expense = db.execute("SELECT * FROM expense WHERE id = ?", (id,)).fetchone()
            return _render_expense_form(expense)

        category = request.form.get('category', 'other').strip()
        vendor = request.form.get('vendor', '').strip()
        notes = request.form.get('notes', '').strip()
        tax_deductible = 1 if request.form.get('tax_deductible') else 0

        with get_db(immediate=True) as db:
            db.execute(
                "UPDATE expense SET amount = ?, date = ?, category = ?, vendor = ?, "
                "notes = ?, tax_deductible = ? WHERE id = ?",
                (amount, date, category, vendor, notes, tax_deductible, id),
            )
            db.execute(
                "INSERT INTO activity_log (action, entity_type, entity_id, description) VALUES (?, ?, ?, ?)",
                ('updated', 'expense', id, f"Updated expense ${amount / 100:.2f} for {category}"),
            )

        flash("Expense updated successfully.", "success")
        return redirect(url_for('revenue.pl'))

    with get_db() as db:
        expense = db.execute("SELECT * FROM expense WHERE id = ?", (id,)).fetchone()
    if not expense:
        flash("Expense record not found.", "error")
        return redirect(url_for('revenue.pl'))
    return _render_expense_form(expense)


@bp.route('/expense/<int:id>/delete', methods=['POST'])
@setup_required
def delete_expense(id):
    with get_db(immediate=True) as db:
        db.execute("DELETE FROM expense WHERE id = ?", (id,))
        db.execute(
            "INSERT INTO activity_log (action, entity_type, entity_id, description) VALUES (?, ?, ?, ?)",
            ('deleted', 'expense', id, "Deleted expense record"),
        )
    flash("Expense deleted.", "success")
    return redirect(url_for('revenue.pl'))


# ---------------------------------------------------------------------------
# Report Views
# ---------------------------------------------------------------------------

@bp.route('/pl')
@setup_required
def pl():
    """Monthly profit & loss statement."""
    with get_db() as db:
        # Income grouped by month
        income_rows = db.execute(
            "SELECT strftime('%%Y-%%m', date) AS month, SUM(amount) AS total "
            "FROM income GROUP BY month ORDER BY month DESC"
        ).fetchall()

        # Expenses grouped by month
        expense_rows = db.execute(
            "SELECT strftime('%%Y-%%m', date) AS month, SUM(amount) AS total "
            "FROM expense GROUP BY month ORDER BY month DESC"
        ).fetchall()

    # Build lookup dicts
    income_by_month = {r['month']: r['total'] for r in income_rows}
    expense_by_month = {r['month']: r['total'] for r in expense_rows}

    # Collect all months from both tables
    all_months = sorted(set(list(income_by_month.keys()) + list(expense_by_month.keys())), reverse=True)

    ytd_income = 0
    ytd_expenses = 0
    months = []

    for m in all_months:
        inc = income_by_month.get(m, 0)
        exp = expense_by_month.get(m, 0)
        profit = inc - exp
        margin_pct = (profit / inc * 100) if inc > 0 else 0.0
        months.append({
            'month': m,
            'income': inc,
            'expenses': exp,
            'profit': profit,
            'margin_pct': round(margin_pct, 1),
        })
        ytd_income += inc
        ytd_expenses += exp

    ytd_profit = ytd_income - ytd_expenses

    return render_template(
        'revenue/pl.html',
        months=months,
        ytd_income=ytd_income,
        ytd_expenses=ytd_expenses,
        ytd_profit=ytd_profit,
    )


@bp.route('/by-client')
@setup_required
def by_client():
    """Revenue grouped by client (contact)."""
    with get_db() as db:
        rows = db.execute(
            "SELECT c.name AS contact_name, "
            "       SUM(i.amount) AS total_revenue, "
            "       COUNT(DISTINCT i.project_id) AS project_count "
            "FROM income i "
            "JOIN contact c ON i.contact_id = c.id "
            "GROUP BY i.contact_id "
            "ORDER BY total_revenue DESC"
        ).fetchall()

    clients = []
    for r in rows:
        total = r['total_revenue'] or 0
        count = r['project_count'] or 0
        avg_value = total // count if count > 0 else 0
        clients.append({
            'contact_name': r['contact_name'],
            'total_revenue': total,
            'project_count': count,
            'avg_value': avg_value,
        })

    return render_template('revenue/by_client.html', clients=clients)


@bp.route('/by-month')
@setup_required
def by_month():
    """Revenue and expenses by month -- same data as P&L, different layout."""
    with get_db() as db:
        income_rows = db.execute(
            "SELECT strftime('%%Y-%%m', date) AS month, SUM(amount) AS total "
            "FROM income GROUP BY month ORDER BY month DESC"
        ).fetchall()

        expense_rows = db.execute(
            "SELECT strftime('%%Y-%%m', date) AS month, SUM(amount) AS total "
            "FROM expense GROUP BY month ORDER BY month DESC"
        ).fetchall()

    income_by_month = {r['month']: r['total'] for r in income_rows}
    expense_by_month = {r['month']: r['total'] for r in expense_rows}

    all_months = sorted(set(list(income_by_month.keys()) + list(expense_by_month.keys())), reverse=True)

    months = []
    for m in all_months:
        inc = income_by_month.get(m, 0)
        exp = expense_by_month.get(m, 0)
        profit = inc - exp
        margin_pct = (profit / inc * 100) if inc > 0 else 0.0
        months.append({
            'month': m,
            'income': inc,
            'expenses': exp,
            'profit': profit,
            'margin_pct': round(margin_pct, 1),
        })

    return render_template('revenue/by_month.html', months=months)


# ---------------------------------------------------------------------------
# Helper: render income form with contacts, projects, categories
# ---------------------------------------------------------------------------

def _render_income_form(income):
    """Render income_form.html with all required dropdown data."""
    with get_db() as db:
        contacts = db.execute("SELECT id, name FROM contact ORDER BY name").fetchall()
        projects = db.execute("SELECT id, name FROM project ORDER BY name").fetchall()
        categories = db.execute("SELECT id, name FROM income_category ORDER BY name").fetchall()
    return render_template(
        'revenue/income_form.html',
        income=income,
        contacts=contacts,
        projects=projects,
        categories=categories,
    )


def _render_expense_form(expense):
    """Render expense_form.html with category dropdown data."""
    with get_db() as db:
        categories = db.execute("SELECT id, name FROM expense_category ORDER BY name").fetchall()
    return render_template(
        'revenue/expense_form.html',
        expense=expense,
        categories=categories,
    )
