import React, { useEffect, useMemo, useState } from 'react';
import { CalendarClock, Play, Check, Moon } from 'lucide-react';
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

    // Editorial voice: the site never puts emoji in display copy
    const plain = (t) => t.replace(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{FE0F}]/gu, '').trim();
    const examSoon = examDays !== null && examDays >= 0;

    return (
        <section className="mb-14 grid grid-cols-1 gap-10 lg:grid-cols-12 lg:items-end lg:gap-8" aria-label="Today">
            {/* Greeting: the site's hero, set in the display face */}
            <div className="lg:col-span-7">
                <p data-reveal="fade" className="mb-4 text-sm font-semibold uppercase tracking-[0.14em] text-[#5E5046]">
                    {new Date().toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long' })}
                </p>
                <h2 className="display h-mega mark-em text-[#163628]">
                    {timeGreeting()},<br /><em>{name}</em>.
                </h2>
                <div data-reveal="up" data-delay="0.15" className="mt-6 flex items-start gap-3">
                    <span className="mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#163628] text-lg" aria-hidden="true">
                        {settings.aiAvatar || '✨'}
                    </span>
                    <p className="lede max-w-[38ch]">
                        <span className="font-semibold text-[#163628]">{aiName(settings)}:</span> {plain(companionLine)}{' '}
                        <span className="text-base text-[#5E5046]/80">{plain(tip)}</span>
                    </p>
                </div>
                <div data-reveal="up" data-delay="0.25" className="mt-8 flex flex-wrap items-center gap-3">
                    {onContinue && (
                        <button onClick={onContinue} data-magnetic="0.25" className="btn btn--dark">
                            <Play className="h-4 w-4 fill-current" />
                            <span className="max-w-[16rem] truncate">{continueLabel}</span>
                            <svg className="arrow" viewBox="0 0 16 16" aria-hidden="true"><path d="M3 8h9M8.5 4.5 12 8l-3.5 3.5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" /></svg>
                        </button>
                    )}
                    {onCram && (
                        <button onClick={onCram} className="btn btn--light">
                            <Moon className="h-4 w-4" />
                            {examDays !== null && examDays >= 0 && examDays <= 1 ? 'Cram for it now' : 'Exam tonight?'}
                        </button>
                    )}
                    {examSoon && (
                        <span className="inline-flex min-h-[2.5rem] items-center gap-2 rounded-full bg-[#F2E6DB] px-4 text-sm text-[#163628]">
                            <CalendarClock className="h-4 w-4" />
                            <span><b>{examDays === 0 ? 'Today' : `${examDays} day${examDays === 1 ? '' : 's'}`}</b> to {settings.examName || 'your exam'}</span>
                        </span>
                    )}
                </div>
            </div>

            {/* Today in numbers: the site's stats row, then the quests as a tick list */}
            <div className="lg:col-span-5">
                <ul className="grid grid-cols-3 gap-4 border-t border-[#163628]/15">
                    {[
                        { v: progress.minutes, unit: `/${goal}`, label: 'minutes today', mark: goalPct >= 1 },
                        { v: streak, unit: streak === 1 ? ' day' : ' days', label: 'in a row', mark: streak > 2 },
                        { v: g?.level ?? 1, unit: '', label: g?.level_title || 'Curious Reader', mark: false, pre: 'Lv ' },
                    ].map((st, i) => (
                        <li key={st.label} data-reveal="up" data-delay={0.1 + i * 0.06} className="pt-5">
                            <p className="font-display text-[clamp(2.2rem,1.6rem+2vw,3.4rem)] font-light leading-none tracking-[-0.04em] tabular-nums text-[#163628]">
                                {st.pre && <span className="text-[0.55em] italic">{st.pre}</span>}
                                <span className={st.mark ? 'bg-[linear-gradient(#D3EE6A,#D3EE6A)] bg-[length:100%_0.28em] bg-[position:0_88%] bg-no-repeat' : ''}>{st.v}</span>
                                <span className="text-[0.45em] italic text-[#5E5046]">{st.unit}</span>
                            </p>
                            <p className="mt-2 text-sm text-[#5E5046]">{st.label}</p>
                        </li>
                    ))}
                </ul>
                <div data-reveal="settle" data-delay="0.2" className="mt-6 rounded-[1.25rem] border border-[#163628]/10 bg-white p-5 shadow-[0_18px_40px_-26px_rgba(22,54,40,0.35)]">
                    <div className="mb-3 flex items-baseline justify-between">
                        <span className="font-display text-xl">Today&apos;s <em>quests</em></span>
                        <span className="text-xs text-[#5E5046]">{questsDone} of {quests.length} · {(g?.total_xp ?? 0).toLocaleString()} XP</span>
                    </div>
                    <ul className="space-y-3">
                        {quests.map((q) => {
                            const done = q.value >= q.target;
                            return (
                                <li key={q.id} className="flex items-center gap-3">
                                    <span className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full ${done ? 'bg-[#163628]' : 'border border-[#163628]/25'}`}>
                                        {done && <Check className="h-3.5 w-3.5 text-[#D3EE6A]" strokeWidth={3} />}
                                    </span>
                                    <div className="min-w-0 flex-1">
                                        <div className={`text-sm ${done ? 'text-[#5E5046] line-through' : 'text-[#163628]'}`}>{q.label}</div>
                                        <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-[#163628]/10">
                                            <div className="h-full rounded-full bg-[#D3EE6A] shadow-[inset_0_0_0_1px_rgba(22,54,40,0.15)]" style={{ width: `${Math.min(100, (q.value / q.target) * 100)}%` }} />
                                        </div>
                                    </div>
                                    <span className="text-xs tabular-nums text-[#5E5046]">{q.value}/{q.target}</span>
                                </li>
                            );
                        })}
                    </ul>
                </div>
            </div>
        </section>
    );
};

export default TodayHero;
