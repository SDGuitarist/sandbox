from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from app.db import get_db
from app.models import (
    create_snippet,
    delete_snippet,
    get_snippet,
    list_snippets,
    update_snippet,
)

snippets_bp = Blueprint('snippets', __name__, url_prefix='/')

TITLE_MAX = 200
BODY_MAX = 10000


def _validate(title, body):
    """Return an error message string if invalid, else None."""
    if not title or not title.strip():
        return 'Title is required.'
    if len(title) > TITLE_MAX:
        return 'Title must be 200 characters or fewer.'
    if len(body) > BODY_MAX:
        return 'Body must be 10000 characters or fewer.'
    return None


@snippets_bp.route('/')
def list_():
    conn = get_db()
    rows = list_snippets(conn)
    return render_template('snippets/list.html', snippets=rows)


@snippets_bp.route('/new', methods=['GET', 'POST'])
def new():
    if request.method == 'POST':
        title = request.form.get('title', '')
        body = request.form.get('body', '')
        error = _validate(title, body)
        if error is not None:
            flash(error, 'error')
            return render_template('snippets/new.html', title=title, body=body)
        conn = get_db()
        create_snippet(conn, title, body)
        flash('Snippet created.', 'success')
        return redirect(url_for('snippets.list_'))
    return render_template('snippets/new.html', title='', body='')


@snippets_bp.route('/<int:snippet_id>/edit', methods=['GET', 'POST'])
def edit(snippet_id):
    conn = get_db()
    row = get_snippet(conn, snippet_id)
    if row is None:
        abort(404)
    if request.method == 'POST':
        title = request.form.get('title', '')
        body = request.form.get('body', '')
        error = _validate(title, body)
        if error is not None:
            flash(error, 'error')
            return render_template(
                'snippets/edit.html',
                snippet=row,
                title=title,
                body=body,
            )
        update_snippet(conn, snippet_id, title, body)
        flash('Snippet updated.', 'success')
        return redirect(url_for('snippets.list_'))
    return render_template(
        'snippets/edit.html',
        snippet=row,
        title=row['title'],
        body=row['body'],
    )


@snippets_bp.route('/<int:snippet_id>/delete', methods=['POST'])
def delete(snippet_id):
    conn = get_db()
    row = get_snippet(conn, snippet_id)
    if row is None:
        abort(404)
    delete_snippet(conn, snippet_id)
    flash('Snippet deleted.', 'success')
    return redirect(url_for('snippets.list_'))
