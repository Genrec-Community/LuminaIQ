'use client';
// The signature: an illustrative forgetting curve. A grey curve shows recall after reading once;
// the lime curve resets at each SM-2 review (day 1, 6, 15, 38) and decays more slowly every time.
// Point at it, drag on it, or use the arrow keys to pick a day. At rest, the marker keeps walking.
import { useMemo, useRef } from 'react';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { usePage } from '@/engine/next';
import { prefersReducedMotion } from '@/engine';

const DAYS = 40;
const REVIEWS = [1, 6, 15, 38];
const S0 = 2.2; // stability in days after one read
const GROWTH = 3; // each successful review makes the memory this much more stable

const once = (t: number) => Math.exp(-t / S0);
function withReviews(t: number) {
  let k = 0;
  let last = 0;
  for (const r of REVIEWS) if (t >= r) { k++; last = r; }
  return Math.exp(-(t - last) / (S0 * Math.pow(GROWTH, k)));
}

const W = 800;
const H = 300;
const PAD = { l: 8, r: 8, t: 14, b: 10 };
const X = (t: number) => PAD.l + (t / DAYS) * (W - PAD.l - PAD.r);
const Y = (r: number) => PAD.t + (1 - r) * (H - PAD.t - PAD.b);

function path(fn: (t: number) => number, jumps: number[] = []) {
  let d = `M${X(0).toFixed(1)} ${Y(fn(0)).toFixed(1)}`;
  for (let i = 1; i <= DAYS * 10; i++) {
    const t = i / 10;
    const j = jumps.find((r) => r > (i - 1) / 10 && r <= t);
    if (j !== undefined) {
      const before = fn(j - 1e-6);
      d += ` L${X(j).toFixed(1)} ${Y(before).toFixed(1)} L${X(j).toFixed(1)} ${Y(1).toFixed(1)}`;
    }
    d += ` L${X(t).toFixed(1)} ${Y(fn(t)).toFixed(1)}`;
  }
  return d;
}

const pct = (r: number) => `${Math.round(r * 100)}%`;

export function MemoryCurve() {
  const root = useRef<HTMLDivElement>(null);
  const svg = useRef<SVGSVGElement>(null);
  const paths = useMemo(() => ({ once: path(once), reviews: path(withReviews, REVIEWS) }), []);

  usePage(() => {
    const el = root.current;
    const plot = svg.current;
    if (!el || !plot) return;
    const marker = el.querySelector<SVGGElement>('[data-marker]')!;
    const dotOnce = el.querySelector<SVGCircleElement>('[data-dot-once]')!;
    const dotRev = el.querySelector<SVGCircleElement>('[data-dot-rev]')!;
    const outDay = el.querySelector<HTMLElement>('[data-out-day]')!;
    const outOnce = el.querySelector<HTMLElement>('[data-out-once]')!;
    const outRev = el.querySelector<HTMLElement>('[data-out-rev]')!;
    const slider = el.querySelector<HTMLElement>('[role="slider"]')!;

    const state = { day: 12, manualUntil: 0, inView: true };
    const render = () => {
      const d = state.day;
      const x = X(d);
      marker.setAttribute('transform', `translate(${x.toFixed(1)} 0)`);
      dotOnce.setAttribute('cy', Y(once(d)).toFixed(1));
      dotRev.setAttribute('cy', Y(withReviews(d)).toFixed(1));
      const day = Math.floor(d);
      outDay.textContent = String(day);
      outOnce.textContent = pct(once(d));
      outRev.textContent = pct(withReviews(d));
      slider.setAttribute('aria-valuenow', String(day));
      slider.setAttribute('aria-valuetext', `Day ${day}: read once ${pct(once(d))}, with reviews ${pct(withReviews(d))}`);
    };
    render();

    const toDay = (clientX: number) => {
      const r = plot.getBoundingClientRect();
      const t = ((((clientX - r.left) / r.width) * W - PAD.l) / (W - PAD.l - PAD.r)) * DAYS;
      state.day = gsap.utils.clamp(0, DAYS - 0.01, t);
      state.manualUntil = performance.now() + 3500;
      render();
    };
    const onMove = (e: PointerEvent) => {
      if (e.pointerType === 'mouse' || e.buttons) toDay(e.clientX);
    };
    const onDown = (e: PointerEvent) => toDay(e.clientX);
    const onKey = (e: KeyboardEvent) => {
      const step = e.shiftKey ? 5 : 1;
      if (e.key === 'ArrowRight' || e.key === 'ArrowUp') state.day = Math.min(DAYS - 0.01, Math.floor(state.day) + step);
      else if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') state.day = Math.max(0, Math.floor(state.day) - step);
      else if (e.key === 'Home') state.day = 0;
      else if (e.key === 'End') state.day = DAYS - 0.01;
      else return;
      e.preventDefault();
      state.manualUntil = performance.now() + 6000;
      render();
    };
    plot.addEventListener('pointermove', onMove);
    plot.addEventListener('pointerdown', onDown);
    slider.addEventListener('keydown', onKey);

    // Scroll is time: scrolling the hero away moves the marker through the weeks.
    let scrollSt: ScrollTrigger | null = null;
    if (!prefersReducedMotion()) {
      scrollSt = ScrollTrigger.create({
        trigger: el,
        start: 'top 85%',
        end: 'bottom top',
        onUpdate: (s) => {
          if (Math.abs(s.getVelocity()) < 5) return;
          state.day = 2 + s.progress * (DAYS - 4);
          state.manualUntil = performance.now() + 1200;
          render();
        },
      });
    }

    // Idle: the marker walks the curve, one pass every ~16 s, only while on screen.
    let tick: (() => void) | null = null;
    let st: ScrollTrigger | null = null;
    if (!prefersReducedMotion()) {
      tick = () => {
        if (performance.now() < state.manualUntil) return;
        state.day = (state.day + gsap.ticker.deltaRatio() * (DAYS / (16 * 60))) % DAYS;
        render();
      };
      st = ScrollTrigger.create({
        trigger: el,
        start: 'top bottom',
        end: 'bottom top',
        onToggle: (s) => (s.isActive ? gsap.ticker.add(tick!) : gsap.ticker.remove(tick!)),
      });
    }
    return () => {
      plot.removeEventListener('pointermove', onMove);
      plot.removeEventListener('pointerdown', onDown);
      slider.removeEventListener('keydown', onKey);
      if (tick) gsap.ticker.remove(tick);
      st?.kill();
      scrollSt?.kill();
    };
  });

  return (
    <div className="curve" ref={root}>
      <div className="curve__head">
        <h2 className="curve__title">How much you still remember</h2>
        <dl className="curve__readout" aria-live="off">
          <div>
            <dt>Day</dt>
            <dd data-out-day>12</dd>
          </div>
          <div className="curve__once">
            <dt>Read once</dt>
            <dd data-out-once>{pct(once(12))}</dd>
          </div>
          <div className="curve__rev">
            <dt>With reviews</dt>
            <dd data-out-rev>{pct(withReviews(12))}</dd>
          </div>
        </dl>
      </div>

      <div
        className="curve__plot"
        role="slider"
        tabIndex={0}
        aria-label="Day since you first read the material"
        aria-valuemin={0}
        aria-valuemax={DAYS - 1}
        aria-valuenow={12}
      >
        <svg ref={svg} viewBox={`0 0 ${W} ${H}`} aria-hidden="true">
          {[0.25, 0.5, 0.75].map((r) => (
            <line key={r} className="curve__grid" x1={X(0)} x2={X(DAYS)} y1={Y(r)} y2={Y(r)} />
          ))}
          {REVIEWS.map((r) => (
            <line key={r} className="curve__review" x1={X(r)} x2={X(r)} y1={Y(0)} y2={Y(1)} />
          ))}
          <path className="curve__line curve__line--once" d={paths.once} pathLength={1} data-draw data-draw-intro data-delay="0.5" data-duration="1.4" />
          <path className="curve__line curve__line--rev" d={paths.reviews} pathLength={1} data-draw data-draw-intro data-delay="0.75" data-duration="2" />
          <g data-marker transform={`translate(${X(12)} 0)`}>
            <line className="curve__marker" x1={0} x2={0} y1={Y(0)} y2={Y(1)} />
            <circle className="curve__dot curve__dot--once" cx={0} cy={Y(once(12))} r={6} data-dot-once />
            <circle className="curve__dot curve__dot--rev" cx={0} cy={Y(withReviews(12))} r={7} data-dot-rev />
          </g>
        </svg>
        <ol className="curve__axis" aria-hidden="true">
          {REVIEWS.map((r) => (
            <li key={r} style={{ left: `${(X(r) / W) * 100}%` }}>
              <span className="curve__rv">Review </span>
              <span>day {r}</span>
            </li>
          ))}
        </ol>
      </div>
      <p className="curve__note">
        Illustrative forgetting curve. Each on-time review resets recall and makes the memory last about three times longer.
      </p>
    </div>
  );
}
