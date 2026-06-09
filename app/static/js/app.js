// Film Production PM -- shared client-side utilities.

// Extract the CSRF token from the meta tag in base.html for JSON POST requests.
function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : '';
}

// Convenience wrapper for CSRF-protected JSON POSTs (e.g. schedule reorder).
function postJson(url, data) {
    return fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify(data)
    });
}
