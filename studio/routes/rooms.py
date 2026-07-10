"""Rooms CRUD blueprint (hosted by the scaffold agent)."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from studio.auth import current_user, login_required, role_required
from studio.models.audit_models import record
from studio.models.room_models import (
    create_room as create_room_model,
    get_room,
    list_rooms as list_rooms_model,
    update_room,
)

bp = Blueprint("rooms", __name__, url_prefix="/rooms")


def _validate_room_form(form):
    """Return (name, capacity, error) — error is None when valid."""
    name = (form.get("name") or "").strip()
    if not name:
        return None, None, "Name is required."
    capacity_raw = (form.get("capacity") or "").strip()
    try:
        capacity = int(capacity_raw)
    except (TypeError, ValueError):
        return None, None, "Capacity must be a whole number of at least 1."
    if capacity < 1:
        return None, None, "Capacity must be a whole number of at least 1."
    return name, capacity, None


@bp.route("/")
@login_required
@role_required("admin", "instructor")
def list_rooms():
    rooms = list_rooms_model()
    return render_template("rooms/list.html", rooms=rooms)


@bp.route("/new", methods=["GET", "POST"])
@login_required
@role_required("admin")
def create_room():
    if request.method == "POST":
        name, capacity, error = _validate_room_form(request.form)
        if error:
            flash(error, "error")
            return render_template("rooms/form.html", room=None), 400
        location = (request.form.get("location") or "").strip() or None
        room_id = create_room_model(name, capacity=capacity, location=location)
        record(
            current_user()["id"],
            "create",
            "room",
            room_id,
        )
        flash("Room created.", "success")
        return redirect(url_for("rooms.list_rooms"))
    return render_template("rooms/form.html", room=None)


@bp.route("/<int:rid>/edit", methods=["GET", "POST"])
@login_required
@role_required("admin")
def edit_room(rid):
    room = get_room(rid) or abort(404)
    if request.method == "POST":
        name, capacity, error = _validate_room_form(request.form)
        if error:
            flash(error, "error")
            return render_template("rooms/form.html", room=room), 400
        location = (request.form.get("location") or "").strip() or None
        update_room(rid, name=name, capacity=capacity, location=location)
        record(
            current_user()["id"],
            "update",
            "room",
            rid,
        )
        flash("Room updated.", "success")
        return redirect(url_for("rooms.list_rooms"))
    return render_template("rooms/form.html", room=room)
