/* GigSheet -- minimal JS: flash dismiss, fetch helpers */

document.addEventListener('DOMContentLoaded', function () {
    // Auto-dismiss flash messages after 5 seconds
    var flashAlerts = document.querySelectorAll('.flash-container .alert');
    flashAlerts.forEach(function (alert) {
        setTimeout(function () {
            alert.style.transition = 'opacity 0.3s';
            alert.style.opacity = '0';
            setTimeout(function () {
                alert.remove();
            }, 300);
        }, 5000);
    });
});

/**
 * POST JSON to a URL and return the parsed response.
 * Includes CSRF token from the meta tag.
 */
function postJSON(url, data) {
    var csrfMeta = document.querySelector('meta[name="csrf-token"]');
    var csrfToken = csrfMeta ? csrfMeta.getAttribute('content') : '';
    return fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
        },
        body: JSON.stringify(data),
    }).then(function (response) {
        if (!response.ok) {
            throw new Error('Request failed: ' + response.status);
        }
        return response.json();
    });
}
