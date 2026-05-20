// Poll notification count on page load
document.addEventListener('DOMContentLoaded', function() {
    var badge = document.getElementById('notif-badge');
    if (!badge) return;
    fetch('/notifications/unread-count')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.count > 0) {
                badge.textContent = data.count;
                badge.classList.remove('d-none');
            }
        })
        .catch(function() { /* silently fail */ });
});
