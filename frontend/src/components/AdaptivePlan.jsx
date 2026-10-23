import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import {
    Sparkles, Clock, ArrowRight, Brain, RotateCcw, Lock, Layers, ChevronDown, Info, Loader2, GitBranch, Scale,
} from 'lucide-react';
import { getLearningPlan } from '../api';

/*
 * The learning engine's plan: what to learn next and why, what follows, the
 * learner's mastery per topic (with how well each estimate is supported), and
 * topics waiting on a foundation. Re-fetched whenever the page regains focus,
 * so it adapts as answers come in.
 */

const LAYERS = {
    foundation: { label: 'Foundation', hint: 'Ideas that unlock other ideas', color: '#B07A52' },
    expansion: { label: 'Expansion', hint: 'Breadth and connections', color: '#C8A288' },
    completeness: { label: 'Completeness', hint: 'Details and edge cases', color: '#A99383' },
    retention: { label: 'Retention', hint: 'Keep it from fading', color: '#5E8C6A' },
};

const STATUS = {
    strong: { label: 'Strong', color: '#4f8a5b' },
    developing: { label: 'Developing', color: '#C8A288' },
    weak: { label: 'Weak', color: '#c2674b' },
    untested: { label: 'Untested', color: '#b9aca2' },
};

const pct = (x) => `${Math.round((x || 0) * 100)}%`;

const MasteryBar = ({ value, status }) => (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-[#F1E6DD]">
        <div className="h-full rounded-full transition-all" style={{ width: `${Math.max(3, Math.round((value || 0) * 100))}%`, background: STATUS[status]?.color || '#C8A288' }} />
    </div>
);

const Ring = ({ value, size = 56 }) => {
    const r = (size - 6) / 2;
    const c = 2 * Math.PI * r;
    return (
        <svg width={size} height={size} className="shrink-0 -rotate-90">
            <circle cx={size / 2} cy={size / 2} r={r} stroke="#F1E6DD" strokeWidth="6" fill="none" />
            <circle cx={size / 2} cy={size / 2} r={r} stroke="#C8A288" strokeWidth="6" fill="none" strokeLinecap="round"
                strokeDasharray={c} strokeDashoffset={c * (1 - (value || 0))} />
            <text x="50%" y="50%" dominantBaseline="central" textAnchor="middle" className="rotate-90 fill-[#4A3B32] text-[13px] font-bold"
                style={{ transformOrigin: 'center' }}>{pct(value)}</text>
        </svg>
    );
};

const AdaptivePlan = ({ projectId, selectedDocuments, onLearn, onPractise, colors = {} }) => {
    const { card = '#ffffff', cardBorder = '#E6D5CC', bodyText = '#4A3B32', mutedText = '#8a6a5c' } = colors;
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [showAll, setShowAll] = useState(false);
    const [showHow, setShowHow] = useState(false);

    const load = useCallback(async () => {
        try {
            setError('');
            const res = await getLearningPlan(projectId, { horizon: 8, documents: selectedDocuments });
            setData(res);
        } catch (e) {
            setError(e?.response?.data?.detail || 'Could not work out your plan right now.');
        } finally {
            setLoading(false);
        }
    }, [projectId, selectedDocuments]);

    useEffect(() => { load(); }, [load]);
    // Answers given elsewhere change the plan: refresh when the page comes back
    useEffect(() => {
        const onFocus = () => { if (document.visibilityState === 'visible') load(); };
        window.addEventListener('focus', onFocus);
        document.addEventListener('visibilitychange', onFocus);
        return () => { window.removeEventListener('focus', onFocus); document.removeEventListener('visibilitychange', onFocus); };
    }, [load]);

    const byLayer = useMemo(() => {
        const groups = { foundation: [], expansion: [], completeness: [], retention: [] };
        for (const row of data?.profile || []) (groups[row.layer] || groups.expansion).push(row);
        return groups;
    }, [data]);

    if (loading) {
        return (
            <div className="mb-6 flex items-center gap-3 rounded-2xl border p-5" style={{ background: card, borderColor: cardBorder, color: mutedText }}>
                <Loader2 className="h-5 w-5 animate-spin text-[#C8A288]" /> Working out the best next step for you…
            </div>
        );
    }
    if (error || !data?.next) {
        if (!error && !data?.profile?.length) return null;
        return (
            <div className="mb-6 rounded-2xl border p-5 text-sm" style={{ background: card, borderColor: cardBorder, color: mutedText }}>
                {error || "You've reached your target on every topic. Reviews will show up here when something starts to fade."}
            </div>
        );
    }

    const next = data.next;
    const then = (data.sequence || []).slice(1, 6);
    const s = data.summary || {};

    return (
        <div className="mb-8 space-y-4">
            {/* Up next */}
            <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                className="rounded-3xl border p-5 md:p-6 shadow-sm" style={{ background: card, borderColor: cardBorder }}>
                <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wide text-[#C8A288]">
                    <Sparkles className="h-4 w-4" /> {next.kind === 'review' ? 'Review next' : 'Learn next'}
                </div>
                <div className="mt-3 flex items-start gap-4">
                    <Ring value={next.mastery} />
                    <div className="min-w-0 flex-1">
                        <h3 className="text-xl md:text-2xl font-bold leading-tight" style={{ color: bodyText }}>{next.topic}</h3>
                        <div className="mt-1.5 flex flex-wrap items-center gap-2 text-xs" style={{ color: mutedText }}>
                            <span className="rounded-full px-2 py-0.5 font-semibold text-white" style={{ background: LAYERS[next.layer]?.color }}>{LAYERS[next.layer]?.label}</span>
                            <span className="inline-flex items-center gap-1"><Clock className="h-3 w-3" /> about {Math.round(next.minutes)} min</span>
                            <span>· {next.status === 'untested' ? 'new to you' : `${STATUS[next.status]?.label} · ${next.confidence}`}</span>
                        </div>
                    </div>
                </div>
                <ul className="mt-4 space-y-1.5">
                    {next.why.map((w) => (
                        <li key={w} className="flex gap-2 text-sm leading-relaxed" style={{ color: bodyText }}>
                            <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-[#C8A288]" />{w}
                        </li>
                    ))}
                </ul>
                <div className="mt-5 flex flex-col gap-2 sm:flex-row">
                    {next.kind === 'review' ? (
                        <button onClick={() => onPractise?.(next.topic)}
                            className="flex flex-1 items-center justify-center gap-2 rounded-2xl bg-[#C8A288] px-4 py-3 font-semibold text-white hover:bg-[#B08B72]">
                            <RotateCcw className="h-4 w-4" /> Review it now
                        </button>
                    ) : (
                        <>
                            <button onClick={() => onLearn?.(next.topic)}
                                className="flex flex-1 items-center justify-center gap-2 rounded-2xl bg-[#C8A288] px-4 py-3 font-semibold text-white hover:bg-[#B08B72]">
                                <Brain className="h-4 w-4" /> Learn it
                            </button>
                            <button onClick={() => onPractise?.(next.topic)}
                                className="flex flex-1 items-center justify-center gap-2 rounded-2xl border-2 border-[#C8A288] px-4 py-3 font-semibold hover:bg-[#FDF6F0]" style={{ color: bodyText }}>
                                I know it — test me <ArrowRight className="h-4 w-4" />
                            </button>
                        </>
                    )}
                </div>
            </motion.div>

            {/* Then */}
            {then.length > 0 && (
                <div className="rounded-2xl border" style={{ background: card, borderColor: cardBorder }}>
                    <div className="px-5 pt-4 text-xs font-bold uppercase tracking-wide" style={{ color: mutedText }}>Then</div>
                    <ol className="divide-y divide-[#F1E6DD]">
                        {then.map((item, i) => (
                            <li key={item.topic}>
                                <button onClick={() => (item.kind === 'review' ? onPractise : onLearn)?.(item.topic)}
                                    className="flex w-full items-center gap-3 px-5 py-3 text-left hover:bg-[#FDF6F0]/60">
                                    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white" style={{ background: LAYERS[item.layer]?.color }}>{i + 2}</span>
                                    <span className="min-w-0 flex-1">
                                        <span className="block truncate font-semibold" style={{ color: bodyText }}>{item.kind === 'review' && <RotateCcw className="mr-1 inline h-3.5 w-3.5 text-[#5E8C6A]" />}{item.topic}</span>
                                        <span className="block truncate text-xs" style={{ color: mutedText }}>{item.reason}</span>
                                    </span>
                                    <span className="shrink-0 text-xs tabular-nums" style={{ color: mutedText }}>{Math.round(item.minutes)} min</span>
                                </button>
                            </li>
                        ))}
                    </ol>
                </div>
            )}

            {/* Waiting on a foundation */}
            {data.blocked?.length > 0 && (
                <div className="rounded-2xl border p-4" style={{ background: card, borderColor: cardBorder }}>
                    <div className="mb-2 flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide" style={{ color: mutedText }}>
                        <Lock className="h-3.5 w-3.5" /> Waiting on a foundation
                    </div>
                    <div className="space-y-1.5 text-sm" style={{ color: bodyText }}>
                        {data.blocked.slice(0, 3).map((b) => (
                            <p key={b.topic}><b>{b.topic}</b> <span style={{ color: mutedText }}>needs</span> {b.needs.join(', ')}</p>
                        ))}
                    </div>
                </div>
            )}

            {/* Knowledge profile */}
            <div className="rounded-2xl border p-5" style={{ background: card, borderColor: cardBorder }}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide" style={{ color: mutedText }}>
                        <Layers className="h-3.5 w-3.5" /> What you know
                    </div>
                    <span className="text-xs" style={{ color: mutedText }}>{pct(s.coverage)} of topics practised · average {pct(s.average_mastery)}</span>
                </div>
                <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-5">
                    {[['strong', s.strong], ['developing', s.developing], ['weak', s.weak], ['untested', s.untested]].map(([k, n]) => (
                        <div key={k} className="rounded-xl border px-3 py-2" style={{ borderColor: cardBorder }}>
                            <div className="text-lg font-bold tabular-nums" style={{ color: STATUS[k].color }}>{n || 0}</div>
                            <div className="text-[11px]" style={{ color: mutedText }}>{STATUS[k].label}</div>
                        </div>
                    ))}
                    <div className="rounded-xl border px-3 py-2" style={{ borderColor: cardBorder }}>
                        <div className="text-lg font-bold tabular-nums text-[#5E8C6A]">{s.due_reviews || 0}</div>
                        <div className="text-[11px]" style={{ color: mutedText }}>Due for review</div>
                    </div>
                </div>

                <button onClick={() => setShowAll((v) => !v)} className="mt-4 flex items-center gap-1 text-sm font-semibold text-[#B08B72] hover:underline">
                    {showAll ? 'Hide topics' : 'See every topic'} <ChevronDown className={`h-4 w-4 transition-transform ${showAll ? 'rotate-180' : ''}`} />
                </button>
                {showAll && (
                    <div className="mt-3 space-y-5">
                        {Object.entries(byLayer).filter(([, rows]) => rows.length).map(([layer, rows]) => (
                            <div key={layer}>
                                <div className="mb-2 flex items-baseline gap-2">
                                    <span className="text-sm font-bold" style={{ color: LAYERS[layer].color }}>{LAYERS[layer].label}</span>
                                    <span className="text-xs" style={{ color: mutedText }}>{LAYERS[layer].hint}</span>
                                </div>
                                <div className="space-y-2">
                                    {rows.map((row) => (
                                        <button key={row.topic} onClick={() => (row.due ? onPractise : onLearn)?.(row.topic)}
                                            className="block w-full rounded-xl px-2 py-1.5 text-left hover:bg-[#FDF6F0]/70">
                                            <div className="flex items-center justify-between gap-3 text-sm">
                                                <span className="min-w-0 truncate" style={{ color: bodyText }}>{row.topic}</span>
                                                <span className="shrink-0 text-xs tabular-nums" style={{ color: mutedText }}>
                                                    {row.status === 'untested' ? 'untested' : `${pct(row.mastery)} · ${row.confidence}`}{row.due ? ' · review' : ''}
                                                </span>
                                            </div>
                                            <div className="mt-1"><MasteryBar value={row.mastery} status={row.status} /></div>
                                        </button>
                                    ))}
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* How it decides */}
            <button onClick={() => setShowHow((v) => !v)} className="flex items-center gap-1.5 text-xs font-semibold" style={{ color: mutedText }}>
                <Info className="h-3.5 w-3.5" /> How Lumina picks your next topic
            </button>
            {showHow && (
                <div className="rounded-2xl border p-4 text-sm leading-relaxed" style={{ background: card, borderColor: cardBorder, color: bodyText }}>
                    <p className="mb-2">Each topic is scored on what it's worth to you right now, divided by the minutes it takes:</p>
                    <ul className="space-y-1">
                        <li className="flex gap-2"><GitBranch className="mt-0.5 h-4 w-4 shrink-0 text-[#C8A288]" /> <span><b>Leverage</b>: how much else it unlocks, and how it helps related topics.</span></li>
                        <li className="flex gap-2"><Scale className="mt-0.5 h-4 w-4 shrink-0 text-[#C8A288]" /> <span><b>Importance</b>: how much of your material it covers.</span></li>
                        <li className="flex gap-2"><Brain className="mt-0.5 h-4 w-4 shrink-0 text-[#C8A288]" /> <span><b>Your gap</b>: how far your answers say you are from mastering it.</span></li>
                        <li className="flex gap-2"><RotateCcw className="mt-0.5 h-4 w-4 shrink-0 text-[#C8A288]" /> <span><b>Fading</b>: topics you knew come back before you forget them.</span></li>
                    </ul>
                    <p className="mt-2" style={{ color: mutedText }}>A topic only comes up once the topics it depends on are solid. Every answer you give updates your estimates, so the plan keeps adjusting.</p>
                </div>
            )}
        </div>
    );
};

export default AdaptivePlan;
