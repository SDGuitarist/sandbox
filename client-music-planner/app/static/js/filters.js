// filters.js -- Debounced AJAX song filtering for portal browse page
// Vanilla JS only. Reads CSRF token from meta[name="csrf-token"].

var debounceTimer;

function filterSongs(token) {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(function() {
        var genre = document.getElementById('genre-filter').value;
        var energy = document.getElementById('energy-filter').value;
        var search = document.getElementById('search-input').value;
        var params = new URLSearchParams({token: token, genre: genre, energy: energy, search: search});
        fetch('/api/filters/songs?' + params)
            .then(function(r) { return r.json(); })
            .then(function(data) { renderSongList(data.songs); });
    }, 300);
}

function renderSongList(songs) {
    var container = document.getElementById('song-list');
    if (!container) return;

    if (!songs || songs.length === 0) {
        container.innerHTML = '<p class="text-muted">No songs match your filters.</p>';
        return;
    }

    var html = '';
    for (var i = 0; i < songs.length; i++) {
        var song = songs[i];
        var inPlaylist = song.in_playlist;
        var duration = song.duration_seconds ? formatDuration(song.duration_seconds) : '';
        var energy = formatEnergy(song.energy);
        var genre = formatGenre(song.genre);

        html += '<div class="card mb-2">';
        html += '<div class="card-body d-flex justify-content-between align-items-center">';
        html += '<div>';
        html += '<strong>' + escapeHtml(song.title) + '</strong>';
        if (song.artist) {
            html += ' <span class="text-muted">by ' + escapeHtml(song.artist) + '</span>';
        }
        html += '<br><small class="text-muted">' + escapeHtml(genre);
        if (energy) {
            html += ' &middot; ' + escapeHtml(energy);
        }
        if (duration) {
            html += ' &middot; ' + escapeHtml(duration);
        }
        html += '</small>';
        html += '</div>';
        html += '<div>';
        if (inPlaylist) {
            html += '<span class="badge bg-success">In Playlist</span>';
        }
        html += '</div>';
        html += '</div>';
        html += '</div>';
    }

    container.innerHTML = html;
}

function formatDuration(seconds) {
    if (!seconds) return '';
    var minutes = Math.floor(seconds / 60);
    var secs = seconds % 60;
    return minutes + ':' + (secs < 10 ? '0' : '') + secs;
}

function formatEnergy(energy) {
    var labels = {1: 'Low', 2: 'Mellow', 3: 'Moderate', 4: 'Upbeat', 5: 'High'};
    return labels[energy] || String(energy);
}

function formatGenre(genre) {
    var special = {'r_and_b': 'R&B', 'hip_hop': 'Hip Hop'};
    if (special[genre]) return special[genre];
    return genre.replace(/_/g, ' ').replace(/\b\w/g, function(c) { return c.toUpperCase(); });
}

function escapeHtml(text) {
    if (!text) return '';
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(text));
    return div.innerHTML;
}
