// True inside the Android app (Capacitor). Google Play's payments policy means
// plans can't be sold inside the app, so purchase buttons are hidden there.
export const isNativeApp = () => {
    try {
        return Boolean(window.Capacitor?.isNativePlatform?.());
    } catch {
        return false;
    }
};
