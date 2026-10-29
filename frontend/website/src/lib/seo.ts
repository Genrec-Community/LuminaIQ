import type { Metadata } from 'next';
import { site } from '@/data/site';

/** Per-page metadata: title, description, canonical, and matching Open Graph / Twitter tags. */
export function pageMeta({ title, description, path, absolute }: { title: string; description: string; path: string; absolute?: boolean }): Metadata {
  const full = absolute ? title : `${title} | ${site.name}`;
  return {
    title: absolute ? { absolute: title } : title,
    description,
    alternates: { canonical: path },
    openGraph: {
      type: 'website',
      siteName: site.name,
      locale: 'en_US',
      url: path,
      title: full,
      description,
      images: [{ url: '/og.png', width: 1200, height: 630, alt: 'Lumina IQ: read it once, remember it for the exam' }],
    },
    twitter: { card: 'summary_large_image', title: full, description, images: ['/og.png'] },
  };
}

/** BreadcrumbList JSON-LD for an inner page. */
export function breadcrumbs(name: string, path: string) {
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: [
      { '@type': 'ListItem', position: 1, name: 'Home', item: `${site.url}/` },
      { '@type': 'ListItem', position: 2, name, item: `${site.url}${path}` },
    ],
  };
}

export const ld = (data: object) => ({ __html: JSON.stringify(data).replace(/</g, '\\u003c') });
