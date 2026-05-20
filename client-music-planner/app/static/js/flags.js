// flags.js -- Toggle must-play/do-not-play flags via AJAX
// Vanilla JS only. Reads CSRF token from meta[name="csrf-token"].

function toggleFlag(token, songId, flagType) {
    var formData = new FormData();
    formData.append('song_id', songId);
    formData.append('flag_type', flagType);
    fetch('/portal/' + token + '/flags/toggle', {
        method: 'POST',
        headers: {'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content},
        body: formData
    }).then(function(r) { return r.json(); }).then(function(data) {
        if (data.success) {
            updateFlagUI(songId, data.is_must_play, data.is_do_not_play);
        }
    });
}

function updateFlagUI(songId, isMustPlay, isDoNotPlay) {
    // Find the playlist item containing this song
    var items = document.querySelectorAll('.playlist-item');
    for (var i = 0; i < items.length; i++) {
        var item = items[i];
        // Check if this item has a flag button for this song
        var mustPlayBtn = item.querySelector('.flag-must-play[data-song-id="' + songId + '"]');
        var doNotPlayBtn = item.querySelector('.flag-do-not-play[data-song-id="' + songId + '"]');

        if (mustPlayBtn) {
            if (isMustPlay) {
                mustPlayBtn.classList.add('active', 'btn-success');
                mustPlayBtn.classList.remove('btn-outline-success');
            } else {
                mustPlayBtn.classList.remove('active', 'btn-success');
                mustPlayBtn.classList.add('btn-outline-success');
            }
        }

        if (doNotPlayBtn) {
            if (isDoNotPlay) {
                doNotPlayBtn.classList.add('active', 'btn-danger');
                doNotPlayBtn.classList.remove('btn-outline-danger');
            } else {
                doNotPlayBtn.classList.remove('active', 'btn-danger');
                doNotPlayBtn.classList.add('btn-outline-danger');
            }
        }
    }

    // Announce for screen readers
    var announcer = document.getElementById('sr-announcer');
    if (announcer) {
        if (isMustPlay) {
            announcer.textContent = 'Song marked as must play.';
        } else if (isDoNotPlay) {
            announcer.textContent = 'Song marked as do not play.';
        } else {
            announcer.textContent = 'Song flag cleared.';
        }
    }
}
