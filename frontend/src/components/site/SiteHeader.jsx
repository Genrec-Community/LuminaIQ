import { useEffect, useState } from 'react';
import Logo from '../brand/Logo';

// The marketing site's header (frontend/website/src/components/Header.tsx), for the app's
// public pages, so moving from the site into Log in or Plans never changes the frame.
// Site pages are separate documents, so these are plain links.
const NAV = [
    { href: '/features/', label: 'Features' },
    { href: '/how-it-works/', label: 'How it works' },
    { href: '/pricing/', label: 'Pricing' },
    { href: '/about/', label: 'About' },
];

export default function SiteHeader({ cta = true }) {
    const [open, setOpen] = useState(false);
    useEffect(() => {
        document.documentElement.classList.toggle('menu-open', open);
        if (!open) return undefined;
        const onKey = (e) => { if (e.key === 'Escape') setOpen(false); };
        document.addEventListener('keydown', onKey);
        return () => document.removeEventListener('keydown', onKey);
    }, [open]);

    return (
        <header className="site-header">
            <div className="site-wrap site-header__inner">
                <a href="/" className="site-header__home" title="Home"><Logo /></a>
                <nav className="site-nav" aria-label="Main">
                    <ul>{NAV.map((n) => <li key={n.href}><a href={n.href} className="mark">{n.label}</a></li>)}</ul>
                </nav>
                <div className="site-header__actions">
                    <a href="/login" className="mark site-header__login">Log in</a>
                    {cta && <a href="/login?signup=1" className="btn btn--dark btn--sm"><span>Start free</span></a>}
                    <button type="button" className="menu-button" aria-expanded={open} aria-controls="site-menu" onClick={() => setOpen((v) => !v)}>
                        <span className="menu-button__lines" aria-hidden="true" />
                        <span>{open ? 'Close' : 'Menu'}</span>
                    </button>
                </div>
            </div>
            <div id="site-menu" className="menu" hidden={!open}>
                <nav aria-label="Mobile">
                    <ul>
                        <li><a href="/">Home</a></li>
                        {NAV.map((n) => <li key={n.href}><a href={n.href}>{n.label}</a></li>)}
                    </ul>
                </nav>
                <div className="menu__foot">
                    <a href="/login?signup=1" className="btn btn--dark"><span>Start free</span></a>
                    <a href="/login" className="btn btn--light"><span>Log in</span></a>
                </div>
            </div>
        </header>
    );
}
