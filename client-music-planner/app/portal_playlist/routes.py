from flask import render_template, request, redirect, url_for, flash

from . import bp
from ..db import get_db
from ..decorators import require_portal_token, require_portal_writable


@bp.route('/<token>/playlist')
@require_portal_token
def playlist(token):
    """Show the client's playlist for this event."""
    with get_db() as db:
        event = db.execute(
            "SELECT * FROM event WHERE portal_token = ?", (token,)
        ).fetchone()

        if not event:
            flash("Event not found.", "error")
            return redirect(url_for('portal_landing.index'))

        # Fetch playlist items joined with song details, ordered by position
        items = db.execute("""
            SELECT pi.id, pi.song_id, pi.position, pi.client_note,
                   s.title, s.artist, s.genre, s.energy, s.duration,
                   s.tempo, s.song_key
            FROM playlist_item pi
            JOIN song s ON pi.song_id = s.id
            WHERE pi.event_id = ?
            ORDER BY pi.position ASC
        """, (event['id'],)).fetchall()

        # Fetch available songs (full repertoire for this musician)
        songs = db.execute("""
            SELECT s.id, s.title, s.artist, s.genre, s.energy, s.duration
            FROM song s
            WHERE s.musician_id = ?
            ORDER BY s.title ASC
        """, (event['musician_id'],)).fetchall()

    return render_template('portal_playlist/playlist.html',
                           event=event, items=items, songs=songs)


@bp.route('/<token>/playlist/add', methods=['POST'])
@require_portal_token
@require_portal_writable
def add_to_playlist(token):
    """Add a song to the client's playlist."""
    song_id = request.form.get('song_id', '').strip()
    client_note = request.form.get('client_note', '').strip()

    if not song_id:
        flash("Please select a song.", "error")
        return redirect(url_for('portal_playlist.playlist', token=token))

    try:
        song_id = int(song_id)
    except (ValueError, TypeError):
        flash("Invalid song selection.", "error")
        return redirect(url_for('portal_playlist.playlist', token=token))

    with get_db(immediate=True) as db:
        event = db.execute(
            "SELECT * FROM event WHERE portal_token = ?", (token,)
        ).fetchone()

        if not event:
            flash("Event not found.", "error")
            return redirect(url_for('portal_landing.index'))

        # Verify the song exists and belongs to this musician
        song = db.execute(
            "SELECT id, title FROM song WHERE id = ? AND musician_id = ?",
            (song_id, event['musician_id'])
        ).fetchone()

        if not song:
            flash("Song not found.", "error")
            return redirect(url_for('portal_playlist.playlist', token=token))

        # Check for duplicate
        existing = db.execute(
            "SELECT id FROM playlist_item WHERE event_id = ? AND song_id = ?",
            (event['id'], song_id)
        ).fetchone()

        if existing:
            flash("That song is already in your playlist.", "error")
            return redirect(url_for('portal_playlist.playlist', token=token))

        # Determine next position (append to end)
        row = db.execute(
            "SELECT COALESCE(MAX(position), 0) + 1 AS next_pos FROM playlist_item WHERE event_id = ?",
            (event['id'],)
        ).fetchone()
        next_pos = row['next_pos']

        db.execute("""
            INSERT INTO playlist_item (event_id, song_id, position, client_note)
            VALUES (?, ?, ?, ?)
        """, (event['id'], song_id, next_pos, client_note or None))

    flash(f"Added \"{song['title']}\" to your playlist.", "success")
    return redirect(url_for('portal_playlist.playlist', token=token))


@bp.route('/<token>/playlist/remove', methods=['POST'])
@require_portal_token
@require_portal_writable
def remove_from_playlist(token):
    """Remove a song from the client's playlist."""
    item_id = request.form.get('item_id', '').strip()

    if not item_id:
        flash("No item specified.", "error")
        return redirect(url_for('portal_playlist.playlist', token=token))

    try:
        item_id = int(item_id)
    except (ValueError, TypeError):
        flash("Invalid item.", "error")
        return redirect(url_for('portal_playlist.playlist', token=token))

    with get_db(immediate=True) as db:
        event = db.execute(
            "SELECT * FROM event WHERE portal_token = ?", (token,)
        ).fetchone()

        if not event:
            flash("Event not found.", "error")
            return redirect(url_for('portal_landing.index'))

        # Verify item belongs to this event
        item = db.execute(
            "SELECT pi.id, s.title FROM playlist_item pi JOIN song s ON pi.song_id = s.id WHERE pi.id = ? AND pi.event_id = ?",
            (item_id, event['id'])
        ).fetchone()

        if not item:
            flash("Playlist item not found.", "error")
            return redirect(url_for('portal_playlist.playlist', token=token))

        removed_title = item['title']
        db.execute("DELETE FROM playlist_item WHERE id = ?", (item_id,))

        # Re-sequence remaining items to close the gap
        remaining = db.execute(
            "SELECT id FROM playlist_item WHERE event_id = ? ORDER BY position ASC",
            (event['id'],)
        ).fetchall()
        for idx, row in enumerate(remaining, start=1):
            db.execute(
                "UPDATE playlist_item SET position = ? WHERE id = ?",
                (idx, row['id'])
            )

    flash(f"Removed \"{removed_title}\" from your playlist.", "success")
    return redirect(url_for('portal_playlist.playlist', token=token))
