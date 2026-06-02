/**
 * Film Production PM Tool - Shared JS Utilities
 */

/**
 * Extract CSRF token from the meta tag in base.html.
 * Used by all JavaScript POST requests (e.g., schedule reorder).
 * @returns {string} The CSRF token value
 */
function getCsrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : '';
}

/**
 * Make a JSON POST request with CSRF protection.
 * @param {string} url - The endpoint URL
 * @param {Object} data - The data to send as JSON
 * @returns {Promise<Response>} The fetch response
 */
function postJSON(url, data) {
    return fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify(data)
    });
}
