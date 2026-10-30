# SEO analysis: LuminaIQ website

Checked on 27 Oct 2026 against the production build (`audit.mjs` crawl of all 5 pages plus the 404).

## Result

**0 failures, 0 warnings** in the technical audit after the fixes below.

## Fixed in this pass

| Issue | Why it mattered | Fix |
|---|---|---|
| Canonical URLs and share image pointed at `www.luminaiq.fun` | That domain serves the app, so `/features/`, `/pricing/` and `/og.png` don't exist there. Google would treat every page as a copy of a URL that returns 404, and link previews would show no image. | The site URL now comes from the deployment (`NEXT_PUBLIC_SITE_URL`, then Vercel's production URL). |
| No `og:url`, and share titles came only from the layout | Weaker link previews on WhatsApp, LinkedIn and X | Each page sets its own title, description, canonical, `og:url` and Twitter card (`src/lib/seo.ts`). |
| Preview deployments could be indexed | Duplicate content across `*.vercel.app` URLs | `noindex` on every Vercel environment except production. |
| Titles over 70 characters | Truncated in search results | All titles are 70 characters or fewer. |
| 292 KB of fonts on the home page | Slower first render on phones | Dropped Newsreader's optical-size axis: 153 KB. |
| Breadcrumbs missing | No breadcrumb trail in search results | `BreadcrumbList` JSON-LD on every inner page. |

## Already in place

- One `<h1>` per page, ordered headings, landmarks, `lang="en"`, skip link.
- Unique title and 120 to 160 character description on every page.
- `sitemap.xml` (5 pages) and `robots.txt` pointing at it; real 404 status and a `noindex` 404 page.
- JSON-LD: `Organization` (with GenrecAI as parent), `WebSite`, `SoftwareApplication` with the three plan prices, `FAQPage` on /pricing/, `BreadcrumbList` on inner pages.
- 1200×630 Open Graph image, SVG favicon, theme colour.
- All content is server-rendered HTML (crawlers see everything without running JavaScript).
- Throttled mobile CLS about 0.005 (target under 0.05).

## Recommendations (need a decision or content from you)

1. **Put the site on the main domain.** Today `www.luminaiq.fun` serves the app's own landing page and this site lives on `luminaiq-website.vercel.app`. Search engines will rank only one. The strongest setup is this site on `luminaiq.fun` with the app on `app.luminaiq.fun`. Once decided, set `NEXT_PUBLIC_SITE_URL` in Vercel and add the domain to the `luminaiq-website` project.
2. **Register in Google Search Console** and submit `/sitemap.xml` once the final domain is live.
3. **Replace stock photos with real product screenshots.** Real UI images can rank in image search and convert better. Add descriptive alt text when you swap them (`src/data/site.ts`).
4. **Publish content for the searches students actually make.** Each of these would be a page or article: "how to make flashcards from a PDF", "spaced repetition schedule explained", "AI quiz generator from notes", "how to study a textbook chapter". `/how-it-works/` already covers the SM-2 explanation and can link to them.
5. **Comparison pages** ("LuminaIQ vs Quizlet", "vs NotebookLM", "vs Knowt") match high-intent searches; keep them factual.
6. **Earn links**: Product Hunt launch, university study-skills pages, the GenrecAI site linking to the marketing site rather than the app.
7. **Add the YouTube video's upload date** to enable `VideoObject` rich results for the walkthrough.
