import hmac
import os
import secrets

from flask import Flask, abort, flash, redirect, request, session, url_for

from app.db import close_db, get_db, init_db
from app.fetch_meta import fetch_page_meta, is_safe_url
from app.models import (
    create_bookmark,
    delete_bookmark,
    get_tags_for_bookmarks,
    search_bookmarks,
    set_bookmark_tags,
)

MAX_URL_LENGTH = 2048
MAX_TAG_LENGTH = 50
MAX_TAGS_PER_BOOKMARK = 20


def create_app(db_path=None):
    app = Flask(__name__)
    app.config['SECRET_KEY'] = secrets.token_hex(24)
    app.config['DATABASE'] = db_path or os.path.join(
        os.path.dirname(os.path.dirname(__file__)), 'bookmark_tagger.db'
    )

    with app.app_context():
        init_db(app)

    app.teardown_appcontext(close_db)

    # --- CSRF ---

    @app.before_request
    def csrf_protect():
        if 'csrf_token' not in session:
            session['csrf_token'] = secrets.token_hex(16)
        if request.method == 'POST':
            token = request.form.get('csrf_token', '')
            if not hmac.compare_digest(token, session.get('csrf_token', '')):
                flash('Invalid or missing CSRF token.', 'error')
                abort(403)

    @app.context_processor
    def inject_csrf():
        return {'csrf_token': session.get('csrf_token', '')}

    # --- Routes ---

    @app.route('/')
    def index():
        from flask import render_template
        db = get_db()
        q = request.args.get('q', '').strip()
        tag = request.args.get('tag', '').strip()
        bookmarks, total = search_bookmarks(db, query=q, tag=tag)
        bookmark_ids = [b['id'] for b in bookmarks]
        tags_map = get_tags_for_bookmarks(db, bookmark_ids)
        return render_template(
            'index.html',
            bookmarks=bookmarks,
            tags_map=tags_map,
            total=total,
            q=q,
            tag=tag,
        )

    @app.route('/add', methods=['POST'])
    def add():
        url = request.form.get('url', '').strip()
        raw_tags = request.form.get('tags', '').strip()

        # Validate URL
        if not url:
            flash('URL is required.', 'error')
            return redirect(url_for('index'))

        if len(url) > MAX_URL_LENGTH:
            flash(f'URL must be {MAX_URL_LENGTH} characters or less.', 'error')
            return redirect(url_for('index'))

        if not is_safe_url(url):
            flash('Invalid URL scheme. Only http and https are allowed.', 'error')
            return redirect(url_for('index'))

        # Parse and validate tags
        raw_tag_list = [t.strip() for t in raw_tags.split(',') if t.strip()]
        truncated = any(len(t) > MAX_TAG_LENGTH for t in raw_tag_list)
        tag_names = [t[:MAX_TAG_LENGTH] for t in raw_tag_list]
        if truncated:
            flash(f'One or more tags were truncated to {MAX_TAG_LENGTH} characters.', 'warning')
        if len(tag_names) > MAX_TAGS_PER_BOOKMARK:
            flash(f'Only the first {MAX_TAGS_PER_BOOKMARK} tags were kept.', 'warning')
            tag_names = tag_names[:MAX_TAGS_PER_BOOKMARK]

        # Fetch metadata
        meta = fetch_page_meta(url)

        # Save (single commit after both bookmark and tags)
        db = get_db()
        bookmark_id = create_bookmark(db, url, meta['title'], meta['description'])
        if tag_names:
            set_bookmark_tags(db, bookmark_id, tag_names)
        db.commit()

        flash('Bookmark added.', 'success')
        return redirect(url_for('index'))

    @app.route('/delete/<int:id>', methods=['POST'])
    def delete(id):
        db = get_db()
        delete_bookmark(db, id)
        flash('Bookmark deleted.', 'success')
        return redirect(url_for('index'))

    return app
