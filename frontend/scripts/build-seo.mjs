// Runs after `vite build`. Turns the Markdown articles in src/content/blog
// into plain static HTML pages (so search engines can read them without
// running JavaScript), and writes sitemap.xml and the blog RSS feed.
//
//   dist/blog/index.html          blog home
//   dist/blog/<slug>/index.html   one page per article
//   dist/blog/feed.xml            RSS
//   dist/sitemap.xml              every public page
//
// No dependencies: the Markdown subset used by the articles is converted below.

import { readFileSync, writeFileSync, mkdirSync, readdirSync, existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const CONTENT = join(ROOT, 'src', 'content', 'blog');
const OUT = join(ROOT, process.argv[2] || 'dist');

const SITE = 'https://luminaiq.fun';
const BRAND = 'Lumina IQ';
const OG_IMAGE = `${SITE}/og-image.png`;

// Public SPA pages listed in the sitemap alongside the blog
const STATIC_PAGES = [
    { path: '/', priority: '1.0', changefreq: 'weekly' },
    // Marketing site pages (frontend/website, merged into dist after this script)
    { path: '/features/', priority: '0.9', changefreq: 'monthly' },
    { path: '/how-it-works/', priority: '0.8', changefreq: 'monthly' },
    { path: '/pricing/', priority: '0.8', changefreq: 'monthly' },
    { path: '/about/', priority: '0.6', changefreq: 'yearly' },
    { path: '/login', priority: '0.5', changefreq: 'yearly' },
    { path: '/privacy', priority: '0.3', changefreq: 'yearly' },
    { path: '/terms', priority: '0.3', changefreq: 'yearly' },
];

/* ───────────── helpers ───────────── */

const esc = (s) => String(s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');

function parseFrontmatter(src) {
    const m = src.match(/^---\n([\s\S]*?)\n---\n?([\s\S]*)$/);
    if (!m) throw new Error('Article is missing its --- frontmatter --- block');
    const meta = {};
    for (const line of m[1].split('\n')) {
        const i = line.indexOf(':');
        if (i < 0) continue;
        let v = line.slice(i + 1).trim();
        if (/^".*"$/.test(v)) v = v.slice(1, -1);
        meta[line.slice(0, i).trim()] = v;
    }
    return { meta, body: m[2] };
}

function inline(text) {
    let s = esc(text);
    s = s.replace(/`([^`]+)`/g, '<code>$1</code>');
    s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    s = s.replace(/(^|[^*])\*([^*\s][^*]*)\*/g, '$1<em>$2</em>');
    s = s.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_, label, href) => {
        const external = /^https?:\/\//.test(href) && !href.startsWith(SITE);
        return `<a href="${href}"${external ? ' rel="noopener" target="_blank"' : ''}>${label}</a>`;
    });
    return s;
}

const slugify = (s) => s.toLowerCase().replace(/<[^>]+>/g, '').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

// Converts the Markdown subset the articles use: headings, paragraphs,
// ordered/unordered lists, tables, blockquotes and inline formatting.
function markdown(md) {
    const lines = md.replace(/\r/g, '').split('\n');
    const out = [];
    const toc = [];
    let i = 0;
    while (i < lines.length) {
        const line = lines[i];
        if (!line.trim()) { i++; continue; }

        const h = line.match(/^(#{2,4})\s+(.*)$/);
        if (h) {
            const level = h[1].length;
            const html = inline(h[2]);
            const id = slugify(h[2]);
            if (level === 2) toc.push({ id, text: h[2] });
            out.push(`<h${level} id="${id}">${html}</h${level}>`);
            i++; continue;
        }

        if (/^\|/.test(line)) {
            const rows = [];
            while (i < lines.length && /^\|/.test(lines[i])) rows.push(lines[i++]);
            const cells = (r) => r.replace(/^\||\|$/g, '').split('|').map((c) => c.trim());
            const head = cells(rows[0]);
            const body = rows.slice(2).map(cells);
            out.push('<div class="table"><table><thead><tr>' + head.map((c) => `<th>${inline(c)}</th>`).join('') +
                '</tr></thead><tbody>' + body.map((r) => '<tr>' + r.map((c) => `<td>${inline(c)}</td>`).join('') + '</tr>').join('') +
                '</tbody></table></div>');
            continue;
        }

        if (/^\s*[-*]\s+/.test(line) || /^\s*\d+\.\s+/.test(line)) {
            const ordered = /^\s*\d+\./.test(line);
            const re = ordered ? /^\s*\d+\.\s+/ : /^\s*[-*]\s+/;
            const items = [];
            while (i < lines.length && re.test(lines[i])) items.push(lines[i++].replace(re, ''));
            const tag = ordered ? 'ol' : 'ul';
            out.push(`<${tag}>` + items.map((t) => `<li>${inline(t)}</li>`).join('') + `</${tag}>`);
            continue;
        }

        if (/^>\s?/.test(line)) {
            const quote = [];
            while (i < lines.length && /^>\s?/.test(lines[i])) quote.push(lines[i++].replace(/^>\s?/, ''));
            out.push(`<blockquote><p>${inline(quote.join(' '))}</p></blockquote>`);
            continue;
        }

        const para = [];
        while (i < lines.length && lines[i].trim() && !/^(#{2,4}\s|\||>|\s*[-*]\s|\s*\d+\.\s)/.test(lines[i])) para.push(lines[i++]);
        out.push(`<p>${inline(para.join(' '))}</p>`);
    }
    return { html: out.join('\n'), toc };
}

const words = (s) => s.replace(/[#*`|>[\]()_-]/g, ' ').split(/\s+/).filter(Boolean).length;
const fmtDate = (d) => new Date(d + 'T00:00:00Z').toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' });
const jsonLd = (obj) => `<script type="application/ld+json">${JSON.stringify(obj).replace(/</g, '\\u003c')}</script>`;

/* ───────────── page shell ───────────── */

const CSS = `
:root{--bg:#FDF6F0;--card:#FFFFFF;--ink:#163628;--muted:#5E5046;--line:rgb(74 59 50/.15);--accent:#D3EE6A;--accent-ink:#1E5C42;--green:#1E5C42}
@media (prefers-color-scheme:dark){:root{--bg:#0f1d16;--card:#182c21;--ink:#f4eee2;--muted:#b7c2b4;--line:rgb(244 238 226/.12);--accent:#D3EE6A;--accent-ink:#D3EE6A;--green:#D3EE6A}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:17px/1.7 "Atkinson Hyperlegible Next",system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
a{color:var(--accent-ink);text-underline-offset:3px}article a:hover{background:linear-gradient(transparent 55%,#D3EE6A 55%);color:#163628;text-decoration:none}
.wrap{max-width:760px;margin:0 auto;padding:0 20px}
header.site{border-bottom:1px solid var(--line);background:var(--bg);position:sticky;top:0;z-index:5}
header.site .wrap{max-width:1040px;display:flex;align-items:center;justify-content:space-between;height:64px}
.logo{display:flex;align-items:center;gap:10px;text-decoration:none;color:var(--ink);font:400 21px/1 Newsreader,Georgia,serif;letter-spacing:-.02em}
.logo i{display:inline-flex;align-items:center;justify-content:center;width:34px;height:34px;border-radius:10px;background:#163628;box-shadow:0 6px 14px rgba(22,54,40,.25)}
.logo b{color:var(--accent-ink)}
nav.top{display:flex;gap:18px;align-items:center;font-size:15px}
nav.top a{text-decoration:none;color:var(--muted)}nav.top a:hover{color:var(--ink)}
.btn{display:inline-block;background:var(--ink) linear-gradient(#D3EE6A,#D3EE6A) no-repeat left/0% 100%;transition:background-size .5s cubic-bezier(.16,1,.3,1),color .3s;color:var(--bg)!important;text-decoration:none;padding:10px 18px;border-radius:999px;font-weight:600;font-size:15px}
h1,h2,h3,h4{font-family:Newsreader,Georgia,serif;font-weight:400;line-height:1.12;letter-spacing:-.02em}
h1{font-size:clamp(30px,5vw,44px);margin:12px 0 14px}
h2{font-size:26px;margin:44px 0 10px}h3{font-size:20px;margin:30px 0 6px}
.crumbs{font-size:14px;color:var(--muted);margin-top:36px}.crumbs a{color:var(--muted)}
.meta{color:var(--muted);font-size:14px;margin-bottom:28px}
.lede{font-size:19px;color:var(--muted)}
article p,article li{margin:0 0 16px}
article ul,article ol{padding-left:24px;margin:0 0 18px}
blockquote{margin:24px 0;padding:6px 20px;border-left:3px solid var(--accent);color:var(--muted)}
code{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:1px 6px;font-size:.9em}
.table{overflow-x:auto;margin:8px 0 22px}
table{border-collapse:collapse;width:100%;font-size:16px;background:var(--card);border-radius:12px;overflow:hidden}
th,td{text-align:left;padding:10px 14px;border-bottom:1px solid var(--line)}th{font-weight:700}
.toc{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:16px 22px;margin:0 0 30px;font-size:15px}
.toc strong{display:block;margin-bottom:6px}.toc ol{margin:0;padding-left:20px}.toc li{margin:2px 0}
.cta{margin:48px 0;padding:28px;border-radius:20px;background:var(--card);border:1px solid var(--line)}
.cta h2{margin:0 0 8px;font-size:24px}.cta p{margin:0 0 18px;color:var(--muted)}
.related{margin:48px 0 0}.related h2{font-size:22px}
.cards{display:grid;gap:16px;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));margin:18px 0 0}
.card{display:block;text-decoration:none;color:var(--ink);background:var(--card);border:1px solid var(--line);border-radius:18px;padding:20px 22px;transition:transform .15s,border-color .15s}
.card:hover{transform:translateY(-2px);border-color:var(--accent)}
.card h3{margin:0 0 8px;font-size:19px}.card p{margin:0;font-size:15px;color:var(--muted);line-height:1.55}
.card small{display:block;margin-top:12px;color:var(--muted);font-size:13px}
.blog-hero{padding:56px 0 18px}.blog-hero p{font-size:19px;color:var(--muted);max-width:620px}
.blog-wrap{max-width:1040px}
footer.site{margin-top:72px;border-top:1px solid var(--line);padding:28px 0 40px;font-size:14px;color:var(--muted)}
footer.site .wrap{max-width:1040px;display:flex;flex-wrap:wrap;gap:12px 24px;justify-content:space-between}
footer.site a{color:var(--muted)}
.btn:hover{background-size:100% 100%;color:#163628!important}
.skip{position:fixed;left:12px;top:-60px;z-index:99;padding:10px 16px;border-radius:999px;background:var(--ink);color:var(--bg)!important;font-weight:700;text-decoration:none}.skip:focus{top:12px}
footer.site a,.toc li a{display:inline-block;padding:4px 0}
nav.top a:not(.btn){background:linear-gradient(#D3EE6A,#D3EE6A) no-repeat left calc(100% - 2px)/0% 3px;transition:background-size .4s cubic-bezier(.16,1,.3,1);padding:6px 0}nav.top a:not(.btn):hover{background-size:100% 3px}
.logo{transition:transform .3s cubic-bezier(.16,1,.3,1)}.logo:hover{transform:translateY(-1px)}.logo:hover i{transform:rotate(-6deg)}.logo i{transition:transform .3s cubic-bezier(.16,1,.3,1)}
@media (max-width:640px){nav.top .hide-sm{display:none}body{font-size:16px}h2{font-size:23px}}
`;

function shell({ title, description, path, type = 'website', extraHead = '', body, keywords, published }) {
    const url = SITE + path;
    return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${esc(title)}</title>
<meta name="description" content="${esc(description)}">
${keywords ? `<meta name="keywords" content="${esc(keywords)}">\n` : ''}<meta name="robots" content="index, follow, max-image-preview:large">
<link rel="canonical" href="${url}">
<meta property="og:type" content="${type}">
<meta property="og:site_name" content="${BRAND}">
<meta property="og:title" content="${esc(title)}">
<meta property="og:description" content="${esc(description)}">
<meta property="og:url" content="${url}">
<meta property="og:image" content="${OG_IMAGE}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:locale" content="en_IN">
${published ? `<meta property="article:published_time" content="${published}">\n` : ''}<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="${esc(title)}">
<meta name="twitter:description" content="${esc(description)}">
<meta name="twitter:image" content="${OG_IMAGE}">
<meta name="theme-color" content="#FDF6F0">
<link rel="icon" href="/favicon.ico">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="alternate" type="application/rss+xml" title="${BRAND} blog" href="${SITE}/blog/feed.xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible+Next:wght@400;700&family=Newsreader:ital,opsz,wght@0,6..72,400;1,6..72,400&display=swap" rel="stylesheet">
<style>${CSS.trim()}</style>
${extraHead}
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="site"><div class="wrap">
  <a class="logo" href="/" aria-label="${BRAND} home"><i><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 7v14"/><path d="M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z"/></svg></i><span>Lumina IQ</span></a>
  <nav class="top"><a href="/blog/">Blog</a><a class="hide-sm" href="/pricing">Pricing</a><a class="btn" href="/login">Start free</a></nav>
</div></header>
${body}
<footer class="site"><div class="wrap">
  <span>© ${new Date().getFullYear()} ${BRAND}. Built for students, by students.</span>
  <span><a href="/">Home</a> · <a href="/blog/">Blog</a> · <a href="/pricing">Pricing</a> · <a href="/privacy">Privacy</a> · <a href="/terms">Terms</a></span>
</div></footer>
</body>
</html>
`;
}

const CTA = `<section class="cta">
  <h2>Study your own textbook the smart way</h2>
  <p>Upload a book or your notes. ${BRAND} puts the foundations first, turns each topic into practice questions, and brings back what you're about to forget.</p>
  <a class="btn" href="/login">Try ${BRAND} free</a>
</section>`;

const card = (a) => `<a class="card" href="/blog/${a.slug}/"><h3>${esc(a.title)}</h3><p>${esc(a.description)}</p><small>${fmtDate(a.date)} · ${a.minutes} min read</small></a>`;

/* ───────────── build ───────────── */

if (!existsSync(OUT)) {
    console.error(`[seo] ${OUT} does not exist. Run vite build first.`);
    process.exit(1);
}

const articles = readdirSync(CONTENT).filter((f) => f.endsWith('.md')).map((file) => {
    const { meta, body } = parseFrontmatter(readFileSync(join(CONTENT, file), 'utf8'));
    for (const k of ['title', 'description', 'date']) if (!meta[k]) throw new Error(`${file}: missing "${k}"`);
    const { html, toc } = markdown(body);
    return { ...meta, slug: meta.slug || file.replace(/\.md$/, ''), html, toc, minutes: Math.max(1, Math.round(words(body) / 220)) };
}).sort((a, b) => b.date.localeCompare(a.date));

const publisher = { '@type': 'Organization', name: BRAND, url: SITE, logo: { '@type': 'ImageObject', url: `${SITE}/android-chrome-512x512.png` } };

for (const a of articles) {
    const path = `/blog/${a.slug}/`;
    const related = articles.filter((x) => x.slug !== a.slug).slice(0, 3);
    const toc = a.toc.length > 3
        ? `<nav class="toc" aria-label="On this page"><strong>On this page</strong><ol>${a.toc.map((t) => `<li><a href="#${t.id}">${inline(t.text)}</a></li>`).join('')}</ol></nav>`
        : '';
    const ld = [
        {
            '@context': 'https://schema.org', '@type': 'BlogPosting',
            headline: a.title, description: a.description,
            datePublished: a.date, dateModified: a.updated || a.date,
            mainEntityOfPage: { '@type': 'WebPage', '@id': SITE + path },
            image: OG_IMAGE, author: { '@type': 'Organization', name: `${BRAND} team`, url: SITE },
            publisher, keywords: a.keywords, inLanguage: 'en', wordCount: words(a.html.replace(/<[^>]+>/g, ' ')),
        },
        {
            '@context': 'https://schema.org', '@type': 'BreadcrumbList',
            itemListElement: [
                { '@type': 'ListItem', position: 1, name: 'Home', item: SITE + '/' },
                { '@type': 'ListItem', position: 2, name: 'Blog', item: SITE + '/blog/' },
                { '@type': 'ListItem', position: 3, name: a.title, item: SITE + path },
            ],
        },
    ];
    const body = `<main id="main" class="wrap">
<div class="crumbs"><a href="/">Home</a> / <a href="/blog/">Blog</a></div>
<article>
<h1>${esc(a.title)}</h1>
<p class="lede">${esc(a.description)}</p>
<div class="meta">By the ${BRAND} team · <time datetime="${a.date}">${fmtDate(a.date)}</time> · ${a.minutes} min read</div>
${toc}
${a.html}
</article>
${CTA}
<section class="related"><h2>Keep reading</h2><div class="cards">${related.map(card).join('')}</div></section>
</main>`;
    mkdirSync(join(OUT, 'blog', a.slug), { recursive: true });
    writeFileSync(join(OUT, 'blog', a.slug, 'index.html'), shell({
        title: `${a.title} | ${BRAND}`, description: a.description, path, type: 'article',
        keywords: a.keywords, published: a.date, extraHead: ld.map(jsonLd).join('\n'), body,
    }));
}

// Blog home
const blogLd = {
    '@context': 'https://schema.org', '@type': 'Blog', name: `${BRAND} blog`, url: SITE + '/blog/',
    description: 'Study tips for exams, learning fast and remembering more.', publisher,
    blogPost: articles.map((a) => ({ '@type': 'BlogPosting', headline: a.title, url: `${SITE}/blog/${a.slug}/`, datePublished: a.date })),
};
writeFileSync(join(OUT, 'blog', 'index.html'), shell({
    title: `Study Tips for Exams, Learning Fast and Remembering More | ${BRAND} Blog`,
    description: 'Practical, no-fluff guides for students: how to study for exams, learn faster, focus, plan your revision and remember what you read.',
    path: '/blog/',
    keywords: 'study tips, how to study for exams, learn fast, exam preparation, revision tips, study plan',
    extraHead: jsonLd(blogLd),
    body: `<main id="main" class="wrap blog-wrap">
<section class="blog-hero"><h1>Study smarter, not longer</h1>
<p>Honest, practical guides for students who have exams coming and not enough time. How to study, how to learn fast, and how to actually remember it.</p></section>
<h2>Latest guides</h2>
<div class="cards">${articles.map(card).join('')}</div>
${CTA}
</main>`,
}));

// RSS
const rss = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>
<title>${BRAND} blog</title><link>${SITE}/blog/</link><description>Study tips for exams, learning fast and remembering more.</description><language>en</language>
<atom:link href="${SITE}/blog/feed.xml" rel="self" type="application/rss+xml"/>
${articles.map((a) => `<item><title>${esc(a.title)}</title><link>${SITE}/blog/${a.slug}/</link><guid>${SITE}/blog/${a.slug}/</guid><pubDate>${new Date(a.date + 'T06:00:00Z').toUTCString()}</pubDate><description>${esc(a.description)}</description></item>`).join('\n')}
</channel></rss>
`;
writeFileSync(join(OUT, 'blog', 'feed.xml'), rss);

// Sitemap
const latest = articles[0]?.date;
const urls = [
    ...STATIC_PAGES.map((p) => ({ loc: SITE + p.path, lastmod: p.path === '/' ? latest : undefined, ...p })),
    { loc: SITE + '/blog/', lastmod: latest, changefreq: 'weekly', priority: '0.9' },
    ...articles.map((a) => ({ loc: `${SITE}/blog/${a.slug}/`, lastmod: a.updated || a.date, changefreq: 'monthly', priority: '0.8' })),
];
writeFileSync(join(OUT, 'sitemap.xml'), `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls.map((u) => `  <url><loc>${u.loc}</loc>${u.lastmod ? `<lastmod>${u.lastmod}</lastmod>` : ''}<changefreq>${u.changefreq}</changefreq><priority>${u.priority}</priority></url>`).join('\n')}
</urlset>
`);

console.log(`[seo] wrote ${articles.length} articles, blog index, feed.xml and sitemap.xml (${urls.length} URLs)`);
