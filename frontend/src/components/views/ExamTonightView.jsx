import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Moon, Clock, Loader2, ArrowRight, ArrowLeft, CheckCircle2, XCircle, Coffee, Printer,
    Sparkles, Lightbulb, AlertTriangle, Target, FlaskConical, RotateCcw, Layers, BookOpen,
} from 'lucide-react';
import { getCramPlan, getCramCard, recordLearning } from '../../api';
import { useAuth } from '../../context/AuthContext';
import { useSettings } from '../../context/SettingsContext';
import { useGamification } from '../../context/GamificationContext';
import { bumpDailyProgress } from '../../utils/dailyProgress';
import { getCharacter, aiName, displayName, pick } from '../../utils/persona';
import { Link } from 'react-router-dom';
import usePlan from '../../hooks/usePlan';
import { isNativeApp } from '../../utils/platform';

const BUDGETS = [
    { minutes: 30, label: '30 min', hint: 'Panic mode' },
    { minutes: 60, label: '1 hour', hint: 'The essentials' },
    { minutes: 120, label: '2 hours', hint: 'Solid pass' },
    { minutes: 180, label: '3 hours', hint: 'Most of it' },
    { minutes: 300, label: '5 hours', hint: 'The whole night' },
    { minutes: 480, label: '8 hours', hint: 'Everything, twice' },
];

const sessionKey = (projectId) => `lumina_cram_${projectId}`;
const loadSession = (projectId) => {
    try { return JSON.parse(localStorage.getItem(sessionKey(projectId)) || 'null'); } catch { return null; }
};
const saveSession = (projectId, s) => {
    try {
        if (s) localStorage.setItem(sessionKey(projectId), JSON.stringify(s));
        else localStorage.removeItem(sessionKey(projectId));
    } catch { /* ignore */ }
};

const fmtMin = (m) => {
    const mins = Math.round(m);
    if (mins < 60) return `${mins} min`;
    const h = Math.floor(mins / 60), r = mins % 60;
    return r ? `${h}h ${r}m` : `${h}h`;
};
const clockAt = (startedAt, offsetMin) => {
    const d = new Date((startedAt || Date.now()) + offsetMin * 60000);
    return d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
};
const errMsg = (e, fallback) => e?.response?.data?.detail || e?.response?.data?.message || fallback;

const daysUntil = (iso) => {
    if (!iso) return null;
    const d = new Date(`${iso}T00:00:00`);
    if (Number.isNaN(d.getTime())) return null;
    const today = new Date(); today.setHours(0, 0, 0, 0);
    return Math.round((d - today) / 86400000);
};

/* ── Skimmable text ───────────────────────────────────────────────────────
 * Card text arrives as plain strings, sometimes one long run-on paragraph
 * ("Performance: Car — …; Fridge — …. Features: …"). These helpers lay it out
 * for fast reading: "Label:" sections become a list with bold labels, "; "
 * separated parts become lines, and "Thing — detail" starts with a bold thing.
 */
const inline = (text) => {
    // **bold** first, then a leading "Thing — " / "Thing: " in bold
    const parts = String(text).split(/(\*\*[^*]+\*\*)/g).filter(Boolean);
    return parts.map((part, i) => {
        if (part.startsWith('**') && part.endsWith('**')) return <strong key={i} className="font-semibold">{part.slice(2, -2)}</strong>;
        if (i === 0) {
            const m = part.match(/^([^—:]{1,40}?)\s*(—|–|:)\s+(.+)$/s);
            if (m) return <React.Fragment key={i}><strong className="font-semibold">{m[1]}</strong> <span className="text-[#5E5046]">{m[2] === ':' ? '' : '— '}</span>{m[3]}</React.Fragment>;
        }
        return <React.Fragment key={i}>{part}</React.Fragment>;
    });
};

// "Label: text. Label2: text" → [{label, body}] when there are at least two labels
const labelledSections = (text) => {
    const re = /(?:^|(?<=[.;!?]\s))([A-Z][A-Za-z0-9()/&' -]{1,40}):\s/g;
    const hits = [...text.matchAll(re)];
    if (hits.length < 2) return null;
    const out = [];
    if (hits[0].index > 0) out.push({ label: '', body: text.slice(0, hits[0].index).trim() });
    hits.forEach((h, i) => {
        const end = i + 1 < hits.length ? hits[i + 1].index : text.length;
        out.push({ label: h[1].trim(), body: text.slice(h.index + h[0].length, end).trim().replace(/[.;]$/, '') });
    });
    return out;
};

const splitParts = (body) => body.split(/;\s+/).map((x) => x.trim()).filter(Boolean);

const RichText = ({ text, className = '' }) => {
    const t = String(text || '').trim();
    if (!t) return null;
    const lines = t.split(/\n+/).map((l) => l.replace(/^\s*(?:[-•*]|\d+[.)])\s+/, '').trim()).filter(Boolean);
    if (lines.length > 1) {
        return (
            <ul className={`space-y-1.5 ${className}`}>
                {lines.map((l, i) => (
                    <li key={i} className="flex gap-2 leading-relaxed"><span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-[#1E5C42]" /><span>{inline(l)}</span></li>
                ))}
            </ul>
        );
    }
    const sections = labelledSections(t);
    if (sections) {
        return (
            <div className={`divide-y divide-[#F1E6DD] rounded-xl border border-[#E6D5CC] bg-white ${className}`}>
                {sections.map((sec, i) => {
                    const parts = splitParts(sec.body);
                    return (
                        <div key={i} className="px-3.5 py-2.5 sm:flex sm:gap-4">
                            {sec.label && <div className="mb-1 shrink-0 text-sm font-bold text-[#163628] sm:mb-0 sm:w-40">{sec.label}</div>}
                            <div className="min-w-0 flex-1 space-y-1 text-[15px] leading-relaxed text-[#163628]">
                                {parts.length > 1
                                    ? parts.map((p, j) => <div key={j}>{inline(p)}</div>)
                                    : <div>{inline(sec.body)}</div>}
                            </div>
                        </div>
                    );
                })}
            </div>
        );
    }
    const parts = splitParts(t);
    if (parts.length >= 3) {
        return (
            <ul className={`space-y-1.5 ${className}`}>
                {parts.map((p, i) => (
                    <li key={i} className="flex gap-2 leading-relaxed"><span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-[#1E5C42]" /><span>{inline(p)}</span></li>
                ))}
            </ul>
        );
    }
    return <p className={`leading-relaxed ${className}`}>{inline(t)}</p>;
};

/** One cram card: the minimum you need to understand a topic and score on it. */
const CramCard = ({ card, tier, onVisualize }) => (
    <div className="space-y-4">
        {card.tldr && (
            <div className="rounded-2xl bg-[#FDF6F0] border border-[#E6D5CC] p-4 text-[#163628] leading-relaxed">
                <span className="text-xs font-bold uppercase tracking-wide text-[#1E5C42] block mb-1">In a nutshell</span>
                {card.tldr}
            </div>
        )}
        {card.key_points?.length > 0 && (
            <div>
                <h4 className="text-sm font-bold text-[#163628] mb-2 flex items-center gap-1.5"><Target className="h-4 w-4 text-[#1E5C42]" /> What carries the marks</h4>
                <ul className="space-y-1.5">
                    {card.key_points.map((p, i) => (
                        <li key={i} className="flex gap-2 leading-relaxed text-[#163628]"><span className="text-[#1E5C42] font-bold">{i + 1}.</span><span>{inline(p)}</span></li>
                    ))}
                </ul>
            </div>
        )}
        {card.formulas?.length > 0 && (
            <div>
                <h4 className="text-sm font-bold text-[#163628] mb-2">Formulas</h4>
                <div className="grid gap-2 sm:grid-cols-2">
                    {card.formulas.map((f, i) => (
                        <div key={i} className="rounded-xl border border-[#E6D5CC] bg-white p-3">
                            <div className="font-mono text-base font-semibold text-[#163628] break-words">{f.expr}</div>
                            {f.meaning && <div className="text-xs text-[#5E5046] mt-1">{f.meaning}</div>}
                        </div>
                    ))}
                </div>
            </div>
        )}
        {tier === 'learn' && card.example && (
            <div>
                <h4 className="text-sm font-bold text-[#163628] mb-2 flex items-center gap-1.5"><BookOpen className="h-4 w-4 text-[#1E5C42]" /> Example</h4>
                <RichText text={card.example} className="text-[#163628]" />
            </div>
        )}
        <div className="grid gap-2 sm:grid-cols-2">
            {card.memory_hook && (
                <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-amber-900">
                    <span className="text-xs font-bold uppercase tracking-wide flex items-center gap-1"><Lightbulb className="h-3.5 w-3.5" /> Memory hook</span>
                    <RichText text={card.memory_hook} className="mt-1 text-sm" />
                </div>
            )}
            {card.exam_tip && (
                <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-emerald-900">
                    <span className="text-xs font-bold uppercase tracking-wide flex items-center gap-1"><Sparkles className="h-3.5 w-3.5" /> Exam tip</span>
                    <RichText text={card.exam_tip} className="mt-1 text-sm" />
                </div>
            )}
        </div>
        {tier === 'learn' && card.mistakes?.length > 0 && (
            <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-rose-900">
                <span className="text-xs font-bold uppercase tracking-wide flex items-center gap-1"><AlertTriangle className="h-3.5 w-3.5" /> Don&apos;t lose marks on</span>
                <ul className="mt-1 text-sm list-disc pl-5 space-y-0.5">{card.mistakes.map((m, i) => <li key={i}>{inline(m)}</li>)}</ul>
            </div>
        )}
        {onVisualize && (
            <button onClick={onVisualize}
                className="inline-flex items-center gap-2 rounded-xl border border-[#E6D5CC] px-3 py-2 text-sm font-semibold text-[#163628] hover:border-[#1E5C42] hover:bg-[#FDF6F0]">
                <FlaskConical className="h-4 w-4 text-[#1E5C42]" /> See it in the Visual Lab
            </button>
        )}
    </div>
);

/** Two quick questions to lock the topic in before moving on. */
const QuickCheck = ({ questions, onDone, onAnswer }) => {
    const [i, setI] = useState(0);
    const [picked, setPicked] = useState(null);
    const [correct, setCorrect] = useState(0);
    const q = questions[i];
    if (!q) return null;
    const answered = picked !== null;
    const choose = (idx) => {
        if (answered) return;
        setPicked(idx);
        if (idx === q.answer_index) setCorrect((c) => c + 1);
        onAnswer?.(idx === q.answer_index);
    };
    const next = () => {
        const total = correct;
        if (i + 1 >= questions.length) { onDone(total, questions.length); return; }
        setI(i + 1); setPicked(null);
    };
    return (
        <div className="rounded-2xl border border-[#E6D5CC] bg-white p-4">
            <div className="text-xs font-bold uppercase tracking-wide text-[#1E5C42] mb-1">Quick check {i + 1}/{questions.length}</div>
            <p className="font-semibold text-[#163628] mb-3">{q.q}</p>
            <div className="grid gap-2">
                {q.options.map((opt, idx) => {
                    const isRight = idx === q.answer_index;
                    const cls = !answered
                        ? 'border-[#E6D5CC] hover:border-[#1E5C42] bg-white'
                        : isRight ? 'border-emerald-400 bg-emerald-50 text-emerald-900'
                            : idx === picked ? 'border-rose-400 bg-rose-50 text-rose-900' : 'border-[#E6D5CC] bg-white opacity-60';
                    return (
                        <button key={idx} onClick={() => choose(idx)} disabled={answered}
                            className={`text-left rounded-xl border-2 px-3 py-2 text-[#163628] transition-colors ${cls}`}>
                            <span className="font-bold mr-2">{String.fromCharCode(65 + idx)}.</span>{opt}
                            {answered && isRight && <CheckCircle2 className="inline h-4 w-4 ml-2 text-emerald-600" />}
                            {answered && idx === picked && !isRight && <XCircle className="inline h-4 w-4 ml-2 text-rose-600" />}
                        </button>
                    );
                })}
            </div>
            {answered && (
                <div className="mt-3 flex flex-col sm:flex-row sm:items-center gap-2 justify-between">
                    <p className="text-sm text-[#5E5046]">{q.why}</p>
                    <button onClick={next} className="shrink-0 inline-flex items-center gap-1 rounded-xl bg-[#1E5C42] px-4 py-2 text-sm font-semibold text-white hover:bg-[#163628]">
                        {i + 1 >= questions.length ? 'Done' : 'Next'} <ArrowRight className="h-4 w-4" />
                    </button>
                </div>
            )}
        </div>
    );
};

/** One printable page with everything you studied tonight. */
const RevisionSheet = ({ timeline, cards, onBack, onRestart }) => {
    const topics = timeline.filter((e) => e.type === 'topic');
    return (
        <div className="h-full overflow-y-auto p-4 md:p-8">
            <div className="max-w-4xl mx-auto">
                <div className="flex flex-wrap items-center justify-between gap-2 mb-4 print:hidden">
                    <button onClick={onBack} className="inline-flex items-center gap-1 rounded-xl border border-[#E6D5CC] px-3 py-2 text-sm font-semibold text-[#163628] hover:border-[#1E5C42]">
                        <ArrowLeft className="h-4 w-4" /> Back
                    </button>
                    <div className="flex gap-2">
                        {onRestart && (
                            <button onClick={onRestart} className="inline-flex items-center gap-1 rounded-xl border border-[#E6D5CC] px-3 py-2 text-sm font-semibold text-[#163628] hover:border-[#1E5C42]">
                                <RotateCcw className="h-4 w-4" /> New plan
                            </button>
                        )}
                        <button onClick={() => window.print()} className="inline-flex items-center gap-1 rounded-xl bg-[#1E5C42] px-3 py-2 text-sm font-semibold text-white hover:bg-[#163628]">
                            <Printer className="h-4 w-4" /> Print / save PDF
                        </button>
                    </div>
                </div>
                <div id="cram-revision-sheet" className="rounded-3xl border border-[#E6D5CC] bg-white p-5 md:p-8">
                    <h2 className="text-2xl font-bold text-[#163628]">Rapid revision sheet</h2>
                    <p className="text-sm text-[#5E5046] mb-4">Read this top to bottom right before the exam. Topics are in the order they build on each other.</p>
                    <div className="grid gap-4 md:grid-cols-2">
                        {topics.map((e, n) => {
                            const c = cards[e.topic];
                            return (
                                <div key={e.topic} className="break-inside-avoid rounded-2xl border border-[#E6D5CC] p-3">
                                    <div className="font-bold text-[#163628]">{n + 1}. {e.topic}</div>
                                    {c ? (
                                        <>
                                            {c.tldr && <p className="text-sm text-[#163628] mt-1">{c.tldr}</p>}
                                            {c.formulas?.length > 0 && (
                                                <div className="mt-1 font-mono text-sm text-[#163628]">{c.formulas.map((f) => f.expr).join('   ·   ')}</div>
                                            )}
                                            {c.memory_hook && <p className="text-xs text-amber-800 mt-1">💡 {c.memory_hook}</p>}
                                        </>
                                    ) : (
                                        <p className="text-xs text-[#5E5046] mt-1">Not studied yet: open it in the plan to fill this in.</p>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                </div>
            </div>
        </div>
    );
};

/**
 * Exam Tonight: tell us how much time you have; get the plan that buys the
 * most marks in that time (foundations first, biggest topics prioritised,
 * what you already know only refreshed), then work through fast cram cards
 * with quick checks, breaks and a final rapid-revision sheet.
 */
const ExamTonightView = ({ projectId, selectedDocuments = [], onTopicMastered, onVisualize }) => {
    const { user } = useAuth();
    const { settings } = useSettings();
    const { earnXP } = useGamification();
    const character = getCharacter(settings.aiCharacter);
    const companion = aiName(settings);
    const name = displayName(settings, user);
    const { plan: myPlan } = usePlan();
    const offerPass = myPlan && myPlan.plan !== 'topper' && !isNativeApp();

    const saved = useMemo(() => loadSession(projectId), [projectId]);
    const [phase, setPhase] = useState(saved?.plan ? 'plan' : 'setup'); // setup | plan | study | revision
    const [minutes, setMinutes] = useState(saved?.minutes || 120);
    const [plan, setPlan] = useState(saved?.plan || null);
    const [startedAt, setStartedAt] = useState(saved?.startedAt || null);
    const [step, setStep] = useState(saved?.step || 0);
    const [done, setDone] = useState(() => new Set(saved?.done || []));
    const [loadingPlan, setLoadingPlan] = useState(false);
    const [error, setError] = useState('');
    const [message, setMessage] = useState('');
    const [cards, setCards] = useState({}); // topic -> card
    const [cardErrors, setCardErrors] = useState({});
    const [checking, setChecking] = useState(false);
    const [cheer, setCheer] = useState('');
    const inflight = useRef({});

    const timeline = plan?.timeline || [];
    const entry = timeline[step];

    useEffect(() => {
        saveSession(projectId, plan ? { plan, minutes, startedAt, step, done: [...done] } : null);
    }, [projectId, plan, minutes, startedAt, step, done]);

    const fetchCard = useCallback((topic, refresh = false) => {
        if (!topic || (inflight.current[topic] && !refresh)) return;
        inflight.current[topic] = true;
        setCardErrors((e) => ({ ...e, [topic]: '' }));
        getCramCard(projectId, topic, selectedDocuments, refresh)
            .then((r) => setCards((c) => ({ ...c, [topic]: r.card })))
            .catch((e) => {
                inflight.current[topic] = false;
                setCardErrors((er) => ({ ...er, [topic]: errMsg(e, 'Could not load this card.') }));
            });
    }, [projectId, selectedDocuments]);

    // Keep the current and the next three topics warm so there's no waiting.
    // While the plan is on screen, the first ones are prepared already.
    useEffect(() => {
        if (phase !== 'study' && phase !== 'plan') return;
        const from = phase === 'plan' ? 0 : step;
        const ahead = phase === 'plan' ? 2 : 4;
        let warmed = 0;
        for (let i = from; i < timeline.length && warmed < ahead; i++) {
            if (timeline[i].type === 'topic') { fetchCard(timeline[i].topic); warmed++; }
        }
    }, [phase, step, timeline, fetchCard]);

    // A card that failed in the background is fetched again when it comes up
    useEffect(() => {
        if (phase === 'study' && entry?.type === 'topic' && cardErrors[entry.topic] && !inflight.current[entry.topic]) {
            fetchCard(entry.topic);
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [phase, step]);

    // The revision sheet needs every studied card
    useEffect(() => {
        if (phase !== 'revision') return;
        timeline.filter((e) => e.type === 'topic' && done.has(e.topic)).forEach((e) => fetchCard(e.topic));
    }, [phase, timeline, done, fetchCard]);

    const buildPlan = async () => {
        setLoadingPlan(true); setError(''); setMessage('');
        try {
            const r = await getCramPlan(projectId, minutes, selectedDocuments);
            if (!r.plan) { setMessage(r.message || 'No plan could be built yet.'); return; }
            setPlan(r.plan); setStep(0); setDone(new Set()); setStartedAt(null);
            setPhase('plan');
        } catch (e) {
            setError(errMsg(e, 'Could not build your plan. Please try again.'));
        } finally {
            setLoadingPlan(false);
        }
    };

    const startStudy = (at = 0) => {
        if (!startedAt) setStartedAt(Date.now());
        setStep(at); setChecking(false); setCheer('');
        setPhase('study');
    };

    // Next topic opens at the top; going back lands at the bottom of the previous
    // topic, where its "next" button was
    const scrollRef = useRef(null);
    const pendingScroll = useRef(null);
    useEffect(() => {
        if (phase !== 'study' || !pendingScroll.current) return;
        const where = pendingScroll.current;
        const apply = () => {
            const el = scrollRef.current;
            if (!el) return;
            const top = where === 'bottom' ? el.scrollHeight : 0;
            el.scrollTo({ top, behavior: 'auto' });
            // Phone app: the page itself may be what scrolls
            if (where === 'top') window.scrollTo({ top: 0 });
            else window.scrollTo({ top: document.documentElement.scrollHeight });
        };
        apply();
        // Again after the card's enter animation has laid out its full height
        const t1 = setTimeout(apply, 120);
        const t2 = setTimeout(apply, 450);
        const t3 = setTimeout(() => { apply(); pendingScroll.current = null; }, 800);
        return () => { clearTimeout(t1); clearTimeout(t2); clearTimeout(t3); };
    }, [phase, step]);

    const prevTopicIndex = (() => {
        for (let i = step - 1; i >= 0; i--) if (timeline[i]?.type === 'topic') return i;
        return -1;
    })();
    const goBack = () => {
        if (prevTopicIndex < 0) return;
        setChecking(false); setCheer('');
        pendingScroll.current = 'bottom';
        setStep(prevTopicIndex);
    };

    const advance = (topicDone) => {
        pendingScroll.current = 'top';
        if (topicDone && entry?.type === 'topic') {
            setDone((d) => new Set(d).add(entry.topic));
            if (entry.tier === 'learn') onTopicMastered?.(entry.topic);
            bumpDailyProgress(user?.id, { cards: 1, minutes: Math.round(entry.minutes) });
            earnXP('sprint', { topic: entry.topic });
        }
        setChecking(false); setCheer('');
        if (step + 1 >= timeline.length || timeline[step + 1]?.type === 'revision') {
            setStep(timeline.length - 1);
            setPhase('revision');
        } else {
            setStep(step + 1);
        }
    };

    const resetPlan = () => {
        setPlan(null); setStep(0); setDone(new Set()); setStartedAt(null); setCards({});
        inflight.current = {};
        setPhase('setup');
    };

    // ---------------------------------------------------------------- setup
    if (phase === 'setup') {
        const days = daysUntil(settings.examDate);
        return (
            <div className="h-full overflow-y-auto p-4 md:p-8">
                <div className="max-w-3xl mx-auto">
                    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
                        className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-[#163628] via-[#1b4331] to-[#0f271c] p-6 md:p-8 text-white shadow-xl">
                        <div className="absolute -right-10 -top-10 h-48 w-48 rounded-full bg-[#D3EE6A]/20 blur-3xl" />
                        <div className="relative flex items-center gap-2 text-[#D3EE6A] text-sm font-semibold">
                            <Moon className="h-4 w-4" /> Exam Tonight
                        </div>
                        <h2 className="relative mt-2 text-3xl md:text-4xl font-bold leading-tight">
                            Short on time? Learn what <em>matters</em>, in the right order.
                        </h2>
                        <p className="relative mt-2 text-white/80 max-w-xl">
                            Tell {companion} how long you have. You&apos;ll get a plan that starts with the foundations everything else
                            builds on, puts the biggest topics first, skips what you already know, and ends with a one-page revision sheet.
                        </p>
                        {days !== null && days >= 0 && days <= 30 && (
                            <div className="relative mt-3 inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-sm">
                                <Clock className="h-4 w-4" /> {settings.examName || 'Exam'} {days === 0 ? 'is today' : days === 1 ? 'is tomorrow' : `in ${days} days`}
                            </div>
                        )}
                    </motion.div>

                    <div className="mt-5 rounded-3xl border border-[#E6D5CC] bg-white p-5 md:p-6">
                        <h3 className="text-lg font-bold text-[#163628]">How much time do you have?</h3>
                        <div className="mt-3 grid grid-cols-2 sm:grid-cols-3 gap-2">
                            {BUDGETS.map((b) => (
                                <button key={b.minutes} onClick={() => setMinutes(b.minutes)}
                                    className={`rounded-2xl border-2 px-3 py-3 text-left transition-colors ${minutes === b.minutes ? 'border-[#1E5C42] bg-[#FDF6F0]' : 'border-[#E6D5CC] bg-white hover:border-[#1E5C42]'}`}>
                                    <div className="font-bold text-[#163628]">{b.label}</div>
                                    <div className="text-xs text-[#5E5046]">{b.hint}</div>
                                </button>
                            ))}
                        </div>
                        <label className="mt-4 block text-sm text-[#5E5046]">
                            Or set it exactly: <b className="text-[#163628]">{fmtMin(minutes)}</b>
                            <input type="range" min={20} max={720} step={10} value={minutes}
                                onChange={(e) => setMinutes(Number(e.target.value))}
                                className="mt-2 w-full accent-[#1E5C42]" aria-label="Study time in minutes" />
                        </label>
                        {error && <p className="mt-3 text-sm text-rose-600">{error}</p>}
                        {message && <p className="mt-3 text-sm text-[#5E5046]">{message}</p>}
                        <button onClick={buildPlan} disabled={loadingPlan}
                            className="mt-4 w-full flex items-center justify-center gap-2 rounded-2xl bg-[#1E5C42] px-4 py-3.5 font-semibold text-white hover:bg-[#163628] disabled:opacity-60 active:scale-[0.99]">
                            {loadingPlan ? <><Loader2 className="h-5 w-5 animate-spin" /> Weighing every topic in your book…</> : <>Build my plan <ArrowRight className="h-5 w-5" /></>}
                        </button>
                        {offerPass && (
                            <Link to="/pricing#pass" className="mt-3 flex items-center justify-center gap-2 rounded-2xl border border-dashed border-[#1E5C42] px-4 py-2.5 text-sm text-[#163628] hover:bg-[#FDF6F0]">
                                <Moon className="h-4 w-4 text-[#1E5C42]" /> Big night? Get Deep cram cards and Topper limits for 48 hours: <b>Exam Night Pass ₹49</b>
                            </Link>
                        )}
                    </div>

                    <div className="mt-4 grid gap-3 sm:grid-cols-3">
                        {[
                            ['Foundations first', 'Topics that unlock the most other topics come first, so each next one is easier.'],
                            ['Biggest marks', 'Topics the book spends the most pages on get priority and more time.'],
                            ['No wasted minutes', 'What you already know gets a 90-second refresh, not a full lesson.'],
                        ].map(([t, d]) => (
                            <div key={t} className="rounded-2xl border border-[#E6D5CC] bg-white p-4">
                                <div className="font-semibold text-[#163628]">{t}</div>
                                <div className="text-sm text-[#5E5046] mt-1">{d}</div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        );
    }

    // ------------------------------------------------------------- revision
    if (phase === 'revision') {
        return (
            <RevisionSheet timeline={timeline} cards={cards}
                onBack={() => setPhase('plan')} onRestart={resetPlan} />
        );
    }

    // ----------------------------------------------------------------- plan
    if (phase === 'plan') {
        const s = plan.summary;
        const studied = timeline.filter((e) => e.type === 'topic' && done.has(e.topic)).length;
        const totalTopics = timeline.filter((e) => e.type === 'topic').length;
        const resumeAt = timeline.findIndex((e) => e.type === 'topic' && !done.has(e.topic));
        return (
            <div className="h-full overflow-y-auto p-4 md:p-8">
                <div className="max-w-3xl mx-auto">
                    <div className="rounded-3xl border border-[#E6D5CC] bg-white p-5 md:p-6">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                            <div>
                                <div className="text-sm font-semibold text-[#1E5C42] flex items-center gap-1"><Moon className="h-4 w-4" /> Your {fmtMin(plan.budget_minutes)} plan</div>
                                <h2 className="text-2xl font-bold text-[#163628] mt-1">
                                    {s.coverage_percent}% of what matters in your book
                                </h2>
                                <p className="text-sm text-[#5E5046] mt-1">
                                    {character.greet(name)} Learn {s.learn}, skim {s.skim}{s.skip ? `, leave ${s.skip} for later` : ''}. Every topic comes after the ones it builds on.
                                </p>
                            </div>
                            <button onClick={resetPlan} className="text-sm font-semibold text-[#5E5046] hover:text-[#163628] inline-flex items-center gap-1">
                                <RotateCcw className="h-4 w-4" /> Change time
                            </button>
                        </div>
                        <div className="mt-4 grid grid-cols-3 gap-2 text-center">
                            {[['Learn', s.learn, 'bg-[#1E5C42] text-white'], ['Skim', s.skim, 'bg-[#FDF6F0] text-[#163628]'], ['Later', s.skip, 'bg-white text-[#5E5046] border border-[#E6D5CC]']].map(([l, v, c]) => (
                                <div key={l} className={`rounded-2xl p-3 ${c}`}>
                                    <div className="text-2xl font-bold">{v}</div>
                                    <div className="text-xs opacity-90">{l}</div>
                                </div>
                            ))}
                        </div>
                        <div className="mt-4 flex flex-col sm:flex-row gap-2">
                            <button onClick={() => startStudy(resumeAt >= 0 ? resumeAt : 0)}
                                className="flex-1 flex items-center justify-center gap-2 rounded-2xl bg-[#1E5C42] px-4 py-3 font-semibold text-white hover:bg-[#163628] active:scale-[0.99]">
                                {studied ? `Continue (${studied}/${totalTopics} done)` : 'Start cramming'} <ArrowRight className="h-5 w-5" />
                            </button>
                            <button onClick={() => setPhase('revision')}
                                className="flex items-center justify-center gap-2 rounded-2xl border-2 border-[#E6D5CC] px-4 py-3 font-semibold text-[#163628] hover:border-[#1E5C42]">
                                <Layers className="h-4 w-4 text-[#1E5C42]" /> Revision sheet
                            </button>
                        </div>
                    </div>

                    <div className="mt-4 rounded-3xl border border-[#E6D5CC] bg-white p-4 md:p-6">
                        <h3 className="text-lg font-bold text-[#163628] mb-2">Tonight&apos;s timeline</h3>
                        <ol className="relative border-l-2 border-[#E6D5CC] ml-3 space-y-3">
                            {timeline.map((e, i) => {
                                if (e.type === 'break') return (
                                    <li key={`b${i}`} className="ml-5 text-sm text-[#5E5046] flex items-center gap-2">
                                        <span className="absolute -left-[9px] h-4 w-4 rounded-full bg-white border-2 border-[#E6D5CC]" />
                                        <Coffee className="h-4 w-4" /> {fmtMin(e.minutes)} break
                                    </li>
                                );
                                if (e.type === 'revision') return (
                                    <li key="rev" className="ml-5 text-sm text-[#163628] flex items-center gap-2 font-semibold">
                                        <span className="absolute -left-[9px] h-4 w-4 rounded-full bg-emerald-500" />
                                        <Layers className="h-4 w-4 text-emerald-600" /> {fmtMin(e.minutes)} rapid revision
                                    </li>
                                );
                                const isDone = done.has(e.topic);
                                return (
                                    <li key={e.topic} className="ml-5">
                                        <span className={`absolute -left-[9px] h-4 w-4 rounded-full ${isDone ? 'bg-emerald-500' : e.tier === 'learn' ? 'bg-[#1E5C42]' : 'bg-white border-2 border-[#1E5C42]'}`} />
                                        <button onClick={() => startStudy(i)} className="w-full text-left group">
                                            <div className="flex items-center gap-2 flex-wrap">
                                                <span className={`font-semibold text-[#163628] group-hover:underline ${isDone ? 'line-through opacity-60' : ''}`}>{e.topic}</span>
                                                <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${e.tier === 'learn' ? 'bg-[#1E5C42] text-white' : 'bg-[#FDF6F0] text-[#5E5046] border border-[#E6D5CC]'}`}>{e.tier}</span>
                                                <span className="text-xs text-[#5E5046] tabular-nums">{fmtMin(e.minutes)}{startedAt ? ` · ${clockAt(startedAt, e.start)}` : ''}</span>
                                            </div>
                                            <div className="text-xs text-[#5E5046] mt-0.5">
                                                {e.reason}{e.prerequisites?.length ? ` · builds on ${e.prerequisites.join(', ')}` : ''}
                                            </div>
                                        </button>
                                    </li>
                                );
                            })}
                        </ol>
                        {plan.skipped?.length > 0 && (
                            <details className="mt-4 text-sm">
                                <summary className="cursor-pointer font-semibold text-[#5E5046]">Left for later ({plan.skipped.length})</summary>
                                <p className="mt-2 text-[#5E5046]">These carry the fewest marks for the time they take. Add more time to include them.</p>
                                <div className="mt-2 flex flex-wrap gap-1.5">
                                    {plan.skipped.map((t) => <span key={t} className="rounded-full border border-dashed border-[#E6D5CC] px-2.5 py-1 text-xs text-[#5E5046]">{t}</span>)}
                                </div>
                            </details>
                        )}
                    </div>
                </div>
            </div>
        );
    }

    // ---------------------------------------------------------------- study
    const topicEntries = timeline.filter((e) => e.type === 'topic');
    const position = topicEntries.findIndex((e) => e === entry) + 1;
    const progress = topicEntries.length ? (done.size / topicEntries.length) * 100 : 0;

    return (
        <div ref={scrollRef} className="h-full overflow-y-auto p-4 md:p-8">
            <div className="max-w-3xl mx-auto">
                <div className="flex items-center gap-3 mb-4">
                    <button onClick={() => setPhase('plan')} className="inline-flex items-center gap-1 rounded-xl border border-[#E6D5CC] px-3 py-1.5 text-sm font-semibold text-[#163628] hover:border-[#1E5C42]">
                        <ArrowLeft className="h-4 w-4" /> Plan
                    </button>
                    <div className="flex-1 h-2 rounded-full bg-[#E6D5CC]/60 overflow-hidden">
                        <div className="h-full bg-[#1E5C42] transition-all" style={{ width: `${progress}%` }} />
                    </div>
                    <span className="text-xs text-[#5E5046] tabular-nums">{done.size}/{topicEntries.length}</span>
                </div>

                <AnimatePresence mode="wait">
                    {entry?.type === 'break' ? (
                        <motion.div key={`break-${step}`} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                            className="rounded-3xl border border-[#E6D5CC] bg-white p-8 text-center">
                            <Coffee className="mx-auto h-12 w-12 text-[#1E5C42]" />
                            <h2 className="mt-3 text-2xl font-bold text-[#163628]">{fmtMin(entry.minutes)} break</h2>
                            <p className="mt-1 text-[#5E5046]">Stand up, drink water, look away from the screen. Your brain files away what you just learned while you rest.</p>
                            <div className="mt-5 flex flex-wrap justify-center gap-2">
                                {prevTopicIndex >= 0 && (
                                    <button onClick={goBack} className="inline-flex items-center gap-1.5 rounded-2xl border border-[#E6D5CC] px-5 py-3 font-semibold text-[#163628] hover:border-[#1E5C42]">
                                        <ArrowLeft className="h-4 w-4" /> Previous
                                    </button>
                                )}
                                <button onClick={() => advance(false)} className="inline-flex items-center gap-2 rounded-2xl bg-[#1E5C42] px-6 py-3 font-semibold text-white hover:bg-[#163628]">
                                    I&apos;m back <ArrowRight className="h-4 w-4" />
                                </button>
                            </div>
                        </motion.div>
                    ) : entry?.type === 'topic' ? (
                        <motion.div key={entry.topic} initial={{ opacity: 0, x: 30 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -30 }}
                            className="rounded-3xl border border-[#E6D5CC] bg-white p-5 md:p-7">
                            <div className="flex flex-wrap items-center gap-2 text-xs text-[#5E5046]">
                                <span className={`rounded-full px-2 py-0.5 font-bold uppercase ${entry.tier === 'learn' ? 'bg-[#1E5C42] text-white' : 'bg-[#FDF6F0] border border-[#E6D5CC]'}`}>{entry.tier}</span>
                                <span>Topic {position} of {topicEntries.length}</span>
                                <span>· {fmtMin(entry.minutes)}</span>
                                {entry.chapter && <span className="flex items-center gap-1">· <BookOpen className="h-3 w-3" /> {entry.chapter}</span>}
                            </div>
                            <h2 className="mt-2 text-2xl md:text-3xl font-bold text-[#163628]">{entry.topic}</h2>
                            <p className="text-sm text-[#5E5046] mt-1">{entry.reason}{entry.prerequisites?.length ? ` · builds on ${entry.prerequisites.join(', ')}` : ''}</p>

                            <div className="mt-5">
                                {cards[entry.topic] ? (
                                    <>
                                        <CramCard card={cards[entry.topic]} tier={entry.tier}
                                            onVisualize={onVisualize ? () => onVisualize(entry.topic) : null} />
                                        <div className="mt-5">
                                            {checking && cards[entry.topic].quick_check?.length > 0 ? (
                                                <QuickCheck key={entry.topic} questions={cards[entry.topic].quick_check}
                                                    onAnswer={(right) => recordLearning(projectId, { topic: entry.topic, correct: right, kind: 'quick_check', source: 'exam_tonight' })}
                                                    onDone={(right, total) => {
                                                        setCheer(right === total ? pick(character.cheers) : right ? 'Nearly there: reread the key points once more.' : pick(character.consoles));
                                                        setChecking(false);
                                                        setDone((d) => new Set(d).add(entry.topic));
                                                    }} />
                                            ) : (
                                                <div className="flex flex-col sm:flex-row gap-2">
                                                    {prevTopicIndex >= 0 && (
                                                        <button onClick={goBack}
                                                            className="order-last sm:order-first flex items-center justify-center gap-1.5 rounded-2xl border border-[#E6D5CC] px-4 py-3 font-semibold text-[#163628] hover:border-[#1E5C42] hover:bg-[#FDF6F0]">
                                                            <ArrowLeft className="h-4 w-4" /> Previous
                                                        </button>
                                                    )}
                                                    {cheer && <p className="flex-1 self-center text-sm font-semibold text-[#1E5C42]">{companion}: {cheer}</p>}
                                                    {!cheer && entry.tier === 'learn' && cards[entry.topic].quick_check?.length > 0 && (
                                                        <button onClick={() => setChecking(true)}
                                                            className="flex-1 rounded-2xl border-2 border-[#1E5C42] px-4 py-3 font-semibold text-[#163628] hover:bg-[#FDF6F0]">
                                                            Quick check ({cards[entry.topic].quick_check.length} Qs)
                                                        </button>
                                                    )}
                                                    <button onClick={() => advance(true)}
                                                        className="flex-1 flex items-center justify-center gap-2 rounded-2xl bg-[#1E5C42] px-4 py-3 font-semibold text-white hover:bg-[#163628]">
                                                        Got it, next <ArrowRight className="h-4 w-4" />
                                                    </button>
                                                </div>
                                            )}
                                        </div>
                                    </>
                                ) : cardErrors[entry.topic] ? (
                                    <div className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-rose-900">
                                        <p>{cardErrors[entry.topic]}</p>
                                        <div className="mt-3 flex gap-2">
                                            <button onClick={() => fetchCard(entry.topic, true)} className="rounded-xl bg-rose-600 px-4 py-2 text-sm font-semibold text-white">Try again</button>
                                            <button onClick={() => advance(false)} className="rounded-xl border border-rose-300 px-4 py-2 text-sm font-semibold">Skip</button>
                                        </div>
                                    </div>
                                ) : (
                                    <div className="flex items-center gap-3 rounded-2xl bg-[#FDF6F0] p-5 text-[#5E5046]">
                                        <Loader2 className="h-5 w-5 animate-spin text-[#1E5C42]" /> {companion} is boiling this topic down to what matters…
                                    </div>
                                )}
                            </div>
                        </motion.div>
                    ) : null}
                </AnimatePresence>
            </div>
        </div>
    );
};

export default ExamTonightView;
