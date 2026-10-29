import type { Metadata } from 'next';
import Link from 'next/link';
import { NotFoundCard } from '@/components/NotFoundCard';

export const metadata: Metadata = {
  title: 'Page not found',
  description: 'This page is not in your notes. Head back to the LuminaIQ home page or browse the study tools.',
  robots: { index: false },
};

export default function NotFound() {
  return (
    <section className="lost" aria-labelledby="lost-title">
      <div className="wrap lost__grid">
        <div className="lost__copy">
          <p className="lost__code">404</p>
          <h1 id="lost-title" className="display h-xl rise">
            This one is <em>not in your notes.</em>
          </h1>
          <p className="lede">The page may have moved, or the link was mistyped. Flip the card, then pick up where you were.</p>
          <div className="actions">
            <Link href="/" className="btn btn--dark">
              <span>Back to home</span>
            </Link>
            <Link href="/features/" className="btn btn--light">
              <span>Browse the tools</span>
            </Link>
          </div>
        </div>
        <NotFoundCard />
      </div>
    </section>
  );
}
