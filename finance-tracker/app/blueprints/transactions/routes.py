from flask import abort, flash, redirect, render_template, request, url_for

from app.blueprints.transactions import transactions_bp
from app.db import get_db
from app.models import (
    ITEMS_PER_PAGE,
    create_transaction,
    delete_transaction,
    get_all_categories,
    get_transaction,
    get_transaction_count,
    get_transactions,
    update_transaction,
)
from app.utils import dollars_to_cents, validate_date, validate_year_month


@transactions_bp.route("/")
def index():
    year_month = request.args.get("month")
    if year_month:
        try:
            year_month = validate_year_month(year_month)
        except ValueError:
            year_month = None
    category_id = request.args.get("category", type=int)
    page = request.args.get("page", 1, type=int)
    page = max(1, page)
    offset = (page - 1) * ITEMS_PER_PAGE

    with get_db() as conn:
        transactions = get_transactions(conn, year_month, category_id, ITEMS_PER_PAGE, offset)
        total = get_transaction_count(conn, year_month, category_id)
        categories = get_all_categories(conn)

    total_pages = max(1, -(-total // ITEMS_PER_PAGE))

    return render_template(
        "transactions/list.html",
        transactions=transactions,
        year_month=year_month,
        category_id=category_id,
        categories=categories,
        page=page,
        total_pages=total_pages,
    )


@transactions_bp.route("/new", methods=["GET", "POST"])
def create():
    if request.method == "GET":
        with get_db() as conn:
            categories = get_all_categories(conn)
        return render_template(
            "transactions/form.html",
            transaction=None,
            categories=categories,
            is_edit=False,
        )

    try:
        amount = dollars_to_cents(request.form["amount"])
    except (ValueError, KeyError):
        flash("Invalid amount.", "error")
        with get_db() as conn:
            categories = get_all_categories(conn)
        return render_template(
            "transactions/form.html",
            transaction=None,
            categories=categories,
            is_edit=False,
        )

    description = request.form.get("description", "").strip()
    if len(description) > 200:
        flash("Description must be 200 characters or fewer.", "error")
        with get_db() as conn:
            categories = get_all_categories(conn)
        return render_template(
            "transactions/form.html",
            transaction=None,
            categories=categories,
            is_edit=False,
        )

    transaction_date = request.form.get("transaction_date", "").strip()
    category_id = request.form.get("category_id", type=int)

    if not transaction_date or not category_id:
        flash("Date and category are required.", "error")
        with get_db() as conn:
            categories = get_all_categories(conn)
        return render_template(
            "transactions/form.html",
            transaction=None,
            categories=categories,
            is_edit=False,
        )

    try:
        validate_date(transaction_date)
    except ValueError:
        flash("Invalid date format.", "error")
        with get_db() as conn:
            categories = get_all_categories(conn)
        return render_template(
            "transactions/form.html",
            transaction=None,
            categories=categories,
            is_edit=False,
        )

    with get_db(immediate=True) as conn:
        txn_id = create_transaction(conn, category_id, amount, description, transaction_date)

    return redirect(url_for("transactions.index"))


@transactions_bp.route("/<int:transaction_id>/edit", methods=["GET", "POST"])
def edit(transaction_id):
    if request.method == "GET":
        with get_db() as conn:
            transaction = get_transaction(conn, transaction_id)
            if transaction is None:
                abort(404)
            categories = get_all_categories(conn)
        return render_template(
            "transactions/form.html",
            transaction=dict(transaction, amount_dollars="%.2f" % (transaction["amount"] / 100)),
            categories=categories,
            is_edit=True,
        )

    try:
        amount = dollars_to_cents(request.form["amount"])
    except (ValueError, KeyError):
        flash("Invalid amount.", "error")
        with get_db() as conn:
            transaction = get_transaction(conn, transaction_id)
            if transaction is None:
                abort(404)
            categories = get_all_categories(conn)
        return render_template(
            "transactions/form.html",
            transaction=dict(transaction, amount_dollars="%.2f" % (transaction["amount"] / 100)),
            categories=categories,
            is_edit=True,
        )

    description = request.form.get("description", "").strip()
    if len(description) > 200:
        flash("Description must be 200 characters or fewer.", "error")
        with get_db() as conn:
            transaction = get_transaction(conn, transaction_id)
            if transaction is None:
                abort(404)
            categories = get_all_categories(conn)
        return render_template(
            "transactions/form.html",
            transaction=dict(transaction, amount_dollars="%.2f" % (transaction["amount"] / 100)),
            categories=categories,
            is_edit=True,
        )

    transaction_date = request.form.get("transaction_date", "").strip()
    category_id = request.form.get("category_id", type=int)

    if not transaction_date or not category_id:
        flash("Date and category are required.", "error")
        with get_db() as conn:
            transaction = get_transaction(conn, transaction_id)
            if transaction is None:
                abort(404)
            categories = get_all_categories(conn)
        return render_template(
            "transactions/form.html",
            transaction=dict(transaction, amount_dollars="%.2f" % (transaction["amount"] / 100)),
            categories=categories,
            is_edit=True,
        )

    try:
        validate_date(transaction_date)
    except ValueError:
        flash("Invalid date format.", "error")
        with get_db() as conn:
            transaction = get_transaction(conn, transaction_id)
            if transaction is None:
                abort(404)
            categories = get_all_categories(conn)
        return render_template(
            "transactions/form.html",
            transaction=dict(transaction, amount_dollars="%.2f" % (transaction["amount"] / 100)),
            categories=categories,
            is_edit=True,
        )

    with get_db(immediate=True) as conn:
        update_transaction(conn, transaction_id, category_id, amount, description, transaction_date)

    return redirect(url_for("transactions.index"))


@transactions_bp.route("/<int:transaction_id>/delete", methods=["POST"])
def delete(transaction_id):
    with get_db(immediate=True) as conn:
        delete_transaction(conn, transaction_id)
    flash("Transaction deleted.", "success")
    return redirect(url_for("transactions.index"))
