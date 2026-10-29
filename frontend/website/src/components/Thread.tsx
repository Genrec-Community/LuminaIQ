'use client';
// The memory curve continues down the page as one lime thread. It passes through review nodes
// ([data-node] inside the wrapper) and draws itself as you scroll. Under reduced motion it is drawn.
import { useRef, type ReactNode } from 'react';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { usePage } from '@/engine/next';
import { prefersReducedMotion } from '@/engine';

export function Thread({ children }: { children: ReactNode }) {
  const wrap = useRef<HTMLDivElement>(null);
  const svg = useRef<SVGSVGElement>(null);

  usePage(() => {
    const el = wrap.current;
    const s = svg.current;
    if (!el || !s) return;
    const line = s.querySelector<SVGPathElement>('path')!;

    const build = () => {
      const box = el.getBoundingClientRect();
      const nodes = [...el.querySelectorAll<HTMLElement>('[data-node]')].map((n) => {
        const r = n.getBoundingClientRect();
        return { x: r.left + r.width / 2 - box.left, y: r.top + r.height / 2 - box.top };
      });
      s.setAttribute('viewBox', `0 0 ${box.width} ${box.height}`);
      if (!nodes.length) return;
      // Enter at the top right, swoop left between reviews (forgetting), rise back into each node.
      const pts = [{ x: box.width * 0.9, y: 0 }, ...nodes, { x: box.width * 0.55, y: box.height }];
      let d = `M${pts[0].x} ${pts[0].y}`;
      for (let i = 1; i < pts.length; i++) {
        const a = pts[i - 1];
        const b = pts[i];
        const dy = b.y - a.y;
        const sag = -Math.min(box.width * 0.5, 680) * (i % 2 ? 1 : 0.7);
        d += ` C${a.x + sag * 0.2} ${a.y + dy * 0.55}, ${b.x + sag} ${b.y - dy * 0.45}, ${b.x} ${b.y}`;
      }
      line.setAttribute('d', d);
    };
    build();
    const ro = new ResizeObserver(() => {
      build();
      ScrollTrigger.refresh();
    });
    ro.observe(el);

    if (!prefersReducedMotion()) {
      gsap.fromTo(
        line,
        { strokeDashoffset: 1 },
        { strokeDashoffset: 0, ease: 'none', scrollTrigger: { trigger: el, start: 'top 75%', end: 'bottom 85%', scrub: 0.6 } },
      );
      el.querySelectorAll<HTMLElement>('[data-node]').forEach((n) =>
        ScrollTrigger.create({ trigger: n, start: 'top 75%', onEnter: () => n.classList.add('is-on'), onLeaveBack: () => n.classList.remove('is-on') }),
      );
    } else {
      el.querySelectorAll<HTMLElement>('[data-node]').forEach((n) => n.classList.add('is-on'));
    }
    return () => ro.disconnect();
  });

  return (
    <div className="thread" ref={wrap}>
      <svg ref={svg} className="thread__svg" aria-hidden="true" preserveAspectRatio="none">
        <path pathLength={1} />
      </svg>
      {children}
    </div>
  );
}

/** A review node on the thread. `day` is the SM-2 interval it stands for. */
export function Node({ day }: { day: number }) {
  return (
    <span className="node" data-node={day} aria-hidden="true">
      <span className="node__dot" />
      <span className="node__label">
        Review <b>day {day}</b>
      </span>
    </span>
  );
}
