/**
 * Job Finder Web App - Main JavaScript
 */

// Initialize Alpine.js components
document.addEventListener('alpine:init', () => {
    // Global Alpine.js data can be defined here
});

// HTMX event listeners
document.body.addEventListener('htmx:afterRequest', function(evt) {
    // Handle HTMX request completion
    console.log('HTMX request completed');
});

document.body.addEventListener('htmx:error', function(evt) {
    // Handle HTMX errors
    console.error('HTMX error:', evt.detail);
    alert('An error occurred. Please try again.');
});

// Bootstrap tooltips
var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
    return new bootstrap.Tooltip(tooltipTriggerEl);
});

// Bootstrap popovers
var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
var popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
    return new bootstrap.Popover(popoverTriggerEl);
});

// Theme toggle (dark/light workspace preference, persisted in localStorage)
var themeToggleBtn = document.getElementById('themeToggleBtn');
if (themeToggleBtn) {
    var applyThemeIcon = function (theme) {
        var icon = themeToggleBtn.querySelector('i');
        icon.className = theme === 'dark' ? 'bi bi-sun' : 'bi bi-moon-stars';
    };
    applyThemeIcon(document.documentElement.getAttribute('data-bs-theme') || 'light');
    themeToggleBtn.addEventListener('click', function () {
        var current = document.documentElement.getAttribute('data-bs-theme') || 'light';
        var next = current === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-bs-theme', next);
        window.localStorage.setItem('jobfinder-theme', next);
        applyThemeIcon(next);
    });
}

// Confirm delete actions
document.querySelectorAll('[data-confirm]').forEach(function(element) {
    element.addEventListener('click', function(e) {
        var message = element.getAttribute('data-confirm');
        if (!confirm(message)) {
            e.preventDefault();
        }
    });
});

// Auto-dismiss alerts after 5 seconds
document.querySelectorAll('.alert-dismissible').forEach(function(alert) {
    setTimeout(function() {
        var bsAlert = new bootstrap.Alert(alert);
        bsAlert.close();
    }, 5000);
});

// Console welcome message
console.log('%c🚀 Job Finder Web App', 'color: blue; font-size: 20px; font-weight: bold;');
console.log('%cWelcome to Job Finder! Open browser console to see logs.', 'color: green; font-size: 12px;');
