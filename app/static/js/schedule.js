// Schedule day view: drag-and-drop reorder (SortableJS) + accessible move buttons.
// Sends the new order to the reorder endpoint as JSON with the CSRF token in the
// X-CSRFToken header (read from the base.html meta tag).

(function () {
  'use strict';

  var list = document.getElementById('schedule-list');
  if (!list) {
    return;
  }

  var reorderUrl = list.dataset.reorderUrl;
  var shootDate = list.dataset.shootDate;

  function getCsrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : '';
  }

  function currentOrder() {
    var items = list.querySelectorAll('.schedule-item');
    var ids = [];
    items.forEach(function (el) {
      ids.push(parseInt(el.dataset.id, 10));
    });
    return ids;
  }

  function persistOrder() {
    var ids = currentOrder();
    fetch(reorderUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken()
      },
      body: JSON.stringify({ order: ids, shoot_date: shootDate })
    })
      .then(function (response) {
        if (!response.ok) {
          // Re-sync with the server's truth on failure.
          window.location.reload();
        }
      })
      .catch(function () {
        window.location.reload();
      });
  }

  // Drag-and-drop reordering.
  if (typeof Sortable !== 'undefined') {
    Sortable.create(list, {
      handle: '.drag-handle',
      animation: 150,
      onEnd: function () {
        persistOrder();
      }
    });
  }

  // Accessible move-up / move-down buttons (keyboard / no-drag fallback).
  list.addEventListener('click', function (event) {
    var upBtn = event.target.closest('.btn-move-up');
    var downBtn = event.target.closest('.btn-move-down');
    if (!upBtn && !downBtn) {
      return;
    }
    var row = event.target.closest('.schedule-item');
    if (!row) {
      return;
    }
    if (upBtn) {
      var prev = row.previousElementSibling;
      if (prev) {
        list.insertBefore(row, prev);
        persistOrder();
      }
    } else if (downBtn) {
      var next = row.nextElementSibling;
      if (next) {
        list.insertBefore(next, row);
        persistOrder();
      }
    }
  });
})();
