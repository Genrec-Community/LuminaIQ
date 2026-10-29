// Global motion for the Lumina IQ site. Runs once on the client, before the first page initializes.
// Motion verb: "mark and settle". Strokes draw like a highlighter; cards settle like paper.
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { ease, isTouch, onPage, onScroll, prefersReducedMotion, setTransition } from '@/engine';
import { idle, startIdle } from './idle';

let label = '';

function transition() {
  // Remember what was clicked, so the curtain can name the destination.
  document.addEventListener(
    'click',
    (e) => {
      const a = (e.target as Element).closest('a');
      label = (a?.dataset.title || a?.textContent || '').trim().slice(0, 40);
    },
    true,
  );
  setTransition({
    leave: (c) => {
      const panel = c.querySelector<HTMLElement>('.curtain__panel')!;
      const text = c.querySelector<HTMLElement>('.curtain__label')!;
      text.textContent = label;
      return gsap
        .timeline()
        .set(c, { autoAlpha: 1 })
        .fromTo(panel, { yPercent: 100 }, { yPercent: 0, duration: 0.85, ease: ease.inOut })
        .fromTo(text, { yPercent: 60, autoAlpha: 0 }, { yPercent: 0, autoAlpha: 1, duration: 0.6, ease: ease.out }, 0.35);
    },
    enter: (c) => {
      const panel = c.querySelector<HTMLElement>('.curtain__panel')!;
      const text = c.querySelector<HTMLElement>('.curtain__label')!;
      return gsap
        .timeline()
        .to(text, { yPercent: -60, autoAlpha: 0, duration: 0.45, ease: ease.inOut })
        .to(panel, { yPercent: -100, duration: 0.9, ease: ease.inOut }, 0.1)
        .set(c, { autoAlpha: 0 });
    },
  });
}

/** [data-draw] paths (pathLength=1) draw like a highlighter stroke: with the intro or on scroll. */
function strokes() {
  onPage(({ intro }) => {
    if (prefersReducedMotion()) return;
    document.querySelectorAll<SVGPathElement>('[data-draw]').forEach((path) => {
      const delay = parseFloat(path.dataset.delay || '0');
      const isIntro = path.hasAttribute('data-draw-intro');
      const tween = gsap.fromTo(
        path,
        { strokeDashoffset: 1 },
        {
          strokeDashoffset: 0,
          duration: parseFloat(path.dataset.duration || '1.3'),
          ease: 'power2.inOut',
          delay,
          paused: isIntro,
          scrollTrigger: isIntro ? undefined : { trigger: path.closest('svg') || path, start: 'top 85%', once: true },
        },
      );
      if (isIntro) intro.add(() => tween.play(), 0);
    });
  });
}

/** The header steps aside on the way down and returns on the way up. */
function header() {
  let last = 0;
  onScroll(({ y }) => {
    const h = document.documentElement.classList;
    h.toggle('is-scrolled', y > 8);
    // Phones: a Start free bar rises after the hero and steps aside for the footer's own CTA.
    const max = document.documentElement.scrollHeight - innerHeight;
    h.toggle('dock-on', y > innerHeight * 0.75 && y < max - innerHeight * 1.1);
    if (Math.abs(y - last) < 4) return;
    // Over the closing band the header stays away, so it never covers that band's own Start free
    const finale = document.querySelector('.finale');
    const overFinale = !!finale && finale.getBoundingClientRect().top < innerHeight * 0.35;
    h.toggle('frame-away', !h.contains('menu-open') && ((y > 240 && y > last) || overFinale));
    last = y;
  });
  onPage(() => {
    document.documentElement.classList.remove('frame-away', 'dock-on');
    // A nav link keeps focus after Back; drop it so its band does not stick to the old page
    const active = document.activeElement as HTMLElement | null;
    if (active?.closest('.site-header')) active.blur();
  });
}

/** Hotlinked photos: if one fails, its frame shows the grid-paper fallback instead of a broken icon. */
function photos() {
  const mark = (img: HTMLImageElement) => img.closest('.photo')?.classList.add('is-broken');
  document.addEventListener(
    'error',
    (e) => {
      const t = e.target;
      if (t instanceof HTMLImageElement) mark(t);
    },
    true,
  );
  onPage(() => {
    document.querySelectorAll<HTMLImageElement>('.photo img').forEach((img) => {
      if (img.complete && img.naturalWidth === 0) mark(img);
    });
  });
}

/** Floating study cards drift a few pixels with the pointer (idle input), only while on screen. */
function floats() {
  onPage(() => {
    if (prefersReducedMotion()) return;
    const items = [...document.querySelectorAll<HTMLElement>('[data-float]')];
    if (!items.length) return;
    const tick = () => {
      for (const el of items) {
        const k = parseFloat(el.dataset.float || '1');
        const t = idle.t * 0.6 + k * 2;
        gsap.set(el, { x: idle.x * 26 * k + Math.sin(t) * 3, y: idle.y * 18 * k + Math.cos(t * 0.8) * 4 });
      }
    };
    const st = ScrollTrigger.create({
      trigger: items[0].closest('section') || items[0],
      start: 'top bottom',
      end: 'bottom top',
      onToggle: (s) => (s.isActive ? gsap.ticker.add(tick) : gsap.ticker.remove(tick)),
    });
    return () => {
      gsap.ticker.remove(tick);
      st.kill();
    };
  });
}

/** The tools index: a preview card follows the pointer on desktop. Touch shows the line inline. */
function toolIndex() {
  onPage(() => {
    const list = document.querySelector<HTMLElement>('[data-index]');
    const box = document.querySelector<HTMLElement>('[data-preview-box]');
    if (!list || !box || isTouch()) return;
    const cards = [...box.querySelectorAll<HTMLElement>('[data-preview-card]')];
    const x = gsap.quickTo(box, 'x', { duration: 0.6, ease: 'power3.out' });
    const y = gsap.quickTo(box, 'y', { duration: 0.6, ease: 'power3.out' });
    const rot = gsap.quickTo(box, 'rotate', { duration: 0.8, ease: 'power3.out' });
    let lastX = 0;
    let px = 0;
    let py = 0;
    let visible = false;
    const move = (e: PointerEvent) => {
      px = e.clientX;
      py = e.clientY;
      x(px + 24);
      y(py);
      rot(gsap.utils.clamp(-6, 6, (px - lastX) * 0.4));
      lastX = px;
    };
    const show = (key: string, at?: DOMRect) => {
      cards.forEach((c) => c.classList.toggle('is-on', c.dataset.previewCard === key));
      if (at) {
        gsap.set(box, { x: at.right - at.width * 0.3, y: at.top + at.height / 2 });
      }
      if (!visible) gsap.to(box, { autoAlpha: 1, scale: 1, duration: 0.5, ease: ease.out, overwrite: 'auto' });
      visible = true;
    };
    const hide = () => {
      if (!visible) return;
      visible = false;
      gsap.to(box, { autoAlpha: 0, scale: 0.9, duration: 0.35, ease: ease.out, overwrite: 'auto' });
    };
    const rows = [...list.querySelectorAll<HTMLAnchorElement>('a[data-preview]')];
    const onEnter = (e: Event) => show((e.currentTarget as HTMLElement).dataset.preview!);
    const onFocus = (e: Event) => {
      const a = e.currentTarget as HTMLElement;
      show(a.dataset.preview!, a.getBoundingClientRect());
    };
    rows.forEach((a) => {
      a.addEventListener('pointerenter', onEnter);
      a.addEventListener('focus', onFocus);
      a.addEventListener('blur', hide);
    });
    list.addEventListener('pointerleave', hide);
    addEventListener('pointermove', move, { passive: true });
    const off = onScroll(() => {
      if (visible && !list.contains(document.elementFromPoint(px, py))) hide();
    });
    return () => {
      removeEventListener('pointermove', move);
      off();
      rows.forEach((a) => {
        a.removeEventListener('pointerenter', onEnter);
        a.removeEventListener('focus', onFocus);
        a.removeEventListener('blur', hide);
      });
    };
  });
}

/** Real numbers count up once when they enter. The final text is in the HTML. */
function counters() {
  onPage(() => {
    if (prefersReducedMotion()) return;
    document.querySelectorAll<HTMLElement>('[data-count]').forEach((el) => {
      const target = parseFloat(el.dataset.count || '0');
      const decimals = parseInt(el.dataset.decimals || '0', 10);
      const final = el.textContent;
      const o = { v: 0 };
      const fmt = (v: number) => v.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
      gsap.to(o, {
        v: target,
        duration: 1.6,
        ease: ease.out,
        scrollTrigger: { trigger: el, start: 'top 90%', once: true },
        onStart: () => {
          el.textContent = fmt(0);
        },
        onUpdate: () => {
          el.textContent = fmt(o.v);
        },
        onComplete: () => {
          el.textContent = final;
        },
      });
    });
  });
}

/** Sticky "loop" dial: the active stage follows the chapter in view. */
function loopStage() {
  onPage(() => {
    const stage = document.querySelector<HTMLElement>('[data-loop-stage]');
    const chapters = [...document.querySelectorAll<HTMLElement>('[data-loop-chapter]')];
    if (!stage || !chapters.length) return;
    chapters.forEach((ch, i) =>
      ScrollTrigger.create({
        trigger: ch,
        start: 'top 60%',
        end: 'bottom 60%',
        onToggle: (s) => {
          if (!s.isActive) return;
          stage.dataset.state = String(i);
          chapters.forEach((c, j) => c.classList.toggle('is-active', j === i));
        },
      }),
    );
  });
}


/** Reading with a highlighter: as each tool row crosses the middle of the screen, the lime band marks it. */
function readingMark() {
  onPage(() => {
    // Phones show the tools as a swipe deck, where a vertical reading line makes no sense.
    if (prefersReducedMotion() || matchMedia('(max-width: 767px)').matches) return;
    document.querySelectorAll<HTMLElement>('[data-index] > li').forEach((row) =>
      ScrollTrigger.create({ trigger: row, start: 'top 55%', end: 'bottom 45%', toggleClass: 'is-reading' }),
    );
  });
}

/** Italic words in headings on paper get a highlighter stroke the moment they arrive. */
function headingMarks() {
  onPage(() => {
    const heads = [...document.querySelectorAll<HTMLElement>('main h2.display, main h1.display')].filter(
      (h) => h.querySelector('em') && !h.closest('.watch, .sched') && !h.classList.contains('hero__title'),
    );
    heads.forEach((h) => {
      h.classList.add('has-mark');
      if (prefersReducedMotion()) return h.classList.add('is-marked');
      ScrollTrigger.create({ trigger: h, start: 'top 75%', once: true, onEnter: () => h.classList.add('is-marked') });
    });
  });
}

/** The video field widens from a card to full bleed as it arrives; the screen grows toward you. */
function watchField() {
  onPage(() => {
    const field = document.querySelector<HTMLElement>('.watch');
    if (!field || prefersReducedMotion()) return;
    const frame = field.querySelector<HTMLElement>('.watch__frame');
    const tl = gsap.timeline({ scrollTrigger: { trigger: field, start: 'top bottom', end: 'top 15%', scrub: 0.6 } });
    tl.fromTo(field, { clipPath: 'inset(0% 6% 0% 6% round 48px)' }, { clipPath: 'inset(0% 0% 0% 0% round 32px)', ease: 'none' }, 0);
    if (frame) tl.fromTo(frame, { scale: 0.86, rotate: -1.5 }, { scale: 1, rotate: 0, ease: 'none' }, 0);
  });
}

/** Photos on the gallery wall pull focus: they ease from a close crop to the full frame as you pass. */
function wallFocus() {
  onPage(() => {
    if (prefersReducedMotion()) return;
    document.querySelectorAll<HTMLElement>('.wall__media > div').forEach((inner) =>
      gsap.fromTo(inner, { scale: 1.25 }, {
        scale: 1.04,
        ease: 'none',
        scrollTrigger: { trigger: inner.parentElement, start: 'top bottom', end: 'bottom top', scrub: true },
      }),
    );
  });
}

/** The pipeline line draws with the scroll, and each step lights up as the line reaches it. */
function pipeline() {
  onPage(() => {
    const track = document.querySelector<HTMLElement>('.pipe__track');
    if (!track) return;
    const steps = [...track.querySelectorAll<HTMLElement>('.step')];
    const path = track.querySelector<SVGPathElement>('.pipe__line path');
    if (prefersReducedMotion()) return steps.forEach((s) => s.classList.add('is-lit'));
    ScrollTrigger.create({
      trigger: track,
      start: 'top 75%',
      end: 'bottom 45%',
      scrub: 0.5,
      onUpdate: (st) => {
        if (path) path.style.strokeDashoffset = String(1 - st.progress);
        steps.forEach((s, i) => s.classList.toggle('is-lit', st.progress >= i / steps.length + 0.02 || st.progress > 0.98));
      },
    });
  });
}

/** [data-draw-scrub] strokes are tied to the scroll instead of playing once. */
function scrubStrokes() {
  onPage(() => {
    if (prefersReducedMotion()) return;
    document.querySelectorAll<SVGPathElement>('[data-draw-scrub]').forEach((path) =>
      gsap.fromTo(path, { strokeDashoffset: 1 }, {
        strokeDashoffset: 0,
        ease: 'none',
        scrollTrigger: { trigger: path.closest('svg') || path, start: 'top 95%', end: 'top 45%', scrub: 0.6 },
      }),
    );
  });
}

export function setupMotion() {
  startIdle();
  transition();
  strokes();
  header();
  photos();
  floats();
  toolIndex();
  counters();
  loopStage();
  readingMark();
  headingMarks();
  watchField();
  wallFocus();
  pipeline();
  scrubStrokes();
}
