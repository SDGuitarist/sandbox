"""CPAA Shadow Lab configuration — immutable config dicts with tuple sequences."""

EVENT_CONFIG = {
    'scenario_start': '2026-06-15 18:00:00',
    'scenario_end': '2026-06-15 22:00:00',
    'heartbeat_ttl_seconds': 60,
    'heartbeat_interval_seconds': 30,
    'temp_warning_c': 5.0,
    'temp_critical_c': 7.0,
    'auction_stall_minutes': 15,
}

REPLAY_CONFIG = {
    'default_speed': 1,
    'allowed_speeds': (1, 2, 5, 10),
    'poll_interval_ms': 500,
}

STATIONS = (
    {'id': 'station_1', 'name': 'Ceviche Bar', 'initial_weight_kg': 8.0,
     'has_temp_sensor': True, 'initial_temp_c': 2.0},
    {'id': 'station_2', 'name': 'Taco Station', 'initial_weight_kg': 10.0,
     'has_temp_sensor': False},
    {'id': 'station_3', 'name': 'Dessert Table', 'initial_weight_kg': 6.0,
     'has_temp_sensor': False},
)

AUCTION_LOTS = (
    {'id': 'lot_1', 'name': 'Surf Trip Package', 'opening_bid_cents': 50000},
    {'id': 'lot_2', 'name': 'Private Chef Dinner', 'opening_bid_cents': 30000},
    {'id': 'lot_3', 'name': 'Art Print Collection', 'opening_bid_cents': 20000},
)
