import React, { useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { ChevronLeft, ArrowRight, Bell, Check, CalendarDays } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useSettings } from '../../context/SettingsContext';
import { onboardedKey } from '../../components/Onboarding';
import { AI_CHARACTERS, USER_AVATARS } from '../../utils/persona';
import { tap, notify, scheduleStudyReminder } from '../device';

/*
 * First-run setup in the app. Psychology behind it:
 *  - one question per screen, mostly one tap (low effort keeps people going)
 *  - their own name and goal come back to them straight away (it feels made for them)
 *  - a small default goal, 10 minutes, framed as "most people start here" (easy to say yes)
 *  - the notification permission is explained before Android asks (people say yes to a reason)
 *  - it ends with a plan they chose and one clear next step: add the first book
 */

const GOALS = [
    { id: 'school', emoji: '📚', label: 'School exams', age: 'teen' },
    { id: 'college', emoji: '🎓', label: 'College or university', age: 'young' },
    { id: 'competitive', emoji: '🎯', label: 'A competitive exam', hint: 'JEE, NEET, UPSC, CAT…', age: 'young' },
    { id: 'work', emoji: '💼', label: 'Work or a certification', age: 'adult' },
    { id: 'curious', emoji: '🌱', label: 'Learning for myself', age: 'mature' },
];

const WHEN = [
    { id: 'week', label: 'This week', days: 5 },
    { id: 'month', label: 'This month', days: 21 },
    { id: 'later', label: 'In a few months', days: 90 },
    { id: 'none', label: 'No exam, just learning', days: null },
];

const MINUTES = [
    { m: 5, label: 'Light', e: '🌱' },
    { m: 10, label: 'Steady', e: '📘', popular: true },
    { m: 20, label: 'Serious', e: '🔥' },
    { m: 30, label: 'Intense', e: '🚀' },
];

const TIMES = [
    { t: '08:00', label: 'Morning', e: '☀️' },
    { t: '17:00', label: 'After class', e: '🎒' },
    { t: '19:30', label: 'Evening', e: '🌆' },
    { t: '21:30', label: 'Before bed', e: '🌙' },
];

const BUDDIES = ['buddy', 'mentor', 'coach', 'sage'];

const isoIn = (days) => {
    const d = new Date();
    d.setDate(d.getDate() + days);
    return d.toISOString().slice(0, 10);
};

const Option = ({ active, onClick, children, className = '' }) => (
    <motion.button
        whileTap={{ scale: 0.97 }}
        onClick={() => { tap(); onClick(); }}
        className={`flex w-full items-center gap-3 rounded-2xl border-2 p-4 text-left transition-colors ${className}`}
        style={{
            borderColor: active ? 'var(--m-accent)' : 'var(--m-border)',
            background: active ? 'color-mix(in srgb, var(--m-accent) 12%, var(--m-surface))' : 'var(--m-surface)',
        }}
    >
        {children}
        {active && <Check className="ml-auto h-5 w-5 shrink-0" style={{ color: 'var(--m-accent-text)' }} strokeWidth={3} />}
    </motion.button>
);

const Title = ({ children, sub }) => (
    <div className="mb-6">
        <h1 className="text-[28px] font-extrabold leading-[1.12] tracking-tight">{children}</h1>
        {sub && <p className="mt-2 text-[15px] leading-relaxed" style={{ color: 'var(--m-muted)' }}>{sub}</p>}
    </div>
);

const Setup = () => {
    const navigate = useNavigate();
    const { user } = useAuth();
    const { settings, updateSettings } = useSettings();
    const firstName = (settings.studentName || user?.full_name || '').trim().split(' ')[0] || '';
    const [step, setStep] = useState(0);
    const dir = React.useRef(1);
    const [f, setF] = useState(() => ({
        name: firstName,
        avatar: settings.userAvatar || '🦊',
        goal: '',
        when: '',
        examDate: settings.examDate || '',
        examName: settings.examName || '',
        minutes: 10,
        buddy: settings.aiCharacter || 'buddy',
        remind: true,
        time: '19:30',
    }));
    const [askingPerm, setAskingPerm] = useState(false);
    const set = (k, v) => setF((s) => ({ ...s, [k]: v }));
    const name = f.name.trim() || 'friend';
    const TOTAL = 6;

    const go = (n) => { dir.current = n > step ? 1 : -1; setStep(n); };
    const next = () => go(step + 1);
    const auto = (fn) => { fn(); setTimeout(next, 280); };

    const save = (extra = {}) => {
        const g = GOALS.find((x) => x.id === f.goal);
        updateSettings({
            studentName: f.name.trim() || settings.studentName,
            nickname: f.name.trim() || settings.nickname,
            userAvatar: f.avatar,
            learningGoal: g?.label || settings.learningGoal,
            ageGroup: g?.age || settings.ageGroup,
            examName: f.examName,
            examDate: f.examDate,
            dailyStudyGoal: f.minutes,
            aiCharacter: f.buddy,
            aiAvatar: AI_CHARACTERS[f.buddy]?.emoji || settings.aiAvatar,
            reminderTime: f.time,
            studyReminders: f.remind,
            onboardingComplete: true,
            ...extra,
        });
        try { localStorage.setItem(onboardedKey(user?.id), '1'); } catch { /* ignore */ }
    };

    const enableReminder = async () => {
        setAskingPerm(true);
        const ok = await scheduleStudyReminder(true, f.time);
        setAskingPerm(false);
        set('remind', ok !== false);
        if (ok !== false) notify('success');
        next();
    };

    const finish = (addBook) => {
        notify('success');
        save();
        navigate('/app/home', { replace: true });
        if (addBook) setTimeout(() => window.dispatchEvent(new Event('lumina-add')), 450);
    };

    const examDays = f.examDate ? Math.round((new Date(f.examDate + 'T00:00:00') - new Date(new Date().toDateString())) / 86400000) : null;
    const buddy = AI_CHARACTERS[f.buddy] || AI_CHARACTERS.buddy;
    const plan = useMemo(() => {
        const perWeek = f.minutes * 7;
        return perWeek >= 60 ? `${Math.round(perWeek / 60 * 10) / 10} hours a week` : `${perWeek} minutes a week`;
    }, [f.minutes]);

    const screens = [
        // 0 — name and avatar
        <div key="name">
            <Title sub="So your study buddy knows who it's cheering for.">Hi! What should we call you?</Title>
            <input autoFocus value={f.name} onChange={(e) => set('name', e.target.value.slice(0, 30))} placeholder="Your first name"
                className="h-14 w-full rounded-2xl px-4 text-[18px] font-semibold outline-none focus:ring-2"
                style={{ background: 'var(--m-soft)', color: 'var(--m-text)', '--tw-ring-color': 'var(--m-accent)' }} />
            <p className="mb-2 mt-6 text-[13px] font-bold uppercase tracking-[0.1em]" style={{ color: 'var(--m-muted)' }}>Pick your look</p>
            <div className="grid grid-cols-6 gap-2">
                {USER_AVATARS.slice(0, 12).map((a) => (
                    <button key={a} onClick={() => { tap(); set('avatar', a); }}
                        className="m-pressable flex aspect-square items-center justify-center rounded-2xl text-[26px]"
                        style={{ background: f.avatar === a ? 'color-mix(in srgb, var(--m-accent) 22%, transparent)' : 'var(--m-soft)', boxShadow: f.avatar === a ? '0 0 0 2px var(--m-accent)' : 'none' }}>
                        {a}
                    </button>
                ))}
            </div>
        </div>,

        // 1 — goal
        <div key="goal">
            <Title sub="We'll shape questions and tone around it.">{f.name.trim() ? `Nice to meet you, ${f.name.trim()}! ` : ''}What are you studying for?</Title>
            <div className="space-y-2.5">
                {GOALS.map((g) => (
                    <Option key={g.id} active={f.goal === g.id} onClick={() => auto(() => set('goal', g.id))}>
                        <span className="text-[26px]">{g.emoji}</span>
                        <span>
                            <span className="block text-[16px] font-bold">{g.label}</span>
                            {g.hint && <span className="block text-[13px]" style={{ color: 'var(--m-muted)' }}>{g.hint}</span>}
                        </span>
                    </Option>
                ))}
            </div>
        </div>,

        // 2 — exam timing
        <div key="when">
            <Title sub="We'll count down with you and plan the revision.">When's your next exam?</Title>
            <div className="space-y-2.5">
                {WHEN.map((w) => (
                    <Option key={w.id} active={f.when === w.id}
                        onClick={() => auto(() => setF((s) => ({ ...s, when: w.id, examDate: w.days ? isoIn(w.days) : '' })))}>
                        <span className="text-[16px] font-bold">{w.label}</span>
                    </Option>
                ))}
            </div>
            <label className="mt-5 flex items-center gap-3 rounded-2xl p-4" style={{ background: 'var(--m-soft)' }}>
                <CalendarDays className="h-5 w-5 shrink-0" style={{ color: 'var(--m-accent-text)' }} />
                <span className="flex-1 text-[14px] font-semibold">Know the exact date?</span>
                <input type="date" value={f.examDate} min={isoIn(0)}
                    onChange={(e) => setF((s) => ({ ...s, examDate: e.target.value, when: e.target.value ? 'exact' : s.when }))}
                    className="bg-transparent text-[14px] outline-none" style={{ color: 'var(--m-text)' }} />
            </label>
        </div>,

        // 3 — daily goal
        <div key="minutes">
            <Title sub="Small goals win. Short daily sessions beat long weekly ones, and you can change this any time.">How much time a day?</Title>
            <div className="grid grid-cols-2 gap-3">
                {MINUTES.map((o) => {
                    const on = f.minutes === o.m;
                    return (
                        <motion.button key={o.m} whileTap={{ scale: 0.96 }} onClick={() => { tap(); set('minutes', o.m); }}
                            className="relative rounded-2xl border-2 p-4 text-left"
                            style={{ borderColor: on ? 'var(--m-accent)' : 'var(--m-border)', background: on ? 'color-mix(in srgb, var(--m-accent) 12%, var(--m-surface))' : 'var(--m-surface)' }}>
                            {o.popular && <span className="absolute -top-2.5 right-3 rounded-full px-2 py-0.5 text-[10.5px] font-bold text-white" style={{ background: 'var(--m-accent)' }}>Most popular</span>}
                            <span className="text-[28px]">{o.e}</span>
                            <p className="mt-1 text-[20px] font-extrabold">{o.m} min</p>
                            <p className="text-[13px]" style={{ color: 'var(--m-muted)' }}>{o.label}</p>
                        </motion.button>
                    );
                })}
            </div>
            <p className="mt-5 text-center text-[14px] font-semibold" style={{ color: 'var(--m-accent-text)' }}>That's {plan} of real progress.</p>
        </div>,

        // 4 — study buddy
        <div key="buddy">
            <Title sub="Pick a personality. It shapes how answers are explained to you.">Choose your study buddy</Title>
            <div className="grid grid-cols-2 gap-3">
                {BUDDIES.map((k) => {
                    const c = AI_CHARACTERS[k];
                    const on = f.buddy === k;
                    return (
                        <motion.button key={k} whileTap={{ scale: 0.96 }} onClick={() => { tap(); set('buddy', k); }}
                            className="rounded-2xl border-2 p-4 text-left"
                            style={{ borderColor: on ? 'var(--m-accent)' : 'var(--m-border)', background: on ? 'color-mix(in srgb, var(--m-accent) 12%, var(--m-surface))' : 'var(--m-surface)' }}>
                            <span className="text-[30px]">{c.emoji}</span>
                            <p className="mt-1 text-[15px] font-extrabold leading-tight">{c.label}</p>
                        </motion.button>
                    );
                })}
            </div>
            <AnimatePresence mode="wait">
                <motion.div key={f.buddy} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                    className="mt-5 flex items-start gap-3 rounded-2xl p-4" style={{ background: 'var(--m-soft)' }}>
                    <span className="text-[28px]">{buddy.emoji}</span>
                    <p className="text-[15px] leading-relaxed">{buddy.greet(name)}</p>
                </motion.div>
            </AnimatePresence>
        </div>,

        // 5 — reminder (explained before Android asks)
        <div key="remind">
            <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-3xl text-white" style={{ background: 'var(--m-accent)' }}>
                <Bell className="h-8 w-8" />
            </div>
            <Title sub="One gentle nudge a day makes a streak much easier to keep. Never spam, and you can turn it off in one tap.">When should {buddy.emoji} remind you?</Title>
            <div className="grid grid-cols-2 gap-3">
                {TIMES.map((o) => {
                    const on = f.time === o.t;
                    return (
                        <motion.button key={o.t} whileTap={{ scale: 0.96 }} onClick={() => { tap(); set('time', o.t); }}
                            className="rounded-2xl border-2 p-3.5 text-left"
                            style={{ borderColor: on ? 'var(--m-accent)' : 'var(--m-border)', background: on ? 'color-mix(in srgb, var(--m-accent) 12%, var(--m-surface))' : 'var(--m-surface)' }}>
                            <span className="text-[22px]">{o.e}</span>
                            <p className="mt-1 text-[15px] font-bold">{o.label}</p>
                            <p className="text-[12.5px]" style={{ color: 'var(--m-muted)' }}>{new Date(`2000-01-01T${o.t}`).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}</p>
                        </motion.button>
                    );
                })}
            </div>
        </div>,

        // 6 — the plan
        <div key="plan" className="flex flex-col">
            <motion.div initial={{ scale: 0.6, rotate: -10, opacity: 0 }} animate={{ scale: 1, rotate: 0, opacity: 1 }} transition={{ type: 'spring', damping: 11 }}
                className="mb-6 flex h-20 w-20 items-center justify-center rounded-[26px] text-[44px] shadow-xl"
                style={{ background: 'linear-gradient(135deg, var(--m-accent), var(--m-accent-deep))' }}>
                {f.avatar}
            </motion.div>
            <Title>{`You're all set, ${name}!`}</Title>
            <div className="m-card divide-y overflow-hidden" style={{ borderColor: 'var(--m-border)' }}>
                {[
                    ['🎯', 'Goal', GOALS.find((g) => g.id === f.goal)?.label || 'Learning'],
                    ['⏱️', 'Every day', `${f.minutes} minutes`],
                    ['📅', 'Exam', examDays != null && examDays >= 0 ? (examDays === 0 ? 'Today' : `In ${examDays} day${examDays === 1 ? '' : 's'}`) : 'No date yet'],
                    ['🔔', 'Reminder', f.remind ? new Date(`2000-01-01T${f.time}`).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }) : 'Off'],
                    [buddy.emoji, 'Study buddy', buddy.label],
                ].map(([e, k, v]) => (
                    <div key={k} className="flex items-center gap-3 px-4 py-3" style={{ borderColor: 'var(--m-border)' }}>
                        <span className="text-[20px]">{e}</span>
                        <span className="flex-1 text-[14px]" style={{ color: 'var(--m-muted)' }}>{k}</span>
                        <span className="text-[15px] font-bold">{v}</span>
                    </div>
                ))}
            </div>
            <p className="mt-5 text-[15px] leading-relaxed"><b>{buddy.emoji} </b>{buddy.greet(name)}</p>
        </div>,
    ];

    const footers = {
        0: { label: 'Continue', onClick: next, disabled: !f.name.trim() },
        1: { label: 'Skip', ghost: true, onClick: next },
        2: { label: f.when ? 'Continue' : 'Skip', ghost: !f.when, onClick: next },
        3: { label: 'Continue', onClick: next },
        4: { label: 'Continue', onClick: next },
        5: { label: askingPerm ? 'Asking…' : 'Turn on reminder', onClick: enableReminder, second: { label: 'Not now', onClick: () => { set('remind', false); next(); } } },
        6: { label: 'Add my first book', onClick: () => finish(true), second: { label: 'Look around first', onClick: () => finish(false) } },
    };
    const ft = footers[step];

    return (
        <div className="m-app m-shell fixed inset-0 z-[9999] flex flex-col m-safe-top m-safe-bottom">
            <div className="flex h-14 items-center gap-3 px-3">
                <button onClick={() => { tap(); if (step > 0) go(step - 1); }} aria-label="Back"
                    className={`m-pressable flex h-10 w-10 items-center justify-center rounded-full ${step === 0 ? 'invisible' : ''}`}>
                    <ChevronLeft className="h-6 w-6" />
                </button>
                <div className="h-1.5 flex-1 overflow-hidden rounded-full" style={{ background: 'var(--m-soft)' }}>
                    <motion.div className="h-full rounded-full" style={{ background: 'var(--m-accent)' }}
                        animate={{ width: `${((step + 1) / (TOTAL + 1)) * 100}%` }} transition={{ type: 'spring', damping: 20 }} />
                </div>
                <div className="w-10" />
            </div>

            <div className="m-scroll relative flex-1 px-6 pt-4">
                <AnimatePresence mode="wait" custom={dir.current}>
                    <motion.div key={step} initial={{ x: 40 * dir.current, opacity: 0 }} animate={{ x: 0, opacity: 1 }} exit={{ x: -40 * dir.current, opacity: 0 }}
                        transition={{ duration: 0.22, ease: [0.2, 0.8, 0.2, 1] }} className="pb-6">
                        {screens[step]}
                    </motion.div>
                </AnimatePresence>
            </div>

            <div className="space-y-1 px-6 pb-5 pt-2">
                <motion.button whileTap={{ scale: 0.97 }} disabled={ft.disabled || askingPerm} onClick={() => { tap('medium'); ft.onClick(); }}
                    className="flex h-14 w-full items-center justify-center gap-2 rounded-2xl text-[17px] font-bold disabled:opacity-40"
                    style={ft.ghost
                        ? { color: 'var(--m-muted)' }
                        : { background: 'linear-gradient(135deg, var(--m-accent), var(--m-accent-deep))', color: '#fff', boxShadow: '0 14px 28px -12px color-mix(in srgb, var(--m-accent) 80%, transparent)' }}>
                    {ft.label} {!ft.ghost && <ArrowRight className="h-5 w-5" />}
                </motion.button>
                {ft.second && (
                    <button onClick={() => { tap(); ft.second.onClick(); }} className="m-pressable h-11 w-full text-[14px] font-semibold" style={{ color: 'var(--m-muted)' }}>
                        {ft.second.label}
                    </button>
                )}
            </div>
        </div>
    );
};

export default Setup;
