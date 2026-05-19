/* Invoice & CRM -- Vanilla JavaScript */

document.addEventListener('DOMContentLoaded', function () {

    /* ===== CSRF Token for AJAX ===== */
    var csrfToken = (function () {
        var meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.content : '';
    })();

    /* ===== Invoice Line Items -- Add Row ===== */
    var addBtn = document.getElementById('add-line-item');
    if (addBtn) {
        addBtn.addEventListener('click', function () {
            var tbody = document.getElementById('line-items-body');
            var template = document.getElementById('line-item-template');
            if (tbody && template) {
                var clone = template.content.cloneNode(true);
                tbody.appendChild(clone);
                updateRowIndices();
            }
        });
    }

    /* ===== Invoice Line Items -- Remove Row (delegated) ===== */
    document.addEventListener('click', function (e) {
        if (e.target.classList.contains('remove-line-item') ||
            e.target.closest('.remove-line-item')) {
            var btn = e.target.classList.contains('remove-line-item')
                ? e.target
                : e.target.closest('.remove-line-item');
            var row = btn.closest('tr');
            if (row) {
                row.remove();
                updateRowIndices();
            }
        }
    });

    /* ===== Catalog Item Autofill (delegated) ===== */
    document.addEventListener('change', function (e) {
        if (e.target.classList.contains('catalog-select')) {
            var option = e.target.selectedOptions[0];
            var row = e.target.closest('tr');
            if (option && row) {
                var desc = option.dataset.description || '';
                var price = option.dataset.price || '';
                var descInput = row.querySelector('input[name="descriptions[]"]');
                var priceInput = row.querySelector('input[name="unit_prices[]"]');
                if (descInput && desc) {
                    descInput.value = desc;
                }
                if (priceInput && price) {
                    priceInput.value = price;
                }
            }
        }
    });

    /* ===== Row Index Updater ===== */
    /* Keeps row numbering consistent after adds/removes */
    function updateRowIndices() {
        var tbody = document.getElementById('line-items-body');
        if (!tbody) return;
        var rows = tbody.querySelectorAll('tr');
        rows.forEach(function (row, idx) {
            var numCell = row.querySelector('.line-item-number');
            if (numCell) {
                numCell.textContent = idx + 1;
            }
        });
    }

    /* ===== Pipeline Stage Move Buttons ===== */
    /* Handles inline stage-change buttons on the kanban view */
    document.addEventListener('click', function (e) {
        if (e.target.classList.contains('move-deal-btn') ||
            e.target.closest('.move-deal-btn')) {
            var btn = e.target.classList.contains('move-deal-btn')
                ? e.target
                : e.target.closest('.move-deal-btn');
            var dealId = btn.dataset.dealId;
            var newStage = btn.dataset.stage;
            if (!dealId || !newStage) return;

            var form = document.createElement('form');
            form.method = 'POST';
            form.action = '/pipeline/' + dealId + '/move';

            var stageInput = document.createElement('input');
            stageInput.type = 'hidden';
            stageInput.name = 'stage';
            stageInput.value = newStage;
            form.appendChild(stageInput);

            var tokenInput = document.createElement('input');
            tokenInput.type = 'hidden';
            tokenInput.name = 'csrf_token';
            tokenInput.value = csrfToken;
            form.appendChild(tokenInput);

            document.body.appendChild(form);
            form.submit();
        }
    });

    /* ===== Auto-dismiss Flash Messages ===== */
    var alerts = document.querySelectorAll('.alert-dismissible');
    alerts.forEach(function (alert) {
        setTimeout(function () {
            var closeBtn = alert.querySelector('[data-bs-dismiss="alert"]');
            if (closeBtn) {
                closeBtn.click();
            }
        }, 5000);
    });

    /* ===== Confirm Destructive Actions ===== */
    document.addEventListener('submit', function (e) {
        var form = e.target;
        if (form.dataset.confirm) {
            if (!window.confirm(form.dataset.confirm)) {
                e.preventDefault();
            }
        }
    });

    /* ===== Search Input -- Submit on Enter ===== */
    var searchInput = document.querySelector('.navbar input[name="q"]');
    if (searchInput) {
        searchInput.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') {
                var form = searchInput.closest('form');
                if (form && searchInput.value.trim()) {
                    form.submit();
                }
            }
        });
    }

});
