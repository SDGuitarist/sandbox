from datetime import date as date_module

from flask import render_template, request, redirect, url_for, flash

from . import bp
from ..db import get_db
from ..decorators import setup_required


# -- Journal routes ------------------------------------------------------------
# GET and POST share the /journal path but need separate url_for names
# (notes.journal and notes.save_journal). We use add_url_rule for these two.

def _journal_get():
    """GET /notes/journal - Show today's journal entry (or entry for ?date=YYYY-MM-DD)."""
    date = request.args.get('date', date_module.today().isoformat())
    with get_db() as db:
        entry = db.execute(
            "SELECT * FROM journal_entry WHERE date = ?", (date,)
        ).fetchone()
    return render_template('notes/journal.html', entry=entry, date=date)


def _journal_post():
    """POST /notes/journal - Insert or replace today's journal entry."""
    date = request.form.get('date', date_module.today().isoformat()).strip()
    content = request.form.get('content', '').strip()

    if not content:
        flash("Journal entry cannot be empty.", "error")
        return render_template('notes/journal.html', entry=None, date=date)

    with get_db(immediate=True) as db:
        existing = db.execute(
            "SELECT id FROM journal_entry WHERE date = ?", (date,)
        ).fetchone()

        if existing:
            db.execute(
                "UPDATE journal_entry SET content = ?, updated_at = datetime('now') WHERE date = ?",
                (content, date)
            )
            entry_id = existing['id']
        else:
            db.execute(
                "INSERT INTO journal_entry (date, content) VALUES (?, ?)",
                (date, content)
            )
            entry_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Activity log
        db.execute(
            "INSERT INTO activity_log (action, entity_type, entity_id, description) VALUES (?, ?, ?, ?)",
            ('journal_saved', 'journal_entry', entry_id, f"Updated journal for {date}")
        )

    flash("Journal entry saved.", "success")
    return redirect(url_for('notes.journal', date=date))


bp.add_url_rule('/journal', endpoint='journal', view_func=setup_required(_journal_get), methods=['GET'])
bp.add_url_rule('/journal', endpoint='save_journal', view_func=setup_required(_journal_post), methods=['POST'])


# -- Standalone notes ----------------------------------------------------------

@bp.route('/')
@setup_required
def note_list():
    """List all standalone notes."""
    with get_db() as db:
        notes = db.execute(
            "SELECT * FROM note ORDER BY updated_at DESC LIMIT 1000"
        ).fetchall()
    return render_template('notes/list.html', notes=notes)


@bp.route('/new', methods=['GET', 'POST'])
@setup_required
def create_note():
    """Create a new note."""
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        tags = request.form.get('tags', '').strip()

        if not title:
            flash("Title is required.", "error")
            return render_template('notes/form.html', note={
                'title': title, 'content': content, 'tags': tags
            })

        with get_db(immediate=True) as db:
            db.execute(
                "INSERT INTO note (title, content, tags) VALUES (?, ?, ?)",
                (title, content, tags)
            )
            note_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

            # Activity log
            db.execute(
                "INSERT INTO activity_log (action, entity_type, entity_id, description) VALUES (?, ?, ?, ?)",
                ('note_created', 'note', note_id, f"Created note {title}")
            )

        flash("Note created.", "success")
        return redirect(url_for('notes.note_list'))

    return render_template('notes/form.html', note=None)


@bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@setup_required
def edit_note(id):
    """Edit an existing note."""
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        tags = request.form.get('tags', '').strip()

        if not title:
            flash("Title is required.", "error")
            return render_template('notes/form.html', note={
                'id': id, 'title': title, 'content': content, 'tags': tags
            })

        with get_db(immediate=True) as db:
            db.execute(
                "UPDATE note SET title = ?, content = ?, tags = ?, updated_at = datetime('now') WHERE id = ?",
                (title, content, tags, id)
            )
            db.execute(
                "INSERT INTO activity_log (action, entity_type, entity_id, description) VALUES (?, ?, ?, ?)",
                ('updated', 'note', id, f"Updated note {title}"),
            )

        flash("Note updated.", "success")
        return redirect(url_for('notes.note_list'))

    with get_db() as db:
        note = db.execute("SELECT * FROM note WHERE id = ?", (id,)).fetchone()
    if not note:
        flash("Note not found.", "error")
        return redirect(url_for('notes.note_list'))

    return render_template('notes/form.html', note=note)


@bp.route('/<int:id>/delete', methods=['POST'])
@setup_required
def delete_note(id):
    """Delete a note."""
    with get_db(immediate=True) as db:
        note = db.execute("SELECT title FROM note WHERE id = ?", (id,)).fetchone()
        if not note:
            flash("Note not found.", "error")
            return redirect(url_for('notes.note_list'))

        db.execute("DELETE FROM note WHERE id = ?", (id,))
        db.execute(
            "INSERT INTO activity_log (action, entity_type, entity_id, description) VALUES (?, ?, ?, ?)",
            ('deleted', 'note', id, f"Deleted note {note['title']}"),
        )

    flash("Note deleted.", "success")
    return redirect(url_for('notes.note_list'))


# -- Full-text search ----------------------------------------------------------

@bp.route('/search')
@setup_required
def search_notes():
    """Full-text search across notes and journal entries using FTS5."""
    query = request.args.get('q', '').strip()
    results = []

    if query:
        with get_db() as db:
            # Search notes via FTS5
            note_results = db.execute(
                "SELECT n.id, n.title, n.content, n.tags, n.created_at, 'note' AS entry_type "
                "FROM note n JOIN notes_fts ON n.id = notes_fts.rowid "
                "WHERE notes_fts MATCH ? ORDER BY rank LIMIT 50",
                (query,)
            ).fetchall()

            # Search journal entries via FTS5
            journal_results = db.execute(
                "SELECT j.id, j.date AS title, j.content, '' AS tags, j.created_at, 'journal' AS entry_type "
                "FROM journal_entry j JOIN journal_fts ON j.id = journal_fts.rowid "
                "WHERE journal_fts MATCH ? ORDER BY rank LIMIT 50",
                (query,)
            ).fetchall()

            results = list(note_results) + list(journal_results)

    return render_template('notes/search_results.html', results=results, query=query)
