import sqlite3

from flask import render_template, request, redirect, url_for, flash, g

from . import bp
from ..db import get_db
from ..decorators import require_portal_token, require_portal_writable
from ..models import (
    get_playlist_items,
    get_song_requests,
    get_next_position,
    add_playlist_item,
    remove_playlist_item,
)


@bp.route('/<token>/playlist')
@require_portal_token
def playlist(token):
    """Show the client's playlist for this event."""
    with get_db() as db:
        playlist_items = get_playlist_items(db, g.portal_event['id'])
        song_requests = get_song_requests(db, g.portal_event['id'])

    return render_template('portal_playlist/playlist.html',
                           event=g.portal_event,
                           playlist_items=playlist_items,
                           song_requests=song_requests,
                           is_approved=g.portal_is_approved)


@bp.route('/<token>/playlist/add', methods=['POST'])
@require_portal_token
@require_portal_writable
def add_to_playlist(token):
    """Add a song to the client's playlist."""
    song_id = request.form.get('song_id', type=int)
    if not song_id:
        flash("Invalid song.", "error")
        return redirect(url_for('portal_browse.browse', token=token))
    with get_db(immediate=True) as db:
        position = get_next_position(db, g.portal_event['id'])
        try:
            add_playlist_item(db, g.portal_event['id'], song_id, position)
            db.commit()
            flash("Song added to playlist.", "success")
        except sqlite3.IntegrityError:
            flash("Song is already in your playlist.", "warning")
    return redirect(url_for('portal_playlist.playlist', token=token))


@bp.route('/<token>/playlist/remove', methods=['POST'])
@require_portal_token
@require_portal_writable
def remove_from_playlist(token):
    """Remove a song from the client's playlist."""
    song_id = request.form.get('song_id', type=int)
    if not song_id:
        flash("Invalid song.", "error")
        return redirect(url_for('portal_playlist.playlist', token=token))
    with get_db(immediate=True) as db:
        remove_playlist_item(db, g.portal_event['id'], song_id)
        db.commit()
    flash("Song removed from playlist.", "success")
    return redirect(url_for('portal_playlist.playlist', token=token))
