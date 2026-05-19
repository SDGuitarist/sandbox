from flask import request, render_template, jsonify, url_for

from . import bp
from ..db import get_db
from ..decorators import setup_required


@bp.route('/')
@setup_required
def search():
    """Full-page search results. Query param: ?q=term"""
    query = request.args.get('q', '').strip()

    contacts = []
    projects = []
    tasks = []
    deals = []
    notes = []

    if query:
        like_pattern = f'%{query}%'

        with get_db() as db:
            contacts = db.execute(
                "SELECT * FROM contact WHERE name LIKE ? OR email LIKE ? LIMIT 5",
                (like_pattern, like_pattern)
            ).fetchall()

            projects = db.execute(
                "SELECT * FROM project WHERE name LIKE ? LIMIT 5",
                (like_pattern,)
            ).fetchall()

            tasks = db.execute(
                "SELECT * FROM task WHERE title LIKE ? LIMIT 5",
                (like_pattern,)
            ).fetchall()

            deals = db.execute(
                "SELECT * FROM deal WHERE title LIKE ? LIMIT 5",
                (like_pattern,)
            ).fetchall()

            # Notes use FTS5 for full-text search
            try:
                notes = db.execute(
                    "SELECT id, title, snippet(notes_fts, 1, '<mark>', '</mark>', '...', 20) as content "
                    "FROM notes_fts WHERE notes_fts MATCH ? LIMIT 5",
                    (query,)
                ).fetchall()
            except Exception:
                # FTS match can fail on invalid query syntax — fall back to LIKE
                notes = db.execute(
                    "SELECT id, title, content FROM note WHERE title LIKE ? LIMIT 5",
                    (like_pattern,)
                ).fetchall()

    return render_template('search/results.html',
                           query=query,
                           contacts=contacts,
                           projects=projects,
                           tasks=tasks,
                           deals=deals,
                           notes=notes)


@bp.route('/api')
@setup_required
def api_search():
    """JSON search endpoint for the sidebar dropdown. Query param: ?q=term
    Returns: {"contacts": [...], "projects": [...], "tasks": [...], "deals": [...], "notes": [...]}
    Each item: {"id": N, "title": "...", "url": "/contacts/5", "type": "contact"}
    """
    query = request.args.get('q', '').strip()

    result = {
        'contacts': [],
        'projects': [],
        'tasks': [],
        'deals': [],
        'notes': [],
    }

    if not query:
        return jsonify(result)

    like_pattern = f'%{query}%'

    with get_db() as db:
        contacts = db.execute(
            "SELECT id, name FROM contact WHERE name LIKE ? OR email LIKE ? LIMIT 5",
            (like_pattern, like_pattern)
        ).fetchall()
        result['contacts'] = [
            {'id': c['id'], 'title': c['name'],
             'url': url_for('contacts.detail', id=c['id']), 'type': 'contact'}
            for c in contacts
        ]

        projects = db.execute(
            "SELECT id, name FROM project WHERE name LIKE ? LIMIT 5",
            (like_pattern,)
        ).fetchall()
        result['projects'] = [
            {'id': p['id'], 'title': p['name'],
             'url': url_for('projects.detail', id=p['id']), 'type': 'project'}
            for p in projects
        ]

        tasks = db.execute(
            "SELECT id, title FROM task WHERE title LIKE ? LIMIT 5",
            (like_pattern,)
        ).fetchall()
        result['tasks'] = [
            {'id': t['id'], 'title': t['title'],
             'url': url_for('tasks.edit', id=t['id']), 'type': 'task'}
            for t in tasks
        ]

        deals = db.execute(
            "SELECT id, title FROM deal WHERE title LIKE ? LIMIT 5",
            (like_pattern,)
        ).fetchall()
        result['deals'] = [
            {'id': d['id'], 'title': d['title'],
             'url': url_for('pipeline.detail', id=d['id']), 'type': 'deal'}
            for d in deals
        ]

        # Notes use FTS5
        try:
            notes = db.execute(
                "SELECT id, title, snippet(notes_fts, 1, '<mark>', '</mark>', '...', 20) as content "
                "FROM notes_fts WHERE notes_fts MATCH ? LIMIT 5",
                (query,)
            ).fetchall()
        except Exception:
            notes = db.execute(
                "SELECT id, title FROM note WHERE title LIKE ? LIMIT 5",
                (like_pattern,)
            ).fetchall()

        result['notes'] = [
            {'id': n['id'], 'title': n['title'],
             'url': url_for('notes.edit_note', id=n['id']), 'type': 'note'}
            for n in notes
        ]

    return jsonify(result)
