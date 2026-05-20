from flask import render_template, request, redirect, url_for, flash, g

from . import bp
from ..db import get_db
from ..decorators import require_portal_token, require_portal_writable
from ..models import get_song_requests, add_song_request, delete_song_request


@bp.route('/<token>/requests')
@require_portal_token
def requests(token):
    with get_db() as db:
        song_requests = get_song_requests(db, g.portal_event['id'])
    return render_template('portal_requests/requests.html',
        event=g.portal_event,
        requests=song_requests,
        is_approved=g.portal_is_approved)


@bp.route('/<token>/requests/add', methods=['POST'])
@require_portal_token
@require_portal_writable
def add_request(token):
    title = request.form.get('title', '').strip()
    artist = request.form.get('artist', '').strip()
    notes = request.form.get('notes', '').strip()

    if not title:
        flash("Song title is required.", "error")
        return redirect(url_for('portal_requests.requests', token=token))

    with get_db(immediate=True) as db:
        add_song_request(db, g.portal_event['id'], title, artist, notes)
        db.commit()

    flash("Song request submitted.", "success")
    return redirect(url_for('portal_requests.requests', token=token))


@bp.route('/<token>/requests/<int:request_id>/delete', methods=['POST'])
@require_portal_token
@require_portal_writable
def delete_request(token, request_id):
    with get_db(immediate=True) as db:
        delete_song_request(db, request_id, g.portal_event['id'])
        db.commit()

    flash("Song request deleted.", "success")
    return redirect(url_for('portal_requests.requests', token=token))
