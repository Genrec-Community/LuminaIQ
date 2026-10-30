'use client';
// Next.js App Router adapter. Render <Engine setup={…} /> once, as the LAST child of <body> in the
// root layout (React runs child effects first, so page components register before the engine boots).
// `setup` (global motion: transition, loader, background, driver) must come from a client module.
// Internal links (plain <a> or next/link) get the leave → push → enter transition automatically.
// Opt a link out with data-no-transition. Back/forward re-inits the page without the curtain.
// `pages` lists the paths this Next app owns. Links to any other same-origin path (another app
// served next to this one) still get the leave animation, then a full page load.
import { useEffect, useRef } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { boot, cleanup, enter, leave, onPage, resume, type PageFn } from './index';

const slash = (p: string) => (p.endsWith('/') ? p : p + '/');

export function Engine({ setup, pages }: { setup?: () => void; pages?: string[] }) {
  const router = useRouter();
  const pathname = usePathname();
  const mode = useRef<'idle' | 'push' | 'pop' | 'away'>('idle');
  const first = useRef(true);
  const fallback = useRef<number>(0);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { boot(setup); }, []);

  useEffect(() => {
    const own = pages && new Set(pages.map(slash));
    const onClick = async (e: MouseEvent) => {
      if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      const a = (e.target as Element).closest('a');
      if (!a || (a.target && a.target !== '_self') || a.hasAttribute('download') || a.hasAttribute('data-no-transition')) return;
      const url = new URL(a.href, location.href);
      if (url.origin !== location.origin || url.pathname === location.pathname) return; // external, hash or same page
      e.preventDefault(); // next/link sees defaultPrevented and stands down
      if (mode.current !== 'idle') return;
      const href = url.pathname + url.search + url.hash;
      if (own && !own.has(slash(url.pathname))) {
        // Not a page of this app: cover the screen, then load it for real. The page stays intact,
        // so a back/forward cache restore can lift the curtain again (pageshow below).
        mode.current = 'away';
        await leave();
        location.assign(href);
        return;
      }
      mode.current = 'push';
      router.prefetch(href);
      await leave();
      cleanup();
      router.push(href, { scroll: false });
      // If the route never arrives, never leave the visitor under the curtain.
      fallback.current = window.setTimeout(() => location.assign(href), 6000);
    };
    const onPop = () => { mode.current = 'pop'; cleanup(); };
    const onShow = (e: PageTransitionEvent) => {
      if (!e.persisted || mode.current !== 'away') return;
      mode.current = 'idle';
      resume();
    };
    document.addEventListener('click', onClick, true);
    addEventListener('popstate', onPop);
    addEventListener('pageshow', onShow);
    return () => {
      document.removeEventListener('click', onClick, true);
      removeEventListener('popstate', onPop);
      removeEventListener('pageshow', onShow);
    };
  }, [router, pages]);

  useEffect(() => {
    if (first.current) { first.current = false; return; }
    clearTimeout(fallback.current);
    const pop = mode.current === 'pop';
    mode.current = 'idle';
    enter({ transition: !pop, scrollTop: !pop });
  }, [pathname]);

  return null;
}

/** Component-level page code: runs when the page is ready (after the loader), reverted on leave. */
export function usePage(fn: PageFn) {
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => onPage(fn), []);
}
