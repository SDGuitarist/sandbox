"""Server-side replay clock for CPAA Shadow Lab.

Thread-safe replay state machine: stopped -> playing <-> paused.
All mutations acquire _replay_lock. The replay clock calculates
current event time from wall clock elapsed * speed.
"""

import threading
import time
from datetime import datetime, timedelta


_replay_lock = threading.Lock()
_replay_state = {
    'status': 'stopped',
    'speed': 1,
    'current_event_time': None,
    'wall_time_at_play': None,
    'event_time_at_play': None,
    'scenario_start': datetime(2026, 6, 15, 18, 0, 0),
    'scenario_end': datetime(2026, 6, 15, 22, 0, 0),
}

FMT = "%Y-%m-%d %H:%M:%S"


def get_current_event_time():
    """Calculate current position in event time. Thread-safe.

    Returns datetime or None (if stopped and never played).
    """
    with _replay_lock:
        if _replay_state['status'] != 'playing':
            return _replay_state['current_event_time']
        elapsed_wall = time.time() - _replay_state['wall_time_at_play']
        elapsed_event = elapsed_wall * _replay_state['speed']
        current = _replay_state['event_time_at_play'] + timedelta(
            seconds=elapsed_event
        )
        return min(current, _replay_state['scenario_end'])


def get_replay_info():
    """Return replay status dict for API response."""
    current = get_current_event_time()
    with _replay_lock:
        info = {
            'status': _replay_state['status'],
            'speed': _replay_state['speed'],
            'current_event_time': current.strftime(FMT) if current else None,
            'scenario_start': _replay_state['scenario_start'].strftime(FMT),
            'scenario_end': _replay_state['scenario_end'].strftime(FMT),
        }
        # Auto-pause at end of data
        if (_replay_state['status'] == 'playing'
                and current
                and current >= _replay_state['scenario_end']):
            _replay_state['status'] = 'paused'
            _replay_state['current_event_time'] = _replay_state['scenario_end']
            _replay_state['wall_time_at_play'] = None
            _replay_state['event_time_at_play'] = None
            info['status'] = 'paused'
    return info


def play():
    """Start or resume replay. No-op if already playing."""
    with _replay_lock:
        if _replay_state['status'] == 'playing':
            return
        if _replay_state['current_event_time'] is None:
            _replay_state['current_event_time'] = (
                _replay_state['scenario_start']
            )
        _replay_state['status'] = 'playing'
        _replay_state['wall_time_at_play'] = time.time()
        _replay_state['event_time_at_play'] = (
            _replay_state['current_event_time']
        )


def pause():
    """Pause replay. No-op if not playing."""
    with _replay_lock:
        if _replay_state['status'] != 'playing':
            return
        # Freeze current time
        elapsed_wall = time.time() - _replay_state['wall_time_at_play']
        elapsed_event = elapsed_wall * _replay_state['speed']
        current = _replay_state['event_time_at_play'] + timedelta(
            seconds=elapsed_event
        )
        _replay_state['current_event_time'] = min(
            current, _replay_state['scenario_end']
        )
        _replay_state['status'] = 'paused'
        _replay_state['wall_time_at_play'] = None
        _replay_state['event_time_at_play'] = None


def set_speed(speed):
    """Set replay speed. Takes effect on next poll cycle."""
    with _replay_lock:
        # If playing, anchor the new speed from current position
        if _replay_state['status'] == 'playing':
            elapsed_wall = time.time() - _replay_state['wall_time_at_play']
            elapsed_event = elapsed_wall * _replay_state['speed']
            current = _replay_state['event_time_at_play'] + timedelta(
                seconds=elapsed_event
            )
            _replay_state['event_time_at_play'] = min(
                current, _replay_state['scenario_end']
            )
            _replay_state['wall_time_at_play'] = time.time()
        _replay_state['speed'] = speed


def jump(target_time_str):
    """Jump to a specific event time. Auto-pauses if playing.

    Returns the target as datetime (for projection rebuild).
    """
    target = datetime.strptime(target_time_str, FMT)
    with _replay_lock:
        # Clamp to scenario bounds
        target = max(target, _replay_state['scenario_start'])
        target = min(target, _replay_state['scenario_end'])
        _replay_state['status'] = 'paused'
        _replay_state['current_event_time'] = target
        _replay_state['wall_time_at_play'] = None
        _replay_state['event_time_at_play'] = None
    return target


def reset():
    """Reset to stopped state."""
    with _replay_lock:
        _replay_state['status'] = 'stopped'
        _replay_state['speed'] = 1
        _replay_state['current_event_time'] = None
        _replay_state['wall_time_at_play'] = None
        _replay_state['event_time_at_play'] = None
