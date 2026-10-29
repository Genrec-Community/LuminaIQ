import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';

// Keeps the page title, description, canonical link and robots tag in step
// with the current route. index.html carries the home page defaults; this
// swaps them as the user (or a search crawler running JS) moves around.

const SITE = 'https://luminaiq.fun';
const DEFAULT_TITLE = 'Lumina IQ: Study Smarter, Learn Fast and Ace Your Exams';
const DEFAULT_DESCRIPTION = 'Lumina IQ turns your textbooks and notes into a study plan, practice questions and flashcards, so you learn the whole book in less time.';

const PUBLIC = {
    '/': { title: DEFAULT_TITLE, description: DEFAULT_DESCRIPTION },
    '/pricing': {
        title: 'Pricing: Free and Student Plans | Lumina IQ',
        description: 'Start studying free with Lumina IQ. Compare plans for students, exam night passes and school or institution seats.',
    },
    '/login': {
        title: 'Sign in or Create a Free Account | Lumina IQ',
        description: 'Sign in to Lumina IQ or create a free account to turn your textbooks and notes into practice questions, flashcards and a study plan.',
    },
    '/privacy': { title: 'Privacy Policy | Lumina IQ', description: 'How Lumina IQ collects, uses and protects your data.' },
    '/terms': { title: 'Terms of Service | Lumina IQ', description: 'The terms for using the Lumina IQ website and app.' },
};

function setMeta(selector, attr, key, value) {
    let el = document.head.querySelector(selector);
    if (!el) {
        el = document.createElement(attr === 'rel' ? 'link' : 'meta');
        el.setAttribute(attr, key);
        document.head.appendChild(el);
    }
    el.setAttribute(attr === 'rel' ? 'href' : 'content', value);
}

export default function RouteMeta() {
    const { pathname } = useLocation();

    useEffect(() => {
        const path = pathname.length > 1 ? pathname.replace(/\/+$/, '') : '/';
        const page = PUBLIC[path];
        const title = page?.title || 'Lumina IQ';
        const description = page?.description || DEFAULT_DESCRIPTION;

        document.title = title;
        setMeta('meta[name="description"]', 'name', 'description', description);
        setMeta('meta[property="og:title"]', 'property', 'og:title', title);
        setMeta('meta[property="og:description"]', 'property', 'og:description', description);
        setMeta('meta[property="og:url"]', 'property', 'og:url', SITE + path);
        setMeta('link[rel="canonical"]', 'rel', 'canonical', SITE + path);
        // Signed-in pages (dashboard, books, settings...) are private: keep them out of search
        setMeta('meta[name="robots"]', 'name', 'robots', page ? 'index, follow, max-image-preview:large' : 'noindex, nofollow');
    }, [pathname]);

    return null;
}
