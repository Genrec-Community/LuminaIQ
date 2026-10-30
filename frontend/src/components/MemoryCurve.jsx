import React, { useEffect, useMemo, useRef, useState } from 'react';

/*
 * The signature, shared with the landing page: a forgetting curve.
 * The grey line is what you would still remember if you stopped today; the
 * lime line is what you keep when you do the reviews Lumi schedules. Each
 * review lifts recall back up and makes the memory last longer.
 *
 * With `profile` (the learning engine's topic rows) the curve is the student's
 * own: every studied topic fades from where it is now at its own stability.
 * Without data it falls back to an illustrative curve and says so.
 *
 * Point at it, drag on it, or use the arrow keys to pick a day. At rest the
 * marker walks the curve while it is on screen (never under reduced motion).
 */

const W = 800;
const PAD = { l: 6, r: 6, t: 12, b: 8 };
const REVIEW_AT = 0.9;   // engine model: R = 0.9 ** (t / S)
const GROWTH = 2.4;      // a successful spaced review makes the memory last ~2.4x longer

const ILLUSTRATIVE = { days: 40, reviews: [1, 6, 15, 38], s0: 2.2 };

function illustrative() {
    const { days, reviews, s0 } = ILLUSTRATIVE;
    // Some of a chapter survives without review (savings), so neither curve reaches 0, same as the site's
    const floor = 0.2;
    const once = (t) => floor + (1 - floor) * Math.exp(-t / s0);
    const withReviews = (t) => {
        let k = 0; let last = 0;
        for (const r of reviews) if (t >= r) { k += 1; last = r; }
        return floor + (1 - floor) * Math.exp(-(t - last) / (s0 * 3 ** k));
    };
    return { days, once, withReviews, reviews, personal: false };
}

/** Average recall over the studied topics, without and with scheduled reviews. */
function personal(profile) {
    const topics = (profile || [])
        .filter((r) => r.attempts > 0)
        .map((r) => ({
            p: Math.max(0.05, Math.min(1, r.p_known ?? r.mastery ?? 0.5)),
            s: Math.max(0.5, r.stability_days || 1),
            age: Math.max(0, r.last_seen_days ?? 0),
        }));
    if (topics.length < 2) return null;
    const days = 30;
    const step = 0.1;
    const n = Math.round(days / step);

    // Without reviews: each topic keeps fading from its last study session
    const onceAt = (t) => topics.reduce((a, x) => a + x.p * REVIEW_AT ** ((x.age + t) / x.s), 0) / topics.length;

    // With reviews: a topic is reviewed when the engine would schedule it
    // (after S * (0.5 + 0.5p) days), which resets it and grows its stability
    const sim = topics.map((x) => ({ ...x }));
    const withSeries = new Float64Array(n + 1);
    const reviewDays = new Map();
    for (let i = 0; i <= n; i += 1) {
        const t = i * step;
        let sum = 0;
        for (const x of sim) {
            if (x.age >= x.s * (0.5 + 0.5 * x.p)) {
                const day = Math.max(0, Math.round(t));
                reviewDays.set(day, (reviewDays.get(day) || 0) + 1);
                x.s = Math.min(180, x.s * GROWTH * (0.6 + 0.4 * x.p));
                x.p = Math.min(0.97, x.p + (1 - x.p) * 0.35);
                x.age = 0;
            }
            sum += x.p * REVIEW_AT ** (x.age / x.s);
            x.age += step;
        }
        withSeries[i] = sum / sim.length;
    }
    const withReviews = (t) => withSeries[Math.max(0, Math.min(n, Math.round(t / step)))];
    // Label the busiest review days (at most four) on the axis
    const reviews = [...reviewDays.entries()].sort((a, b) => b[1] - a[1]).slice(0, 4).map(([d]) => d).sort((a, b) => a - b);
    return { days, once: onceAt, withReviews, reviews, personal: true, count: topics.length };
}

const pct = (r) => `${Math.round(r * 100)}%`;

export default function MemoryCurve({ profile, title, note, action, startDay, compact = false, height = 280, titleAs = 'h2' }) {
    const H = height;
    const model = useMemo(() => personal(profile) || illustrative(), [profile]);
    const { days } = model;
    const X = (t) => PAD.l + (t / days) * (W - PAD.l - PAD.r);
    const Y = (r) => PAD.t + (1 - r) * (H - PAD.t - PAD.b);

    const paths = useMemo(() => {
        const line = (fn, jumps) => {
            let d = `M${X(0).toFixed(1)} ${Y(fn(0)).toFixed(1)}`;
            for (let i = 1; i <= days * 10; i += 1) {
                const t = i / 10;
                const y = fn(t);
                // Draw review jumps as clean verticals
                if (jumps && fn(t) - fn(t - 0.1) > 0.02) d += ` L${X(t).toFixed(1)} ${Y(fn(t - 0.1)).toFixed(1)}`;
                d += ` L${X(t).toFixed(1)} ${Y(y).toFixed(1)}`;
            }
            return d;
        };
        return { once: line(model.once, false), rev: line(model.withReviews, true) };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [model, H]);

    const initial = startDay ?? Math.round(days * (model.personal ? 0.47 : 0.3));
    // The marker moves every frame through refs; React re-renders the readout
    // only when the whole day changes (text updates 60x a second are wasteful)
    const [day, setDay] = useState(initial);
    const pos = useRef(initial);
    const markRef = useRef(null);
    const onceRef = useRef(null);
    const revRef = useRef(null);
    const root = useRef(null);
    const plot = useRef(null);
    const manualUntil = useRef(0);

    // Idle walk: only while visible, never with reduced motion
    useEffect(() => {
        const el = root.current;
        if (!el || window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return undefined;
        let raf = 0; let last = 0; let visible = false;
        const tick = (now) => {
            const dt = last ? Math.min(64, now - last) : 16;
            last = now;
            if (performance.now() > manualUntil.current) placeRef.current((pos.current + dt * (days / 16000)) % days);
            raf = requestAnimationFrame(tick);
        };
        const io = new IntersectionObserver(([e]) => {
            if (e.isIntersecting && !visible) { visible = true; last = 0; raf = requestAnimationFrame(tick); }
            if (!e.isIntersecting && visible) { visible = false; cancelAnimationFrame(raf); }
        }, { threshold: 0.2 });
        io.observe(el);
        return () => { io.disconnect(); cancelAnimationFrame(raf); };
    }, [days]);

    function place(d) {
        const prev = pos.current;
        pos.current = d;
        markRef.current?.setAttribute('transform', `translate(${X(d).toFixed(1)} 0)`);
        onceRef.current?.setAttribute('cy', Y(model.once(d)).toFixed(1));
        revRef.current?.setAttribute('cy', Y(model.withReviews(d)).toFixed(1));
        if (Math.floor(prev) !== Math.floor(d)) setDay(d);
    }

    const placeRef = useRef(place);
    placeRef.current = place;

    const pick = (clientX, hold = 3500) => {
        const r = plot.current.getBoundingClientRect();
        const t = ((((clientX - r.left) / r.width) * W - PAD.l) / (W - PAD.l - PAD.r)) * days;
        manualUntil.current = performance.now() + hold;
        place(Math.max(0, Math.min(days - 0.01, t)));
    };
    const onKey = (e) => {
        const stepBy = e.shiftKey ? 5 : 1;
        let d = Math.floor(pos.current);
        if (e.key === 'ArrowRight' || e.key === 'ArrowUp') d = Math.min(days - 1, d + stepBy);
        else if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') d = Math.max(0, d - stepBy);
        else if (e.key === 'Home') d = 0;
        else if (e.key === 'End') d = days - 1;
        else return;
        e.preventDefault();
        manualUntil.current = performance.now() + 6000;
        place(d);
    };

    // Axis labels never collide: keep ones at least 15% of the width apart
    const labels = [];
    for (const r of model.reviews) {
        const prev = labels.length ? labels[labels.length - 1] : (model.personal ? 0 : -Infinity);
        if (r - prev >= days * 0.15 && r <= days * 0.92) labels.push(r);
    }
    const once = model.once(day);
    const rev = model.withReviews(day);
    const whole = Math.floor(day);
    const today = model.once(0);
    // Beside a page's own form (Login) the chart is an aside, so its title need not be a heading
    const Title = titleAs;

    return (
        <section ref={root} className={`lumina-curve ${compact ? 'lumina-curve--compact' : ''}`} aria-label="Memory curve">
            <div className="lumina-curve__head">
                <div>
                    <Title className="lumina-curve__title">
                        {title || (model.personal ? <>What you'll still <em>remember</em></> : <>Why you <em>forget</em>, and the fix</>)}
                    </Title>
                    {model.personal && (
                        <p className="lumina-curve__sub">Across the {model.count} topics you've studied here. You remember about <b>{pct(today)}</b> today.</p>
                    )}
                </div>
                <dl className="lumina-curve__readout">
                    <div><dt>{model.personal ? 'In' : 'Day'}</dt><dd>{whole}{model.personal && <small> d</small>}</dd></div>
                    <div className="lumina-curve__once"><dt>{model.personal ? 'If you stop' : 'Read once'}</dt><dd>{pct(once)}</dd></div>
                    <div className="lumina-curve__rev"><dt>With reviews</dt><dd>{pct(rev)}</dd></div>
                </dl>
            </div>

            <div
                ref={plot}
                className="lumina-curve__plot"
                role="slider"
                tabIndex={0}
                aria-label={model.personal ? 'Days from today' : 'Days since you first read the material'}
                aria-valuemin={0}
                aria-valuemax={days - 1}
                aria-valuenow={whole}
                aria-valuetext={`Day ${whole}: ${model.personal ? 'if you stop' : 'read once'} ${pct(once)}, with reviews ${pct(rev)}`}
                onPointerDown={(e) => pick(e.clientX)}
                onPointerMove={(e) => { if (e.pointerType === 'mouse' || e.buttons) pick(e.clientX); }}
                onKeyDown={onKey}
            >
                <svg viewBox={`0 0 ${W} ${H}`} style={{ aspectRatio: `${W} / ${H}` }} aria-hidden="true">
                    {[0.25, 0.5, 0.75].map((r) => (
                        <line key={r} className="lumina-curve__grid" x1={X(0)} x2={X(days)} y1={Y(r)} y2={Y(r)} />
                    ))}
                    {model.reviews.map((r) => (
                        <line key={r} className="lumina-curve__review" x1={X(r)} x2={X(r)} y1={Y(0)} y2={Y(1)} />
                    ))}
                    <path className="lumina-curve__line lumina-curve__line--once" d={paths.once} pathLength={1} />
                    <path className="lumina-curve__line lumina-curve__line--rev" d={paths.rev} pathLength={1} />
                    <g ref={markRef} transform={`translate(${X(day).toFixed(1)} 0)`}>
                        <line className="lumina-curve__marker" x1={0} x2={0} y1={Y(0)} y2={Y(1)} />
                        <circle ref={onceRef} className="lumina-curve__dot--once" cx={0} cy={Y(once)} r={6} />
                        <circle ref={revRef} className="lumina-curve__dot--rev" cx={0} cy={Y(rev)} r={7} />
                    </g>
                </svg>
                <ol className="lumina-curve__axis" aria-hidden="true">
                    {model.personal && <li style={{ left: 0, translate: '0 0' }}><span>today</span></li>}
                    {labels.map((r) => (
                        <li key={r} style={{ left: `${(X(r) / W) * 100}%` }}>
                            <span className="lumina-curve__rv">Review </span><span>day {r}</span>
                        </li>
                    ))}
                </ol>
            </div>

            <div className="lumina-curve__foot">
                <p className="lumina-curve__note">
                    {note || (model.personal
                        ? 'Estimated from your answers. Each on-time review lifts recall back up and makes it last longer.'
                        : 'Illustrative. Each on-time review lifts recall back up and makes the memory last about three times longer. Answer a few questions and this becomes your own curve.')}
                </p>
                {action}
            </div>
        </section>
    );
}
