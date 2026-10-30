import { useEffect, useLayoutEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import { boot, curtain, scrollTop, smoothScroll } from './engine';

// Pages that scroll the window get Lenis; the project workspace scrolls its own panes.
const SMOOTH = /^\/(dashboard|plans|settings|login|bookstore|privacy|terms|delete-account|institution|platform|join|reset-password)(\/|$)/;
const NAMES = {
    dashboard: 'Your books', project: 'Opening your book', plans: 'Plans', settings: 'Settings',
    login: 'Welcome back', bookstore: 'Book store', institution: 'Your school', platform: 'Platform',
};

/** Global feel layer: the curtain, the cursor follower, smooth scroll and reveals. */
export default function Feel() {
    const { pathname } = useLocation();
    const first = useRef(true);
    const lastSection = useRef(pathname.split('/')[1]);
    const clicked = useRef('');

    useEffect(() => {
        boot();
        // Remember what was clicked so the curtain can name the destination
        const onClick = (e) => {
            const el = e.target instanceof Element ? e.target.closest('a, button') : null;
            clicked.current = (el?.dataset.title || el?.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 40);
        };
        document.addEventListener('click', onClick, true);
        return () => document.removeEventListener('click', onClick, true);
    }, []);

    // Before paint: cover with the curtain when moving to another part of the app
    useLayoutEffect(() => {
        const section = pathname.split('/')[1];
        if (first.current) { first.current = false; return; }
        if (section !== lastSection.current) {
            curtain(clicked.current && clicked.current.length > 2 ? clicked.current : NAMES[section] || 'Lumina IQ');
            scrollTop();
        }
        lastSection.current = section;
        clicked.current = '';
    }, [pathname]);

    useEffect(() => { smoothScroll(SMOOTH.test(pathname)); }, [pathname]);

    return (
        <>
            <div id="curtain" aria-hidden="true">
                <div className="curtain__panel">
                    <span className="curtain__band curtain__band--top" />
                    <span className="curtain__label" />
                    <span className="curtain__band curtain__band--bottom" />
                </div>
            </div>
            <div id="cursor" aria-hidden="true"><span data-cursor-label /></div>
        </>
    );
}
