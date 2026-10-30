// True inside the Android app (Capacitor). Google Play's payments policy means
// plans can't be sold inside the app, so purchase buttons are hidden there.
export const isNativeApp = () => {
    try {
        return Boolean(window.Capacitor?.isNativePlatform?.());
    } catch {
        return false;
    }
};

const PREVIEW_KEY = 'lumina_app_preview';

/**
 * True when the phone app interface is used: always inside the Android app,
 * and in a browser after opening any page with ?app=1 (?app=0 turns it off),
 * so the app can be tried and tested on the web.
 */
export const isAppShell = () => {
    if (isNativeApp()) return true;
    try {
        const flag = new URLSearchParams(window.location.search).get('app');
        if (flag === '1') localStorage.setItem(PREVIEW_KEY, '1');
        if (flag === '0') localStorage.removeItem(PREVIEW_KEY);
        return localStorage.getItem(PREVIEW_KEY) === '1';
    } catch {
        return false;
    }
};
