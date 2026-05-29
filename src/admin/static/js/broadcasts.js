/**
 * Broadcast form logic (TASK-061-amendment).
 *
 * Toggles category dropdown visibility based on selected segment.
 * CSP-compliant: no inline scripts, uses CSS class instead of inline style.
 */

(function () {
    "use strict";

    /**
     * Initializes segment/category toggle logic.
     */
    function initSegmentToggle() {
        const segmentInputs = document.querySelectorAll('input[name="segment"]');
        const categoryGroup = document.getElementById("category-group");

        if (!categoryGroup) {
            return;
        }

        function toggleCategory() {
            const selected = document.querySelector('input[name="segment"]:checked');
            if (selected && selected.value === "category") {
                categoryGroup.classList.remove("pv-hidden");
            } else {
                categoryGroup.classList.add("pv-hidden");
            }
        }

        segmentInputs.forEach(function (input) {
            input.addEventListener("change", toggleCategory);
        });

        // Initialize on load
        toggleCategory();
    }

    // Initialize on DOMContentLoaded
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initSegmentToggle);
    } else {
        initSegmentToggle();
    }
})();
