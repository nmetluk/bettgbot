/**
 * Safe confirmation dialog for delete actions.
 *
 * Delegated event handler on document.body reads data-confirm and data-name
 * from the clicked element, constructs message safely via DOM textContent
 * (no innerHTML), then submits the form.
 *
 * Works with both regular forms and HTMX: after confirmation, removes
 * the confirmation class and re-triggers the click.
 *
 * Replaces inline onsubmit="return confirm(...{{ name }}...)" which is
 * vulnerable to XSS despite Jinja autoescape (HTML-escape ≠ JS-string-escape).
 */
(function () {
    "use strict";

    document.body.addEventListener("click", function (e) {
        const target = e.target;

        // Find the confirmation trigger
        const trigger = target.matches(".js-confirm-delete")
            ? target
            : target.closest(".js-confirm-delete");

        if (!trigger || trigger.hasAttribute("data-confirmed")) {
            return;
        }

        e.preventDefault();
        e.stopPropagation();

        const confirmMsg = trigger.getAttribute("data-confirm");
        const itemName = trigger.getAttribute("data-name");

        // Build message safely via DOM, not string concatenation
        const wrapper = document.createElement("div");
        if (confirmMsg) {
            wrapper.textContent = confirmMsg;
        }
        if (itemName) {
            if (wrapper.hasChildNodes()) {
                wrapper.appendChild(document.createTextNode(" "));
            }
            const nameSpan = document.createElement("span");
            nameSpan.textContent = itemName;
            nameSpan.style.fontWeight = "bold";
            wrapper.appendChild(nameSpan);
            wrapper.appendChild(document.createTextNode("?"));
        }

        const message = wrapper.textContent || "Вы уверены?";

        if (window.confirm(message)) {
            // Mark as confirmed and re-trigger
            trigger.setAttribute("data-confirmed", "true");
            trigger.click();
        }
    }, false);
})();
