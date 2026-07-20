/**
 * Shared behavior for collapsible curated collections on a candidate profile.
 * Header actions deliberately sit outside the toggle so parsing or editing does
 * not change the card's folded state.
 */
document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.collection-more-toggle').forEach(function (toggle) {
        const selector = toggle.getAttribute('data-bs-target');
        const collection = selector ? document.querySelector(selector) : null;
        if (!collection) return;

        const moreLabel = toggle.dataset.moreLabel;
        const setLabel = function (expanded) {
            toggle.setAttribute('aria-expanded', String(expanded));
            toggle.innerHTML = expanded
                ? '<i class="bi bi-chevron-up"></i> Show less'
                : '<i class="bi bi-chevron-down"></i> ' + moreLabel;
        };

        collection.addEventListener('shown.bs.collapse', function () { setLabel(true); });
        collection.addEventListener('hidden.bs.collapse', function () { setLabel(false); });
    });
});
