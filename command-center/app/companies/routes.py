from flask import render_template, request, redirect, url_for, flash, abort

from . import bp
from ..db import get_db
from ..decorators import setup_required


@bp.route('/')
@setup_required
def index():
    """List all companies."""
    with get_db() as db:
        companies = db.execute(
            "SELECT * FROM company ORDER BY name ASC"
        ).fetchall()
    return render_template('companies/list.html', companies=companies)


@bp.route('/<int:id>')
@setup_required
def detail(id):
    """Show company detail with linked contacts."""
    with get_db() as db:
        company = db.execute(
            "SELECT * FROM company WHERE id = ?", (id,)
        ).fetchone()
        if company is None:
            abort(404)
        contacts = db.execute(
            "SELECT * FROM contact WHERE company_id = ? ORDER BY name ASC",
            (id,)
        ).fetchall()
    return render_template('companies/detail.html',
                           company=company, contacts=contacts)


@bp.route('/new', methods=['GET', 'POST'])
@setup_required
def create():
    """Create a new company."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash("Company name is required.", "error")
            return render_template('companies/form.html', company=None)

        website = request.form.get('website', '').strip()
        industry = request.form.get('industry', '').strip()
        address = request.form.get('address', '').strip()
        notes = request.form.get('notes', '').strip()

        with get_db(immediate=True) as db:
            db.execute(
                "INSERT INTO company (name, website, industry, address, notes) "
                "VALUES (?, ?, ?, ?, ?)",
                (name, website, industry, address, notes)
            )
            company_id = db.execute(
                "SELECT last_insert_rowid()"
            ).fetchone()[0]
            db.execute(
                "INSERT INTO activity_log (action, entity_type, entity_id, description) "
                "VALUES (?, ?, ?, ?)",
                ('created', 'company', company_id, f"Created company {name}")
            )

        flash("Company created successfully.", "success")
        return redirect(url_for('companies.detail', id=company_id))

    return render_template('companies/form.html', company=None)


@bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@setup_required
def edit(id):
    """Edit an existing company."""
    with get_db() as db:
        company = db.execute(
            "SELECT * FROM company WHERE id = ?", (id,)
        ).fetchone()
    if company is None:
        abort(404)

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash("Company name is required.", "error")
            return render_template('companies/form.html', company=company)

        website = request.form.get('website', '').strip()
        industry = request.form.get('industry', '').strip()
        address = request.form.get('address', '').strip()
        notes = request.form.get('notes', '').strip()

        with get_db(immediate=True) as db:
            db.execute(
                "UPDATE company SET name = ?, website = ?, industry = ?, "
                "address = ?, notes = ? WHERE id = ?",
                (name, website, industry, address, notes, id)
            )
            db.execute(
                "INSERT INTO activity_log (action, entity_type, entity_id, description) "
                "VALUES (?, ?, ?, ?)",
                ('updated', 'company', id, f"Updated company {name}")
            )

        flash("Company updated successfully.", "success")
        return redirect(url_for('companies.detail', id=id))

    return render_template('companies/form.html', company=company)


@bp.route('/<int:id>/delete', methods=['POST'])
@setup_required
def delete(id):
    """Delete a company."""
    with get_db(immediate=True) as db:
        company = db.execute(
            "SELECT * FROM company WHERE id = ?", (id,)
        ).fetchone()
        if company is None:
            abort(404)
        name = company['name']
        db.execute("DELETE FROM company WHERE id = ?", (id,))
        db.execute(
            "INSERT INTO activity_log (action, entity_type, entity_id, description) "
            "VALUES (?, ?, ?, ?)",
            ('deleted', 'company', id, f"Deleted company {name}")
        )

    flash("Company deleted successfully.", "success")
    return redirect(url_for('companies.index'))
