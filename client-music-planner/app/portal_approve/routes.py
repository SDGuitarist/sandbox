from flask import (
    flash, g, redirect, render_template, url_for,
)

from ..db import get_db
from ..decorators import require_portal_token, require_portal_writable
from ..models import (
    approve_event,
    get_playlist_items,
    get_playlist_stats,
    get_song_requests,
)
from . import bp


@bp.route('/<token>/approve')
@require_portal_token
def approve(token):
    """Review summary of playlist, flags, and song requests before approval."""
    with get_db() as db:
        playlist_items = get_playlist_items(db, g.portal_event['id'])
        song_requests = get_song_requests(db, g.portal_event['id'])
        stats = get_playlist_stats(db, g.portal_event['id'])
    return render_template(
        'portal_approve/approve.html',
        event=g.portal_event,
        playlist_items=playlist_items,
        song_requests=song_requests,
        stats=stats,
        is_approved=g.portal_is_approved,
    )


@bp.route('/<token>/approve/confirm', methods=['POST'])
@require_portal_token
@require_portal_writable
def confirm_approval(token):
    """Submit client approval -- locks event for further edits."""
    with get_db(immediate=True) as db:
        approve_event(db, g.portal_event['id'])
        db.commit()
    flash("Your selections have been approved! Thank you.", "success")
    return redirect(url_for('portal_browse.browse', token=token))
