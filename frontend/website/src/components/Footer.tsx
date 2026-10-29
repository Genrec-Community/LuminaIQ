import Link from 'next/link';
import { site } from '@/data/site';
import { Mark } from './Logo';

export function Footer() {
  const year = 2026;
  return (
    <footer className="finale">
      <div className="wrap">
        <div className="finale__head">
          <p className="finale__title display" data-split="lines">
            Read it today. <em>Still know it</em> in June.
          </p>
          <svg className="finale__curve" viewBox="0 0 600 100" aria-hidden="true">
            <path
              data-draw-scrub
              pathLength={1}
              d="M2 20 C 40 70 70 88 110 92 L 110 20 C 170 60 210 74 250 76 L 250 20 C 330 46 380 54 420 55 L 420 20 C 500 32 550 36 598 37"
            />
          </svg>
          <div className="finale__actions">
            <a href={site.appUrl} className="btn btn--accent">
              <span>Start free</span>
              <Arrow />
            </a>
            <Link href="/pricing/" className="btn btn--ghost">
              <span>Compare plans</span>
            </Link>
          </div>
        </div>

        <div className="finale__cols">
          <div className="finale__brand">
            <Mark className="finale__mark" />
            <p>
              Lumina IQ turns your own study material into practice, and tells you when to come back to it.
            </p>
          </div>
          <nav aria-label="Product">
            <h2 className="finale__h">Product</h2>
            <ul>
              <li><Link href="/features/">Features</Link></li>
              <li><Link href="/how-it-works/">How it works</Link></li>
              <li><Link href="/pricing/">Pricing</Link></li>
            </ul>
          </nav>
          <nav aria-label="Company">
            <h2 className="finale__h">Company</h2>
            <ul>
              <li><Link href="/about/">About</Link></li>
              <li><a href={site.maker.url} rel="noopener" target="_blank">{site.maker.name}</a></li>
              <li><a href={`mailto:${site.email}`}>Contact</a></li>
            </ul>
          </nav>
          <nav aria-label="Get started">
            <h2 className="finale__h">Get started</h2>
            <ul>
              <li><a href={site.appUrl}>Create an account</a></li>
              <li><a href={site.loginUrl}>Log in</a></li>
              <li><a href={`https://www.youtube.com/watch?v=${site.youtubeId}`} rel="noopener" target="_blank">Watch the walkthrough</a></li>
            </ul>
          </nav>
        </div>

        <div className="finale__base">
          <p>© {year} Lumina IQ. Built by {site.maker.name}.</p>
          <p>Screens from the Lumina IQ app. Set in Newsreader and Atkinson Hyperlegible Next.</p>
        </div>
      </div>
    </footer>
  );
}

export function Arrow() {
  return (
    <svg className="arrow" viewBox="0 0 16 16" aria-hidden="true" focusable="false">
      <path d="M2 8h11M9 4l4 4-4 4" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
