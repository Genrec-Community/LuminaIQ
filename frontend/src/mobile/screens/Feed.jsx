import React, { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useLocation, useNavigate } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Heart, MessageCircle, ChevronUp, ChevronDown, Check, X, RotateCcw, Sparkles, Upload, RefreshCw, BookOpen } from 'lucide-react';
import {
    api, getTopics, getDueCards, recordReview, createReviewCard, getFlashcardSets, getFlashcards, recordPerformance,
} from '../../api';
import { useAuth } from '../../context/AuthContext';
import { useSettings } from '../../context/SettingsContext';
import { useGamification } from '../../context/GamificationContext';
import { bumpDailyProgress, getDailyProgress } from '../../utils/dailyProgress';
import { aiName, pick } from '../../utils/persona';
import useFocusTimer from '../../hooks/useFocusTimer';
import { useBooks, coverFor, emojiFor } from '../data';
import { Sheet } from '../ui';
import { addAnswered } from '../GetStarted';
import { tap, notify, setStatusBar } from '../device';

/*
 * The Learn feed: full-screen cards from the student's own books, one swipe
 * at a time (quick questions, flashcards, review cards that are due). Wrong
 * answers go into the spaced-repetition deck so they come back later; streaks,
 * combos and XP make the next swipe feel worth it.
 */

const QUESTIONS_PER_BATCH = 4;
const DAILY_TARGET = 10; // matches the "Answer 10 questions" daily quest
const MILESTONES = { 5: 'Warmed up', 10: 'On a roll', 20: 'Unstoppable', 35: 'Big brain energy', 50: 'Legendary session' };
const PRAISE = ['Nailed it!', 'Yes! 🎯', 'Too easy.', 'Brain: activated.', 'Correct!', 'Big brain move.'];
const COMFORT = ['Close one. It is in your review deck now.', 'Now you will remember it. Saved for review.', 'Mistakes are memory glue. Saved for later.'];

const weakTopics = (projectId) => {
    try { return JSON.parse(localStorage.getItem(`lumina_weak_${projectId}`) || '[]'); } catch { return []; }
};

const plain = (md = '') => md.replace(/[*_`#>]/g, '').replace(/\s+/g, ' ').trim();

const shuffle = (arr) => {
    const a = [...arr];
    for (let i = a.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
};

const Md = ({ children, className = '' }) => (
    <div className={`prose prose-invert max-w-none prose-p:my-1.5 prose-strong:text-white prose-code:text-amber-200 ${className}`}>
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{children || ''}</ReactMarkdown>
    </div>
);

const bg = (projectId) => {
    const [a, b] = coverFor(projectId || '');
    return `radial-gradient(120% 70% at 85% 0%, ${a}cc 0%, transparent 60%), radial-gradient(90% 60% at 0% 100%, ${b}aa 0%, transparent 65%), #08120D`;
};

/** Right-hand actions, Reels style. */
const Rail = ({ saved, onSave, onAsk }) => (
    <div className="absolute bottom-[calc(var(--m-tabbar-h)+var(--m-safe-bottom)+28px)] right-3 z-10 flex flex-col items-center gap-5 text-white">
        <button onClick={onSave} className="m-pressable flex flex-col items-center gap-1" aria-label={saved ? 'Saved for review' : 'Save for review'}>
            <motion.span animate={saved ? { scale: [1, 1.35, 1] } : {}} className="flex h-12 w-12 items-center justify-center rounded-full bg-black/25 backdrop-blur">
                <Heart className="h-7 w-7" fill={saved ? '#ff4d6d' : 'none'} stroke={saved ? '#ff4d6d' : 'currentColor'} />
            </motion.span>
            <span className="text-[11px] font-semibold">{saved ? 'Saved' : 'Save'}</span>
        </button>
        <button onClick={onAsk} className="m-pressable flex flex-col items-center gap-1" aria-label="Ask about this">
            <span className="flex h-12 w-12 items-center justify-center rounded-full bg-black/25 backdrop-blur"><MessageCircle className="h-7 w-7" /></span>
            <span className="text-[11px] font-semibold">Explain</span>
        </button>
    </div>
);

const Caption = ({ card, onOpen }) => (
    <button onClick={onOpen} className="absolute bottom-[calc(var(--m-tabbar-h)+var(--m-safe-bottom)+20px)] left-4 right-20 z-10 flex items-center gap-2 text-left text-white">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-lg" style={{ background: coverFor(card.projectId)[0] }}>{emojiFor(card.bookName)}</span>
        <span className="min-w-0">
            <span className="block truncate text-[13.5px] font-bold">{card.bookName}</span>
            {card.topic && <span className="block truncate text-[12px] text-white/70">#{card.topic.replace(/\s+/g, '')}</span>}
        </span>
    </button>
);

const QuizCard = ({ card, onAnswer, active }) => {
    const [picked, setPicked] = useState(null);
    const [line, setLine] = useState('');
    const correct = picked && picked === card.correct;
    const whyRef = useRef(null);
    // Bring the explanation into view on small screens
    useEffect(() => {
        if (picked) setTimeout(() => whyRef.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' }), 180);
    }, [picked]);
    const choose = (opt) => {
        if (picked) return;
        setPicked(opt);
        const ok = opt === card.correct;
        setLine(ok ? pick(PRAISE) : pick(COMFORT));
        onAnswer(card, ok);
    };
    return (
        // Centred when it fits, scrolls inside the card when it doesn't (small phones)
        <div className="m-card-scroll m-feed-col absolute inset-x-0 bottom-[calc(var(--m-tabbar-h)+var(--m-safe-bottom)+86px)] top-[calc(var(--m-safe-top)+76px)] flex flex-col overflow-y-auto px-5 pr-16">
            <div className="my-auto py-2">
            <span className="mb-3 inline-flex w-fit items-center gap-1.5 rounded-full bg-white/15 px-3 py-1 text-[11px] font-bold uppercase tracking-wider text-white/90">
                <Sparkles className="h-3.5 w-3.5" /> Quick question
            </span>
            <Md className="m-selectable text-[19px] font-bold leading-snug text-white prose-p:text-white">{card.question}</Md>
            <div className="mt-5 space-y-2.5">
                {card.options.map((o) => {
                    const isRight = picked && o.option === card.correct;
                    const isWrongPick = picked === o.option && !isRight;
                    return (
                        <motion.button
                            key={o.option}
                            onClick={() => choose(o.option)}
                            animate={isWrongPick ? { x: [0, -8, 8, -5, 5, 0] } : {}}
                            transition={{ duration: 0.4 }}
                            className="m-pressable flex w-full items-center gap-3 rounded-2xl px-4 py-3.5 text-left text-[15px] font-semibold text-white"
                            style={{
                                background: isRight ? 'rgba(34,197,94,0.9)' : isWrongPick ? 'rgba(239,68,68,0.9)' : 'rgba(255,255,255,0.13)',
                                border: `1px solid ${isRight ? '#4ade80' : isWrongPick ? '#f87171' : 'rgba(255,255,255,0.18)'}`,
                                opacity: picked && !isRight && !isWrongPick ? 0.55 : 1,
                                backdropFilter: 'blur(6px)',
                            }}
                        >
                            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-black/25 text-[13px] font-extrabold">
                                {isRight ? <Check className="h-4 w-4" strokeWidth={3} /> : isWrongPick ? <X className="h-4 w-4" strokeWidth={3} /> : o.option}
                            </span>
                            <span className="min-w-0 flex-1">{plain(o.text)}</span>
                        </motion.button>
                    );
                })}
            </div>
            <AnimatePresence>
                {picked && (
                    <motion.div ref={whyRef} initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} className="mt-4 rounded-2xl bg-black/30 p-4 text-white backdrop-blur">
                        <p className={`text-[15px] font-extrabold ${correct ? 'text-green-300' : 'text-amber-200'}`}>{line}</p>
                        {card.explanation && <Md className="m-selectable mt-1 text-[13.5px] leading-relaxed text-white/85">{card.explanation}</Md>}
                    </motion.div>
                )}
            </AnimatePresence>
            {picked && active && (
                <motion.div className="mt-3 flex items-center justify-center gap-1 text-[12px] font-semibold text-white/70" animate={{ y: [0, -5, 0] }} transition={{ duration: 1.4, repeat: Infinity }}>
                    <ChevronUp className="h-4 w-4" /> Swipe up for the next one
                </motion.div>
            )}
            </div>
        </div>
    );
};

const FlashCard = ({ card, onGrade }) => {
    const [flipped, setFlipped] = useState(false);
    const [graded, setGraded] = useState(null);
    const grade = (ok) => {
        if (graded != null) return;
        setGraded(ok);
        onGrade(card, ok);
    };
    return (
        // Centred when it fits, scrolls inside the card when it doesn't (small phones)
        <div className="m-card-scroll m-feed-col absolute inset-x-0 bottom-[calc(var(--m-tabbar-h)+var(--m-safe-bottom)+86px)] top-[calc(var(--m-safe-top)+76px)] flex flex-col overflow-y-auto px-5 pr-16">
            <div className="my-auto py-2">
            <span className="mb-3 inline-flex w-fit items-center gap-1.5 rounded-full bg-white/15 px-3 py-1 text-[11px] font-bold uppercase tracking-wider text-white/90">
                {card.source === 'review' ? <><RotateCcw className="h-3.5 w-3.5" /> Due for review</> : <><BookOpen className="h-3.5 w-3.5" /> Flashcard</>}
            </span>
            <button onClick={() => { tap(); setFlipped((f) => !f); }} className={`m-flip h-[min(44dvh,360px)] min-h-[220px] w-full text-left ${flipped ? 'is-flipped' : ''}`} aria-label="Flip card">
                <div className="m-flip-inner">
                    <div className="m-flip-face flex flex-col rounded-[26px] border border-white/20 bg-white/12 p-6 text-white backdrop-blur-md" style={{ background: 'rgba(255,255,255,0.12)' }}>
                        <div className="flex flex-1 items-center overflow-y-auto">
                            <Md className="text-[21px] font-bold leading-snug text-white prose-p:text-white">{card.front}</Md>
                        </div>
                        <p className="mt-3 text-center text-[12px] font-semibold text-white/60">Tap to reveal</p>
                    </div>
                    <div className="m-flip-face m-flip-back flex flex-col rounded-[26px] border border-white/25 p-6 text-white" style={{ background: 'rgba(255,255,255,0.2)' }}>
                        <div className="flex flex-1 items-center overflow-y-auto">
                            <Md className="m-selectable text-[17px] leading-relaxed text-white prose-p:text-white">{card.back}</Md>
                        </div>
                    </div>
                </div>
            </button>
            <AnimatePresence>
                {flipped && (
                    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="mt-5 grid grid-cols-2 gap-3">
                        <button onClick={() => grade(false)} disabled={graded != null}
                            className="m-pressable h-14 rounded-2xl text-[15px] font-bold text-white disabled:opacity-60"
                            style={{ background: graded === false ? '#ef4444' : 'rgba(239,68,68,0.28)', border: '1px solid rgba(248,113,113,0.6)' }}>
                            Again
                        </button>
                        <button onClick={() => grade(true)} disabled={graded != null}
                            className="m-pressable h-14 rounded-2xl text-[15px] font-bold text-white disabled:opacity-60"
                            style={{ background: graded === true ? '#22c55e' : 'rgba(34,197,94,0.28)', border: '1px solid rgba(74,222,128,0.6)' }}>
                            Got it
                        </button>
                    </motion.div>
                )}
            </AnimatePresence>
            </div>
        </div>
    );
};

const Milestone = ({ card }) => (
    <div className="flex h-full flex-col items-center justify-center px-8 text-center text-white">
        <motion.div initial={{ scale: 0.3, rotate: -30 }} whileInView={{ scale: 1, rotate: 0 }} transition={{ type: 'spring', damping: 9 }} className="text-[96px]">{card.emoji}</motion.div>
        <h2 className="mt-4 text-[34px] font-extrabold leading-tight">{card.title}</h2>
        <p className="mt-2 text-[16px] text-white/75">{card.body}</p>
        <motion.div className="mt-10 flex items-center gap-1 text-[13px] font-semibold text-white/70" animate={{ y: [0, -6, 0] }} transition={{ duration: 1.4, repeat: Infinity }}>
            <ChevronUp className="h-4 w-4" /> Keep going
        </motion.div>
    </div>
);

const InfoCard = ({ emoji, title, body, action, onAction, icon: Icon }) => (
    <div className="flex h-full flex-col items-center justify-center px-8 text-center text-white">
        <div className="text-[72px]">{emoji}</div>
        <h2 className="mt-4 text-[26px] font-extrabold leading-tight">{title}</h2>
        <p className="mt-2 max-w-xs text-[15px] text-white/75">{body}</p>
        {action && (
            <button onClick={() => { tap('medium'); onAction?.(); }} className="m-pressable mt-7 flex h-13 items-center gap-2 rounded-2xl m-white px-6 py-3.5 text-[15px] font-bold text-[#0F1D16]">
                {Icon && <Icon className="h-5 w-5" />} {action}
            </button>
        )}
    </div>
);

const LoaderCard = ({ book }) => (
    <div className="m-col flex h-full flex-col justify-center px-6 pb-[calc(var(--m-tabbar-h)+60px)] pt-24">
        <p className="mb-5 flex items-center gap-2 text-[14px] font-semibold text-white/80">
            <motion.span animate={{ rotate: 360 }} transition={{ duration: 1.6, repeat: Infinity, ease: 'linear' }}><Sparkles className="h-4 w-4" /></motion.span>
            {book ? `Writing fresh questions from ${book}…` : 'Getting your feed ready…'}
        </p>
        <div className="space-y-3 opacity-60">
            <div className="h-7 w-11/12 rounded-xl bg-white/15" />
            <div className="h-7 w-8/12 rounded-xl bg-white/15" />
            {[0, 1, 2, 3].map((i) => <motion.div key={i} className="h-14 rounded-2xl bg-white/10" animate={{ opacity: [0.4, 0.9, 0.4] }} transition={{ duration: 1.3, repeat: Infinity, delay: i * 0.15 }} />)}
        </div>
    </div>
);

const Feed = () => {
    const navigate = useNavigate();
    const location = useLocation();
    const { user } = useAuth();
    const { settings } = useSettings();
    const { earnXP } = useGamification();
    const { books: allBooks, loading: booksLoading } = useBooks();
    useFocusTimer(user?.id);

    const books = useMemo(() => allBooks.filter((b) => (b.docs || 0) > 0), [allBooks]);
    // Opened from a book ("Learn feed" / book ready): that book only
    const [filter, setFilter] = useState(() => location.state?.bookId || 'all');
    const [cards, setCards] = useState([]);
    const [active, setActive] = useState(0);
    const [generating, setGenerating] = useState(false);
    const [genBook, setGenBook] = useState('');
    const [limitHit, setLimitHit] = useState(false);
    const [failures, setFailures] = useState(0);
    const [saved, setSaved] = useState(() => new Set());
    const [session, setSession] = useState({ answered: 0, correct: 0, combo: 0 });
    const [toast, setToast] = useState(null);
    const [hearts, setHearts] = useState([]);
    const [picker, setPicker] = useState(false);

    const feedRef = useRef(null);
    const topicsRef = useRef({});
    const usedRef = useRef(new Set());
    const rrRef = useRef(0);
    const genRef = useRef(false);
    const runRef = useRef(0); // bumps on filter change so stale batches are dropped
    const lastTap = useRef(0);

    const pool = useMemo(() => (filter === 'all' ? books : books.filter((b) => b.id === filter)), [books, filter]);

    useEffect(() => { setStatusBar(true, '#08120D'); return () => setStatusBar(settings.darkMode, null); }, [settings.darkMode]);

    const activeRef = useRef(0);
    activeRef.current = active;
    const jumpRef = useRef(null);
    const append = useCallback((run, list) => {
        if (run !== runRef.current || !list.length) return;
        setCards((c) => {
            // Waiting on the loader: show the first new card (scroll snap would otherwise stay on the loader)
            if (activeRef.current >= c.length) jumpRef.current = c.length;
            return [...c, ...list];
        });
    }, []);

    useLayoutEffect(() => {
        const i = jumpRef.current;
        if (i == null) return;
        jumpRef.current = null;
        const el = feedRef.current?.querySelector(`section[data-index="${i}"]`);
        if (el) feedRef.current.scrollTo({ top: el.offsetTop });
    }, [cards.length]);

    const topicsFor = async (bookId) => {
        if (!topicsRef.current[bookId]) {
            try { topicsRef.current[bookId] = (await getTopics(bookId))?.all || []; } catch { topicsRef.current[bookId] = []; }
        }
        return topicsRef.current[bookId];
    };

    const generate = useCallback(async () => {
        if (genRef.current || limitHit || !pool.length) return;
        genRef.current = true;
        setGenerating(true);
        const run = runRef.current;
        const book = pool[rrRef.current++ % pool.length];
        setGenBook(book.name);
        try {
            const topics = await topicsFor(book.id);
            const weak = weakTopics(book.id).filter((t) => topics.includes(t));
            const fresh = topics.filter((t) => !usedRef.current.has(`${book.id}|${t}`));
            const choices = fresh.length ? fresh : topics;
            const topic = weak.length && Math.random() < 0.35 ? pick(weak) : (choices.length ? pick(choices) : null);
            if (topic) usedRef.current.add(`${book.id}|${topic}`);
            const res = await api.post('/mcq/generate', {
                project_id: book.id, topic, num_questions: QUESTIONS_PER_BATCH, selected_documents: [], difficulty: 'medium',
            }, { silentLimit: true, timeout: 120000 });
            const qs = (res.data?.questions || []).filter((q) => q?.question && Array.isArray(q.options) && q.options.length >= 2);
            append(run, qs.map((q, n) => ({
                key: `q-${Date.now()}-${n}`, type: 'quiz', projectId: book.id, bookName: book.name, topic: res.data?.topic || topic,
                question: q.question, options: q.options, correct: q.correct_answer, explanation: q.explanation,
            })));
            setFailures(0);
        } catch (e) {
            if (e?.response?.status === 402) {
                setLimitHit(true);
            } else {
                setFailures((f) => f + 1);
            }
        } finally {
            genRef.current = false;
            setGenerating(false);
        }
    }, [pool, limitHit, append]);

    // (Re)build the feed: due reviews and saved flashcards first (instant), questions stream in after
    useEffect(() => {
        if (booksLoading) return;
        const run = ++runRef.current;
        setCards([]); setActive(0); setLimitHit(false); setFailures(0);
        usedRef.current = new Set();
        feedRef.current?.scrollTo({ top: 0 });
        if (!pool.length) return;
        (async () => {
            const names = Object.fromEntries(books.map((b) => [b.id, b.name]));
            const instant = [];
            try {
                const due = await getDueCards(filter === 'all' ? null : filter, 12);
                instant.push(...(due || []).filter((c) => names[c.project_id]).map((c) => ({
                    key: `r-${c.id}`, type: 'flash', source: 'review', id: c.id, projectId: c.project_id, bookName: names[c.project_id],
                    topic: c.topic, front: c.question, back: c.answer,
                })));
            } catch { /* no due cards */ }
            try {
                const sets = (await Promise.all(shuffle(pool).slice(0, 2).map(async (b) => {
                    const list = await getFlashcardSets(b.id).catch(() => []);
                    const set = shuffle(Array.isArray(list) ? list : list?.sets || [])[0];
                    if (!set) return [];
                    const cardsRes = await getFlashcards(set.id).catch(() => []);
                    const items = Array.isArray(cardsRes) ? cardsRes : cardsRes?.cards || [];
                    return shuffle(items).slice(0, 5).map((c, n) => ({
                        key: `f-${set.id}-${n}`, type: 'flash', source: 'set', projectId: b.id, bookName: b.name,
                        topic: set.topic, front: c.front, back: c.back,
                    }));
                }))).flat();
                instant.push(...sets);
            } catch { /* no sets */ }
            append(run, shuffle(instant));
        })();
        generate();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [booksLoading, filter, pool.length]);

    // Track the card on screen; keep a few cards ahead
    useEffect(() => {
        const root = feedRef.current;
        if (!root) return undefined;
        const io = new IntersectionObserver((entries) => {
            entries.forEach((e) => { if (e.isIntersecting) setActive(Number(e.target.dataset.index)); });
        }, { root, threshold: 0.6 });
        root.querySelectorAll('section[data-index]').forEach((el) => io.observe(el));
        return () => io.disconnect();
    }, [cards.length, generating, limitHit]);

    // Keep a few cards ahead, never more (each batch uses the daily question allowance)
    useEffect(() => {
        const ahead = cards.length - active;
        if (ahead <= 3 && ahead >= 0 && !generating && failures < 3) generate();
    }, [active, cards.length, generating, failures, generate]);

    const showToast = (text) => {
        setToast({ text, id: Date.now() });
        setTimeout(() => setToast((t) => (t && Date.now() - t.id >= 1400 ? null : t)), 1500);
    };

    // Daily goal reached: celebrate, and make it OK to stop (no endless-scroll guilt)
    const insertGoalDone = () => {
        notify('success');
        setCards((c) => {
            const at = Math.min(c.length, active + 1);
            const m = { key: `goal-${Date.now()}`, type: 'milestone', emoji: '🎉', title: "Today's goal: done!", body: `Your streak is safe for today. Keep going if you're enjoying it, or come back tomorrow. ${aiName(settings)} will be here.` };
            return [...c.slice(0, at), m, ...c.slice(at)];
        });
    };

    const insertMilestone = (answered) => {
        const title = MILESTONES[answered];
        if (!title || answered === DAILY_TARGET) return;
        notify('success');
        setCards((c) => {
            const at = Math.min(c.length, active + 1);
            const m = { key: `m-${answered}-${Date.now()}`, type: 'milestone', emoji: answered >= 20 ? '🏆' : answered >= 10 ? '🚀' : '🔥', title, body: `${answered} answered this session. ${aiName(settings)} is impressed.` };
            return [...c.slice(0, at), m, ...c.slice(at)];
        });
    };

    const onAnswer = (card, ok) => {
        notify(ok ? 'success' : 'error');
        const next = { answered: session.answered + 1, correct: session.correct + (ok ? 1 : 0), combo: ok ? session.combo + 1 : 0 };
        setSession(next);
        const today = bumpDailyProgress(user?.id, { answered: 1, correct: ok ? 1 : 0, bestCombo: next.combo });
        addAnswered();
        if (today.answered === DAILY_TARGET) insertGoalDone();
        recordPerformance(card.projectId, card.topic || 'General', ok ? 1 : 0, ok ? 0 : 1).catch(() => {});
        if (ok) {
            earnXP('sprint', { topic: card.topic, source: 'feed' });
            if (next.combo >= 3) showToast(`🔥 ${next.combo} in a row!`);
        } else {
            const answer = card.options.find((o) => o.option === card.correct);
            createReviewCard(card.projectId, card.topic || 'General', plain(card.question), `${plain(answer?.text || card.correct)}${card.explanation ? `\n\n${card.explanation}` : ''}`)
                .then(() => setSaved((s) => new Set(s).add(card.key))).catch(() => {});
        }
        insertMilestone(next.answered);
    };

    const onGrade = (card, ok) => {
        notify(ok ? 'success' : 'warning');
        if (card.source === 'review' && card.id) recordReview(card.id, ok ? 4 : 1).catch(() => {});
        if (ok) {
            bumpDailyProgress(user?.id, { cards: 1 });
            earnXP('review', { topic: card.topic, source: 'feed' });
        }
        const answered = session.answered + 1;
        setSession((s) => ({ ...s, answered }));
        insertMilestone(answered);
        // Flashcards move on by themselves
        setTimeout(() => {
            const el = feedRef.current;
            if (el) el.scrollTo({ top: el.scrollTop + el.clientHeight, behavior: 'smooth' });
        }, 650);
    };

    const save = (card) => {
        if (saved.has(card.key) || card.source === 'review') { setSaved((s) => new Set(s).add(card.key)); return; }
        tap('medium');
        setSaved((s) => new Set(s).add(card.key));
        const q = card.type === 'quiz' ? plain(card.question) : plain(card.front);
        const a = card.type === 'quiz' ? plain(card.options.find((o) => o.option === card.correct)?.text || '') : card.back;
        createReviewCard(card.projectId, card.topic || 'General', q, a).catch(() => {});
        showToast('Saved to your review deck');
    };

    const ask = (card) => {
        tap();
        const q = card.type === 'quiz' ? plain(card.question) : plain(card.front);
        navigate(`/project/${card.projectId}?tool=chat&ask=${encodeURIComponent(`Explain this simply, with an example: ${q}`)}`);
    };

    const onDoubleTap = (e, card) => {
        if (e.target.closest('button')) return;
        const now = Date.now();
        if (now - lastTap.current < 300) {
            const rect = e.currentTarget.getBoundingClientRect();
            const h = { id: now, x: e.clientX - rect.left, y: e.clientY - rect.top };
            setHearts((hs) => [...hs, h]);
            setTimeout(() => setHearts((hs) => hs.filter((x) => x.id !== h.id)), 950);
            save(card);
        }
        lastTap.current = now;
    };

    const scrollBy = (dir) => {
        const el = feedRef.current;
        if (el) el.scrollTo({ top: el.scrollTop + dir * el.clientHeight, behavior: 'smooth' });
    };

    const accuracy = session.answered ? Math.round((session.correct / Math.max(1, session.answered)) * 100) : null;
    const daily = getDailyProgress(user?.id);
    const filterBook = books.find((b) => b.id === filter);
    const empty = !booksLoading && !books.length;

    let tail = null;
    if (empty) {
        tail = <InfoCard emoji="📚" title="Your feed needs a book" body="Add a PDF, your notes or some pasted text. Your first cards are ready about a minute later." action="Add a book" icon={Upload} onAction={() => window.dispatchEvent(new Event('lumina-add'))} />;
    } else if (limitHit) {
        tail = <InfoCard emoji="🌙" title="That's today's fresh questions" body={`You used today's free questions. Review cards and flashcards still work, and fresh questions are back tomorrow.`} action="Open your books" icon={BookOpen} onAction={() => navigate('/app/library')} />;
    } else if (failures >= 3) {
        tail = <InfoCard emoji="😵‍💫" title="Couldn't make new cards" body="The connection dropped or your book is still being read. Try again in a moment." action="Try again" icon={RefreshCw} onAction={() => { setFailures(0); }} />;
    } else if (!booksLoading) {
        tail = <LoaderCard book={generating ? genBook : ''} />;
    } else {
        tail = <LoaderCard />;
    }

    return (
        <div className="m-app fixed inset-0 overflow-hidden" style={{ background: '#08120D' }}>
            {/* Top bar */}
            <div className="m-safe-top pointer-events-none absolute inset-x-0 top-0 z-20" style={{ background: 'linear-gradient(to bottom, rgba(0,0,0,0.5), transparent)' }}>
                <div className="pointer-events-auto flex h-14 items-center gap-2 px-4 text-white">
                    <button onClick={() => { tap(); setPicker(true); }} className="m-pressable flex min-w-0 items-center gap-1 text-[18px] font-extrabold">
                        <span className="truncate">{filterBook ? filterBook.name : 'For you'}</span> <ChevronDown className="h-5 w-5 shrink-0" />
                    </button>
                    <div className="flex-1" />
                    {session.combo >= 2 && (
                        <motion.span key={session.combo} initial={{ scale: 1.4 }} animate={{ scale: 1 }} className="rounded-full bg-orange-500/90 px-2.5 py-1 text-[12px] font-extrabold">🔥 x{session.combo}</motion.span>
                    )}
                    {accuracy != null && <span className="rounded-full bg-white/15 px-2.5 py-1 text-[12px] font-bold">{accuracy}% · {session.answered}</span>}
                    <span className="rounded-full bg-white/15 px-2.5 py-1 text-[12px] font-bold tabular-nums">🎯 {Math.min(daily.answered, DAILY_TARGET)}/{DAILY_TARGET}</span>
                </div>
                <div className="mx-4 h-1 overflow-hidden rounded-full bg-white/15" aria-label={`Today's goal: ${daily.answered} of ${DAILY_TARGET} answered`}>
                    <motion.div className="h-full rounded-full" style={{ background: daily.answered >= DAILY_TARGET ? '#4ade80' : 'linear-gradient(90deg, #f59e0b, #f97316)' }}
                        animate={{ width: `${Math.min(100, (daily.answered / DAILY_TARGET) * 100)}%` }} transition={{ type: 'spring', damping: 20 }} />
                </div>
            </div>

            <AnimatePresence>
                {toast && (
                    <motion.div key={toast.id} initial={{ y: -20, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: -20, opacity: 0 }}
                        className="absolute left-1/2 top-[calc(var(--m-safe-top)+64px)] z-30 -translate-x-1/2 rounded-full m-white px-4 py-2 text-[13px] font-bold text-[#0F1D16] shadow-xl">
                        {toast.text}
                    </motion.div>
                )}
            </AnimatePresence>

            <div ref={feedRef} className="m-feed">
                {cards.map((card, i) => (
                    <section key={card.key} data-index={i} className="relative overflow-hidden" style={{ background: bg(card.projectId) }} onClick={(e) => onDoubleTap(e, card)}>
                        {card.type === 'quiz' && <QuizCard card={card} onAnswer={onAnswer} active={i === active} />}
                        {card.type === 'flash' && <FlashCard card={card} onGrade={onGrade} />}
                        {card.type === 'milestone' && <Milestone card={card} />}
                        {(card.type === 'quiz' || card.type === 'flash') && (
                            <>
                                <Rail saved={saved.has(card.key) || card.source === 'review'} onSave={() => save(card)} onAsk={() => ask(card)} />
                                <Caption card={card} onOpen={() => { tap(); navigate(`/app/book/${card.projectId}`); }} />
                            </>
                        )}
                        {hearts.map((h) => (
                            <span key={h.id} className="m-heart text-[90px]" style={{ left: h.x, top: h.y }}>❤️</span>
                        ))}
                    </section>
                ))}
                <section data-index={cards.length} className="relative" style={{ background: bg(pool[0]?.id) }}>{tail}</section>
            </div>

            {/* Up / down for people who prefer tapping */}
            {cards.length > 0 && (
                <div className="absolute right-3 top-1/2 z-10 hidden -translate-y-1/2 flex-col gap-2 sm:flex">
                    <button onClick={() => scrollBy(-1)} aria-label="Previous" className="m-pressable flex h-10 w-10 items-center justify-center rounded-full bg-white/15 text-white"><ChevronUp className="h-5 w-5" /></button>
                    <button onClick={() => scrollBy(1)} aria-label="Next" className="m-pressable flex h-10 w-10 items-center justify-center rounded-full bg-white/15 text-white"><ChevronDown className="h-5 w-5" /></button>
                </div>
            )}

            <Sheet open={picker} onClose={() => setPicker(false)} title="What do you want to learn?">
                <div className="space-y-2">
                    {[{ id: 'all', name: 'For you', sub: 'A mix from all your books' }, ...books.map((b) => ({ id: b.id, name: b.name, sub: `${b.docs} ${b.docs === 1 ? 'file' : 'files'}` }))].map((o) => (
                        <button key={o.id} onClick={() => { tap(); setFilter(o.id); setPicker(false); }}
                            className="m-pressable flex w-full items-center gap-3 rounded-2xl p-3 text-left"
                            style={{ background: filter === o.id ? 'color-mix(in srgb, var(--m-accent) 16%, transparent)' : 'var(--m-soft)' }}>
                            <span className="flex h-11 w-11 items-center justify-center rounded-xl text-xl" style={{ background: o.id === 'all' ? 'var(--m-accent)' : coverFor(o.id)[0] }}>{o.id === 'all' ? '✨' : emojiFor(o.name)}</span>
                            <span className="min-w-0 flex-1">
                                <span className="block truncate text-[15px] font-bold">{o.name}</span>
                                <span className="block text-[12.5px]" style={{ color: 'var(--m-muted)' }}>{o.sub}</span>
                            </span>
                            {filter === o.id && <Check className="h-5 w-5" style={{ color: 'var(--m-accent)' }} />}
                        </button>
                    ))}
                </div>
            </Sheet>
        </div>
    );
};

export default Feed;
