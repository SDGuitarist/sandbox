/**
 * pipeline.js - Pipeline deal stage management for Command Center
 *
 * Handles:
 * - "Move to [stage]" buttons: POST to /pipeline/{id}/move with {stage: 'new_stage'}
 * - On success, reload the page to reflect updated stage
 */

(function () {
    'use strict';

    function getCsrfToken() {
        var meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute('content') : '';
    }

    // Delegate click events on all "move to stage" buttons
    document.addEventListener('click', function (e) {
        var btn = e.target.closest('[data-move-deal]');
        if (!btn) {
            return;
        }

        e.preventDefault();

        var dealId = btn.getAttribute('data-move-deal');
        var newStage = btn.getAttribute('data-stage');

        if (!dealId || !newStage) {
            return;
        }

        // Disable button to prevent double-clicks
        btn.disabled = true;
        var originalText = btn.textContent;
        btn.textContent = 'Moving...';

        fetch('/pipeline/' + encodeURIComponent(dealId) + '/move', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({ stage: newStage })
        })
            .then(function (response) {
                if (response.ok || response.redirected) {
                    window.location.reload();
                } else {
                    return response.json().then(function (data) {
                        alert(data.error || 'Failed to move deal');
                        btn.disabled = false;
                        btn.textContent = originalText;
                    });
                }
            })
            .catch(function () {
                alert('Network error. Please try again.');
                btn.disabled = false;
                btn.textContent = originalText;
            });
    });
})();
