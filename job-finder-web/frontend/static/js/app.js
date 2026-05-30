/**
 * Job Finder Web App - Main JavaScript
 */

window.JobFinder = window.JobFinder || {
    async onModelSelectorChange(functionName, modelId) {
        const statusSpan = document.getElementById(`status-${functionName}`);
        if (statusSpan) {
            statusSpan.innerHTML = '<span class="badge bg-secondary"><i class="bi bi-hourglass-split"></i> Saving...</span>';
        }

        try {
            const response = await fetch(`/api/llm/function/${functionName}/model`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({model_id: modelId ? parseInt(modelId, 10) : null})
            });
            const data = await response.json();

            if (!data.success) {
                throw new Error(data.message || 'Failed to save model selection');
            }

            if (statusSpan) {
                statusSpan.dataset.modelId = modelId || '';
                statusSpan.innerHTML = modelId
                    ? '<span class="badge bg-success"><i class="bi bi-check-circle"></i> Ready</span>'
                    : '<span class="badge bg-warning text-dark"><i class="bi bi-exclamation-triangle"></i> Not configured</span>';
            }
        } catch (error) {
            if (statusSpan) {
                statusSpan.innerHTML = '<span class="badge bg-danger"><i class="bi bi-x-circle"></i> Error</span>';
            }
            console.error('Error saving model selection:', error);
        }
    },

    async loadModelsForWidget(widget) {
        if (!widget) return;

        const functionName = widget.getAttribute('data-function');
        const selectElement = widget.querySelector('select');
        const statusElement = document.getElementById(`status-${functionName}`);

        if (!functionName || !selectElement || selectElement.dataset.modelsLoaded === 'true') {
            return;
        }

        try {
            let currentModelId = statusElement?.dataset.modelId || '';
            if (!currentModelId) {
                const mappingResponse = await fetch(`/api/llm/function/${functionName}/model`);
                if (mappingResponse.ok) {
                    const mappingData = await mappingResponse.json();
                    currentModelId = mappingData.model_id ? String(mappingData.model_id) : '';
                    if (statusElement && currentModelId) {
                        statusElement.dataset.modelId = currentModelId;
                    }
                }
            }

            const response = await fetch('/api/llm/models');
            const data = await response.json();

            selectElement.innerHTML = '<option value="">-- Select Model --</option>';

            data.providers.forEach(provider => {
                if (!provider.models || provider.models.length === 0) return;

                const optgroup = document.createElement('optgroup');
                optgroup.label = provider.name.charAt(0).toUpperCase() + provider.name.slice(1);

                provider.models.forEach(model => {
                    const option = document.createElement('option');
                    option.value = model.id;
                    option.textContent = model.display_name || model.model_name || model.name;
                    if (model.is_default) {
                        option.textContent += ' (default)';
                    }
                    if (currentModelId && String(model.id) === String(currentModelId)) {
                        option.selected = true;
                    }
                    optgroup.appendChild(option);
                });

                selectElement.appendChild(optgroup);
            });

            selectElement.dataset.modelsLoaded = 'true';

            if (statusElement) {
                statusElement.innerHTML = currentModelId
                    ? '<span class="badge bg-success"><i class="bi bi-check-circle"></i> Ready</span>'
                    : '<span class="badge bg-warning text-dark"><i class="bi bi-exclamation-triangle"></i> Not configured</span>';
            }
        } catch (error) {
            console.error('Error loading models:', error);
            selectElement.innerHTML = '<option value="">Error loading models</option>';
            if (statusElement) {
                statusElement.innerHTML = '<span class="badge bg-danger"><i class="bi bi-x-circle"></i> Error</span>';
            }
        }
    },

    initModelSelectors(root = document) {
        if (!root || !root.querySelectorAll) return;
        root.querySelectorAll('.model-selector-widget').forEach(widget => this.loadModelsForWidget(widget));
    }
};

window.onModelSelectorChange = function(functionName, modelId) {
    return window.JobFinder.onModelSelectorChange(functionName, modelId);
};

window.loadModelsForWidget = function(widget) {
    return window.JobFinder.loadModelsForWidget(widget);
};

// Initialize Alpine.js components
document.addEventListener('alpine:init', () => {
    // Global Alpine.js data can be defined here
});

document.addEventListener('DOMContentLoaded', function() {
    window.JobFinder.initModelSelectors(document);
});

document.addEventListener('htmx:afterSwap', function(event) {
    window.JobFinder.initModelSelectors(event.target);
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
