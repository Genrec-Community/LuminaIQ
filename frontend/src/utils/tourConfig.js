// Shared react-joyride (v3) settings for every guided tour.
// v3 ignores the old v2 props (disableOverlayClose, showSkipButton, callback,
// styles...), so everything lives in `options` and events go to `onEvent`.
export const TOUR_OPTIONS = {
    // Only "Skip" or finishing the tour can end it
    overlayClickAction: false,   // clicking the dark overlay does nothing
    dismissKeyAction: false,     // ESC does nothing
    buttons: ['back', 'skip', 'primary'], // no ✕ close button
    blockTargetInteraction: true, // clicks on the highlighted element can't derail the tour
    // Steady tooltips: open each step directly (no beacon dot in between) and
    // never scroll the page or sidebar while moving between steps
    skipBeacon: true,
    skipScroll: true,
    showProgress: true,
    primaryColor: '#C8A288',
    textColor: '#4A3B32',
    overlayColor: 'rgba(42, 31, 24, 0.55)',
    spotlightRadius: 14,
    zIndex: 10000,
};
