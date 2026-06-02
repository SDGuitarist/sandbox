/**
 * Schedule drag-and-drop reorder via SortableJS.
 *
 * SortableJS Class-Name Contract (must match HTML template + Python route):
 * - Container: id="schedule-list"
 * - Items: class="schedule-item" with data-id
 * - Handle: class="drag-handle"
 * - Move buttons: class="btn-move-up" / class="btn-move-down"
 * - Reorder endpoint: POST /<project_id>/reorder with JSON {order: [ids], shoot_date: date}
 * - CSRF: X-CSRFToken header from meta[name="csrf-token"]
 */
(function () {
    'use strict';

    var container = document.getElementById('schedule-list');
    if (!container) return;

    var projectId = container.dataset.projectId;
    var shootDate = container.dataset.shootDate;
    var csrfToken = document.querySelector('meta[name="csrf-token"]').content;

    // Helper: collect current ID order from DOM
    function getOrder() {
        var items = container.querySelectorAll('.schedule-item');
        var ids = [];
        for (var i = 0; i < items.length; i++) {
            ids.push(parseInt(items[i].dataset.id, 10));
        }
        return ids;
    }

    // Helper: send reorder request to server
    function sendReorder(ids) {
        fetch('/schedule/' + projectId + '/reorder', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({ order: ids, shoot_date: shootDate })
        }).then(function (response) {
            if (!response.ok) {
                response.json().then(function (data) {
                    alert('Reorder failed: ' + (data.error || 'Unknown error'));
                }).catch(function () {
                    alert('Reorder failed');
                });
            }
        }).catch(function () {
            alert('Network error during reorder');
        });
    }

    // Initialize SortableJS on the container
    Sortable.create(container, {
        handle: '.drag-handle',
        animation: 150,
        onEnd: function () {
            sendReorder(getOrder());
        }
    });

    // Accessibility: move-up / move-down button handlers
    container.addEventListener('click', function (e) {
        var btn = e.target.closest('.btn-move-up, .btn-move-down');
        if (!btn) return;

        var item = btn.closest('.schedule-item');
        if (!item) return;

        if (btn.classList.contains('btn-move-up')) {
            var prev = item.previousElementSibling;
            if (prev && prev.classList.contains('schedule-item')) {
                container.insertBefore(item, prev);
            }
        } else if (btn.classList.contains('btn-move-down')) {
            var next = item.nextElementSibling;
            if (next && next.classList.contains('schedule-item')) {
                container.insertBefore(next, item);
            }
        }

        sendReorder(getOrder());
    });
})();
