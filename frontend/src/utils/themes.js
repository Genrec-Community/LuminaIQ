// Theme palettes. Applying a theme writes CSS variables on <html>; src/themes.css
// maps the app's colours to them. Dark themes also feed the existing dark-mode
// variables (--dm-*) so every dark-mode style follows the theme.
//
// Light palette keys:  bg (page), alt (sidebars / soft panels), surface (cards),
//                      border, text, muted, accent
// Dark palette keys:   bg, sidebar, surface, hover, elevated, text, secondary,
//                      muted, accent

export const THEMES = {
    latte: {
        name: 'Lumina Paper', mode: 'light', blurb: 'Warm paper, forest ink, a lime highlighter',
        swatch: ['#FDF6F0', '#E6D5CC', '#1E5C42', '#163628'],
        // built-in: no overrides
    },
    espresso: {
        name: 'Forest Night', mode: 'dark', blurb: 'Deep forest with a lime glow',
        swatch: ['#0f1d16', '#182c21', '#D3EE6A', '#f4eee2'],
    },
    orchid: {
        name: 'Midnight Orchid', mode: 'dark', blurb: 'Velvet violet for late-night focus',
        swatch: ['#140f1f', '#221a33', '#b48cff', '#efe9ff'],
        palette: { bg: '#140f1f', sidebar: '#1a1428', surface: '#221a33', hover: '#2c2242', elevated: '#281f3b', text: '#efe9ff', secondary: '#b3a6d6', muted: '#7b6f9e', accent: '#b48cff' },
    },
    phosphor: {
        name: 'Phosphor Grid', mode: 'dark', blurb: 'Glowing green on black, terminal energy',
        swatch: ['#050a06', '#0c1a0f', '#39ff88', '#c9ffd9'],
        palette: { bg: '#050a06', sidebar: '#08110a', surface: '#0c1a0f', hover: '#12261a', elevated: '#0f2014', text: '#c9ffd9', secondary: '#6fdc95', muted: '#3f7a52', accent: '#39ff88' },
        font: 'mono',
    },
    ember: {
        name: 'Ember Noir', mode: 'dark', blurb: 'Charcoal with a firelit edge',
        swatch: ['#160e0c', '#261813', '#ff7a45', '#fbe9e2'],
        palette: { bg: '#160e0c', sidebar: '#1d1310', surface: '#261813', hover: '#331f18', elevated: '#2d1c16', text: '#fbe9e2', secondary: '#d9a593', muted: '#8a5c4d', accent: '#ff7a45' },
    },
    abyss: {
        name: 'Abyssal Tide', mode: 'dark', blurb: 'Deep-sea navy with bioluminescent teal',
        swatch: ['#08111a', '#11202e', '#2dd4bf', '#e2f1ff'],
        palette: { bg: '#08111a', sidebar: '#0c1722', surface: '#11202e', hover: '#172b3d', elevated: '#142636', text: '#e2f1ff', secondary: '#8fb3cf', muted: '#557590', accent: '#2dd4bf' },
    },
    glacier: {
        name: 'Glacier Mist', mode: 'light', blurb: 'Crisp icy blues, clear-headed calm',
        swatch: ['#f2f7fb', '#d3e3ef', '#3b8fd6', '#1f3447'],
        palette: { bg: '#f2f7fb', alt: '#e8f1f8', surface: '#ffffff', border: '#d3e3ef', text: '#1f3447', muted: '#5b7489', accent: '#3b8fd6' },
    },
    sakura: {
        name: 'Sakura Bloom', mode: 'light', blurb: 'Blush petals and soft rose',
        swatch: ['#fff5f7', '#f5d3dc', '#e46a91', '#4a2a35'],
        palette: { bg: '#fff5f7', alt: '#ffeef2', surface: '#ffffff', border: '#f5d3dc', text: '#4a2a35', muted: '#8f5f6f', accent: '#e46a91' },
    },
    grove: {
        name: 'Emerald Grove', mode: 'light', blurb: 'Fresh leaves and quiet forest air',
        swatch: ['#f3f8f3', '#cfe3d0', '#2f9e5b', '#1f3a28'],
        palette: { bg: '#f3f8f3', alt: '#eaf3ea', surface: '#ffffff', border: '#cfe3d0', text: '#1f3a28', muted: '#557a60', accent: '#2f9e5b' },
    },
};

export const FONT_STYLES = {
    default: { name: 'Lumina', sample: 'Aa', stack: '"Atkinson Hyperlegible Next Variable", "Atkinson Hyperlegible Next", "Plus Jakarta Sans Variable", "Plus Jakarta Sans", ui-sans-serif, system-ui, sans-serif' },
    rounded: { name: 'Rounded', sample: 'Aa', stack: '"Outfit Variable", "Outfit", "Plus Jakarta Sans Variable", "Plus Jakarta Sans", ui-sans-serif, system-ui, sans-serif' },
    clean: { name: 'Clean', sample: 'Aa', stack: '"Plus Jakarta Sans Variable", "Plus Jakarta Sans", ui-sans-serif, system-ui, sans-serif' },
    serif: { name: 'Bookish', sample: 'Aa', stack: 'Georgia, "Iowan Old Style", "Times New Roman", serif' },
    mono: { name: 'Coder', sample: 'Aa', stack: 'ui-monospace, "JetBrains Mono", "SFMono-Regular", Menlo, Consolas, monospace' },
};

export const ACCENT_PRESETS = ['#1E5C42', '#e46a91', '#b48cff', '#3b8fd6', '#2dd4bf', '#2f9e5b', '#39ff88', '#ff7a45', '#f5b301'];

export const THEME_CACHE_KEY = 'lumina_theme_vars';

/** Effective theme id: classic latte/espresso follow the dark-mode switch. */
export const resolveThemeId = (settings) => {
    const id = settings?.theme;
    if (!id || id === 'latte' || id === 'espresso' || !THEMES[id]) {
        return settings?.darkMode ? 'espresso' : 'latte';
    }
    return id;
};

/** CSS variables + attributes for a theme (pure, so index.html can replay it). */
export const buildThemeState = (settings) => {
    const id = resolveThemeId(settings);
    const theme = THEMES[id];
    const vars = {};
    const p = theme.palette;
    if (p && theme.mode === 'dark') {
        Object.assign(vars, {
            '--dm-bg': p.bg, '--dm-sidebar': p.sidebar, '--dm-surface': p.surface,
            '--dm-surface-hover': p.hover, '--dm-surface-elevated': p.elevated,
            '--dm-text-primary': p.text, '--dm-text-secondary': p.secondary, '--dm-text-muted': p.muted,
            '--dm-accent': p.accent, '--dm-accent-hover': p.accent,
            '--dm-accent-bg': `color-mix(in srgb, ${p.accent} 18%, transparent)`,
            '--th-accent': p.accent,
        });
    } else if (p) {
        Object.assign(vars, {
            '--th-bg': p.bg, '--th-alt': p.alt, '--th-surface': p.surface, '--th-border': p.border,
            '--th-text': p.text, '--th-muted': p.muted, '--th-accent': p.accent,
        });
    }
    const accent = /^#[0-9a-f]{6}$/i.test(settings?.customAccent || '') ? settings.customAccent : null;
    if (accent) {
        vars['--th-accent'] = accent;
        if (theme.mode === 'dark') {
            vars['--dm-accent'] = accent;
            vars['--dm-accent-hover'] = accent;
            vars['--dm-accent-bg'] = `color-mix(in srgb, ${accent} 18%, transparent)`;
        }
    }
    const fontKey = settings?.fontStyle && settings.fontStyle !== 'auto'
        ? settings.fontStyle
        : (theme.font || 'default');
    vars['--app-font'] = (FONT_STYLES[fontKey] || FONT_STYLES.default).stack;
    return {
        id,
        dark: theme.mode === 'dark',
        attrs: {
            'data-theme': p ? id : null,           // palette rules only for non-classic themes
            'data-theme-mode': theme.mode,
            'data-accent': accent || (p ? 'theme' : null), // accent rules when an accent is themed/custom
            'data-font': fontKey !== 'default' ? fontKey : null, // a picked font also replaces the display face
        },
        vars,
    };
};

/** Apply to <html> and cache for the no-flash script in index.html. */
export const applyThemeState = (state) => {
    const el = document.documentElement;
    el.classList.toggle('dark', state.dark);
    for (const [k, v] of Object.entries(state.attrs)) {
        if (v == null) el.removeAttribute(k); else el.setAttribute(k, v);
    }
    // Clear variables from a previous theme, then set the new ones
    for (const name of Array.from(el.style)) {
        if (name.startsWith('--dm-') || name.startsWith('--th-') || name === '--app-font') el.style.removeProperty(name);
    }
    for (const [k, v] of Object.entries(state.vars)) el.style.setProperty(k, v);
    try {
        localStorage.setItem(THEME_CACHE_KEY, JSON.stringify(state));
        localStorage.setItem('lumina_dark_mode', state.dark ? '1' : '0');
    } catch { /* ignore */ }
};
