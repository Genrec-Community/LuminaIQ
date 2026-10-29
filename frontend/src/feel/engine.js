// The app's motion engine, ported from the marketing site (frontend/website/src/engine) so the
// product feels like the site: Lenis smooth scroll on one GSAP clock, "settle" reveals, masked
// line reveals for display type, magnetic CTAs, a labelled cursor follower and a forest curtain
// with lime highlighter edges between pages. Motion verb: mark and settle.
//
// Declarative, in markup:
//   data-reveal="settle|up|fade"   block enters when it scrolls into view (any scroller)
//   data-split                     display heading: lines rise out of a mask
//   data-delay="0.1"               extra delay in seconds
//   data-magnetic="0.3"            element leans toward the pointer (fine pointers only)
//   data-cursor="Open"             the follower grows and shows this label
// Everything is skipped under reduced motion; content is never hidden without JS.
import Lenis from 'lenis';
import { gsap } from 'gsap';
import { SplitText } from 'gsap/SplitText';

gsap.registerPlugin(SplitText);

export const ease = { out: 'expo.out', inOut: 'expo.inOut', soft: 'power3.out' };
export const reducedMotion = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
export const isTouch = () => matchMedia('(hover: none), (pointer: coarse)').matches;

/* ---------- smooth scroll (window pages only; nested scrollers stay native) ---------- */
let lenis = null;
let ticking = false;
export function smoothScroll(on) {
    if (on && !lenis && !reducedMotion()) {
        lenis = new Lenis({ lerp: 0.1, touchMultiplier: 1.2, anchors: true, allowNestedScroll: true });
        if (!ticking) {
            ticking = true;
            gsap.ticker.add((t) => lenis?.raf(t * 1000));
            gsap.ticker.lagSmoothing(0);
        }
    } else if (!on && lenis) {
        lenis.destroy();
        lenis = null;
    }
}
export const scrollTop = () => (lenis ? lenis.scrollTo(0, { immediate: true, force: true }) : window.scrollTo(0, 0));

/* ---------- header steps aside on the way down, returns on the way up ---------- */
let lastY = 0;
function onWindowScroll() {
    const y = window.scrollY;
    const h = document.documentElement.classList;
    h.toggle('is-scrolled', y > 8);
    if (Math.abs(y - lastY) < 4) return;
    h.toggle('frame-away', y > 240 && y > lastY);
    lastY = y;
}

/* ---------- reveals ---------- */
const seen = new WeakSet();
let io = null;

function revealBlock(el) {
    const kind = el.dataset.reveal || 'settle';
    const delay = parseFloat(el.dataset.delay || '0');
    const from = kind === 'fade' ? { autoAlpha: 0 }
        : kind === 'up' ? { y: 40, autoAlpha: 0 }
        : { y: 56, rotate: parseFloat(el.dataset.tilt || '1.6'), autoAlpha: 0, transformOrigin: '50% 100%' };
    el.removeAttribute('data-rv');
    gsap.fromTo(el, from, {
        y: 0, rotate: 0, autoAlpha: 1, duration: kind === 'fade' ? 0.9 : 1.15, ease: ease.out, delay,
        clearProps: 'transform,visibility,opacity',
    });
}

function revealSplit(el) {
    const delay = parseFloat(el.dataset.delay || '0');
    // Split only for the entrance, then restore the original text nodes React owns
    const split = SplitText.create(el, { type: 'lines', mask: 'lines', linesClass: 'split-line' });
    el.removeAttribute('data-rv');
    gsap.from(split.lines, {
        yPercent: 110, rotate: 2, duration: 1.15, stagger: 0.08, ease: ease.out, delay,
        onComplete: () => split.revert(),
    });
}

function watch(el) {
    if (seen.has(el)) return;
    seen.add(el);
    if (reducedMotion()) return;
    // An attribute, not a class: React rewrites className on re-render, never unknown attributes
    el.setAttribute('data-rv', 'wait');
    io.observe(el);
}

export function scanReveals(root = document) {
    if (!io) {
        io = new IntersectionObserver((entries) => {
            for (const e of entries) {
                if (!e.isIntersecting) continue;
                io.unobserve(e.target);
                if (e.target.hasAttribute('data-split')) revealSplit(e.target);
                else revealBlock(e.target);
            }
        }, { rootMargin: '0px 0px -8% 0px', threshold: 0.01 });
    }
    root.querySelectorAll('[data-reveal], [data-split]').forEach(watch);
}

/* ---------- magnetic CTAs and the cursor follower ---------- */
const magnets = new WeakMap();
function magnet(el) {
    let m = magnets.get(el);
    if (!m) {
        m = { x: gsap.quickTo(el, 'x', { duration: 0.6, ease: ease.soft }), y: gsap.quickTo(el, 'y', { duration: 0.6, ease: ease.soft }) };
        magnets.set(el, m);
        el.addEventListener('pointerleave', () => { m.x(0); m.y(0); });
    }
    return m;
}

function pointerCraft() {
    const follower = document.getElementById('cursor');
    const label = follower?.querySelector('[data-cursor-label]');
    const fx = follower && gsap.quickTo(follower, 'x', { duration: 0.45, ease: ease.soft });
    const fy = follower && gsap.quickTo(follower, 'y', { duration: 0.45, ease: ease.soft });
    follower?.classList.add('is-ready');
    addEventListener('pointermove', (e) => {
        const target = e.target instanceof Element ? e.target : null;
        const mag = target?.closest('[data-magnetic]');
        if (mag) {
            const r = mag.getBoundingClientRect();
            const s = parseFloat(mag.dataset.magnetic || '0.3');
            const m = magnet(mag);
            m.x((e.clientX - (r.left + r.width / 2)) * s);
            m.y((e.clientY - (r.top + r.height / 2)) * s);
        }
        if (follower) {
            fx(e.clientX); fy(e.clientY);
            const text = target?.closest('[data-cursor]')?.dataset.cursor || '';
            follower.classList.toggle('is-active', !!text);
            if (label && label.textContent !== text && text) label.textContent = text;
        }
    }, { passive: true });
    document.addEventListener('pointerleave', () => follower?.classList.remove('is-active'));
}

/* ---------- curtain between pages ---------- */
// Called before the new page paints: the panel covers at once, names the destination,
// then lifts off with its lime edge leading, like a highlighter pass.
export function curtain(text) {
    const root = document.getElementById('curtain');
    if (!root || reducedMotion()) return;
    const panel = root.querySelector('.curtain__panel');
    const label = root.querySelector('.curtain__label');
    label.textContent = text || '';
    gsap.killTweensOf([panel, label]);
    gsap.timeline()
        .set(root, { autoAlpha: 1 })
        .set(panel, { yPercent: 0 })
        .fromTo(label, { yPercent: 40, autoAlpha: 0 }, { yPercent: 0, autoAlpha: 1, duration: 0.35, ease: ease.out })
        .to(label, { yPercent: -50, autoAlpha: 0, duration: 0.3, ease: ease.inOut }, 0.45)
        .to(panel, { yPercent: -100, duration: 0.85, ease: ease.inOut }, 0.5)
        .set(root, { autoAlpha: 0 });
}

/* ---------- boot ---------- */
let booted = false;
export function boot() {
    if (booted) return;
    booted = true;
    const h = document.documentElement.classList;
    h.toggle('motion', !reducedMotion());
    addEventListener('scroll', onWindowScroll, { passive: true });
    if (!isTouch() && !reducedMotion()) pointerCraft();
    scanReveals();
    // Pages render data after they mount: pick up new reveal targets as they appear
    let queued = false;
    new MutationObserver(() => {
        if (queued) return;
        queued = true;
        requestAnimationFrame(() => { queued = false; scanReveals(); });
    }).observe(document.body, { childList: true, subtree: true });
}
