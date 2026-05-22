"""Plans blueprint: CRUD for membership plans."""
import math
import sqlite3

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from app.auth import login_required
from app.db import get_db
from app.models.plan import (
    create_plan,
    delete_plan,
    get_active_plans,
    get_all_plans,
    get_plan,
    update_plan,
)

bp = Blueprint("plans", __name__)

VALID_BILLING_CYCLES = ("monthly", "quarterly", "annual")


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


@bp.route("/")
@login_required
def list_plans():
    """GET /plans -- list all membership plans."""
    conn = get_db()
    plans = get_all_plans(conn)
    return render_template("plans/list.html", plans=plans)


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


@bp.route("/new", methods=["GET"])
@login_required
def new_plan():
    """GET /plans/new -- show create form."""
    return render_template("plans/form.html", plan=None)


@bp.route("/new", methods=["POST"])
@login_required
def create():
    """POST /plans/new -- create a new membership plan."""
    # --- name validation ---
    name = request.form.get("name", "").strip()
    if not name or len(name) > 100:
        flash("Name is required and must be 100 characters or fewer.", "error")
        return redirect(request.url)

    # --- price validation (mandatory money pattern) ---
    raw = request.form.get("price", "0").strip()
    try:
        val = float(raw)
    except ValueError:
        flash("Invalid price.", "error")
        return redirect(request.url)
    if not math.isfinite(val) or val < 0 or val > 999999.99:
        flash("Price out of range.", "error")
        return redirect(request.url)
    price_cents = round(val * 100)

    # --- billing_cycle validation ---
    billing_cycle = request.form.get("billing_cycle", "").strip()
    if billing_cycle not in VALID_BILLING_CYCLES:
        flash("Invalid billing cycle.", "error")
        return redirect(request.url)

    # --- optional description ---
    description = request.form.get("description", "").strip()

    # --- persist ---
    try:
        conn = get_db()
        create_plan(conn, name, price_cents, billing_cycle, description)
    except sqlite3.IntegrityError:
        flash("A plan with that name already exists.", "error")
        return redirect(request.url)

    flash("Plan created successfully.", "success")
    return redirect(url_for("plans.list_plans"))


# ---------------------------------------------------------------------------
# Edit
# ---------------------------------------------------------------------------


@bp.route("/<int:plan_id>/edit", methods=["GET"])
@login_required
def edit_form(plan_id):
    """GET /plans/<id>/edit -- show edit form."""
    conn = get_db()
    plan = get_plan(conn, plan_id)
    if plan is None:
        abort(404)
    return render_template("plans/form.html", plan=plan)


@bp.route("/<int:plan_id>/edit", methods=["POST"])
@login_required
def update(plan_id):
    """POST /plans/<id>/edit -- update a membership plan."""
    conn = get_db()
    plan = get_plan(conn, plan_id)
    if plan is None:
        abort(404)

    # --- name validation ---
    name = request.form.get("name", "").strip()
    if not name or len(name) > 100:
        flash("Name is required and must be 100 characters or fewer.", "error")
        return redirect(request.url)

    # --- price validation (mandatory money pattern) ---
    raw = request.form.get("price", "0").strip()
    try:
        val = float(raw)
    except ValueError:
        flash("Invalid price.", "error")
        return redirect(request.url)
    if not math.isfinite(val) or val < 0 or val > 999999.99:
        flash("Price out of range.", "error")
        return redirect(request.url)
    price_cents = round(val * 100)

    # --- billing_cycle validation ---
    billing_cycle = request.form.get("billing_cycle", "").strip()
    if billing_cycle not in VALID_BILLING_CYCLES:
        flash("Invalid billing cycle.", "error")
        return redirect(request.url)

    # --- is_active checkbox ---
    is_active = 1 if request.form.get("is_active") else 0

    # --- optional description ---
    description = request.form.get("description", "").strip()

    # --- persist ---
    try:
        update_plan(conn, plan_id, name, price_cents, billing_cycle, description, is_active)
    except sqlite3.IntegrityError:
        flash("A plan with that name already exists.", "error")
        return redirect(request.url)

    flash("Plan updated successfully.", "success")
    return redirect(url_for("plans.list_plans"))


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


@bp.route("/<int:plan_id>/delete", methods=["POST"])
@login_required
def delete(plan_id):
    """POST /plans/<id>/delete -- delete a membership plan."""
    conn = get_db()
    plan = get_plan(conn, plan_id)
    if plan is None:
        abort(404)

    delete_plan(conn, plan_id)

    flash("Plan deleted successfully.", "success")
    return redirect(url_for("plans.list_plans"))
