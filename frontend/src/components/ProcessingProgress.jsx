import React, { useEffect, useRef, useState } from 'react';
import { Check, BookOpen } from 'lucide-react';

/*
 * Book processing progress, designed to feel calm and honest:
 *  - one bar for the whole journey (upload → ready), weighted by how long each
 *    step really takes, so it never jumps back to 0 between steps
 *  - it never moves backwards, and while a step is busy it keeps creeping
 *    slowly towards that step's end, so it never looks frozen
 *  - named steps tick off as they finish (seeing what's done keeps people patient)
 *  - soft shimmer and pulse only; both switch off with "reduce motion"
 */

// Each stage owns a slice of the bar: [start, end] in %
const STAGES = {
    uploading: { range: [0, 12], step: 0, label: 'Uploading your book' },
    queued: { range: [12, 13], step: 1, label: 'Waiting for a free reader' },
    pending: { range: [12, 14], step: 1, label: 'Getting ready to read' },
    processing: { range: [13, 24], step: 1, label: 'Reading every page' },
    extracting: { range: [13, 24], step: 1, label: 'Reading every page' },
    chunking: { range: [24, 32], step: 2, label: 'Splitting it into sections' },
    embedding: { range: [32, 82], step: 2, label: 'Learning each section' },
    topics: { range: [82, 93], step: 3, label: 'Finding the key topics' },
    graph: { range: [93, 99], step: 4, label: 'Connecting the ideas' },
    completed: { range: [100, 100], step: 5, label: 'Ready to study' },
    ready: { range: [100, 100], step: 5, label: 'Ready to study' },
};

const STEPS = ['Upload', 'Read', 'Learn', 'Topics', 'Connect'];

/** Overall % for a stage and its own 0-100 progress. */
export const overallPercent = (stage, stagePct = 0) => {
    const s = STAGES[stage] || STAGES.processing;
    const [a, b] = s.range;
    const p = Math.max(0, Math.min(100, Number(stagePct) || 0));
    return a + ((b - a) * p) / 100;
};

/** Friendly detail line, e.g. "Section 12 of 40". */
const detailFor = (stage, message) => {
    if (!message) return '';
    const batch = /Batch (\d+)\/(\d+)/i.exec(message);
    if (stage === 'embedding' && batch) return `Part ${batch[1]} of ${batch[2]}`;
    if (stage === 'uploading') return message;
    const chunks = /Generated (\d+) chunks/i.exec(message);
    if (chunks) return `${chunks[1]} sections found`;
    const chars = /Extracted (\d+) characters/i.exec(message);
    if (chars) return `${Math.round(Number(chars[1]) / 1800).toLocaleString()} pages' worth of text`;
    if (stage === 'queued') return 'Another book is being read first';
    return '';
};

const prefersReducedMotion = () =>
    typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

/**
 * Shown value: eases towards the real progress, never backwards, and while the
 * stage is busy creeps towards (but never reaches) the end of its slice.
 */
const useSmoothProgress = (stage, stagePct) => {
    const target = overallPercent(stage, stagePct);
    const ceiling = stage === 'completed' || stage === 'ready'
        ? 100
        : Math.max(target, (STAGES[stage] || STAGES.processing).range[1] - 0.5);
    const [shown, setShown] = useState(target);
    const shownRef = useRef(target);
    const targetRef = useRef(target);
    const ceilingRef = useRef(ceiling);
    targetRef.current = Math.max(targetRef.current, target);
    ceilingRef.current = Math.max(ceiling, targetRef.current);

    useEffect(() => {
        let raf;
        let last = performance.now();
        const tick = (now) => {
            const dt = Math.min(0.1, (now - last) / 1000);
            last = now;
            const prev = shownRef.current;
            const t = targetRef.current;
            let v = prev;
            if (v < t) {
                v += (t - v) * Math.min(1, dt * 4); // catch up quickly but smoothly
                if (t - v < 0.2) v = t;
            } else {
                v += (ceilingRef.current - v) * dt * 0.06; // slow, asymptotic creep
            }
            v = Math.min(100, Math.max(prev, v));
            shownRef.current = v;
            // Re-render only when the visible value changes (0.1 % steps)
            if (Math.round(v * 10) !== Math.round(prev * 10) || v === 100) setShown(v);
            if (v < 100) raf = requestAnimationFrame(tick);
        };
        raf = requestAnimationFrame(tick);
        return () => cancelAnimationFrame(raf);
    }, []);

    return shown;
};

const Steps = ({ current, done }) => (
    <ol className="mt-3 flex items-center justify-between gap-1" aria-hidden="true">
        {STEPS.map((name, i) => {
            const isDone = done || i < current;
            const isNow = !done && i === current;
            return (
                <li key={name} className="flex flex-1 flex-col items-center gap-1 min-w-0">
                    <span
                        className={`relative flex h-4 w-4 items-center justify-center rounded-full border transition-colors duration-500 ${isDone
                            ? 'border-[#B08B72] bg-[#C8A288] text-white'
                            : isNow
                                ? 'border-[#C8A288] bg-white'
                                : 'border-[#E6D5CC] bg-white'
                            }`}
                    >
                        {isDone && <Check className="h-2.5 w-2.5" strokeWidth={3} />}
                        {isNow && <span className="lumina-step-now h-1.5 w-1.5 rounded-full bg-[#C8A288]" />}
                    </span>
                    <span className={`text-[10px] truncate ${isDone || isNow ? 'text-[#6b4c38] font-semibold' : 'text-[#b8a094]'}`}>
                        {name}
                    </span>
                </li>
            );
        })}
    </ol>
);

/**
 * stage: upload_status or progress-stream stage; stagePct: that stage's 0-100;
 * message: the stream's message; variant: "compact" (document list) or "full".
 */
const ProcessingProgress = ({ stage = 'processing', stagePct = 0, message = '', variant = 'compact', title }) => {
    const value = useSmoothProgress(stage, stagePct);
    const info = STAGES[stage] || STAGES.processing;
    const done = stage === 'completed' || stage === 'ready';
    const detail = detailFor(stage, message);
    const motion = !prefersReducedMotion();
    const pct = Math.floor(value);

    const bar = (
        <div
            className={`relative w-full overflow-hidden rounded-full bg-[#F1E6DD] ${variant === 'full' ? 'h-2.5' : 'h-1.5'}`}
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={pct}
            aria-valuetext={`${info.label}, ${pct}%`}
        >
            <div
                className="relative h-full rounded-full bg-gradient-to-r from-[#E2C9B6] via-[#C8A288] to-[#A9806A]"
                style={{ width: `${Math.max(3, value)}%` }}
            >
                {motion && !done && <span className="lumina-progress-sheen absolute inset-0 rounded-full" />}
                {!done && (
                    <span className="absolute right-0 top-1/2 h-full aspect-square -translate-y-1/2 translate-x-1/2 rounded-full bg-[#FDF6F0] shadow-[0_0_0_2px_#C8A288,0_0_8px_rgba(200,162,136,0.7)]" />
                )}
            </div>
        </div>
    );

    if (variant === 'compact') {
        return (
            <div className="mt-1.5 w-full">
                {bar}
                <div className="mt-1 flex items-center justify-between gap-2 text-[10px]">
                    <span className="truncate font-medium text-[#8a6a5c]">
                        {info.label}{detail ? ` · ${detail}` : ''}
                    </span>
                    <span className="shrink-0 tabular-nums font-semibold text-[#6b4c38]">{done ? 'Ready' : `${pct}%`}</span>
                </div>
            </div>
        );
    }

    return (
        <div className={`w-full rounded-2xl border border-[#E6D5CC] bg-gradient-to-br from-[#FFFBF7] to-[#FDF6F0] p-4 shadow-sm ${done ? 'lumina-progress-done' : ''}`}>
            <div className="flex items-start gap-3">
                <div className={`relative flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${done ? 'bg-[#C8A288] text-white' : 'bg-white text-[#C8A288] border border-[#E6D5CC]'}`}>
                    {done ? <Check className="h-5 w-5" strokeWidth={3} /> : <BookOpen className={`h-5 w-5 ${motion ? 'lumina-book-breathe' : ''}`} />}
                </div>
                <div className="min-w-0 flex-1">
                    {title && <p className="truncate text-xs font-semibold uppercase tracking-wide text-[#a08070]">{title}</p>}
                    <div className="flex items-baseline justify-between gap-3">
                        <p className="truncate font-bold text-[#4A3B32]">{info.label}</p>
                        <p className="shrink-0 tabular-nums text-lg font-bold text-[#6b4c38]">{pct}%</p>
                    </div>
                    <p className="h-4 truncate text-xs text-[#8a6a5c]">
                        {done ? 'Your book is ready. Pick a tool and start studying.' : detail || 'You can keep using the app while this runs.'}
                    </p>
                </div>
            </div>
            <div className="mt-3">{bar}</div>
            <Steps current={info.step} done={done} />
        </div>
    );
};

export default ProcessingProgress;
