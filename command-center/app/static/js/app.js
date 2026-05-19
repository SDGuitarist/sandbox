/**
 * app.js - Global application utilities for Command Center
 *
 * Handles:
 * - "/" keyboard shortcut to focus search
 * - Global search with API integration
 * - Quick-add modal form submissions via POST
 * - CSRF token management for all fetch requests
 */

(function () {
    'use strict';

    // --- CSRF Token Helper ---

    function getCsrfToken() {
        var meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute('content') : '';
    }

    // --- Keyboard Shortcut: "/" focuses search ---

    document.addEventListener('keydown', function (e) {
        // Only trigger when not already in an input/textarea/select
        var tag = e.target.tagName.toLowerCase();
        if (tag === 'input' || tag === 'textarea' || tag === 'select') {
            return;
        }

        if (e.key === '/') {
            e.preventDefault();
            var searchInput = document.getElementById('global-search');
            if (searchInput) {
                searchInput.focus();
            }
        }
    });

    // --- Global Search ---

    var searchInput = document.getElementById('global-search');
    var searchResults = document.getElementById('search-results');
    var searchTimeout = null;

    if (searchInput && searchResults) {
        searchInput.addEventListener('input', function () {
            var query = searchInput.value.trim();

            // Clear previous timeout
            if (searchTimeout) {
                clearTimeout(searchTimeout);
            }

            // Hide results if query is too short
            if (query.length < 2) {
                searchResults.classList.add('d-none');
                searchResults.innerHTML = '';
                return;
            }

            // Debounce: wait 300ms after last keystroke
            searchTimeout = setTimeout(function () {
                fetch('/search/api?q=' + encodeURIComponent(query), {
                    method: 'GET',
                    headers: {
                        'X-CSRFToken': getCsrfToken(),
                        'Accept': 'application/json'
                    }
                })
                    .then(function (response) {
                        return response.json();
                    })
                    .then(function (data) {
                        renderSearchResults(data);
                    })
                    .catch(function () {
                        searchResults.classList.add('d-none');
                    });
            }, 300);
        });

        // Close search results when clicking outside
        document.addEventListener('click', function (e) {
            if (!searchInput.contains(e.target) && !searchResults.contains(e.target)) {
                searchResults.classList.add('d-none');
            }
        });

        // Close search results on Escape
        searchInput.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') {
                searchResults.classList.add('d-none');
                searchInput.blur();
            }
        });
    }

    function renderSearchResults(data) {
        var results = data.results || [];

        if (results.length === 0) {
            searchResults.innerHTML = '<div class="search-no-results">No results found</div>';
            searchResults.classList.remove('d-none');
            return;
        }

        var html = '';
        for (var i = 0; i < results.length; i++) {
            var item = results[i];
            html += '<a href="' + escapeHtml(item.url) + '" class="search-result-item">';
            html += '<span class="result-type">' + escapeHtml(item.type) + '</span><br>';
            html += escapeHtml(item.title);
            html += '</a>';
        }

        searchResults.innerHTML = html;
        searchResults.classList.remove('d-none');
    }

    // --- Quick Add Contact Modal ---

    var contactForm = document.getElementById('quickAddContactForm');
    if (contactForm) {
        contactForm.addEventListener('submit', function (e) {
            e.preventDefault();

            var formData = new FormData(contactForm);

            fetch(contactForm.getAttribute('action'), {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCsrfToken()
                },
                body: formData
            })
                .then(function (response) {
                    if (response.redirected) {
                        window.location.href = response.url;
                        return;
                    }
                    return response.json();
                })
                .then(function (data) {
                    if (data && data.success) {
                        // Close modal and reload
                        var modal = bootstrap.Modal.getInstance(
                            document.getElementById('quickAddContactModal')
                        );
                        if (modal) {
                            modal.hide();
                        }
                        contactForm.reset();
                        window.location.reload();
                    } else if (data && data.error) {
                        alert(data.error);
                    }
                })
                .catch(function () {
                    // Fallback: submit as regular form
                    contactForm.submit();
                });
        });
    }

    // --- Quick Add Task Modal ---

    var taskForm = document.getElementById('quickAddTaskForm');
    if (taskForm) {
        taskForm.addEventListener('submit', function (e) {
            e.preventDefault();

            var formData = new FormData(taskForm);

            fetch(taskForm.getAttribute('action'), {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCsrfToken()
                },
                body: formData
            })
                .then(function (response) {
                    if (response.redirected) {
                        window.location.href = response.url;
                        return;
                    }
                    return response.json();
                })
                .then(function (data) {
                    if (data && data.success) {
                        var modal = bootstrap.Modal.getInstance(
                            document.getElementById('quickAddTaskModal')
                        );
                        if (modal) {
                            modal.hide();
                        }
                        taskForm.reset();
                        window.location.reload();
                    } else if (data && data.error) {
                        alert(data.error);
                    }
                })
                .catch(function () {
                    // Fallback: submit as regular form
                    taskForm.submit();
                });
        });
    }

    // --- Utility: HTML escaping ---

    function escapeHtml(str) {
        if (!str) return '';
        var div = document.createElement('div');
        div.appendChild(document.createTextNode(str));
        return div.innerHTML;
    }
})();
