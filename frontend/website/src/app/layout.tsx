import type { Metadata, Viewport } from 'next';
import { Footer } from '@/components/Footer';
import { Header } from '@/components/Header';
import { Motion } from '@/components/Motion';
import { plans, site } from '@/data/site';
import { display, text } from './fonts';
import '../engine/engine.css';
import './globals.css';

export const metadata: Metadata = {
  metadataBase: new URL(site.url),
  title: { default: `${site.name}: AI study companion for your own notes`, template: `%s | ${site.name}` },
  description: site.description,
  applicationName: site.name,
  alternates: { canonical: './' },
  keywords: ['AI study companion', 'AI quiz generator', 'flashcards from PDF', 'spaced repetition', 'chat with PDF', 'study notes', 'mind maps'],
  openGraph: { type: 'website', siteName: site.name, locale: 'en_US', images: [{ url: '/og.png', width: 1200, height: 630, alt: 'Lumina IQ: read it once, remember it for the exam' }] },
  twitter: { card: 'summary_large_image' },
  // Preview builds on Vercel stay out of search results; production is indexable.
  robots: process.env.VERCEL_ENV && process.env.VERCEL_ENV !== 'production' ? { index: false, follow: false } : { index: true, follow: true },
};

export const viewport: Viewport = {
  themeColor: '#FDF6F0',
};

// Runs before first paint: hidden-until-revealed styles only apply when JS and motion are on.
const flags = `document.documentElement.classList.add('js');if(!matchMedia('(prefers-reduced-motion: reduce)').matches)document.documentElement.classList.add('motion')`;

const jsonLd = {
  '@context': 'https://schema.org',
  '@graph': [
    {
      '@type': 'Organization',
      '@id': `${site.url}/#org`,
      name: site.name,
      url: site.url,
      logo: `${site.url}/icon.svg`,
      parentOrganization: { '@type': 'Organization', name: site.maker.name, url: site.maker.url },
    },
    {
      '@type': 'WebSite',
      '@id': `${site.url}/#website`,
      url: site.url,
      name: site.name,
      publisher: { '@id': `${site.url}/#org` },
    },
    {
      '@type': 'SoftwareApplication',
      name: site.name,
      applicationCategory: 'EducationalApplication',
      operatingSystem: 'Web',
      url: site.url,
      description: site.description,
      offers: plans.map((p) => ({ '@type': 'Offer', name: p.name, price: p.monthly, priceCurrency: 'INR' })),
      publisher: { '@id': `${site.url}/#org` },
    },
  ],
};

export default function RootLayout({ children }: LayoutProps<'/'>) {
  return (
    <html lang="en" className={`${display.variable} ${text.variable}`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: flags }} />
      </head>
      <body>
        <a className="skip-link" href="#main">
          Skip to content
        </a>
        <div id="curtain" aria-hidden="true">
          <div className="curtain__panel">
            <span className="curtain__band curtain__band--top" />
            <span className="curtain__label" />
            <span className="curtain__band curtain__band--bottom" />
          </div>
        </div>
        <Header />
        <main id="main" tabIndex={-1}>
          {children}
        </main>
        <Footer />
        <div className="dock">
          <a href={site.appUrl} className="btn btn--dark dock__main">
            <span>Start free</span>
          </a>
          <a href="/pricing/" className="btn btn--light dock__alt">
            <span>Pricing</span>
          </a>
        </div>
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd).replace(/</g, '\\u003c') }} />
        <Motion />
      </body>
    </html>
  );
}
