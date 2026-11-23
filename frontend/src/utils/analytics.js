// Product analytics: a few named events, first-touch attribution and a browser id, sent
// to our own API (/events/*). No third-party trackers, no personal details in events.
// Every call here is fire-and-forget: analytics must never break the app.
import { API_URL } from '../api';
import { isAppShell } from './platform';

const FIRST_TOUCH_KEY = 'lumina_first_touch';   // also written by the marketing site (website/)
const ANON_KEY = 'lumina_anon_id';
const SESSION_KEY = 'lumina_session_id';
const UTM = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term'];

const store = {
    get: (s, k) => { try { return s.getItem(k); } catch { return null; } },
    set: (s, k, v) => { try { s.setItem(k, v); } catch { /* private mode: fine */ } },
};

const rid = () => (crypto?.randomUUID?.() || `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`);

export const anonId = () => {
    let id = store.get(localStorage, ANON_KEY);
    if (!id) { id = rid(); store.set(localStorage, ANON_KEY, id); }
    return id;
};

const sessionId = () => {
    let id = store.get(sessionStorage, SESSION_KEY);
    if (!id) { id = rid(); store.set(sessionStorage, SESSION_KEY, id); }
    return id;
};

export const platform = () => (isAppShell() ? 'android' : 'web');

/** Remember how this browser first arrived (UTM tags, referrer site, landing page). Kept once. */
export const captureFirstTouch = () => {
    try {
        const params = new URLSearchParams(window.location.search);
        const existing = store.get(localStorage, FIRST_TOUCH_KEY);
        const utm = Object.fromEntries(UTM.map((k) => [k, params.get(k)]).filter(([, v]) => v));
        const ref = params.get('ref') || params.get('referral');
        // A later visit with campaign tags still fills in a first touch that had none
        if (existing) {
            const prev = JSON.parse(existing);
            if (!prev.utm_source && utm.utm_source) store.set(localStorage, FIRST_TOUCH_KEY, JSON.stringify({ ...prev, ...utm }));
            return;
        }
        let referrer = null;
        try {
            const r = document.referrer && new URL(document.referrer);
            if (r && r.hostname !== window.location.hostname) referrer = `${r.protocol}//${r.hostname}`;
        } catch { /* bad referrer */ }
        store.set(localStorage, FIRST_TOUCH_KEY, JSON.stringify({
            ...utm, referrer, referral_code: ref || null,
            landing_path: window.location.pathname, first_seen_at: new Date().toISOString(),
        }));
    } catch { /* never block */ }
};

const authHeader = () => {
    const token = store.get(localStorage, 'token');
    return token ? { Authorization: `Bearer ${token}` } : {};
};

let queue = [];
let timer = null;

const flush = () => {
    clearTimeout(timer);
    timer = null;
    if (!queue.length) return;
    const events = queue.splice(0, 25);
    fetch(`${API_URL}/events/track`, {
        method: 'POST', keepalive: true,
        headers: { 'Content-Type': 'application/json', ...authHeader() },
        body: JSON.stringify({ events, anon_id: anonId(), session_id: sessionId(), platform: platform() }),
    }).catch(() => {});
    if (queue.length) flush();
};

/** Record a product event (names are listed in backend services/product_analytics.py). */
export const track = (name, props = {}, projectId = null) => {
    try {
        queue.push({ name, props, project_id: projectId, path: window.location.pathname });
        if (!timer) timer = setTimeout(flush, 2000);
    } catch { /* never block */ }
};

if (typeof window !== 'undefined') {
    window.addEventListener('pagehide', flush);
    document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'hidden') flush(); });
}

/** Page paths without ids, so /project/123 and /project/456 count as one page. */
export const pagePath = (pathname) => pathname
    .replace(/\/[0-9a-f]{8}-[0-9a-f-]{27,}/gi, '/:id')
    .replace(/\/join\/[^/]+/, '/join/:code');

/** Send the first touch once per signed-in user (the server keeps only the first anyway). */
export const sendAttribution = (userId) => {
    if (!userId) return;
    const sentKey = `lumina_attr_sent_${userId}`;
    if (store.get(localStorage, sentKey)) return;
    let first = {};
    try { first = JSON.parse(store.get(localStorage, FIRST_TOUCH_KEY) || '{}'); } catch { /* none */ }
    const invite = window.location.pathname.match(/^\/join\/([^/]+)/)?.[1]
        || new URLSearchParams(window.location.search).get('next')?.match(/^\/join\/([^/?]+)/)?.[1];
    fetch(`${API_URL}/events/attribution`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeader() },
        body: JSON.stringify({ ...first, invite_code: invite || first.invite_code || null,
                               anon_id: anonId(), platform: platform() }),
    }).then((r) => { if (r.ok) store.set(localStorage, sentKey, '1'); }).catch(() => {});
};
