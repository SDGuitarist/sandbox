import math
import sqlite3 as _sqlite3

from flask import abort, flash, redirect, render_template, request, url_for

from app.blueprints.ingredients import ingredients_bp
from app.db import get_db
from app.models import (
    ITEMS_PER_PAGE,
    create_ingredient,
    delete_ingredient,
    get_all_ingredients,
    get_ingredient,
    get_ingredient_count,
    update_ingredient,
)


@ingredients_bp.route("/")
def index():
    page = request.args.get("page", 1, type=int)
    if page < 1:
        return redirect(url_for("ingredients.index", page=1))
    offset = (page - 1) * ITEMS_PER_PAGE
    with get_db() as conn:
        ingredients = get_all_ingredients(conn, limit=ITEMS_PER_PAGE, offset=offset)
        total = get_ingredient_count(conn)
        total_pages = max(1, math.ceil(total / ITEMS_PER_PAGE))
    return render_template(
        "ingredients/list.html",
        ingredients=ingredients,
        page=page,
        total_pages=total_pages,
    )


@ingredients_bp.route("/new", methods=["GET", "POST"])
def create():
    if request.method == "GET":
        return render_template(
            "ingredients/form.html", ingredient=None, is_edit=False
        )

    name = request.form.get("name", "").strip()

    if not name:
        flash("Name is required.", "error")
        return render_template(
            "ingredients/form.html", ingredient=None, is_edit=False
        )
    if len(name) > 100:
        flash("Name must be 100 characters or fewer.", "error")
        return render_template(
            "ingredients/form.html", ingredient=None, is_edit=False
        )

    with get_db(immediate=True) as conn:
        try:
            create_ingredient(conn, name=name)
        except _sqlite3.IntegrityError:
            flash("An ingredient with that name already exists.", "error")
            return render_template(
                "ingredients/form.html", ingredient=None, is_edit=False
            )

    flash("Ingredient created successfully.", "success")
    return redirect(url_for("ingredients.index"))


@ingredients_bp.route("/<int:ingredient_id>/edit", methods=["GET", "POST"])
def edit(ingredient_id):
    if request.method == "GET":
        with get_db() as conn:
            ingredient = get_ingredient(conn, ingredient_id)
            if ingredient is None:
                abort(404)
        return render_template(
            "ingredients/form.html", ingredient=ingredient, is_edit=True
        )

    with get_db() as conn:
        ingredient = get_ingredient(conn, ingredient_id)
        if ingredient is None:
            abort(404)

    name = request.form.get("name", "").strip()

    if not name:
        flash("Name is required.", "error")
        return render_template(
            "ingredients/form.html", ingredient=ingredient, is_edit=True
        )
    if len(name) > 100:
        flash("Name must be 100 characters or fewer.", "error")
        return render_template(
            "ingredients/form.html", ingredient=ingredient, is_edit=True
        )

    with get_db(immediate=True) as conn:
        try:
            update_ingredient(conn, ingredient_id, name=name)
        except _sqlite3.IntegrityError:
            flash("An ingredient with that name already exists.", "error")
            return render_template(
                "ingredients/form.html", ingredient=ingredient, is_edit=True
            )

    flash("Ingredient updated successfully.", "success")
    return redirect(url_for("ingredients.index"))


@ingredients_bp.route("/<int:ingredient_id>/delete", methods=["POST"])
def delete(ingredient_id):
    with get_db(immediate=True) as conn:
        try:
            delete_ingredient(conn, ingredient_id)
            flash("Ingredient deleted.", "success")
        except _sqlite3.IntegrityError:
            flash(
                "Cannot delete -- this ingredient is used in recipes. Remove it from all recipes first.",
                "error",
            )
    return redirect(url_for("ingredients.index"))
