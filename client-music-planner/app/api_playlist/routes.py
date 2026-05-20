from flask import request, jsonify

from . import bp
from ..db import get_db
from ..models import get_event_by_token, get_playlist_items, update_playlist_positions


@bp.route('/reorder', methods=['POST'])
def reorder():
    """Update playlist positions from drag-and-drop reorder.

    Request body: {"token": "abc123", "item_ids": [5, 3, 1, 4, 2]}
    item_ids are playlist_item.id values (integers), NOT song_ids.

    Validates:
    - token exists and event is not archived and not approved
    - len(item_ids) matches actual playlist count (FC parallel array check)
    - set(item_ids) matches actual playlist_item IDs exactly
    """
    data = request.get_json()

    # FC4: Validate ALL inputs are present and correctly typed
    if not data or 'token' not in data or 'item_ids' not in data:
        return jsonify(error="Missing token or item_ids"), 400

    token = data['token']
    item_ids = data['item_ids']

    # Validate token is a non-empty string
    if not isinstance(token, str) or not token.strip():
        return jsonify(error="Invalid token"), 400

    # Validate item_ids is a list of integers
    if not isinstance(item_ids, list):
        return jsonify(error="item_ids must be a list"), 400
    if not all(isinstance(i, int) for i in item_ids):
        return jsonify(error="item_ids must be integers"), 400

    # Look up the event by portal token (read-only)
    with get_db() as db:
        event = get_event_by_token(db, token)

    if event is None or event['is_archived']:
        return jsonify(error="Invalid portal"), 404

    if event['client_approved']:
        return jsonify(error="Event is approved and locked"), 403

    # Write transaction: validate array match and update positions atomically
    with get_db(immediate=True) as db:
        actual_items = get_playlist_items(db, event['id'])

        # FC1/FC2: Length must match (parallel array desync prevention)
        if len(item_ids) != len(actual_items):
            return jsonify(error="Playlist changed. Please refresh."), 409

        # Validate exact ID set match
        actual_ids = {item['id'] for item in actual_items}
        if set(item_ids) != actual_ids:
            return jsonify(error="Invalid item IDs."), 400

        update_playlist_positions(db, event['id'], item_ids)
        db.commit()

    return jsonify(success=True)
