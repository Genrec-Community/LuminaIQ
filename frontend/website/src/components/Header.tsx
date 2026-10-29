'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';
import { startScroll, stopScroll } from '@/engine';
import { site } from '@/data/site';
import { Logo } from './Logo';

export function Header() {
  const pathname = usePathname();
  // The menu belongs to the page it was opened on, so it closes by itself when the route changes.
  const [openAt, setOpenAt] = useState<string | null>(null);
  const open = openAt === pathname;
  const setOpen = (v: boolean | ((o: boolean) => boolean)) => {
    const next = typeof v === 'function' ? v(open) : v;
    setOpenAt(next ? pathname : null);
  };
  const button = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLDivElement>(null);
  const isCurrent = (href: string) => pathname === href || pathname === href.replace(/\/$/, '');

  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle('menu-open', open);
    if (!open) {
      startScroll();
      return;
    }
    stopScroll();
    const panel = menu.current;
    const inPanel = panel ? [...panel.querySelectorAll<HTMLElement>('a, button')] : [];
    inPanel[0]?.focus();
    // The trap includes the Close button, so keyboard users can always leave.
    const links = button.current ? [button.current, ...inPanel] : inPanel;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setOpenAt(null);
        button.current?.focus();
      }
      if (e.key === 'Tab' && links.length) {
        const first = links[0];
        const last = links[links.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open]);

  return (
    <header className="site-header">
      <div className="wrap site-header__inner">
        <Link href="/" className="site-header__home" aria-label="Lumina IQ home">
          <Logo />
        </Link>
        <nav className="site-nav" aria-label="Main">
          <ul>
            {site.nav.map((item) => (
              <li key={item.href}>
                <Link href={item.href} className="mark" aria-current={isCurrent(item.href) ? 'page' : undefined}>
                  {item.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
        <div className="site-header__actions">
          <a href={site.loginUrl} className="mark site-header__login">
            Log in
          </a>
          <a href={site.appUrl} className="btn btn--dark btn--sm">
            <span>Start free</span>
          </a>
          <button
            ref={button}
            type="button"
            className="menu-button"
            aria-expanded={open}
            aria-controls="menu"
            onClick={() => setOpen((v) => !v)}
          >
            <span className="menu-button__lines" aria-hidden="true" />
            <span>{open ? 'Close' : 'Menu'}</span>
          </button>
        </div>
      </div>
      <div id="menu" className="menu" ref={menu} hidden={!open}>
        <nav aria-label="Mobile">
          <ul>
            <li>
              <Link href="/" aria-current={pathname === '/' ? 'page' : undefined}>
                Home
              </Link>
            </li>
            {site.nav.map((item) => (
              <li key={item.href}>
                <Link href={item.href} aria-current={isCurrent(item.href) ? 'page' : undefined}>
                  {item.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
        <div className="menu__foot">
          <a href={site.appUrl} className="btn btn--dark">
            <span>Start free</span>
          </a>
          <a href={site.loginUrl} className="btn btn--light">
            <span>Log in</span>
          </a>
        </div>
      </div>
    </header>
  );
}
