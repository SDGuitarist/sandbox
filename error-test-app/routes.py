from flask import Blueprint, render_template, request, redirect, url_for, flash
from app import get_db
from models import get_all_items, add_item, remove_item

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    db = get_db()
    bookmarks = get_all_items(db)
    return render_template('list.html', bookmarks=bookmarks)

@bp.route('/add', methods=['POST'])
def add():
    db = get_db()
    url = request.form.get('url', '').strip()
    title = request.form.get('title', '').strip()
    if not url or not title:
        flash('URL and title are required', 'error')
        return redirect(url_for('main.index'))
    add_item(db, url, title)
    flash('Bookmark added', 'success')
    return redirect(url_for('main.index'))

@bp.route('/delete/<int:bookmark_id>', methods=['POST'])
def delete(bookmark_id):
    db = get_db()
    remove_item(db, bookmark_id)
    flash('Bookmark deleted', 'success')
    return redirect(url_for('main.index'))
