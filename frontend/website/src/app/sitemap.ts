import type { MetadataRoute } from 'next';
import { site } from '@/data/site';

export const dynamic = 'force-static';

export default function sitemap(): MetadataRoute.Sitemap {
  const pages = [
    { path: '/', priority: 1 },
    { path: '/features/', priority: 0.9 },
    { path: '/how-it-works/', priority: 0.8 },
    { path: '/pricing/', priority: 0.9 },
    { path: '/about/', priority: 0.6 },
  ];
  return pages.map((p) => ({ url: `${site.url}${p.path}`, lastModified: new Date(), changeFrequency: 'monthly', priority: p.priority }));
}
