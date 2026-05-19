/**
 * timer.js - Time tracking timer for Command Center
 *
 * Handles:
 * - Start button: stores Date.now() in localStorage, shows elapsed time
 * - Stop button: calculates duration, POSTs to /time/stop
 * - Display: updates every second showing HH:MM:SS
 * - Show/hide start/stop buttons based on timer state
 */

(function () {
    'use strict';

    var TIMER_KEY = 'timer_start';
    var timerInterval = null;

    // DOM elements
    var startBtn = document.getElementById('timer-start');
    var stopBtn = document.getElementById('timer-stop');
    var display = document.getElementById('timer-display');

    // Exit early if timer elements are not on the page
    if (!startBtn || !stopBtn || !display) {
        return;
    }

    function getCsrfToken() {
        var meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute('content') : '';
    }

    // --- Format elapsed milliseconds as HH:MM:SS ---

    function formatElapsed(ms) {
        var totalSeconds = Math.floor(ms / 1000);
        var hours = Math.floor(totalSeconds / 3600);
        var minutes = Math.floor((totalSeconds % 3600) / 60);
        var seconds = totalSeconds % 60;

        return (
            String(hours).padStart(2, '0') + ':' +
            String(minutes).padStart(2, '0') + ':' +
            String(seconds).padStart(2, '0')
        );
    }

    // --- Update the display every second ---

    function updateDisplay() {
        var startTime = localStorage.getItem(TIMER_KEY);
        if (!startTime) {
            display.textContent = '00:00:00';
            display.classList.remove('timer-running');
            return;
        }

        var elapsed = Date.now() - parseInt(startTime, 10);
        display.textContent = formatElapsed(elapsed);
        display.classList.add('timer-running');
    }

    // --- Sync button visibility with localStorage state ---

    function syncButtons() {
        var isRunning = localStorage.getItem(TIMER_KEY) !== null;

        if (isRunning) {
            startBtn.classList.add('d-none');
            stopBtn.classList.remove('d-none');
        } else {
            startBtn.classList.remove('d-none');
            stopBtn.classList.add('d-none');
        }
    }

    // --- Start the timer ---

    startBtn.addEventListener('click', function () {
        localStorage.setItem(TIMER_KEY, String(Date.now()));
        syncButtons();
        startTicking();
    });

    // --- Stop the timer ---

    stopBtn.addEventListener('click', function () {
        var startTime = localStorage.getItem(TIMER_KEY);
        if (!startTime) {
            return;
        }

        var elapsed = Date.now() - parseInt(startTime, 10);
        var minutes = Math.round(elapsed / 60000);

        // Ensure at least 1 minute
        if (minutes < 1) {
            minutes = 1;
        }

        // Clear timer state
        localStorage.removeItem(TIMER_KEY);
        stopTicking();
        syncButtons();
        display.textContent = '00:00:00';
        display.classList.remove('timer-running');

        // POST duration to server
        var formData = new FormData();
        formData.append('minutes', String(minutes));

        fetch('/time/stop', {
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
                    window.location.reload();
                }
            })
            .catch(function () {
                // Reload page as fallback to show flash message
                window.location.reload();
            });
    });

    // --- Tick management ---

    function startTicking() {
        if (timerInterval) {
            clearInterval(timerInterval);
        }
        updateDisplay();
        timerInterval = setInterval(updateDisplay, 1000);
    }

    function stopTicking() {
        if (timerInterval) {
            clearInterval(timerInterval);
            timerInterval = null;
        }
    }

    // --- Initialize on page load ---

    syncButtons();
    if (localStorage.getItem(TIMER_KEY)) {
        startTicking();
    } else {
        display.textContent = '00:00:00';
    }
})();
