// The idle input: t in seconds; x and y in -0.5..0.5, lagged. Moves nothing by itself.
import { gsap } from 'gsap';
import { isTouch, onScroll, prefersReducedMotion } from '@/engine';

export const idle = { t: 0, x: 0, y: 0 };

let started = false;
export function startIdle() {
  if (started || prefersReducedMotion()) return; // idle stays at zero: the concept holds still
  started = true;
  const touch = isTouch();
  const aim = { x: 0, y: 0 };
  if (touch) onScroll(({ velocity }) => { aim.y = gsap.utils.clamp(-0.5, 0.5, velocity / 40); });
  else addEventListener('pointermove', (e) => { aim.x = e.clientX / innerWidth - 0.5; aim.y = e.clientY / innerHeight - 0.5; }, { passive: true });
  gsap.ticker.add((t) => {
    const r = gsap.ticker.deltaRatio(); // same feel at 60 and 120 Hz
    if (touch) aim.y *= Math.pow(0.9, r);
    const k = 1 - Math.pow(0.95, r);
    idle.t = t;
    idle.x += (aim.x - idle.x) * k;
    idle.y += (aim.y - idle.y) * k;
  });
}
