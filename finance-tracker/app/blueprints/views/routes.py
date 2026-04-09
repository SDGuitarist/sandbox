from datetime import date

from flask import flash, redirect, render_template, request, url_for

from app.blueprints.views import views_bp
from app.db import get_db
from app.models import (
    get_all_categories,
    get_available_months,
    get_budgets_for_month,
    get_dashboard_data,
    set_budget,
    delete_budget,
)
from app.utils import dollars_to_cents, validate_year_month


@views_bp.route("/")
def dashboard():
    year_month = request.args.get("month", date.today().strftime("%Y-%m"))
    try:
        year_month = validate_year_month(year_month)
    except ValueError:
        year_month = date.today().strftime("%Y-%m")

    with get_db() as conn:
        data = get_dashboard_data(conn, year_month)
        months = get_available_months(conn)

    total_spent = sum(r["spent"] for r in data)
    total_budgeted = sum(r["budget_amount"] or 0 for r in data)

    return render_template(
        "dashboard.html",
        data=data,
        year_month=year_month,
        total_spent=total_spent,
        total_budgeted=total_budgeted,
        months=months,
    )


@views_bp.route("/budgets/", methods=["GET", "POST"])
def budgets_manage():
    if request.method == "GET":
        year_month = request.args.get("month", date.today().strftime("%Y-%m"))
        try:
            year_month = validate_year_month(year_month)
        except ValueError:
            year_month = date.today().strftime("%Y-%m")

        with get_db() as conn:
            cats = get_all_categories(conn)
            budgets_map = get_budgets_for_month(conn, year_month)
            months = get_available_months(conn)

        return render_template(
            "budgets/manage.html",
            categories=cats,
            budgets_map=budgets_map,
            year_month=year_month,
            months=months,
        )

    year_month = request.form.get("year_month", date.today().strftime("%Y-%m"))
    try:
        year_month = validate_year_month(year_month)
    except ValueError:
        flash("Invalid month.", "error")
        return redirect(url_for("views.budgets_manage"))

    errors = []
    with get_db(immediate=True) as conn:
        cats = get_all_categories(conn)
        for cat in cats:
            field = request.form.get(f"budget_{cat['id']}", "").strip()
            if field:
                try:
                    amount_cents = dollars_to_cents(field)
                    set_budget(conn, cat["id"], year_month, amount_cents)
                except ValueError as e:
                    errors.append(f"{cat['name']}: {e}")
            else:
                delete_budget(conn, cat["id"], year_month)

    if errors:
        flash(f"Some budgets had errors: {'; '.join(errors)}", "error")
    else:
        flash("Budgets saved.", "success")

    return redirect(url_for("views.budgets_manage", month=year_month))
