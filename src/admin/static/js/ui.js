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
    setDensity(val) { Alpine.store('ui').setDensity(val); },
    setAccent(val) { Alpine.store('ui').setAccent(val); },
    toggleRail() { Alpine.store('ui').toggleRail(); }
  }));
});
