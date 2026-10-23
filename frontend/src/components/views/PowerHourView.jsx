import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
    Zap, Timer, Flame, SkipForward, ArrowRight, RotateCcw, Trophy, Loader2,
    BookOpen, Target, Sparkles, CheckCircle2, XCircle, Brain, FlaskConical,
} from 'lucide-react';
import { getTopicSummary, generateMCQ, recordLearning } from '../../api';
import { useAuth } from '../../context/AuthContext';
import { useSettings } from '../../context/SettingsContext';
import { useGamification } from '../../context/GamificationContext';
import { bumpDailyProgress } from '../../utils/dailyProgress';
import { getCharacter, aiName, displayName, pick } from '../../utils/persona';

const SPRINT_SECONDS = 60 * 60;
const QUESTIONS_PER_TOPIC = 2;
const weakKey = (projectId) => `lumina_weak_${projectId}`;

const loadWeak = (projectId) => {
    try { return JSON.parse(localStorage.getItem(weakKey(projectId)) || '[]'); } catch { return []; }
};
const saveWeak = (projectId, list) => {
    try { localStorage.setItem(weakKey(projectId), JSON.stringify(list.slice(0, 50))); } catch { /* ignore */ }
};

const fmt = (s) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;

const Confetti = () => {
    const pieces = useMemo(() => Array.from({ length: 40 }, (_, i) => ({
        id: i,
        x: (Math.random() - 0.5) * 600,
        y: -(200 + Math.random() * 300),
        r: Math.random() * 720,
        c: ['#C8A288', '#f59e0b', '#10b981', '#e0b48a', '#f472b6', '#60a5fa'][i % 6],
        d: 0.8 + Math.random() * 0.8,
    })), []);
    return (
        <div className="pointer-events-none fixed inset-0 z-[60] flex items-center justify-center overflow-hidden">
            {pieces.map((p) => (
                <motion.span
                    key={p.id}
                    className="absolute h-2.5 w-1.5 rounded-sm"
                    style={{ background: p.c }}
                    initial={{ x: 0, y: 0, opacity: 1, rotate: 0 }}
                    animate={{ x: p.x, y: [0, p.y, p.y + 600], opacity: [1, 1, 0], rotate: p.r }}
                    transition={{ duration: p.d * 2, ease: 'easeOut' }}
                />
            ))}
        </div>
    );
};

/**
 * Power Hour — the fastest way through a book. Each topic is one bite-sized
 * card: a short focused lesson, then quick-fire questions with instant
 * feedback, combos, XP and a companion cheering you on. The next card is
 * prefetched while you work so there is no waiting between topics.
 */
// Prepared cards survive leaving and re-opening Power Hour (per project)
const PREPARED = {};

const PowerHourView = ({ projectId, availableTopics = [], selectedDocuments = [], completedTopics, topicMeta = {}, onTopicMastered, onOpenChat, onVisualize }) => {
    const { user } = useAuth();
    const { settings } = useSettings();
    const { earnXP } = useGamification();
    const character = getCharacter(settings.aiCharacter);
    const companion = aiName(settings);
    const name = displayName(settings, user);

    const [phase, setPhase] = useState('start'); // start | learn | check | done
    const [mode, setMode] = useState('sprint'); // sprint | quick | review
    const [queue, setQueue] = useState([]);
    const [index, setIndex] = useState(0);
    const [secondsLeft, setSecondsLeft] = useState(SPRINT_SECONDS);
    const [qIndex, setQIndex] = useState(0);
    const [picked, setPicked] = useState(null);
    const [reaction, setReaction] = useState('');
    const [combo, setCombo] = useState(0);
    const [stats, setStats] = useState({ cards: 0, answered: 0, correct: 0, bestCombo: 0, xp: 0 });
    const [weak, setWeak] = useState(() => loadWeak(projectId));
    const [celebrate, setCelebrate] = useState(false);
    const [, forceRender] = useState(0);

    // topic -> { summary?, questions?, error? , loading flags }
    const prepared = (PREPARED[projectId] = PREPARED[projectId] || { cache: {}, inflight: {} });
    const cacheRef = useRef(prepared.cache);
    const inflight = useRef(prepared.inflight);
    cacheRef.current = prepared.cache;
    inflight.current = prepared.inflight;

    const mcqDifficulty = ['easy', 'medium', 'hard'].includes(settings.quizDifficulty) ? settings.quizDifficulty : 'medium';

    const mastered = completedTopics instanceof Set ? completedTopics : new Set(completedTopics || []);
    const remainingTopics = availableTopics.filter((t) => !mastered.has(t));

    // Topics arrive in learning order (prerequisites first). Group them into
    // chapters in order of first appearance so students see a clear path.
    const chapters = useMemo(() => {
        const groups = [];
        const byTitle = new Map();
        for (const t of availableTopics) {
            const title = topicMeta[t]?.chapter || 'Topics';
            if (!byTitle.has(title)) {
                const g = { title, topics: [] };
                byTitle.set(title, g);
                groups.push(g);
            }
            byTitle.get(title).topics.push(t);
        }
        return groups;
    }, [availableTopics, topicMeta]);

    // A topic is "ready" once every prerequisite it has here is mastered
    const isReady = (t) => (topicMeta[t]?.prerequisites || []).every((p) => mastered.has(p) || !availableTopics.includes(p));
    const nextUp = remainingTopics.find(isReady) || remainingTopics[0];

    const prefetch = useCallback((topic) => {
        if (!topic || inflight.current[topic]) return;
        inflight.current[topic] = true;
        const entry = (cacheRef.current[topic] = cacheRef.current[topic] || {});
        delete entry.error;
        delete entry.failed;
        let failed = false;
        const summary = getTopicSummary(projectId, topic)
            .then((r) => { entry.summary = r?.summary || ''; })
            .catch(() => { entry.error = 'summary'; failed = true; })
            .finally(() => forceRender((n) => n + 1));
        const questions = generateMCQ(projectId, topic, QUESTIONS_PER_TOPIC, selectedDocuments, mcqDifficulty)
            .then((r) => { entry.questions = r?.questions || []; })
            .catch(() => { entry.questions = []; failed = true; })
            .finally(() => forceRender((n) => n + 1));
        // A failed prefetch may be fetched again when the topic comes up
        Promise.all([summary, questions]).then(() => {
            if (failed) { entry.failed = true; inflight.current[topic] = false; }
        });
    }, [projectId, selectedDocuments, mcqDifficulty]);

    const topic = queue[index];
    const card = topic ? cacheRef.current[topic] || {} : {};

    // Keep the current and next three cards warm; on the start screen, prepare
    // the first ones already so the first card doesn't wait either
    useEffect(() => {
        if (phase === 'learn' || phase === 'check') {
            const current = cacheRef.current[queue[index]];
            if (current?.failed) prefetch(queue[index]);
            for (let i = index; i <= index + 3 && i < queue.length; i++) prefetch(queue[i]);
        } else if (phase === 'start') {
            const first = remainingTopics.length ? remainingTopics : availableTopics;
            first.slice(0, 2).forEach(prefetch);
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [phase, index, queue, prefetch, availableTopics.length, mastered.size]);

    // Sprint timer
    useEffect(() => {
        if (mode !== 'sprint' || (phase !== 'learn' && phase !== 'check')) return;
        const t = setInterval(() => setSecondsLeft((s) => {
            if (s <= 1) { clearInterval(t); setPhase('done'); return 0; }
            return s - 1;
        }), 1000);
        return () => clearInterval(t);
    }, [mode, phase]);

    const start = (m, only) => {
        let list;
        if (only) {
            const left = only.filter((t) => !mastered.has(t));
            list = left.length ? left : only;
        } else if (m === 'review') list = weak.filter((t) => availableTopics.includes(t));
        else list = remainingTopics.length ? remainingTopics : availableTopics;
        if (m === 'quick') list = list.slice(0, 5);
        if (!list.length) return;
        setMode(m);
        setQueue(list);
        setIndex(0);
        setQIndex(0);
        setPicked(null);
        setCombo(0);
        setStats({ cards: 0, answered: 0, correct: 0, bestCombo: 0, xp: 0 });
        setSecondsLeft(SPRINT_SECONDS);
        setReaction(character.greet(name));
        setPhase('learn');
    };

    const nextTopic = useCallback(() => {
        setQIndex(0);
        setPicked(null);
        setReaction('');
        if (index + 1 >= queue.length) setPhase('done');
        else { setIndex((i) => i + 1); setPhase('learn'); }
    }, [index, queue.length]);

    const completeCard = useCallback((hadMistake) => {
        setStats((s) => ({ ...s, cards: s.cards + 1, xp: s.xp + 12 }));
        bumpDailyProgress(user?.id, { cards: 1 });
        earnXP('sprint', { topic });
        // Finished: next time this topic comes up it gets fresh questions
        const doneTopic = topic;
        setTimeout(() => { delete cacheRef.current[doneTopic]; inflight.current[doneTopic] = false; }, 10000);
        let nextWeak = weak.filter((t) => t !== topic);
        if (hadMistake) nextWeak = [topic, ...nextWeak];
        else onTopicMastered?.(topic);
        setWeak(nextWeak);
        saveWeak(projectId, nextWeak);
        setCelebrate(true);
        setTimeout(() => setCelebrate(false), 1600);
    }, [user?.id, earnXP, topic, weak, projectId, onTopicMastered]);

    const mistakesRef = useRef(false);

    const answer = (opt) => {
        if (picked) return;
        const q = card.questions?.[qIndex];
        if (!q) return;
        const correct = opt === q.correct_answer;
        setPicked(opt);
        const newCombo = correct ? combo + 1 : 0;
        setCombo(newCombo);
        if (!correct) mistakesRef.current = true;
        setStats((s) => ({
            ...s,
            answered: s.answered + 1,
            correct: s.correct + (correct ? 1 : 0),
            bestCombo: Math.max(s.bestCombo, newCombo),
        }));
        bumpDailyProgress(user?.id, { answered: 1, correct: correct ? 1 : 0, bestCombo: newCombo });
        recordLearning(projectId, { topic, correct, kind: 'mcq', difficulty: mcqDifficulty, source: 'power_hour' });
        setReaction(correct
            ? (newCombo >= 3 ? `${newCombo}× combo! ${pick(character.cheers)}` : pick(character.cheers))
            : pick(character.consoles));
    };

    const continueCheck = useCallback(() => {
        const total = card.questions?.length || 0;
        if (qIndex + 1 < total) {
            setQIndex((i) => i + 1);
            setPicked(null);
            setReaction('');
        } else {
            completeCard(mistakesRef.current);
            mistakesRef.current = false;
            nextTopic();
        }
    }, [card.questions, qIndex, completeCard, nextTopic]);

    const goCheck = () => {
        mistakesRef.current = false;
        setQIndex(0);
        setPicked(null);
        setReaction('');
        setPhase('check');
    };

    // Keyboard shortcuts: 1-4 / A-D answer, Enter or → continue
    useEffect(() => {
        const onKey = (e) => {
            if (['INPUT', 'TEXTAREA'].includes(e.target?.tagName)) return;
            if (phase === 'learn' && (e.key === 'Enter' || e.key === 'ArrowRight')) { e.preventDefault(); goCheck(); }
            else if (phase === 'check') {
                const q = card.questions?.[qIndex];
                if (!picked && q) {
                    const idx = '1234'.indexOf(e.key) >= 0 ? '1234'.indexOf(e.key) : 'abcd'.indexOf(e.key.toLowerCase());
                    if (idx >= 0 && q.options[idx]) answer(q.options[idx].option);
                } else if (picked && (e.key === 'Enter' || e.key === 'ArrowRight')) { e.preventDefault(); continueCheck(); }
            }
        };
        window.addEventListener('keydown', onKey);
        return () => window.removeEventListener('keydown', onKey);
    });

    // ───────────────────────────── Screens ─────────────────────────────

    if (!availableTopics.length) {
        return (
            <div className="h-full flex items-center justify-center p-6">
                <div className="max-w-md text-center">
                    <div className="text-5xl mb-4">📚</div>
                    <h2 className="text-2xl font-bold text-[#4A3B32] mb-2">No topics yet</h2>
                    <p className="text-[#8a6a5c]">Select a ready document in the sidebar (or wait for processing to finish). {companion} will break it into bite-sized topics for you.</p>
                </div>
            </div>
        );
    }

    if (phase === 'start') {
        const est = Math.min(60, remainingTopics.length * 4);
        return (
            <div className="h-full overflow-y-auto p-4 md:p-8">
                <div className="max-w-3xl mx-auto">
                    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                        className="relative overflow-hidden rounded-3xl border border-[#E6D5CC] bg-white p-6 md:p-10 text-center">
                        <div className="pointer-events-none absolute -top-20 left-1/2 h-64 w-64 -translate-x-1/2 rounded-full bg-[#C8A288]/20 blur-3xl" />
                        <motion.div animate={{ rotate: [0, -8, 8, 0] }} transition={{ repeat: Infinity, duration: 3 }}
                            className="relative mx-auto mb-4 h-20 w-20 rounded-3xl bg-gradient-to-br from-[#C8A288] to-[#e8c9a8] flex items-center justify-center shadow-xl shadow-[#C8A288]/30">
                            <Zap className="h-10 w-10 text-white fill-white" />
                        </motion.div>
                        <h1 className="relative text-3xl md:text-4xl font-bold text-[#4A3B32]">Power Hour</h1>
                        <p className="relative mt-2 text-[#8a6a5c] text-lg">Bite-sized lessons + instant quizzes. Swipe through your whole book.</p>

                        <div className="relative mt-6 grid grid-cols-3 gap-3 text-left">
                            {[
                                [BookOpen, `${availableTopics.length}`, 'topics'],
                                [CheckCircle2, `${mastered.size}`, 'mastered'],
                                [Timer, `~${est || 4} min`, 'to finish'],
                            ].map(([Icon, v, l]) => (
                                <div key={l} className="rounded-2xl border border-[#E6D5CC] bg-[#FDF6F0] p-3">
                                    <Icon className="h-4 w-4 text-[#C8A288]" />
                                    <div className="mt-1 text-xl font-bold text-[#4A3B32]">{v}</div>
                                    <div className="text-xs text-[#8a6a5c]">{l}</div>
                                </div>
                            ))}
                        </div>
                        <div className="relative mt-3 h-2 overflow-hidden rounded-full bg-[#E6D5CC]/60">
                            <div className="h-full rounded-full bg-gradient-to-r from-[#C8A288] to-emerald-400" style={{ width: `${(mastered.size / availableTopics.length) * 100}%` }} />
                        </div>

                        <div className="relative mt-8 grid gap-3 sm:grid-cols-3">
                            <button onClick={() => start('sprint')}
                                className="sm:col-span-3 flex items-center justify-center gap-2 rounded-2xl bg-[#C8A288] px-6 py-4 text-lg font-bold text-white shadow-lg shadow-[#C8A288]/30 transition-all hover:bg-[#B08B72] active:scale-95">
                                <Timer className="h-5 w-5" /> Start 60-minute sprint
                            </button>
                            <button onClick={() => start('quick')}
                                className="sm:col-span-2 flex items-center justify-center gap-2 rounded-2xl border-2 border-[#E6D5CC] bg-white px-4 py-3 font-semibold text-[#4A3B32] hover:border-[#C8A288] active:scale-95">
                                <Zap className="h-4 w-4 text-[#C8A288]" /> Quick 5 (≈15 min)
                            </button>
                            <button onClick={() => start('review')} disabled={!weak.some((t) => availableTopics.includes(t))}
                                className="flex items-center justify-center gap-2 rounded-2xl border-2 border-[#E6D5CC] bg-white px-4 py-3 font-semibold text-[#4A3B32] hover:border-[#C8A288] disabled:opacity-40 active:scale-95">
                                <RotateCcw className="h-4 w-4 text-[#C8A288]" /> Fix weak spots ({weak.filter((t) => availableTopics.includes(t)).length})
                            </button>
                        </div>
                        <p className="relative mt-4 hidden md:block text-xs text-[#8a6a5c]">Tip: use keys <b>1–4</b> to answer and <b>Enter</b> to continue.</p>
                    </motion.div>

                    <div className="mt-4 flex items-start gap-3 rounded-2xl border border-[#E6D5CC] bg-white p-4">
                        <span className="text-2xl">{settings.aiAvatar || '✨'}</span>
                        <div className="text-[#4A3B32]">
                            <span className="text-xs font-semibold text-[#C8A288] block">{companion}</span>
                            {character.greet(name)} Each card takes about 3 minutes — {remainingTopics.length ? `${remainingTopics.length} topics left to master.` : 'you have mastered everything — time for a review lap!'}
                            {nextUp && <span className="block mt-1 text-sm">Next up: <b>{nextUp}</b>{topicMeta[nextUp]?.prerequisites?.length ? ` (builds on ${topicMeta[nextUp].prerequisites.slice(0, 2).join(', ')})` : ' — a great starting point'}.</span>}
                        </div>
                    </div>

                    {/* Chapter path */}
                    <div className="mt-4 rounded-3xl border border-[#E6D5CC] bg-white p-4 md:p-6">
                        <div className="flex items-center justify-between mb-1">
                            <h3 className="text-lg font-bold text-[#4A3B32]">Your path</h3>
                            <span className="text-xs text-[#8a6a5c]">Basics first, then what builds on them</span>
                        </div>
                        <div className="divide-y divide-[#E6D5CC]">
                            {chapters.map((ch, ci) => {
                                const done = ch.topics.filter((t) => mastered.has(t)).length;
                                const complete = done === ch.topics.length;
                                return (
                                    <div key={ch.title} className="py-3">
                                        <div className="flex items-center gap-3">
                                            <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-xl text-sm font-bold ${complete ? 'bg-emerald-500 text-white' : 'bg-[#FDF6F0] text-[#C8A288]'}`}>
                                                {complete ? <CheckCircle2 className="h-4 w-4" /> : ci + 1}
                                            </span>
                                            <div className="flex-1 min-w-0">
                                                <div className="font-semibold text-[#4A3B32] truncate">{ch.title}</div>
                                                <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-[#E6D5CC]/60">
                                                    <div className="h-full rounded-full bg-[#C8A288]" style={{ width: `${(done / ch.topics.length) * 100}%` }} />
                                                </div>
                                            </div>
                                            <span className="text-xs tabular-nums text-[#8a6a5c]">{done}/{ch.topics.length}</span>
                                            <button onClick={() => start('sprint', ch.topics)}
                                                className="rounded-xl border border-[#E6D5CC] px-3 py-1.5 text-xs font-semibold text-[#4A3B32] hover:border-[#C8A288] hover:bg-[#FDF6F0]">
                                                {complete ? 'Review' : done ? 'Continue' : 'Start'}
                                            </button>
                                        </div>
                                        <div className="mt-2 ml-11 flex flex-wrap gap-1.5">
                                            {ch.topics.map((t) => {
                                                const m = mastered.has(t);
                                                const next = t === nextUp;
                                                const ready = isReady(t);
                                                return (
                                                    <button key={t} onClick={() => start('sprint', [t])}
                                                        title={topicMeta[t]?.prerequisites?.length ? `Builds on: ${topicMeta[t].prerequisites.join(', ')}` : 'No prerequisites'}
                                                        className={`rounded-full border px-2.5 py-1 text-xs transition-colors ${m ? 'border-emerald-300 bg-emerald-50 text-emerald-700'
                                                            : next ? 'border-[#C8A288] bg-[#C8A288] text-white'
                                                                : ready ? 'border-[#E6D5CC] bg-white text-[#4A3B32] hover:border-[#C8A288]'
                                                                    : 'border-dashed border-[#E6D5CC] bg-white text-[#8a6a5c] hover:border-[#C8A288]'}`}>
                                                        {m ? '✓ ' : next ? '▶ ' : ''}{t}
                                                    </button>
                                                );
                                            })}
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                        <p className="mt-2 text-xs text-[#8a6a5c]">Solid chips are ready to learn; dashed ones build on topics you haven&apos;t mastered yet.</p>
                    </div>
                </div>
            </div>
        );
    }

    if (phase === 'done') {
        const acc = stats.answered ? Math.round((stats.correct / stats.answered) * 100) : 0;
        return (
            <div className="h-full overflow-y-auto p-4 md:p-8">
                <Confetti />
                <div className="max-w-xl mx-auto text-center rounded-3xl border border-[#E6D5CC] bg-white p-8">
                    <Trophy className="mx-auto h-14 w-14 text-[#C8A288]" />
                    <h2 className="mt-3 text-3xl font-bold text-[#4A3B32]">Session complete!</h2>
                    <p className="mt-1 text-[#8a6a5c]">{acc >= 80 ? pick(character.cheers) : acc >= 50 ? 'Solid work — your weak spots are saved for a quick fix.' : pick(character.consoles)}</p>
                    <div className="mt-6 grid grid-cols-2 sm:grid-cols-4 gap-3">
                        {[['Cards', stats.cards], ['Accuracy', `${acc}%`], ['Best combo', `${stats.bestCombo}×`], ['XP', `+${stats.xp}`]].map(([l, v]) => (
                            <div key={l} className="rounded-2xl border border-[#E6D5CC] bg-[#FDF6F0] p-3">
                                <div className="text-2xl font-bold text-[#4A3B32]">{v}</div>
                                <div className="text-xs text-[#8a6a5c]">{l}</div>
                            </div>
                        ))}
                    </div>
                    <div className="mt-6 flex flex-col sm:flex-row gap-3 justify-center">
                        <button onClick={() => setPhase('start')} className="flex items-center justify-center gap-2 rounded-2xl bg-[#C8A288] px-6 py-3 font-semibold text-white hover:bg-[#B08B72]">
                            <Zap className="h-4 w-4" /> Another round
                        </button>
                        {weak.some((t) => availableTopics.includes(t)) && (
                            <button onClick={() => start('review')} className="flex items-center justify-center gap-2 rounded-2xl border-2 border-[#E6D5CC] px-6 py-3 font-semibold text-[#4A3B32] hover:border-[#C8A288]">
                                <RotateCcw className="h-4 w-4" /> Fix weak spots
                            </button>
                        )}
                    </div>
                </div>
            </div>
        );
    }

    // learn / check
    const q = card.questions?.[qIndex];
    const progressPct = ((index + (phase === 'check' ? 0.5 : 0)) / queue.length) * 100;

    return (
        <div className="h-full flex flex-col">
            {celebrate && <Confetti />}
            {/* HUD */}
            <div className="shrink-0 px-4 md:px-8 pt-4">
                <div className="max-w-3xl mx-auto flex items-center gap-3">
                    <button onClick={() => setPhase('done')} className="text-xs text-[#8a6a5c] hover:text-[#4A3B32]">End</button>
                    <div className="flex-1 h-2.5 overflow-hidden rounded-full bg-[#E6D5CC]/60">
                        <motion.div className="h-full rounded-full bg-gradient-to-r from-[#C8A288] to-[#e0b48a]" animate={{ width: `${progressPct}%` }} />
                    </div>
                    <span className="text-xs tabular-nums text-[#8a6a5c]">{index + 1}/{queue.length}</span>
                    {mode === 'sprint' && (
                        <span className={`flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold tabular-nums ${secondsLeft < 300 ? 'bg-red-50 text-red-600' : 'bg-[#FDF6F0] text-[#4A3B32]'}`}>
                            <Timer className="h-3.5 w-3.5" />{fmt(secondsLeft)}
                        </span>
                    )}
                    <AnimatePresence>
                        {combo >= 2 && (
                            <motion.span key={combo} initial={{ scale: 0.5, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ opacity: 0 }}
                                className="flex items-center gap-1 rounded-full bg-orange-50 px-2.5 py-1 text-xs font-bold text-orange-600">
                                <Flame className="h-3.5 w-3.5 fill-orange-400" />{combo}×
                            </motion.span>
                        )}
                    </AnimatePresence>
                </div>
            </div>

            <div className="flex-1 overflow-y-auto px-4 md:px-8 py-4">
                <AnimatePresence mode="wait">
                    <motion.div
                        key={`${index}-${phase}-${qIndex}`}
                        initial={{ opacity: 0, x: 60, rotate: 1 }}
                        animate={{ opacity: 1, x: 0, rotate: 0 }}
                        exit={{ opacity: 0, x: -60, rotate: -1 }}
                        transition={{ duration: 0.25 }}
                        className="max-w-3xl mx-auto"
                    >
                        <div className="rounded-3xl border border-[#E6D5CC] bg-white p-5 md:p-8 shadow-sm">
                            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-[#C8A288]">
                                {phase === 'learn' ? <><BookOpen className="h-4 w-4" /> Learn</> : <><Target className="h-4 w-4" /> Quick check {qIndex + 1}/{card.questions?.length || QUESTIONS_PER_TOPIC}</>}
                            </div>
                            <h2 className="mt-2 text-2xl md:text-3xl font-bold text-[#4A3B32]">{topic}</h2>
                            {(topicMeta[topic]?.chapter || topicMeta[topic]?.prerequisites?.length > 0) && (
                                <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs">
                                    {topicMeta[topic]?.chapter && (
                                        <span className="rounded-full bg-[#FDF6F0] border border-[#E6D5CC] px-2.5 py-1 text-[#8a6a5c]">📖 {topicMeta[topic].chapter}</span>
                                    )}
                                    {topicMeta[topic]?.prerequisites?.length > 0 && (
                                        <span className="rounded-full bg-[#FDF6F0] border border-[#E6D5CC] px-2.5 py-1 text-[#8a6a5c]">
                                            🧩 Builds on: {topicMeta[topic].prerequisites.join(', ')}
                                        </span>
                                    )}
                                </div>
                            )}

                            {phase === 'learn' && (
                                card.summary === undefined && !card.error ? (
                                    <div className="mt-6 space-y-3">
                                        {[90, 75, 85, 60].map((w, i) => <div key={i} className="h-4 rounded-full bg-[#E6D5CC]/50 animate-pulse" style={{ width: `${w}%` }} />)}
                                        <p className="flex items-center gap-2 pt-2 text-sm text-[#8a6a5c]"><Loader2 className="h-4 w-4 animate-spin" /> {companion} is reading your book…</p>
                                    </div>
                                ) : (
                                    <div className="prose prose-lg max-w-none mt-4 text-[#4A3B32] prose-strong:text-[#4A3B32] prose-headings:text-[#4A3B32]">
                                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{card.summary || "Couldn't load this lesson right now. You can still test yourself or skip."}</ReactMarkdown>
                                    </div>
                                )
                            )}

                            {phase === 'check' && (
                                !card.questions ? (
                                    <p className="mt-6 flex items-center gap-2 text-[#8a6a5c]"><Loader2 className="h-4 w-4 animate-spin" /> Cooking up questions…</p>
                                ) : !q ? (
                                    <p className="mt-6 text-[#8a6a5c]">No questions for this one — moving on counts as reviewed.</p>
                                ) : (
                                    <div className="mt-5">
                                        <p className="text-lg font-medium text-[#4A3B32]">{q.question}</p>
                                        <div className="mt-4 grid gap-2.5">
                                            {q.options.map((o, i) => {
                                                const isCorrect = o.option === q.correct_answer;
                                                const isPicked = picked === o.option;
                                                const state = !picked ? 'idle' : isCorrect ? 'correct' : isPicked ? 'wrong' : 'dim';
                                                return (
                                                    <motion.button
                                                        key={o.option}
                                                        whileTap={!picked ? { scale: 0.98 } : {}}
                                                        animate={state === 'wrong' ? { x: [0, -8, 8, -4, 0] } : state === 'correct' && isPicked ? { scale: [1, 1.03, 1] } : {}}
                                                        onClick={() => answer(o.option)}
                                                        className={`flex items-center gap-3 rounded-2xl border-2 px-4 py-3 text-left transition-colors ${state === 'idle' ? 'border-[#E6D5CC] bg-white hover:border-[#C8A288] hover:bg-[#FDF6F0]'
                                                            : state === 'correct' ? 'border-emerald-400 bg-emerald-50'
                                                                : state === 'wrong' ? 'border-red-300 bg-red-50' : 'border-[#E6D5CC] bg-white opacity-50'}`}
                                                    >
                                                        <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-xl text-sm font-bold ${state === 'correct' ? 'bg-emerald-500 text-white' : state === 'wrong' ? 'bg-red-400 text-white' : 'bg-[#FDF6F0] text-[#8a6a5c]'}`}>
                                                            {state === 'correct' ? <CheckCircle2 className="h-4 w-4" /> : state === 'wrong' ? <XCircle className="h-4 w-4" /> : i + 1}
                                                        </span>
                                                        <span className={state === 'correct' ? 'text-emerald-800' : state === 'wrong' ? 'text-red-700' : 'text-[#4A3B32]'}>{o.text}</span>
                                                    </motion.button>
                                                );
                                            })}
                                        </div>
                                        {picked && q.explanation && (
                                            <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
                                                className="mt-4 rounded-2xl border border-[#E6D5CC] bg-[#FDF6F0] p-4 text-sm text-[#4A3B32]">
                                                <span className="font-semibold">Why: </span>{q.explanation}
                                            </motion.div>
                                        )}
                                    </div>
                                )
                            )}
                        </div>
                    </motion.div>
                </AnimatePresence>
            </div>

            {/* Companion + actions */}
            <div className="shrink-0 border-t border-[#E6D5CC] bg-white/80 backdrop-blur px-4 md:px-8 py-3">
                <div className="max-w-3xl mx-auto flex flex-col sm:flex-row sm:items-center gap-3">
                    <div className="flex flex-1 items-center gap-2 min-h-[40px]">
                        <span className="text-2xl">{settings.aiAvatar || '✨'}</span>
                        <AnimatePresence mode="wait">
                            {reaction && (
                                <motion.span key={reaction} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                                    className="text-sm font-medium text-[#4A3B32]">{reaction}</motion.span>
                            )}
                        </AnimatePresence>
                    </div>
                    <div className="flex items-center gap-2">
                        {phase === 'learn' && (
                            <>
                                <button onClick={nextTopic} className="flex items-center gap-1.5 rounded-xl px-3 py-2.5 text-sm text-[#8a6a5c] hover:bg-[#FDF6F0]" title="Skip topic">
                                    <SkipForward className="h-4 w-4" /> Skip
                                </button>
                                {onOpenChat && (
                                    <button onClick={() => onOpenChat(`Explain "${topic}" to me simply, with an example and a memory trick.`)}
                                        className="flex items-center gap-1.5 rounded-xl border border-[#E6D5CC] px-3 py-2.5 text-sm text-[#4A3B32] hover:border-[#C8A288]">
                                        <Brain className="h-4 w-4 text-[#C8A288]" /> <span className="hidden sm:inline">Ask {companion}</span>
                                    </button>
                                )}
                                {onVisualize && (
                                    <button onClick={() => onVisualize(topic)} title="Open an interactive simulation of this topic"
                                        className="flex items-center gap-1.5 rounded-xl border border-[#E6D5CC] px-3 py-2.5 text-sm text-[#4A3B32] hover:border-[#C8A288]">
                                        <FlaskConical className="h-4 w-4 text-[#C8A288]" /> <span className="hidden sm:inline">Visualize</span>
                                    </button>
                                )}
                                <button onClick={goCheck} className="flex items-center gap-2 rounded-xl bg-[#C8A288] px-5 py-2.5 font-semibold text-white shadow-md shadow-[#C8A288]/30 hover:bg-[#B08B72] active:scale-95">
                                    Got it — quiz me <ArrowRight className="h-4 w-4" />
                                </button>
                            </>
                        )}
                        {phase === 'check' && (picked || (card.questions && !q)) && (
                            <button onClick={continueCheck} className="flex items-center gap-2 rounded-xl bg-[#C8A288] px-5 py-2.5 font-semibold text-white shadow-md shadow-[#C8A288]/30 hover:bg-[#B08B72] active:scale-95">
                                {qIndex + 1 < (card.questions?.length || 0) ? 'Next question' : <>Next topic <Sparkles className="h-4 w-4" /></>} <ArrowRight className="h-4 w-4" />
                            </button>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default PowerHourView;
