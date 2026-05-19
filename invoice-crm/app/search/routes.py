from flask import render_template, request, session

from app.db import get_db
from app.helpers import login_required
from . import bp


@bp.route('/')
@login_required
def search():
    q = request.args.get('q', '').strip()
    clients = []
    invoices = []
    deals = []

    if q:
        like_pattern = f'%{q}%'
        user_id = session['user_id']

        with get_db() as db:
            clients = db.execute(
                "SELECT id, name, email, company, status FROM clients "
                "WHERE user_id = ? AND name LIKE ?",
                (user_id, like_pattern)
            ).fetchall()

            invoices = db.execute(
                "SELECT id, invoice_number, status, total_cents, issue_date FROM invoices "
                "WHERE user_id = ? AND invoice_number LIKE ?",
                (user_id, like_pattern)
            ).fetchall()

            deals = db.execute(
                "SELECT id, title, stage, value_cents FROM deals "
                "WHERE user_id = ? AND title LIKE ?",
                (user_id, like_pattern)
            ).fetchall()

    return render_template('search/results.html', q=q, clients=clients,
                           invoices=invoices, deals=deals)
