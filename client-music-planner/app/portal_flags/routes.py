from flask import g, jsonify, request

from ..db import get_db
from ..decorators import require_portal_token, require_portal_writable
from ..models import toggle_playlist_flag
from . import bp


@bp.route('/<token>/flags/toggle', methods=['POST'])
@require_portal_token
@require_portal_writable
def toggle_flag(token):
    song_id = request.form.get('song_id', type=int)
    flag_type = request.form.get('flag_type')
    if not song_id or flag_type not in ('must_play', 'do_not_play'):
        return jsonify(error="Invalid request"), 400
    with get_db(immediate=True) as db:
        result = toggle_playlist_flag(db, g.portal_event['id'], song_id, flag_type)
        if result is None:
            return jsonify(error="Song not in playlist"), 404
        db.commit()
    return jsonify(success=True, **result)
