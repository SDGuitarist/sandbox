// playlist.js -- SortableJS drag-and-drop reorder + move up/down buttons
// Vanilla JS only. Reads CSRF token from meta[name="csrf-token"].

var playlistEl = document.getElementById('playlist-container');
var csrfToken = document.querySelector('meta[name="csrf-token"]').content;
var lastKnownOrder = [];  // snapshot for revert on error

document.addEventListener('DOMContentLoaded', function() {
    if (!playlistEl) return;

    // Snapshot initial server-rendered order
    lastKnownOrder = Array.from(
        playlistEl.querySelectorAll('.playlist-item')
    ).map(function(el) { return el.dataset.itemId; });

    // Move up/down buttons always work (accessibility, WCAG 2.5.7)
    initMoveButtons();

    // Drag-and-drop only if SortableJS loaded
    if (typeof Sortable !== 'undefined') {
        initSortable();
        playlistEl.querySelectorAll('.drag-handle').forEach(function(el) {
            el.classList.remove('d-none');
        });
    }
});

function initSortable() {
    var sortable = Sortable.create(playlistEl, {
        animation: 200,
        handle: '.drag-handle',
        ghostClass: 'playlist-ghost',
        chosenClass: 'playlist-chosen',
        dragClass: 'playlist-drag',
        forceFallback: true,
        fallbackTolerance: 3,
        dataIdAttr: 'data-item-id',
        draggable: '.playlist-item',
        onEnd: function(evt) {
            if (evt.oldIndex === evt.newIndex) return;
            savePlaylistOrder(sortable.toArray(), sortable);
        }
    });
}

function savePlaylistOrder(itemIds, sortableInstance) {
    var token = playlistEl.dataset.token;
    fetch('/api/playlist/reorder', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({token: token, item_ids: itemIds.map(Number)})
    }).then(function(r) {
        return r.json().then(function(data) { return {ok: r.ok, data: data}; });
    }).then(function(result) {
        if (result.ok && result.data.success) {
            lastKnownOrder = itemIds;
            announce('Playlist order saved.');
        } else {
            // Revert DOM to last known good state
            if (sortableInstance) sortableInstance.sort(lastKnownOrder, true);
            showToast(result.data.error || 'Save failed. Reverted.', 'danger');
            announce('Reorder failed. Reverted to previous order.');
        }
    }).catch(function() {
        if (sortableInstance) sortableInstance.sort(lastKnownOrder, true);
        showToast('Network error. Reverted.', 'danger');
        announce('Network error. Reverted to previous order.');
    });
}

function initMoveButtons() {
    playlistEl.addEventListener('click', function(e) {
        var btn = e.target.closest('.move-up, .move-down');
        if (!btn) return;

        var item = btn.closest('.playlist-item');
        if (!item) return;

        if (btn.classList.contains('move-up') && item.previousElementSibling) {
            playlistEl.insertBefore(item, item.previousElementSibling);
        } else if (btn.classList.contains('move-down') && item.nextElementSibling) {
            playlistEl.insertBefore(item.nextElementSibling, item);
        } else {
            return;  // already at boundary
        }

        // Collect new order and save
        var newOrder = Array.from(
            playlistEl.querySelectorAll('.playlist-item')
        ).map(function(el) { return el.dataset.itemId; });

        savePlaylistOrder(newOrder, null);
    });
}

function showToast(message, type) {
    // Create a simple Bootstrap alert at top of container
    var container = document.querySelector('.container');
    if (!container) return;
    var alert = document.createElement('div');
    alert.className = 'alert alert-' + (type || 'info') + ' alert-dismissible fade show';
    alert.setAttribute('role', 'alert');
    alert.innerHTML = message +
        '<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>';
    container.insertBefore(alert, container.firstChild);
    setTimeout(function() {
        if (alert.parentNode) alert.remove();
    }, 5000);
}

function announce(message) {
    var announcer = document.getElementById('sr-announcer');
    if (announcer) {
        announcer.textContent = message;
    }
}
