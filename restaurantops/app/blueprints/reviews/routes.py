from flask import Blueprint, render_template, request, redirect, url_for, flash

from app.db import get_db
from app.models.review_models import (
    create_review,
    get_all_reviews,
    get_review,
    delete_review,
    get_review_summary,
)
from app.models.menu_models import get_all_menu_items

bp = Blueprint('reviews', __name__)


@bp.route('/')
def list_reviews():
    conn = get_db()
    reviews = get_all_reviews(conn)
    return render_template('reviews/list.html', reviews=reviews)


@bp.route('/create')
def create_form():
    conn = get_db()
    menu_items = get_all_menu_items(conn)
    return render_template('reviews/form.html', menu_items=menu_items)


@bp.route('/create', methods=['POST'])
def create():
    conn = get_db()

    # Parse menu_item_id (optional)
    raw_menu_item_id = request.form.get('menu_item_id', '').strip()
    menu_item_id = None
    if raw_menu_item_id:
        try:
            menu_item_id = int(raw_menu_item_id)
        except (ValueError, TypeError):
            menu_item_id = None

    # Parse and validate rating (required, 1-5)
    try:
        rating = int(request.form.get('rating', 0))
        if rating < 1 or rating > 5:
            flash('Rating must be between 1 and 5.', 'error')
            return redirect(url_for('reviews.create_form'))
    except (ValueError, TypeError):
        flash('Rating must be between 1 and 5.', 'error')
        return redirect(url_for('reviews.create_form'))

    guest_name = request.form.get('guest_name', '').strip()[:200]
    comment = request.form.get('comment', '').strip()[:2000]

    conn.execute("BEGIN")
    create_review(conn, menu_item_id, rating, guest_name, comment)
    conn.commit()

    flash('Review created successfully.', 'success')
    return redirect(url_for('reviews.list_reviews'))


@bp.route('/<int:id>')
def detail(id):
    conn = get_db()
    review = get_review(conn, id)
    if review is None:
        flash('Review not found.', 'error')
        return redirect(url_for('reviews.list_reviews'))
    return render_template('reviews/detail.html', review=review)


@bp.route('/<int:id>/delete', methods=['POST'])
def delete(id):
    conn = get_db()
    review = get_review(conn, id)
    if review is None:
        flash('Review not found.', 'error')
        return redirect(url_for('reviews.list_reviews'))

    conn.execute("BEGIN")
    delete_review(conn, id)
    conn.commit()

    flash('Review deleted successfully.', 'success')
    return redirect(url_for('reviews.list_reviews'))


@bp.route('/summary')
def summary():
    conn = get_db()
    summary_data = get_review_summary(conn)
    return render_template('reviews/summary.html', summary=summary_data)
