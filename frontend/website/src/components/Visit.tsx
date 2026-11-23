'use client';
import { useEffect } from 'react';

// Same key and shape as the app's utils/analytics.js: the app sends it to the backend once the
// visitor signs up, so we know which channel (search, social, a campaign) brought them.
const FIRST_TOUCH_KEY = 'lumina_first_touch';
const ANON_KEY = 'lumina_anon_id';
const UTM = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term'];
const TEST_API_URL = 'https://luminaiq-api-test.graygrass-e72a94bd.centralindia.azurecontainerapps.io/api/v1';

export function Visit() {
  useEffect(() => {
    try {
      const params = new URLSearchParams(location.search);
      const utm = Object.fromEntries(UTM.map((k) => [k, params.get(k)]).filter(([, v]) => v));
      const existing = localStorage.getItem(FIRST_TOUCH_KEY);
      if (!existing) {
        let referrer: string | null = null;
        try {
          const r = document.referrer ? new URL(document.referrer) : null;
          if (r && r.hostname !== location.hostname) referrer = `${r.protocol}//${r.hostname}`;
        } catch { /* bad referrer */ }
        localStorage.setItem(FIRST_TOUCH_KEY, JSON.stringify({
          ...utm, referrer, referral_code: params.get('ref') || params.get('referral'),
          landing_path: location.pathname, first_seen_at: new Date().toISOString(),
        }));
      } else if (utm.utm_source && !JSON.parse(existing).utm_source) {
        localStorage.setItem(FIRST_TOUCH_KEY, JSON.stringify({ ...JSON.parse(existing), ...utm }));
      }
      let anon = localStorage.getItem(ANON_KEY);
      if (!anon) {
        anon = crypto?.randomUUID?.() || `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
        localStorage.setItem(ANON_KEY, anon);
      }
      const api = location.hostname === 'test.luminaiq.fun' ? TEST_API_URL : process.env.NEXT_PUBLIC_API_URL;
      if (!api) return;
      fetch(`${api}/events/track`, {
        method: 'POST', keepalive: true, headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ anon_id: anon, platform: 'web',
          events: [{ name: 'page_view', path: location.pathname, props: { page: location.pathname, site: 'marketing' } }] }),
      }).catch(() => {});
    } catch { /* never block the page */ }
  }, []);
  return null;
}
