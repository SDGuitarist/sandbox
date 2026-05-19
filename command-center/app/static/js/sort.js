/**
 * sort.js - Client-side table sorting for Command Center
 *
 * Handles:
 * - Click column header (th[data-sort]) to sort table rows by that column
 * - Toggle asc/desc on repeated clicks
 * - Supports text and numeric sorting
 *
 * Usage in HTML:
 *   <table class="table" data-sortable>
 *     <thead>
 *       <tr>
 *         <th data-sort="0">Name</th>
 *         <th data-sort="1" data-sort-type="number">Amount</th>
 *       </tr>
 *     </thead>
 *     <tbody>...</tbody>
 *   </table>
 */

(function () {
    'use strict';

    document.addEventListener('click', function (e) {
        var th = e.target.closest('th[data-sort]');
        if (!th) {
            return;
        }

        var table = th.closest('table');
        if (!table) {
            return;
        }

        var tbody = table.querySelector('tbody');
        if (!tbody) {
            return;
        }

        var colIndex = parseInt(th.getAttribute('data-sort'), 10);
        var sortType = th.getAttribute('data-sort-type') || 'text';

        // Determine sort direction
        var currentDir = th.classList.contains('sort-asc') ? 'asc' : (th.classList.contains('sort-desc') ? 'desc' : 'none');
        var newDir = (currentDir === 'asc') ? 'desc' : 'asc';

        // Clear sort classes from all headers in this table
        var allHeaders = table.querySelectorAll('th[data-sort]');
        for (var i = 0; i < allHeaders.length; i++) {
            allHeaders[i].classList.remove('sort-asc', 'sort-desc');
        }

        // Set new sort class
        th.classList.add('sort-' + newDir);

        // Get rows as array
        var rows = Array.prototype.slice.call(tbody.querySelectorAll('tr'));

        rows.sort(function (a, b) {
            var cellA = a.querySelectorAll('td')[colIndex];
            var cellB = b.querySelectorAll('td')[colIndex];

            if (!cellA || !cellB) {
                return 0;
            }

            var valA = (cellA.getAttribute('data-sort-value') || cellA.textContent).trim();
            var valB = (cellB.getAttribute('data-sort-value') || cellB.textContent).trim();

            var result;

            if (sortType === 'number') {
                // Parse as numbers, treating non-numeric as 0
                var numA = parseFloat(valA.replace(/[^0-9.\-]/g, '')) || 0;
                var numB = parseFloat(valB.replace(/[^0-9.\-]/g, '')) || 0;
                result = numA - numB;
            } else {
                // Case-insensitive text comparison
                result = valA.toLowerCase().localeCompare(valB.toLowerCase());
            }

            return newDir === 'desc' ? -result : result;
        });

        // Re-append sorted rows
        for (var j = 0; j < rows.length; j++) {
            tbody.appendChild(rows[j]);
        }
    });
})();
