// Puts the marketing site (frontend/website, a static Next.js export) in front of the app.
//   dist/index.html (the app)  -> dist/app.html; hosts rewrite unknown paths to /app.html
//   website/out/*              -> dist/ (/, /features/, /how-it-works/, /pricing/, /about/, /_next/)
// The app keeps robots.txt and sitemap.xml (build-seo.mjs lists the site pages too).
// SKIP_WEBSITE=1 (the Android build) leaves dist as a plain app with index.html.
import { execSync } from 'node:child_process';
import { cpSync, existsSync, readdirSync, renameSync } from 'node:fs';
import { join } from 'node:path';

if (process.env.SKIP_WEBSITE === '1') {
    console.log('[website] skipped (SKIP_WEBSITE=1)');
    process.exit(0);
}

const root = new URL('..', import.meta.url).pathname;
const site = join(root, 'website');
const dist = join(root, 'dist');

// Canonical address: the test site for the test branch, luminaiq.fun otherwise
const branch = process.env.VERCEL_GIT_COMMIT_REF || process.env.GITHUB_REF_NAME || '';
const siteUrl = process.env.NEXT_PUBLIC_SITE_URL
    || (branch === 'jaisamyukth-changes' ? 'https://test.luminaiq.fun' : 'https://luminaiq.fun');

const run = (cmd) => execSync(cmd, { cwd: site, stdio: 'inherit', env: { ...process.env, NEXT_PUBLIC_SITE_URL: siteUrl, NEXT_TELEMETRY_DISABLED: '1' } });
if (!existsSync(join(site, 'node_modules'))) run('npm ci --no-audit --no-fund');
run('npx next build');

renameSync(join(dist, 'index.html'), join(dist, 'app.html'));
const out = join(site, 'out');
for (const name of readdirSync(out)) {
    if (name === 'robots.txt' || name === 'sitemap.xml') continue;
    cpSync(join(out, name), join(dist, name), { recursive: true });
}
console.log(`[website] merged into dist (canonical ${siteUrl}); app served from /app.html`);
