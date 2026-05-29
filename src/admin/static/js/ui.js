// ============================================================
// Betting Bot Admin v2 — UI state (theme, density, accent)
// Uses Alpine.js for reactive state without SPA
// ============================================================

document.addEventListener('alpine:init', () => {
  Alpine.data('uiState', () => {
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
    const state = saved ? { ...defaults, ...JSON.parse(saved) } : { ...defaults };

    // Apply state to DOM
    function apply() {
      const root = document.documentElement;

      // Theme
      root.setAttribute('data-theme', state.dark ? 'dark' : 'light');

      // Density
      if (state.density === 'regular') {
        root.removeAttribute('data-density');
      } else {
        root.setAttribute('data-density', state.density);
      }

      // Accent color
      root.style.setProperty('--pv-accent', state.accent);
      // Derive darker hover
      root.style.setProperty('--pv-accent-2',
        'color-mix(in srgb, ' + state.accent + ' 82%, #000)');
      // Derive soft tint
      const softMix = state.dark
        ? 'color-mix(in srgb, ' + state.accent + ' 22%, #14141b)'
        : 'color-mix(in srgb, ' + state.accent + ' 12%, #fff)';
      root.style.setProperty('--pv-accent-soft', softMix);

      // Rail collapse
      const app = document.querySelector('.pv-app');
      if (app) {
        if (state.rail) {
          app.setAttribute('data-rail', 'collapsed');
        } else {
          app.removeAttribute('data-rail');
        }
      }
    }

    // Save to localStorage
    function save() {
      localStorage.setItem('bbAdminUI', JSON.stringify(state));
    }

    // Apply immediately on load
    apply();

    return {
      // State
      dark: state.dark,
      density: state.density,
      accent: state.accent,
      rail: state.rail,
      accents: accents,

      // Computed
      get densityLabel() {
        const labels = { compact: 'Компакт', regular: 'Обычная', comfortable: 'Комфорт' };
        return labels[this.density] || 'Обычная';
      },

      // Actions
      toggleDark() {
        this.dark = !this.dark;
        state.dark = this.dark;
        save();
        apply();
      },
      setDensity(val) {
        this.density = val;
        state.density = val;
        save();
        apply();
      },
      setAccent(val) {
        this.accent = val;
        state.accent = val;
        save();
        apply();
      },
      toggleRail() {
        this.rail = !this.rail;
        state.rail = this.rail;
        save();
        apply();
      }
    };
  });
});
