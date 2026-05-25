/* CPAA Shadow Lab — Client-side replay engine */

const POLL_INTERVAL_MS = 500;
const SCENARIO_START = new Date('2026-06-15T18:00:00');
const SCENARIO_DURATION_S = 14400; // 4 hours

let pollTimer = null;
let isDragging = false;
let activeFilter = 'all';

// ── Polling ──────────────────────────────────────────────────────────

function startPolling() {
    if (pollTimer) return;
    pollState(); // immediate first poll
    pollTimer = setInterval(pollState, POLL_INTERVAL_MS);
}

function stopPolling() {
    if (pollTimer) {
        clearInterval(pollTimer);
        pollTimer = null;
    }
}

async function pollState() {
    try {
        const res = await fetch('/api/state');
        if (!res.ok) return;
        const data = await res.json();
        updateAll(data);
    } catch (e) {
        // Retry on next poll
    }
}

function updateAll(data) {
    updateReplayControls(data.replay);
    updateStations(data.stations);
    updateEnvironment(data.environment);
    updateFinancials(data.financials);
    updateAlerts(data.alerts);
    updateTimeline(data.recent_events);
}

// ── Replay Controls ──────────────────────────────────────────────────

function updateReplayControls(replay) {
    const timeEl = document.getElementById('current-time');
    const statusEl = document.getElementById('replay-status');
    const slider = document.getElementById('progress-slider');

    if (replay.current_event_time) {
        // Show just the time portion (HH:MM:SS)
        timeEl.textContent = replay.current_event_time.split(' ')[1];
    } else {
        timeEl.textContent = '--:--:--';
    }

    statusEl.textContent = replay.status;
    statusEl.className = 'badge ' + {
        stopped: 'bg-secondary',
        playing: 'bg-success',
        paused: 'bg-warning text-dark',
    }[replay.status];

    // Update slider unless user is dragging
    if (!isDragging && replay.current_event_time) {
        const eventTime = new Date(replay.current_event_time.replace(' ', 'T'));
        const elapsed = (eventTime - SCENARIO_START) / 1000;
        slider.value = Math.max(0, Math.min(elapsed, SCENARIO_DURATION_S));
    }

    // Auto-manage polling
    if (replay.status === 'playing' && !pollTimer) {
        startPolling();
    }
}

// ── State Panels ─────────────────────────────────────────────────────

function updateStations(stations) {
    const panel = document.getElementById('stations-panel');
    if (!stations || stations.length === 0) {
        panel.innerHTML = '<p class="text-secondary mb-0">No station data</p>';
        return;
    }
    panel.innerHTML = stations.map(s => {
        const statusClass = s.status || 'unknown';
        const weight = s.current_weight_kg != null ? s.current_weight_kg.toFixed(1) + ' kg' : 'n/a';
        const temp = s.current_temp_c != null ? s.current_temp_c.toFixed(1) + '\u00B0C' : 'n/a';
        const tempClass = s.temp_status === 'critical' ? 'text-danger' :
                          s.temp_status === 'warning' ? 'text-warning' : '';
        return `<div class="station-card">
            <div class="d-flex justify-content-between align-items-center">
                <span class="station-name">
                    <span class="status-dot ${statusClass}"></span>${s.name}
                </span>
                <span class="badge bg-${statusClass === 'healthy' ? 'success' :
                    statusClass === 'warning' ? 'warning' :
                    statusClass === 'critical' ? 'danger' : 'secondary'}">${s.status}</span>
            </div>
            <div class="station-detail mt-1">
                Wt: ${weight} &nbsp;|&nbsp; Tmp: <span class="${tempClass}">${temp}</span>
            </div>
        </div>`;
    }).join('');
}

function updateEnvironment(env) {
    const panel = document.getElementById('environment-panel');
    if (!env || Object.keys(env).length === 0) {
        panel.innerHTML = '<p class="text-secondary mb-0">No readings yet</p>';
        return;
    }
    const temp = env.temperature_c != null ? env.temperature_c.toFixed(1) + '\u00B0C' : 'n/a';
    const hum = env.humidity_pct != null ? env.humidity_pct.toFixed(0) + '%' : 'n/a';
    const wind = env.wind_speed_kmh != null ? env.wind_speed_kmh.toFixed(0) + ' km/h' : 'n/a';
    panel.innerHTML = `
        <div class="financial-row"><span class="financial-label">Temp</span><span class="financial-value">${temp}</span></div>
        <div class="financial-row"><span class="financial-label">Humidity</span><span class="financial-value">${hum}</span></div>
        <div class="financial-row"><span class="financial-label">Wind</span><span class="financial-value">${wind}</span></div>
    `;
}

function updateFinancials(fin) {
    const panel = document.getElementById('financials-panel');
    if (!fin || Object.keys(fin).length === 0) {
        panel.innerHTML = '<p class="text-secondary mb-0">No transactions yet</p>';
        return;
    }
    const revenue = (fin.total_revenue_cents / 100).toLocaleString('en-US', {style: 'currency', currency: 'USD'});
    const topBid = (fin.highest_bid_cents / 100).toLocaleString('en-US', {style: 'currency', currency: 'USD'});
    panel.innerHTML = `
        <div class="financial-row"><span class="financial-label">Revenue</span><span class="financial-value">${revenue}</span></div>
        <div class="financial-row"><span class="financial-label">Transactions</span><span class="financial-value">${fin.transaction_count}</span></div>
        <div class="financial-row"><span class="financial-label">Bids</span><span class="financial-value">${fin.total_bids}</span></div>
        <div class="financial-row"><span class="financial-label">Top Bid</span><span class="financial-value">${topBid}</span></div>
    `;
}

function updateAlerts(alerts) {
    const panel = document.getElementById('alerts-panel');
    const badge = document.getElementById('alert-count');
    badge.textContent = alerts.length;
    badge.className = 'badge ' + (alerts.length > 0 ? 'bg-danger' : 'bg-secondary');

    if (!alerts || alerts.length === 0) {
        panel.innerHTML = '<p class="text-muted mb-0">No alerts</p>';
        return;
    }
    panel.innerHTML = alerts.map(a =>
        `<div class="alert-item ${a.severity}">
            <strong>${a.alert_type}</strong>: ${a.message}
        </div>`
    ).join('');
}

// ── Timeline ─────────────────────────────────────────────────────────

function getEventTag(eventType) {
    if (eventType.includes('alert')) return { tag: 'ALERT', cls: 'alert' };
    if (eventType.includes('transaction')) return { tag: 'SALE', cls: 'sale' };
    if (eventType.includes('bid')) return { tag: 'BID', cls: 'bid' };
    if (eventType.includes('heartbeat')) return { tag: 'BEAT', cls: 'beat' };
    if (eventType.includes('weather')) return { tag: 'ENV', cls: 'env' };
    if (eventType.includes('operator')) return { tag: 'NOTE', cls: 'note' };
    if (eventType.includes('temperature')) return { tag: 'TEMP', cls: 'temp' };
    if (eventType.includes('weight')) return { tag: 'WT', cls: 'weight' };
    return { tag: 'SYS', cls: 'beat' };
}

function getFilterCategory(eventType) {
    if (eventType.includes('alert')) return 'alert';
    if (eventType.includes('transaction') || eventType.includes('bid')) return 'financial';
    if (eventType.includes('heartbeat') || eventType.includes('operator')) return 'system';
    return 'telemetry';
}

function formatEventMessage(eventType, payload) {
    if (eventType.includes('transaction')) {
        return `POS txn ${(payload.amount_cents / 100).toFixed(2)} (${payload.item})`;
    }
    if (eventType.includes('bid')) {
        return `${payload.lot_id} bid #${payload.bid_number} $${(payload.amount_cents / 100).toFixed(0)}`;
    }
    if (eventType.includes('weight')) {
        return `${payload.station_id} weight ${payload.weight_kg} kg`;
    }
    if (eventType.includes('temperature')) {
        return `${payload.station_id} temp ${payload.temp_c}\u00B0C`;
    }
    if (eventType.includes('weather')) {
        return `${payload.temperature_c}\u00B0C, ${payload.humidity_pct}% hum, ${payload.wind_speed_kmh} km/h`;
    }
    if (eventType.includes('heartbeat')) {
        return `${payload.station_id} OK`;
    }
    if (eventType.includes('alert.raised')) {
        return `${payload.message}`;
    }
    if (eventType.includes('alert.resolved')) {
        return `Resolved: ${payload.alert_key}`;
    }
    if (eventType.includes('operator_note')) {
        return payload.note;
    }
    return JSON.stringify(payload);
}

function updateTimeline(events) {
    const container = document.getElementById('timeline');
    if (!events || events.length === 0) {
        container.innerHTML = '<p class="text-secondary p-3 mb-0">Press Play to start replay</p>';
        return;
    }
    container.innerHTML = events.map(e => {
        const { tag, cls } = getEventTag(e.event_type);
        const category = getFilterCategory(e.event_type);
        const time = e.event_time.split(' ')[1];
        const msg = formatEventMessage(e.event_type, e.payload);
        const hidden = (activeFilter !== 'all' && category !== activeFilter) ? ' style="display:none"' : '';
        return `<div class="timeline-event" data-category="${category}"${hidden}>
            <span class="event-time">${time}</span>
            <span class="event-tag ${cls}">${tag}</span>
            ${msg}
        </div>`;
    }).join('');
}

// ── Event Handlers ───────────────────────────────────────────────────

document.getElementById('btn-play').addEventListener('click', () => {
    fetch('/api/replay/play', { method: 'POST' });
    startPolling();
});

document.getElementById('btn-pause').addEventListener('click', () => {
    fetch('/api/replay/pause', { method: 'POST' });
    // Keep polling once more to get paused state, then stop
    setTimeout(() => { pollState(); stopPolling(); }, 200);
});

document.getElementById('btn-reset').addEventListener('click', () => {
    fetch('/api/replay/reset', { method: 'POST' }).then(() => {
        stopPolling();
        pollState();
    });
});

// Speed buttons
document.querySelectorAll('.speed-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const speed = parseInt(btn.dataset.speed);
        fetch('/api/replay/speed', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ speed }),
        });
        document.querySelectorAll('.speed-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
    });
});

// Progress slider
const slider = document.getElementById('progress-slider');
slider.addEventListener('mousedown', () => { isDragging = true; });
slider.addEventListener('touchstart', () => { isDragging = true; });
slider.addEventListener('mouseup', jumpFromSlider);
slider.addEventListener('touchend', jumpFromSlider);

function jumpFromSlider() {
    isDragging = false;
    const seconds = parseInt(slider.value);
    const target = new Date(SCENARIO_START.getTime() + seconds * 1000);
    const timeStr = target.toISOString().replace('T', ' ').substring(0, 19);
    fetch('/api/replay/jump', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ time: timeStr }),
    }).then(() => pollState());
}

// Timeline filter buttons
document.querySelectorAll('.filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        activeFilter = btn.dataset.filter;
        document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        // Apply filter to existing events
        document.querySelectorAll('.timeline-event').forEach(el => {
            if (activeFilter === 'all' || el.dataset.category === activeFilter) {
                el.style.display = '';
            } else {
                el.style.display = 'none';
            }
        });
    });
});

// ── Initial load ─────────────────────────────────────────────────────
pollState();
