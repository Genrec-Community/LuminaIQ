// Android app (Capacitor) integration. Everything here is a no-op on the web.
import { isNativeApp } from './platform';

export const NATIVE_AUTH_REDIRECT = 'fun.luminaiq.app://login-callback';

/**
 * Google blocks sign-in inside embedded web views, so in the app Google sign-in
 * opens in the system browser (Custom Tab) and comes back through the
 * fun.luminaiq.app://login-callback deep link (AndroidManifest.xml).
 */
export async function nativeGoogleSignIn(supabase) {
    const { Browser } = await import('@capacitor/browser');
    const { data, error } = await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: { redirectTo: NATIVE_AUTH_REDIRECT, skipBrowserRedirect: true },
    });
    if (error) throw error;
    await Browser.open({ url: data.url, presentationStyle: 'popover' });
}

/** Wire up deep links (sign-in callback) and the Android back button. */
export async function initNative(supabase) {
    if (!isNativeApp()) return;
    const { App } = await import('@capacitor/app');
    const { Browser } = await import('@capacitor/browser');

    App.addListener('appUrlOpen', async ({ url }) => {
        if (!url?.startsWith(NATIVE_AUTH_REDIRECT)) return;
        try { await Browser.close(); } catch { /* already closed */ }
        const parsed = new URL(url.replace('#', '?'));
        const code = parsed.searchParams.get('code');
        const access_token = parsed.searchParams.get('access_token');
        const refresh_token = parsed.searchParams.get('refresh_token');
        // AuthContext's onAuthStateChange listener exchanges the session for the app token
        if (code) await supabase.auth.exchangeCodeForSession(code);
        else if (access_token && refresh_token) await supabase.auth.setSession({ access_token, refresh_token });
    });

    App.addListener('backButton', ({ canGoBack }) => {
        if (canGoBack && window.location.pathname !== '/dashboard') window.history.back();
        else App.exitApp();
    });
}
