"""Dashboard blueprint — API endpoints for replay control and state."""

import json

from flask import Blueprint, jsonify, render_template, request

from app.db import get_db
from app.models.events import (
    advance_projections, get_derived_state, rebuild_projections_to,
)
from app import replay
from config import REPLAY_CONFIG, STATIONS

dashboard_bp = Blueprint(
    'dashboard', __name__,
    template_folder='../../templates',
)

FMT = "%Y-%m-%d %H:%M:%S"


@dashboard_bp.route('/')
def index():
    return render_template('dashboard/index.html', stations=STATIONS)


@dashboard_bp.route('/api/state')
def api_state():
    """Return current derived state + replay info + recent events."""
    info = replay.get_replay_info()
    current_time = info['current_event_time']

    if current_time is None:
        # Stopped, never played — return initial state from pre-populated tables
        db = get_db()
        stations = [
            dict(row) for row in
            db.execute("SELECT * FROM station_state").fetchall()
        ]
        return jsonify({
            'replay': info,
            'stations': stations,
            'financials': {},
            'environment': {},
            'alerts': [],
            'recent_events': [],
        })

    db = get_db()
    advance_projections(db, current_time)
    state = get_derived_state(db, current_time)

    # Recent events up to current time (last 50)
    recent = db.execute(
        "SELECT id, event_time, source, event_type, payload "
        "FROM events WHERE event_time <= ? "
        "ORDER BY event_time DESC, id DESC LIMIT 50",
        (current_time,),
    ).fetchall()
    recent_events = []
    for r in recent:
        recent_events.append({
            'id': r['id'],
            'event_time': r['event_time'],
            'source': r['source'],
            'event_type': r['event_type'],
            'payload': json.loads(r['payload']),
        })

    return jsonify({
        'replay': info,
        'stations': state['stations'],
        'financials': state['financials'],
        'environment': state['environment'],
        'alerts': state['alerts'],
        'recent_events': recent_events,
    })


@dashboard_bp.route('/api/replay/play', methods=['POST'])
def api_play():
    replay.play()
    return jsonify({'status': 'ok'})


@dashboard_bp.route('/api/replay/pause', methods=['POST'])
def api_pause():
    replay.pause()
    return jsonify({'status': 'ok'})


@dashboard_bp.route('/api/replay/speed', methods=['POST'])
def api_speed():
    if not request.is_json:
        return jsonify({'error': 'Content-Type must be application/json'}), 415
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({'error': 'Request body must be valid JSON'}), 400
    speed = data.get('speed')
    if speed not in REPLAY_CONFIG['allowed_speeds']:
        return jsonify({
            'error': f"speed must be one of {REPLAY_CONFIG['allowed_speeds']}"
        }), 400
    replay.set_speed(speed)
    return jsonify({'status': 'ok', 'speed': speed})


@dashboard_bp.route('/api/replay/jump', methods=['POST'])
def api_jump():
    if not request.is_json:
        return jsonify({'error': 'Content-Type must be application/json'}), 415
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({'error': 'Request body must be valid JSON'}), 400
    time_str = data.get('time')
    if not time_str:
        return jsonify({'error': 'time is required'}), 400

    target = replay.jump(time_str)
    target_str = target.strftime(FMT)

    db = get_db()
    rebuild_projections_to(db, target_str)

    return jsonify({'status': 'ok', 'current_event_time': target_str})


@dashboard_bp.route('/api/replay/reset', methods=['POST'])
def api_reset():
    replay.reset()
    db = get_db()
    rebuild_projections_to(db, None)

    # Re-populate station_state with initial values
    db.execute("BEGIN")
    for s in STATIONS:
        db.execute(
            "INSERT OR IGNORE INTO station_state "
            "(station_id, name, current_weight_kg, current_temp_c, "
            "temp_status, status, updated_at) "
            "VALUES (?, ?, ?, ?, 'normal', 'unknown', ?)",
            (s['id'], s['name'], s['initial_weight_kg'],
             s.get('initial_temp_c'), '2026-06-15 18:00:00'),
        )
    db.execute("COMMIT")

    return jsonify({'status': 'ok'})
