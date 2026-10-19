import React, { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { Flame, Zap, Trophy, CalendarClock, Play, Check, Moon } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useSettings } from '../context/SettingsContext';
import { useGamification } from '../context/GamificationContext';
import { getDailyProgress, onDailyProgress, dailyQuests } from '../utils/dailyProgress';
import { getCharacter, displayName, aiName, timeGreeting, daysUntil, pick } from '../utils/persona';

const TIPS = [
    'Spaced repetition beats cramming — 10 minutes today saves an hour later.',
    'Explaining a topic out loud is the fastest way to find gaps. Try asking me to quiz you!',
    'Getting a question wrong helps you remember it — mistakes are memory glue.',
    'Short focused bursts beat long distracted sessions. One Power Hour round = 5 topics.',
    'Sleep locks in what you learned today. Review flashcards before bed!',
    'Mix topics while practising — interleaving makes exam recall stronger.',
];

const Ring = ({ value, size = 112, stroke = 10, children }) => {
    const r = (size - stroke) / 2;
    const c = 2 * Math.PI * r;
    return (
        <div className="relative" style={{ width: size, height: size }}>
            <svg width={size} height={size} className="-rotate-90">
                <circle cx={size / 2} cy={size / 2} r={r} stroke="#E6D5CC" strokeWidth={stroke} fill="none" opacity="0.6" />
                <motion.circle
                    cx={size / 2} cy={size / 2} r={r} stroke="#C8A288" strokeWidth={stroke} fill="none" strokeLinecap="round"
                    strokeDasharray={c}
                    initial={{ strokeDashoffset: c }}
                    animate={{ strokeDashoffset: c * (1 - Math.min(1, value)) }}
                    transition={{ duration: 1, ease: 'easeOut' }}
                />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">{children}</div>
        </div>
    );
};

/**
 * Dashboard hero: personal greeting from the AI companion, streak, daily goal,
 * level progress, exam countdown and daily quests.
 */
const TodayHero = ({ onContinue, continueLabel, onCram }) => {
    const { user } = useAuth();
    const { settings } = useSettings();
    const { data: g } = useGamification();
    const [progress, setProgress] = useState(() => getDailyProgress(user?.id));

    useEffect(() => {
        setProgress(getDailyProgress(user?.id));
        return onDailyProgress(setProgress);
    }, [user?.id]);

    const name = displayName(settings, user);
    const character = getCharacter(settings.aiCharacter);
    const tip = useMemo(() => pick(TIPS), []);
    const goal = settings.dailyStudyGoal || 30;
    const goalPct = progress.minutes / goal;
    const streak = g?.streak_days ?? g?.stats?.streak_days ?? 0;
    const examDays = daysUntil(settings.examDate);
    const quests = dailyQuests(progress, goal);
    const questsDone = quests.filter((q) => q.value >= q.target).length;

    const companionLine = goalPct >= 1
        ? `Daily goal smashed, ${name}! Anything extra today is pure bonus XP. 🎉`
        : streak > 1
            ? `${streak}-day streak, ${name}! Let's not break the chain today. 🔥`
            : character.greet(name);

    return (
        <section className="mb-10 grid gap-4 lg:grid-cols-[1.6fr_1fr]">
            {/* Greeting + companion */}
            <motion.div
                initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
                className="relative overflow-hidden rounded-3xl border border-[#E6D5CC] bg-white p-6 md:p-8"
            >
                <div className="pointer-events-none absolute -right-16 -top-16 h-56 w-56 rounded-full bg-[#C8A288]/15 blur-2xl" />
                <p className="text-sm font-medium text-[#8a6a5c]">{timeGreeting()},</p>
                <h2 className="mt-1 text-3xl md:text-4xl font-bold text-[#4A3B32]">
                    {name} <span className="inline-block">{settings.userAvatar || '👋'}</span>
                </h2>

                <div className="mt-5 flex items-start gap-3">
                    <motion.div
                        animate={{ y: [0, -4, 0] }} transition={{ repeat: Infinity, duration: 3, ease: 'easeInOut' }}
                        className="h-12 w-12 shrink-0 rounded-2xl bg-gradient-to-br from-[#C8A288] to-[#e8c9a8] flex items-center justify-center text-2xl shadow-md shadow-[#C8A288]/30"
                    >
                        {settings.aiAvatar || '✨'}
                    </motion.div>
                    <div className="rounded-2xl rounded-tl-sm border border-[#E6D5CC] bg-[#FDF6F0] px-4 py-3 text-[#4A3B32]">
                        <div className="text-xs font-semibold text-[#C8A288]">{aiName(settings)}</div>
                        <div>{companionLine}</div>
                        <div className="mt-1.5 text-xs text-[#8a6a5c]">💡 {tip}</div>
                    </div>
                </div>

                <div className="mt-6 flex flex-wrap items-center gap-3">
                    {onContinue && (
                        <button
                            onClick={onContinue}
                            className="group flex items-center gap-2 rounded-2xl bg-[#C8A288] px-6 py-3.5 font-semibold text-white shadow-lg shadow-[#C8A288]/30 transition-all hover:bg-[#B08B72] active:scale-95"
                        >
                            <Play className="h-5 w-5 fill-white" />
                            {continueLabel}
                        </button>
                    )}
                    {onCram && (
                        <button
                            onClick={onCram}
                            className="flex items-center gap-2 rounded-2xl border-2 border-[#C8A288] px-5 py-3 font-semibold text-[#4A3B32] transition-all hover:bg-[#FDF6F0] active:scale-95"
                        >
                            <Moon className="h-5 w-5 text-[#C8A288]" />
                            {examDays !== null && examDays >= 0 && examDays <= 1 ? 'Cram for it now' : 'Exam tonight?'}
                        </button>
                    )}
                    {examDays !== null && examDays >= 0 && (
                        <div className="flex items-center gap-2 rounded-2xl border border-[#E6D5CC] bg-[#FDF6F0] px-4 py-3 text-sm text-[#4A3B32]">
                            <CalendarClock className="h-4 w-4 text-[#C8A288]" />
                            <span><b>{examDays === 0 ? 'Today!' : `${examDays} day${examDays === 1 ? '' : 's'}`}</b> to {settings.examName || 'your exam'}</span>
                        </div>
                    )}
                </div>
            </motion.div>

            {/* Stats + quests */}
            <motion.div
                initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.08 }}
                className="rounded-3xl border border-[#E6D5CC] bg-white p-6"
            >
                <div className="flex items-center gap-5">
                    <Ring value={goalPct}>
                        <span className="text-2xl font-bold text-[#4A3B32]">{progress.minutes}</span>
                        <span className="text-[11px] text-[#8a6a5c]">/ {goal} min</span>
                    </Ring>
                    <div className="flex-1 space-y-3">
                        <div className="flex items-center gap-2">
                            <motion.span animate={streak > 0 ? { scale: [1, 1.15, 1] } : {}} transition={{ repeat: Infinity, duration: 1.8 }}>
                                <Flame className={`h-6 w-6 ${streak > 0 ? 'text-orange-500 fill-orange-400' : 'text-[#8a6a5c]'}`} />
                            </motion.span>
                            <span className="text-lg font-bold text-[#4A3B32]">{streak}</span>
                            <span className="text-sm text-[#8a6a5c]">day streak</span>
                        </div>
                        <div>
                            <div className="flex items-center justify-between text-sm">
                                <span className="flex items-center gap-1.5 font-semibold text-[#4A3B32]">
                                    <Trophy className="h-4 w-4 text-[#C8A288]" /> Lv {g?.level ?? 1}
                                </span>
                                <span className="text-xs text-[#8a6a5c]">{g?.level_title || 'Curious Reader'}</span>
                            </div>
                            <div className="mt-1 h-2 overflow-hidden rounded-full bg-[#E6D5CC]/60">
                                <motion.div
                                    className="h-full rounded-full bg-gradient-to-r from-[#C8A288] to-[#e0b48a]"
                                    initial={{ width: 0 }}
                                    animate={{ width: `${Math.min(100, g?.level_progress ?? 0)}%` }}
                                    transition={{ duration: 1 }}
                                />
                            </div>
                            <div className="mt-1 flex items-center gap-1 text-xs text-[#8a6a5c]">
                                <Zap className="h-3 w-3" /> {(g?.total_xp ?? 0).toLocaleString()} XP total
                            </div>
                        </div>
                    </div>
                </div>

                <div className="mt-5">
                    <div className="mb-2 flex items-center justify-between">
                        <span className="text-sm font-semibold text-[#4A3B32]">Daily quests</span>
                        <span className="text-xs text-[#8a6a5c]">{questsDone}/{quests.length} done</span>
                    </div>
                    <div className="space-y-2">
                        {quests.map((q) => {
                            const done = q.value >= q.target;
                            return (
                                <div key={q.id} className={`flex items-center gap-3 rounded-xl border px-3 py-2 ${done ? 'border-emerald-300 bg-emerald-50' : 'border-[#E6D5CC] bg-[#FDF6F0]'}`}>
                                    <span className="text-lg">{done ? '✅' : q.emoji}</span>
                                    <div className="flex-1">
                                        <div className={`text-sm ${done ? 'text-emerald-700 line-through' : 'text-[#4A3B32]'}`}>{q.label}</div>
                                        <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-[#E6D5CC]/60">
                                            <div className={`h-full rounded-full ${done ? 'bg-emerald-500' : 'bg-[#C8A288]'}`} style={{ width: `${(q.value / q.target) * 100}%` }} />
                                        </div>
                                    </div>
                                    <span className="text-xs tabular-nums text-[#8a6a5c]">{done ? <Check className="h-4 w-4 text-emerald-600" /> : `${q.value}/${q.target}`}</span>
                                </div>
                            );
                        })}
                    </div>
                </div>
            </motion.div>
        </section>
    );
};

export default TodayHero;
