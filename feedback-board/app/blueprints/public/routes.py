from flask import flash, redirect, render_template, request, url_for

from app import limiter
from app.blueprints.public import public_bp
from app.db import get_db
from app.models import (
    VALID_CATEGORIES,
    create_feedback,
    get_all_feedback,
    get_feedback_by_id,
    upvote_feedback,
)


@public_bp.route("/")
def index():
    with get_db() as conn:
        items = get_all_feedback(conn)
    return render_template("index.html", feedback_items=items, categories=VALID_CATEGORIES)


@public_bp.route("/submit", methods=["POST"])
@limiter.limit("10 per minute")
def submit():
    title = (request.form.get("title") or "").strip()
    description = (request.form.get("description") or "").strip()
    category = (request.form.get("category") or "").strip()

    if not title:
        flash("Title is required", "error")
        return redirect(url_for("public.index"))
    if len(title) > 200:
        flash("Title must be under 200 characters", "error")
        return redirect(url_for("public.index"))
    if len(description) > 2000:
        flash("Description must be under 2000 characters", "error")
        return redirect(url_for("public.index"))
    if category not in VALID_CATEGORIES:
        flash("Please select a valid category", "error")
        return redirect(url_for("public.index"))

    ip = request.remote_addr or "unknown"
    with get_db(immediate=True) as conn:
        create_feedback(conn, title, description, category, ip)

    flash("Feedback submitted!", "success")
    return redirect(url_for("public.index"))


@public_bp.route("/upvote/<int:feedback_id>", methods=["POST"])
@limiter.limit("10 per minute")
def upvote(feedback_id):
    ip = request.remote_addr or "unknown"
    with get_db(immediate=True) as conn:
        item = get_feedback_by_id(conn, feedback_id)
        if item is None:
            flash("Feedback item not found", "error")
            return redirect(url_for("public.index"))
        upvote_feedback(conn, feedback_id, ip)

    return redirect(url_for("public.index"))
