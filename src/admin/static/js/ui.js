// ============================================================
// Betting Bot Admin v2 — UI state (theme, density, accent)
// Uses Alpine.js for reactive state without SPA
// CSP-compatible: uses Alpine.store for global state
// ============================================================

document.addEventListener('alpine:init', () => {
  // Default values
  const defaults = {
    dark: false,
    density: 'regular',
    accent: '#e6403a',
    rail: false
  };

  // Available accent colors
  const accents = ['#e6403a', '#36a9e1', '#29b473', '#8e44ad', '#ff6b35'];

  // Load from localStorage
  const saved = localStorage.getItem('bbAdminUI');
  const initialState = saved ? { ...defaults, ...JSON.parse(saved) } : { ...defaults };

  // Global store (source of truth, CSP-compatible)
  Alpine.store('ui', {
    dark: initialState.dark,
    density: initialState.density,
    accent: initialState.accent,
    rail: initialState.rail,

    // Computed
    get densityLabel() {
      const labels = { compact: 'Компакт', regular: 'Обычная', comfortable: 'Комфорт' };
      return labels[this.density] || 'Обычная';
    },

    // Actions
    toggleDark() {
      this.dark = !this.dark;
      saveState();
      applyState();
    },
    setDensity(val) {
      this.density = val;
      saveState();
      applyState();
    },
    setAccent(val) {
      this.accent = val;
      saveState();
      applyState();
    },
    toggleRail() {
      this.rail = !this.rail;
      saveState();
      applyState();
    }
  });

  // Helper: save current store state to localStorage
  function saveState() {
    const store = Alpine.store('ui');
    localStorage.setItem('bbAdminUI', JSON.stringify({
      dark: store.dark,
      density: store.density,
      accent: store.accent,
      rail: store.rail
    }));
  }

  // Helper: apply store state to DOM
  function applyState() {
    const store = Alpine.store('ui');
    const root = document.documentElement;

    // Theme
    root.setAttribute('data-theme', store.dark ? 'dark' : 'light');

    // Density
    if (store.density === 'regular') {
      root.removeAttribute('data-density');
    } else {
      root.setAttribute('data-density', store.density);
    }

    // Accent color
    root.style.setProperty('--pv-accent', store.accent);
    root.style.setProperty('--pv-accent-2',
      'color-mix(in srgb, ' + store.accent + ' 82%, #000)');
    const softMix = store.dark
      ? 'color-mix(in srgb, ' + store.accent + ' 22%, #14141b)'
      : 'color-mix(in srgb, ' + store.accent + ' 12%, #fff)';
    root.style.setProperty('--pv-accent-soft', softMix);

    // Rail collapse
    const app = document.querySelector('.pv-app');
    if (app) {
      if (store.rail) {
        app.setAttribute('data-rail', 'collapsed');
      } else {
        app.removeAttribute('data-rail');
      }
    }
  }

  // Apply immediately on load
  applyState();

  // Component for UI controls (delegates to store)
  Alpine.data('uiState', () => ({
    accents: accents,
    get dark() { return Alpine.store('ui').dark; },
    get density() { return Alpine.store('ui').density; },
    get accent() { return Alpine.store('ui').accent; },
    get rail() { return Alpine.store('ui').rail; },
    get densityLabel() { return Alpine.store('ui').densityLabel; },

    // CSP-compatible computed properties (no inline expressions in templates)
    get themeIcon() { return this.dark ? 'light_mode' : 'dark_mode'; },
    get themeTitle() { return this.dark ? 'Светлая тема' : 'Тёмная тема'; },
    get isRailCollapsed() { return this.rail ? 'collapsed' : null; },

    // Accent swatch helpers (CSP-compatible: methods, not inline expressions)
    accentClass(acc) { return this.accent === acc ? 'active' : ''; },
    accentStyle(acc) { return 'background-color: ' + acc; },
    accentTitle(acc) { return 'Акцент ' + acc; },

    toggleDark() { Alpine.store('ui').toggleDark(); },
    setDensity() {
      // CSP-safe: called as @click="setDensity" (no args/()). Read intent from data-* on the element.
      // this.$el is provided by Alpine in directive handler context (TASK-093).
      const val = this.$el && this.$el.dataset ? this.$el.dataset.density : null;
      if (val) Alpine.store('ui').setDensity(val);
    },
    setAccent() {
      const val = this.$el && this.$el.dataset ? this.$el.dataset.accent : null;
      if (val) Alpine.store('ui').setAccent(val);
    },
    toggleRail() { Alpine.store('ui').toggleRail(); }
  }));
});

// ============================================================
// CSP-safe delegated UI handlers (TASK-084)
// Replaces ALL inline on*= handlers in admin templates.
// - data-href on <tr> (or other) → window.location (skips clicks on interactive children)
// - data-confirm on <button>/<form> → window.confirm before submit/click
// Coexists with confirm.js (which handles .js-confirm-delete + data-name for rich messages)
// ============================================================
(function () {
  "use strict";

  // Row / element navigation via data-href (clickable rows in lists)
  document.addEventListener("click", function (e) {
    const target = e.target;
    const navEl = target.closest("[data-href]");
    if (!navEl) return;

    // Ignore clicks inside links, buttons, form controls, or explicit action elements
    if (target.closest("a, button, input, select, textarea, label, .pv-btn, .js-confirm-delete, [data-no-nav]")) {
      return;
    }

    const href = navEl.getAttribute("data-href");
    if (href) {
      window.location.assign(href);
    }
  });

  // Confirm-before-action via data-confirm (general case for buttons and forms)
  function confirmBeforeAction(ev, el) {
    const msg = el.getAttribute("data-confirm");
    if (!msg) return true;

    if (el.hasAttribute("data-confirmed")) {
      el.removeAttribute("data-confirmed");
      return true;
    }

    if (!window.confirm(msg)) {
      ev.preventDefault();
      if (ev.stopImmediatePropagation) ev.stopImmediatePropagation();
      return false;
    }

    el.setAttribute("data-confirmed", "true");
    return true;
  }

  // Capture-phase click for buttons with data-confirm (before any other handlers)
  document.addEventListener(
    "click",
    function (e) {
      const trigger = e.target.closest("button[data-confirm], input[data-confirm][type='submit']");
      if (trigger) {
        confirmBeforeAction(e, trigger);
      }
    },
    true
  );

  // Submit handler for forms carrying data-confirm
  document.addEventListener(
    "submit",
    function (e) {
      const form = e.target.closest("form[data-confirm]");
      if (form) {
        confirmBeforeAction(e, form);
      }
    },
    true
  );
})();
