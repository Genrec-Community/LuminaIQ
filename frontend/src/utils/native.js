// Android app (Capacitor) integration. Everything here is a no-op on the web.
import { isNativeApp } from './platform';

export const NATIVE_AUTH_REDIRECT = 'fun.luminaiq.app://login-callback';

// Web OAuth client ID (Google Cloud → Credentials → "Web application"), the same
// one Supabase's Google provider uses. Not a secret. Set VITE_GOOGLE_WEB_CLIENT_ID
// (GitHub variable GOOGLE_WEB_CLIENT_ID) to use a different one.
const GOOGLE_WEB_CLIENT_ID = import.meta.env.VITE_GOOGLE_WEB_CLIENT_ID
    || '350306574610-l8caa4eeqqiocisiptr4raoe8r5ne165.apps.googleusercontent.com';

let socialLoginReady = null;
const sha256Hex = async (text) => {
    const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
    return Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, '0')).join('');
};

/**
 * Google sign-in inside the app. With a web client ID configured, Android's own
 * account picker is used (Credential Manager): no browser, one tap, and the
 * Google ID token is handed to Supabase. Without it, or if the picker isn't
 * available, it falls back to the system browser (Custom Tab) and comes back
 * through the fun.luminaiq.app://login-callback deep link (AndroidManifest.xml).
 * Throws an error with code 'cancelled' when the user closes the picker.
 */
const timeoutAfter = (ms, message) => new Promise((_, reject) => setTimeout(() => reject(new Error(message)), ms));

export async function nativeGoogleSignIn(supabase) {
    if (GOOGLE_WEB_CLIENT_ID) {
        try {
            const { SocialLogin } = await import('@capgo/capacitor-social-login');
            socialLoginReady = socialLoginReady || SocialLogin.initialize({ google: { webClientId: GOOGLE_WEB_CLIENT_ID } });
            await Promise.race([socialLoginReady, timeoutAfter(10000, 'Google sign-in did not start')]);
            // Supabase checks the token's nonce against the hash of the raw value
            const rawNonce = crypto.randomUUID();
            const res = await SocialLogin.login({
                provider: 'google',
                options: { scopes: ['email', 'profile'], nonce: await sha256Hex(rawNonce) },
            });
            const idToken = res?.result?.idToken;
            if (!idToken) throw new Error('Google did not return a sign-in token');
            const { error } = await Promise.race([
                supabase.auth.signInWithIdToken({ provider: 'google', token: idToken, nonce: rawNonce }),
                timeoutAfter(20000, 'Sign-in took too long'),
            ]);
            if (error) throw error;
            return; // AuthContext's SIGNED_IN listener finishes the sign-in
        } catch (e) {
            const msg = String(e?.message || e || '').toLowerCase();
            if (msg.includes('cancel')) throw Object.assign(new Error('Sign-in cancelled'), { code: 'cancelled' });
            console.warn('Native Google sign-in unavailable, using the browser instead:', e);
            socialLoginReady = null;
        }
    }
    const { Browser } = await import('@capacitor/browser');
    const { data, error } = await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: { redirectTo: NATIVE_AUTH_REDIRECT, skipBrowserRedirect: true, queryParams: { prompt: 'select_account' } },
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
        const failure = parsed.searchParams.get('error_description') || parsed.searchParams.get('error');
        if (failure) {
            window.dispatchEvent(new CustomEvent('lumina-auth-error', { detail: failure.replace(/\+/g, ' ') }));
            return;
        }
        const code = parsed.searchParams.get('code');
        const access_token = parsed.searchParams.get('access_token');
        const refresh_token = parsed.searchParams.get('refresh_token');
        // AuthContext's onAuthStateChange listener exchanges the session for the app token
        if (code) await supabase.auth.exchangeCodeForSession(code);
        else if (access_token && refresh_token) await supabase.auth.setSession({ access_token, refresh_token });
    });

    // Back: close an open sheet first, then step back; the main tabs return to
    // Home, and Home (or the sign-in screens) leaves the app
    App.addListener('backButton', ({ canGoBack }) => {
        const handled = !window.dispatchEvent(new CustomEvent('lumina-back', { cancelable: true }));
        if (handled) return;
        const path = window.location.pathname;
        if (['/app/home', '/welcome', '/signin', '/'].includes(path)) { App.exitApp(); return; }
        if (/^\/app\/(feed|library|me)$/.test(path)) {
            window.dispatchEvent(new CustomEvent('lumina-navigate', { detail: '/app/home' }));
            return;
        }
        if (canGoBack) window.history.back();
        else window.dispatchEvent(new CustomEvent('lumina-navigate', { detail: '/app/home' }));
    });
}
