import React, { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { Flame, Play, Moon, MessageSquare, CheckSquare, Layers, Zap, ChevronRight, CalendarClock, Upload } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useSettings } from '../../context/SettingsContext';
import { useGamification } from '../../context/GamificationContext';
import { getDailyProgress, onDailyProgress, dailyQuests, LAST_PROJECT_KEY } from '../../utils/dailyProgress';
import { displayName, aiName, timeGreeting, daysUntil, pick } from '../../utils/persona';
import { getReviewStats, getLearningPlan } from '../../api';
import MemoryCurve from '../../components/MemoryCurve';
import { useBooks, coverFor, emojiFor } from '../data';
import { Screen, Ring } from '../ui';
import { tap, reminderScheduled } from '../device';
import GetStarted from '../GetStarted';

const NUDGES = [
    'Two minutes now beats two hours the night before.',
    'Getting one wrong is how it sticks. Go break something.',
    'Your feed has fresh cards. Ten swipes and you are done for today.',
    'Small streaks become big grades.',
    'Explain it back to me and you will never forget it.',
];

export const BookCover = ({ book, size = 'md', onClick }) => {
    const [a, b] = coverFor(book.id);
    const big = size === 'lg';
    return (
        <button onClick={() => { tap(); onClick?.(); }} className={`m-pressable shrink-0 text-left ${big ? 'w-full' : 'w-[128px]'}`}>
            <div className={`relative overflow-hidden rounded-[18px] shadow-lg ${big ? 'h-44' : 'h-[168px]'}`} style={{ background: `linear-gradient(150deg, ${a}, ${b})` }}>
                <span className="absolute left-2 top-0 h-full w-[3px] rounded bg-white/25" />
                <span className="absolute -right-3 -top-3 text-[64px] opacity-90">{emojiFor(book.name)}</span>
                <div className="absolute inset-x-0 bottom-0 p-3">
                    <p className="line-clamp-3 text-[14px] font-extrabold leading-tight text-white drop-shadow">{book.name}</p>
                    <p className="mt-1 text-[11px] font-semibold text-white/75">{book.docs || 0} {book.docs === 1 ? 'file' : 'files'}</p>
                </div>
            </div>
        </button>
    );
};

const Home = () => {
    const navigate = useNavigate();
    const { user } = useAuth();
    const { settings } = useSettings();
    const { data: g } = useGamification();
    const { books, loading } = useBooks();
    const [progress, setProgress] = useState(() => getDailyProgress(user?.id));
    const [due, setDue] = useState(0);
    const nudge = useMemo(() => pick(NUDGES), []);

    useEffect(() => onDailyProgress(setProgress), []);
    useEffect(() => {
        getReviewStats().then((s) => setDue(s?.due_today ?? s?.due ?? s?.due_count ?? 0)).catch(() => {});
    }, []);

    const goal = settings.dailyStudyGoal || 30;
    const quests = dailyQuests(progress, goal);
    const questDone = quests.filter((q) => q.value >= q.target).length;
    const streak = g?.streak_days ?? g?.stats?.streak_days ?? 0;
    const name = displayName(settings, user);
    const examIn = daysUntil(settings.examDate);
    const lastId = (() => { try { return localStorage.getItem(LAST_PROJECT_KEY); } catch { return null; } })();
    const last = books.find((b) => b.id === lastId) || books[0];
    const openTool = (id, tool) => { tap(); navigate(tool ? `/project/${id}?tool=${tool}` : `/app/book/${id}`); };

    // Memory curve for the book they're on (illustrative until there are answers)
    const [memory, setMemory] = useState(null);
    useEffect(() => {
        if (!last?.id) return undefined;
        let alive = true;
        getLearningPlan(last.id, { horizon: 3 }).then((r) => { if (alive) setMemory(r); }).catch(() => {});
        return () => { alive = false; };
    }, [last?.id]);
    const fading = (memory?.profile || []).find((r) => r.due);

    return (
        <Screen className="m-tab-space">
            <header className="m-safe-top px-5 pt-4">
                <div className="flex items-center gap-3">
                    <button onClick={() => navigate('/app/me')} className="m-pressable flex h-12 w-12 items-center justify-center rounded-full text-2xl"
                        style={{ background: 'linear-gradient(135deg, var(--m-accent), var(--m-accent-deep))' }} aria-label="Your profile">
                        {settings.userAvatar || '🦊'}
                    </button>
                    <div className="min-w-0 flex-1">
                        <p className="line-clamp-2 text-[13px] font-medium leading-snug" style={{ color: 'var(--m-muted)' }}>{timeGreeting()}</p>
                        <h1 className="truncate text-[22px] font-extrabold tracking-tight">{name} 👋</h1>
                    </div>
                    <div className="flex items-center gap-1 rounded-full px-3 py-1.5 text-[15px] font-extrabold" style={{ background: 'var(--m-soft)' }}>
                        <span className={streak ? 'm-flame' : ''}>🔥</span>{streak}
                    </div>
                    <div className="flex items-center gap-1 rounded-full px-3 py-1.5 text-[15px] font-extrabold" style={{ background: 'var(--m-soft)' }}>
                        <Zap className="h-4 w-4" style={{ color: '#f5b301' }} fill="#f5b301" />{(g?.total_xp || 0).toLocaleString()}
                    </div>
                </div>
            </header>

            <div className="mt-5 space-y-5 px-5">
                <GetStarted
                    hasBook={books.length > 0}
                    reminderOn={reminderScheduled()}
                    onAddBook={() => window.dispatchEvent(new Event('lumina-add'))}
                    onFeed={() => navigate('/app/feed')}
                    onReminder={() => navigate('/app/me', { state: { open: 'reminder' } })}
                />

                {/* The habit: one tap into the feed */}
                <motion.button
                    whileTap={{ scale: 0.97 }}
                    onClick={() => { tap('medium'); navigate('/app/feed'); }}
                    className="relative w-full overflow-hidden rounded-[28px] p-5 text-left text-white"
                    style={{ background: 'linear-gradient(135deg, #142A1F 0%, var(--m-accent-deep) 55%, var(--m-accent) 100%)', boxShadow: '0 20px 40px -18px color-mix(in srgb, var(--m-accent) 80%, black)' }}
                >
                    <motion.span className="absolute -right-6 -top-8 text-[120px] opacity-25" animate={{ rotate: [0, 8, 0] }} transition={{ duration: 6, repeat: Infinity }}>🔥</motion.span>
                    <p className="text-[12px] font-bold uppercase tracking-[0.14em] text-white/70">Your feed is ready</p>
                    <h2 className="mt-1 text-[26px] font-extrabold leading-tight">Swipe & learn</h2>
                    <p className="mt-1 max-w-[80%] text-[14px] text-white/80">
                        {due > 0 ? `${due} review card${due === 1 ? '' : 's'} due, plus fresh questions from your books.` : 'Quick questions and flashcards from your books, one swipe at a time.'}
                    </p>
                    <span className="mt-4 inline-flex items-center gap-2 rounded-full m-white px-4 py-2 text-[14px] font-bold text-[#142A1F]">
                        <Play className="h-4 w-4" fill="currentColor" /> Start
                    </span>
                </motion.button>

                {/* Daily goal */}
                <div className="m-card flex items-center gap-4 p-4">
                    <Ring value={progress.minutes / goal} size={76} stroke={8}>
                        <div className="text-center leading-none">
                            <p className="text-[18px] font-extrabold">{Math.min(progress.minutes, goal)}</p>
                            <p className="text-[10px] font-semibold" style={{ color: 'var(--m-muted)' }}>/{goal} min</p>
                        </div>
                    </Ring>
                    <div className="min-w-0 flex-1">
                        <p className="text-[15px] font-extrabold">Today's goal</p>
                        <div className="mt-2 space-y-1.5">
                            {quests.map((q) => (
                                <div key={q.id} className="flex items-center gap-2 text-[12.5px]">
                                    <span>{q.value >= q.target ? '✅' : q.emoji}</span>
                                    <span className={`flex-1 truncate ${q.value >= q.target ? 'line-through opacity-60' : ''}`}>{q.label}</span>
                                    <span className="tabular-nums font-semibold" style={{ color: 'var(--m-muted)' }}>{q.value}/{q.target}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
                {questDone === quests.length && (
                    <p className="-mt-2 text-center text-[13px] font-semibold" style={{ color: 'var(--m-accent-text)' }}>All done today. Legend. 🏆</p>
                )}
                {last && (
                    <MemoryCurve
                        profile={memory?.profile}
                        compact
                        action={
                            <button type="button" className="lumina-curve__cta m-pressable" onClick={() => openTool(last.id, fading ? 'path' : 'power')}>
                                <span className="max-w-[15rem] truncate">{fading ? `Review “${fading.topic}” · 3 min` : 'Lock it in · 10 min'}</span> <ChevronRight className="h-4 w-4 shrink-0" />
                            </button>
                        }
                    />
                )}

                {examIn != null && examIn >= 0 && (
                    <button onClick={() => last && openTool(last.id, 'cram')} className="m-card m-pressable flex w-full items-center gap-3 p-4 text-left">
                        <div className="flex h-12 w-12 items-center justify-center rounded-2xl" style={{ background: '#2a2140', color: '#c9b8ff' }}><CalendarClock className="h-6 w-6" /></div>
                        <div className="min-w-0 flex-1">
                            <p className="text-[15px] font-extrabold">{settings.examName || 'Your exam'} {examIn === 0 ? 'is today' : `in ${examIn} day${examIn === 1 ? '' : 's'}`}</p>
                            <p className="text-[13px]" style={{ color: 'var(--m-muted)' }}>Open Exam Tonight for a plan that fits your time</p>
                        </div>
                        <ChevronRight className="h-5 w-5" style={{ color: 'var(--m-muted)' }} />
                    </button>
                )}

                {/* Continue */}
                {last ? (
                    <section>
                        <div className="mb-2 flex items-baseline justify-between">
                            <h2 className="text-[18px] font-extrabold">Continue</h2>
                        </div>
                        <div className="m-card overflow-hidden">
                            <button onClick={() => openTool(last.id)} className="m-pressable flex w-full items-center gap-3 p-4 text-left">
                                <div className="flex h-14 w-11 items-center justify-center rounded-lg text-2xl shadow" style={{ background: `linear-gradient(150deg, ${coverFor(last.id)[0]}, ${coverFor(last.id)[1]})` }}>{emojiFor(last.name)}</div>
                                <div className="min-w-0 flex-1">
                                    <p className="truncate text-[16px] font-extrabold">{last.name}</p>
                                    <p className="text-[12.5px]" style={{ color: 'var(--m-muted)' }}>{last.docs || 0} {last.docs === 1 ? 'file' : 'files'} · tap to open</p>
                                </div>
                                <ChevronRight className="h-5 w-5" style={{ color: 'var(--m-muted)' }} />
                            </button>
                            <div className="grid grid-cols-4 border-t" style={{ borderColor: 'var(--m-border)' }}>
                                {[
                                    { id: 'chat', icon: MessageSquare, label: 'Ask' },
                                    { id: 'quiz', icon: CheckSquare, label: 'Quiz' },
                                    { id: 'flashcards', icon: Layers, label: 'Cards' },
                                    { id: 'cram', icon: Moon, label: 'Cram' },
                                ].map((t) => (
                                    <button key={t.id} onClick={() => openTool(last.id, t.id)} className="m-pressable flex flex-col items-center gap-1 py-3 text-[12px] font-semibold">
                                        <t.icon className="h-5 w-5" style={{ color: 'var(--m-accent-text)' }} />{t.label}
                                    </button>
                                ))}
                            </div>
                        </div>
                    </section>
                ) : !loading && (
                    <button onClick={() => window.dispatchEvent(new Event('lumina-add'))} className="m-pressable flex w-full flex-col items-center rounded-[28px] border-2 border-dashed p-8 text-center" style={{ borderColor: 'var(--m-border)' }}>
                        <div className="flex h-16 w-16 items-center justify-center rounded-3xl text-white" style={{ background: 'var(--m-accent)' }}><Upload className="h-8 w-8" /></div>
                        <p className="mt-4 text-[18px] font-extrabold">Add your first book</p>
                        <p className="mt-1 text-[14px]" style={{ color: 'var(--m-muted)' }}>A PDF, your notes, or just paste some text. Ready in about a minute.</p>
                    </button>
                )}

                {books.length > 1 && (
                    <section>
                        <div className="mb-2 flex items-baseline justify-between">
                            <h2 className="text-[18px] font-extrabold">Your books</h2>
                            <button onClick={() => navigate('/app/library')} className="text-[13px] font-bold" style={{ color: 'var(--m-accent-text)' }}>See all</button>
                        </div>
                        <div className="m-hscroll -mx-5 gap-3 px-5 pb-2">
                            {books.slice(0, 10).map((b) => <BookCover key={b.id} book={b} onClick={() => navigate(`/app/book/${b.id}`)} />)}
                        </div>
                    </section>
                )}

                <div className="flex items-start gap-3 rounded-[22px] p-4" style={{ background: 'var(--m-soft)' }}>
                    <span className="text-2xl">{settings.aiAvatar || '✨'}</span>
                    <p className="text-[14px] leading-relaxed"><b>{aiName(settings)}:</b> {nudge}</p>
                </div>
            </div>
        </Screen>
    );
};

export default Home;
