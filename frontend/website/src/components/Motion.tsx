'use client';
import { useEffect } from 'react';
import { Engine } from '@/engine/next';
import { setupMotion } from '@/motion/setup';
import { site } from '@/data/site';

// Same rule as the app (frontend/src/api.js): the test site always uses the test backend
const TEST_API_URL = 'https://luminaiq-api-test.graygrass-e72a94bd.centralindia.azurecontainerapps.io/api/v1';

export function Motion() {
  // Wake the app's backend (it can scale to zero) while the visitor reads, so sign-up and the
  // dashboard don't wait for a cold start. Fire and forget.
  useEffect(() => {
    const api = location.hostname === 'test.luminaiq.fun' ? TEST_API_URL : process.env.NEXT_PUBLIC_API_URL;
    if (!api) return;
    fetch(api.replace(/\/api\/v1\/?$/, '') + '/health', { mode: 'no-cors', cache: 'no-store' }).catch(() => {});
  }, []);
  return <Engine setup={setupMotion} pages={site.pages} />;
}
