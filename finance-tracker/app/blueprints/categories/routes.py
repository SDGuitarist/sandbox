import re
from sqlite3 import IntegrityError

from flask import abort, flash, redirect, render_template, request, url_for

from app.blueprints.categories import categories_bp
from app.db import get_db
from app.models import (
    create_category,
    delete_category,
    get_all_categories,
    get_category,
    update_category,
)


@categories_bp.route("/")
def index():
    with get_db() as conn:
        categories = get_all_categories(conn)
    return render_template("categories/list.html", categories=categories)


@categories_bp.route("/new", methods=["GET", "POST"])
def create():
    if request.method == "GET":
        return render_template("categories/form.html", category=None, is_edit=False)

    name = request.form.get("name", "").strip()
    color = request.form.get("color", "").strip() or "#6366f1"

    if not name or len(name) > 50:
        flash("Name is required and must be 50 characters or fewer.", "error")
        return render_template("categories/form.html", category=None, is_edit=False)

    if not re.match(r'^#[0-9a-fA-F]{6}$', color):
        flash("Invalid color format.", "error")
        return render_template("categories/form.html", category=None, is_edit=False)

    try:
        with get_db(immediate=True) as conn:
            cat_id = create_category(conn, name, color)
    except IntegrityError:
        flash("A category with that name already exists.", "error")
        return render_template("categories/form.html", category=None, is_edit=False)

    return redirect(url_for("categories.index"))


@categories_bp.route("/<int:category_id>/edit", methods=["GET", "POST"])
def edit(category_id):
    if request.method == "GET":
        with get_db() as conn:
            category = get_category(conn, category_id)
        if category is None:
            abort(404)
        return render_template("categories/form.html", category=category, is_edit=True)

    name = request.form.get("name", "").strip()
    color = request.form.get("color", "").strip() or "#6366f1"

    if not name or len(name) > 50:
        flash("Name is required and must be 50 characters or fewer.", "error")
        with get_db() as conn:
            category = get_category(conn, category_id)
        if category is None:
            abort(404)
        return render_template("categories/form.html", category=category, is_edit=True)

    if not re.match(r'^#[0-9a-fA-F]{6}$', color):
        flash("Invalid color format.", "error")
        with get_db() as conn:
            category = get_category(conn, category_id)
        if category is None:
            abort(404)
        return render_template("categories/form.html", category=category, is_edit=True)

    try:
        with get_db(immediate=True) as conn:
            category = get_category(conn, category_id)
            if category is None:
                abort(404)
            if category_id == 1:
                update_category(conn, category_id, category["name"], color)
            else:
                update_category(conn, category_id, name, color)
    except IntegrityError:
        flash("A category with that name already exists.", "error")
        with get_db() as conn:
            category = get_category(conn, category_id)
        if category is None:
            abort(404)
        return render_template("categories/form.html", category=category, is_edit=True)

    return redirect(url_for("categories.index"))


@categories_bp.route("/<int:category_id>/delete", methods=["POST"])
def delete(category_id):
    with get_db(immediate=True) as conn:
        ok = delete_category(conn, category_id)
    if not ok:
        flash("Cannot delete Uncategorized category.", "error")
    return redirect(url_for("categories.index"))
