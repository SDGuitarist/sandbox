import csv
import io
from datetime import datetime, timezone

from flask import Response, flash, redirect, render_template, request, session, url_for

from app.settings import bp
from ..db import get_db
from ..decorators import setup_required

# Whitelist of exportable modules and their table names
EXPORT_MODULES = {
    'contacts': 'contact',
    'companies': 'company',
    'deals': 'deal',
    'projects': 'project',
    'tasks': 'task',
    'time_entries': 'time_entry',
    'income': 'income',
    'expenses': 'expense',
    'notes': 'note',
    'journal': 'journal_entry',
}


def _log_activity(conn, action, entity_type, entity_id, description):
    """Insert a row into the activity_log table."""
    conn.execute(
        "INSERT INTO activity_log (action, entity_type, entity_id, description, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (action, entity_type, entity_id, description,
         datetime.now(timezone.utc).isoformat()),
    )


def _get_or_create_profile(conn):
    """Return the single business profile row, creating a default if absent."""
    user_id = session.get('user_id')
    row = conn.execute("SELECT * FROM business_profile WHERE user_id = ?", (user_id,)).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO business_profile "
            "(user_id, business_name, owner_name, logo_url, tagline, email, phone, "
            "website, address, tax_id, default_hourly_rate, currency_symbol, "
            "fiscal_year_start, monthly_revenue_target, weekly_hours_target, "
            "quarterly_revenue_target) "
            "VALUES (?, '', '', '', '', '', '', '', '', '', 0, '$', 1, 0, 40, 0)",
            (user_id,)
        )
        row = conn.execute("SELECT * FROM business_profile WHERE user_id = ?", (user_id,)).fetchone()
    return row


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

@bp.route('/profile', methods=['GET', 'POST'])
@setup_required
def profile():
    if request.method == 'POST':
        with get_db(immediate=True) as conn:
            profile = _get_or_create_profile(conn)
            conn.execute(
                "UPDATE business_profile SET "
                "business_name=?, owner_name=?, logo_url=?, tagline=?, "
                "email=?, phone=?, website=?, address=?, tax_id=? "
                "WHERE id=?",
                (
                    request.form.get('business_name', '').strip(),
                    request.form.get('owner_name', '').strip(),
                    request.form.get('logo_url', '').strip(),
                    request.form.get('tagline', '').strip(),
                    request.form.get('email', '').strip(),
                    request.form.get('phone', '').strip(),
                    request.form.get('website', '').strip(),
                    request.form.get('address', '').strip(),
                    request.form.get('tax_id', '').strip(),
                    profile['id'],
                ),
            )
            _log_activity(conn, 'updated', 'business_profile', profile['id'],
                          'Updated business profile')
        flash('Profile updated.', 'success')
        return redirect(url_for('settings.profile'))

    with get_db() as conn:
        profile = _get_or_create_profile(conn)
    return render_template('settings/profile.html', profile=profile)


# ---------------------------------------------------------------------------
# Financial
# ---------------------------------------------------------------------------

@bp.route('/financial', methods=['GET', 'POST'])
@setup_required
def financial():
    if request.method == 'POST':
        with get_db(immediate=True) as conn:
            profile = _get_or_create_profile(conn)
            # Convert dollar input to cents
            rate_dollars = request.form.get('default_hourly_rate', '0')
            try:
                rate_cents = int(float(rate_dollars) * 100)
            except (ValueError, TypeError):
                flash('Invalid hourly rate.', 'error')
                return redirect(url_for('settings.financial'))
            conn.execute(
                "UPDATE business_profile SET "
                "default_hourly_rate=?, currency_symbol=?, fiscal_year_start=? "
                "WHERE id=?",
                (
                    rate_cents,
                    request.form.get('currency_symbol', '$').strip(),
                    int(request.form.get('fiscal_year_start', 1)),
                    profile['id'],
                ),
            )
            _log_activity(conn, 'updated', 'business_profile', profile['id'],
                          'Updated financial settings')
        flash('Financial settings updated.', 'success')
        return redirect(url_for('settings.financial'))

    with get_db() as conn:
        profile = _get_or_create_profile(conn)
    return render_template('settings/financial.html', profile=profile)


# ---------------------------------------------------------------------------
# Targets
# ---------------------------------------------------------------------------

@bp.route('/targets', methods=['GET', 'POST'])
@setup_required
def targets():
    if request.method == 'POST':
        with get_db(immediate=True) as conn:
            profile = _get_or_create_profile(conn)
            # Convert dollar inputs to cents
            monthly_dollars = request.form.get('monthly_revenue_target', '0')
            quarterly_dollars = request.form.get('quarterly_revenue_target', '0')
            try:
                monthly_cents = int(float(monthly_dollars) * 100)
                quarterly_cents = int(float(quarterly_dollars) * 100)
            except (ValueError, TypeError):
                flash('Invalid revenue target.', 'error')
                return redirect(url_for('settings.targets'))
            conn.execute(
                "UPDATE business_profile SET "
                "monthly_revenue_target=?, weekly_hours_target=?, "
                "quarterly_revenue_target=? "
                "WHERE id=?",
                (
                    monthly_cents,
                    int(request.form.get('weekly_hours_target', 40)),
                    quarterly_cents,
                    profile['id'],
                ),
            )
            _log_activity(conn, 'updated', 'business_profile', profile['id'],
                          'Updated revenue targets')
        flash('Targets updated.', 'success')
        return redirect(url_for('settings.targets'))

    with get_db() as conn:
        profile = _get_or_create_profile(conn)
    return render_template('settings/targets.html', profile=profile)


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------

@bp.route('/categories', methods=['GET', 'POST'])
@setup_required
def categories():
    if request.method == 'POST':
        action = request.form.get('action', '')

        with get_db(immediate=True) as conn:
            if action == 'add_income':
                name = request.form.get('name', '').strip()
                if name:
                    conn.execute(
                        "INSERT OR IGNORE INTO income_category (name) VALUES (?)",
                        (name,),
                    )
                    flash(f'Income category "{name}" added.', 'success')
                else:
                    flash('Category name cannot be empty.', 'error')

            elif action == 'add_expense':
                name = request.form.get('name', '').strip()
                if name:
                    conn.execute(
                        "INSERT OR IGNORE INTO expense_category (name) VALUES (?)",
                        (name,),
                    )
                    flash(f'Expense category "{name}" added.', 'success')
                else:
                    flash('Category name cannot be empty.', 'error')

            elif action == 'delete_income':
                cat_id = request.form.get('category_id')
                row = conn.execute(
                    "SELECT is_default FROM income_category WHERE id=?",
                    (cat_id,),
                ).fetchone()
                if row and row['is_default']:
                    flash('Cannot delete a default category.', 'error')
                elif row:
                    conn.execute("DELETE FROM income_category WHERE id=?", (cat_id,))
                    flash('Income category removed.', 'success')

            elif action == 'delete_expense':
                cat_id = request.form.get('category_id')
                row = conn.execute(
                    "SELECT is_default FROM expense_category WHERE id=?",
                    (cat_id,),
                ).fetchone()
                if row and row['is_default']:
                    flash('Cannot delete a default category.', 'error')
                elif row:
                    conn.execute("DELETE FROM expense_category WHERE id=?", (cat_id,))
                    flash('Expense category removed.', 'success')

        return redirect(url_for('settings.categories'))

    with get_db() as conn:
        income_categories = conn.execute(
            "SELECT * FROM income_category ORDER BY name"
        ).fetchall()
        expense_categories = conn.execute(
            "SELECT * FROM expense_category ORDER BY name"
        ).fetchall()

    return render_template(
        'settings/categories.html',
        income_categories=income_categories,
        expense_categories=expense_categories,
    )


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

@bp.route('/export')
@setup_required
def export_data():
    modules = list(EXPORT_MODULES.keys())
    return render_template('settings/export.html', modules=modules)


@bp.route('/export/<module>')
@setup_required
def export_module(module):
    if module not in EXPORT_MODULES:
        flash('Invalid export module.', 'error')
        return redirect(url_for('settings.export_data'))

    table = EXPORT_MODULES[module]

    with get_db() as conn:
        rows = conn.execute(f"SELECT * FROM {table}").fetchall()  # noqa: S608

    output = io.StringIO()
    writer = csv.writer(output)

    if rows:
        # Header from column names
        writer.writerow(rows[0].keys())
        for row in rows:
            writer.writerow([_sanitize_csv(str(v)) for v in tuple(row)])
    else:
        writer.writerow(['(no data)'])

    filename = f"{module}-export-{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv"

    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'},
    )


def _sanitize_csv(value: str) -> str:
    """Prevent formula injection in CSV exports."""
    if not value:
        return value
    value = value.replace('\x00', '')
    stripped = value.strip()
    if stripped and stripped[0] in '=-+@|\t\r\n':
        return "'" + value
    return value
