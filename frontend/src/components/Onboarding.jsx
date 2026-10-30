import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ArrowRight, ArrowLeft, Sparkles, Check } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useSettings } from '../context/SettingsContext';
import { AI_CHARACTERS, USER_AVATARS, AI_AVATARS, AGE_GROUPS, getCharacter } from '../utils/persona';

export const onboardedKey = (userId) => `lumina_onboarded_${userId}`;

const DAILY_GOALS = [
    { minutes: 10, label: 'Casual', emoji: '🌱' },
    { minutes: 20, label: 'Regular', emoji: '📘' },
    { minutes: 30, label: 'Serious', emoji: '🔥' },
    { minutes: 60, label: 'Beast mode', emoji: '🚀' },
];

const Chip = ({ active, onClick, children, className = '' }) => (
    <button
        type="button"
        onClick={onClick}
        className={`rounded-2xl border-2 transition-all active:scale-95 ${active
            ? 'border-[#1E5C42] bg-[#1E5C42]/10 shadow-md shadow-[#1E5C42]/20'
            : 'border-[#E6D5CC] hover:border-[#1E5C42]/60 bg-white'} ${className}`}
    >
        {children}
    </button>
);

const Field = ({ label, hint, children }) => (
    <label className="block">
        <span className="block text-sm font-semibold text-[#163628] mb-1.5">{label}</span>
        {children}
        {hint && <span className="block text-xs text-[#5E5046] mt-1">{hint}</span>}
    </label>
);

const inputCls = 'w-full px-4 py-3 bg-[#FDF6F0] border border-[#E6D5CC] rounded-xl focus:ring-2 focus:ring-[#1E5C42] outline-none text-base text-[#163628]';

/**
 * First-run experience: the learner introduces themselves, designs their AI
 * companion and sets a goal. Everything can be changed later in Settings.
 */
const Onboarding = ({ onDone, fullScreen = false }) => {
    const { user } = useAuth();
    const { settings, updateSettings } = useSettings();
    const [step, setStep] = useState(0);
    const [form, setForm] = useState(() => ({
        studentName: settings.studentName || user?.full_name || '',
        nickname: settings.nickname || '',
        userAvatar: settings.userAvatar || '🦊',
        ageGroup: settings.ageGroup || '',
        aiName: settings.aiName || 'Lumi',
        aiAvatar: settings.aiAvatar || '✨',
        aiCharacter: settings.aiCharacter || 'buddy',
        aiHumor: settings.aiHumor || 'some',
        examName: settings.examName || '',
        examDate: settings.examDate || '',
        dailyStudyGoal: settings.dailyStudyGoal || 30,
        selfLevel: settings.selfLevel || 'intermediate',
    }));
    const set = (k) => (v) => setForm((f) => ({ ...f, [k]: v?.target ? v.target.value : v }));

    const character = getCharacter(form.aiCharacter);
    const callName = form.nickname || form.studentName.split(' ')[0] || 'friend';
    const STEPS = 4;

    const finish = () => {
        updateSettings({ ...form, onboardingComplete: true });
        try { localStorage.setItem(onboardedKey(user?.id), '1'); } catch { /* ignore */ }
        onDone?.();
    };

    const skip = () => {
        updateSettings({ onboardingComplete: true });
        try { localStorage.setItem(onboardedKey(user?.id), '1'); } catch { /* ignore */ }
        onDone?.();
    };

    const canNext = step !== 1 || form.studentName.trim().length > 0;

    const screens = [
        // 0 — Welcome
        <div key="welcome" className="text-center py-6">
            <motion.div
                initial={{ scale: 0, rotate: -30 }}
                animate={{ scale: 1, rotate: 0 }}
                transition={{ type: 'spring', stiffness: 200, damping: 12 }}
                className="mx-auto mb-6 h-28 w-28 rounded-full bg-gradient-to-br from-[#1E5C42] to-[#D3EE6A] flex items-center justify-center text-6xl shadow-xl shadow-[#1E5C42]/30"
            >
                ✨
            </motion.div>
            <h2 className="text-3xl md:text-4xl font-bold text-[#163628] mb-3">Welcome to Lumina IQ</h2>
            <p className="text-[#5E5046] text-lg max-w-md mx-auto">
                Turn any textbook into bite-sized lessons, quizzes and a study buddy that actually gets you.
            </p>
            <div className="grid grid-cols-3 gap-3 mt-8 max-w-md mx-auto text-sm">
                {[['⚡', 'Learn in 60 min'], ['🎯', 'Ace your exams'], ['🔥', 'Build a streak']].map(([e, t]) => (
                    <div key={t} className="bg-[#FDF6F0] border border-[#E6D5CC] rounded-2xl p-3">
                        <div className="text-2xl mb-1">{e}</div>
                        <div className="font-medium text-[#163628]">{t}</div>
                    </div>
                ))}
            </div>
            <p className="text-xs text-[#5E5046] mt-6">Takes about 40 seconds. Let&apos;s set things up!</p>
        </div>,

        // 1 — About you
        <div key="you" className="space-y-5">
            <div>
                <h2 className="text-2xl font-bold text-[#163628]">First, who are you? 👋</h2>
                <p className="text-[#5E5046]">So your companion knows what to call you.</p>
            </div>
            <div className="grid sm:grid-cols-2 gap-4">
                <Field label="Your name">
                    <input autoFocus className={inputCls} value={form.studentName} onChange={set('studentName')} placeholder="e.g. Priya Sharma" />
                </Field>
                <Field label="Nickname (optional)" hint="We'll greet you with this">
                    <input className={inputCls} value={form.nickname} onChange={set('nickname')} placeholder="e.g. Pri, Captain, Doc" />
                </Field>
            </div>
            <Field label="Pick your avatar">
                <div className="grid grid-cols-10 gap-2">
                    {USER_AVATARS.map((a) => (
                        <Chip key={a} active={form.userAvatar === a} onClick={() => set('userAvatar')(a)} className="aspect-square text-2xl flex items-center justify-center">
                            {a}
                        </Chip>
                    ))}
                </div>
            </Field>
            <Field label="Which describes you best?" hint="Your companion adapts its language to you">
                <div className="grid grid-cols-2 gap-2">
                    {Object.entries(AGE_GROUPS).map(([k, g]) => (
                        <Chip key={k} active={form.ageGroup === k} onClick={() => set('ageGroup')(k)} className="p-3 text-left">
                            <div className="font-semibold text-[#163628] text-sm">{g.label}</div>
                            <div className="text-xs text-[#5E5046]">{g.hint}</div>
                        </Chip>
                    ))}
                </div>
            </Field>
        </div>,

        // 2 — Companion
        <div key="ai" className="space-y-5">
            <div>
                <h2 className="text-2xl font-bold text-[#163628]">Design your study companion 🎨</h2>
                <p className="text-[#5E5046]">Give them a name and a personality. You can change this anytime.</p>
            </div>
            <div className="grid sm:grid-cols-[1fr_auto] gap-4 items-end">
                <Field label="Companion's name">
                    <input className={inputCls} value={form.aiName} onChange={set('aiName')} maxLength={24} placeholder="Lumi" />
                </Field>
                <div className="flex flex-wrap gap-1.5 max-w-[280px]">
                    {AI_AVATARS.map((a) => (
                        <Chip key={a} active={form.aiAvatar === a} onClick={() => set('aiAvatar')(a)} className="h-10 w-10 text-xl flex items-center justify-center">
                            {a}
                        </Chip>
                    ))}
                </div>
            </div>
            <div className="grid sm:grid-cols-2 gap-2">
                {Object.entries(AI_CHARACTERS).map(([k, c]) => (
                    <Chip key={k} active={form.aiCharacter === k} onClick={() => set('aiCharacter')(k)} className="p-3 text-left flex gap-3 items-start">
                        <span className="text-2xl">{c.emoji}</span>
                        <span>
                            <span className="block font-semibold text-[#163628] text-sm">{c.label}</span>
                            <span className="block text-xs text-[#5E5046]">{c.tagline}</span>
                        </span>
                    </Chip>
                ))}
            </div>
            <div className="flex items-center gap-2 text-sm">
                <span className="font-semibold text-[#163628]">Humour:</span>
                {[['none', 'Serious'], ['some', 'A little'], ['lots', 'Lots! 😂']].map(([k, l]) => (
                    <Chip key={k} active={form.aiHumor === k} onClick={() => set('aiHumor')(k)} className="px-3 py-1.5 text-[#163628]">{l}</Chip>
                ))}
            </div>
            <motion.div key={form.aiCharacter + form.aiName} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
                className="flex items-start gap-3 bg-[#FDF6F0] border border-[#E6D5CC] rounded-2xl p-4">
                <span className="text-3xl">{form.aiAvatar}</span>
                <div>
                    <div className="text-xs font-semibold text-[#1E5C42]">{form.aiName || 'Lumi'} says</div>
                    <div className="text-[#163628]">{character.greet(callName)}</div>
                </div>
            </motion.div>
        </div>,

        // 3 — Mission
        <div key="goal" className="space-y-5">
            <div>
                <h2 className="text-2xl font-bold text-[#163628]">What&apos;s the mission? 🎯</h2>
                <p className="text-[#5E5046]">We&apos;ll count down to your exam and keep you on track.</p>
            </div>
            <div className="grid sm:grid-cols-2 gap-4">
                <Field label="Exam or goal (optional)">
                    <input className={inputCls} value={form.examName} onChange={set('examName')} placeholder="e.g. Class 12 Boards, NEET, AWS cert" />
                </Field>
                <Field label="Exam date (optional)">
                    <input type="date" className={inputCls} value={form.examDate} onChange={set('examDate')} />
                </Field>
            </div>
            <Field label="Daily study goal">
                <div className="grid grid-cols-4 gap-2">
                    {DAILY_GOALS.map((g) => (
                        <Chip key={g.minutes} active={form.dailyStudyGoal === g.minutes} onClick={() => set('dailyStudyGoal')(g.minutes)} className="p-3 text-center">
                            <div className="text-2xl">{g.emoji}</div>
                            <div className="font-bold text-[#163628]">{g.minutes} min</div>
                            <div className="text-xs text-[#5E5046]">{g.label}</div>
                        </Chip>
                    ))}
                </div>
            </Field>
            <Field label="How well do you know your subject right now?">
                <div className="grid grid-cols-3 gap-2">
                    {[['beginner', '🐣 Just starting'], ['intermediate', '🙂 Know the basics'], ['advanced', '🧠 Polishing up']].map(([k, l]) => (
                        <Chip key={k} active={form.selfLevel === k} onClick={() => set('selfLevel')(k)} className="p-3 text-sm font-medium text-[#163628]">{l}</Chip>
                    ))}
                </div>
            </Field>
        </div>,

        // 4 — Ready
        <div key="ready" className="text-center py-6">
            <motion.div
                initial={{ scale: 0.5, opacity: 0 }}
                animate={{ scale: [0.5, 1.15, 1], opacity: 1 }}
                transition={{ duration: 0.6 }}
                className="mx-auto mb-5 h-24 w-24 rounded-full bg-gradient-to-br from-[#1E5C42] to-[#D3EE6A] flex items-center justify-center text-5xl shadow-xl shadow-[#1E5C42]/30"
            >
                {form.aiAvatar}
            </motion.div>
            <h2 className="text-3xl font-bold text-[#163628] mb-2">You&apos;re all set, {callName}! {form.userAvatar}</h2>
            <p className="text-lg text-[#163628] max-w-md mx-auto mb-6">
                <span className="font-semibold text-[#1E5C42]">{form.aiName || 'Lumi'}:</span> {character.greet(callName)}
            </p>
            <div className="bg-[#FDF6F0] border border-[#E6D5CC] rounded-2xl p-4 max-w-md mx-auto text-left text-sm text-[#163628] space-y-2">
                <div className="font-semibold">Your first hour plan:</div>
                <div>1. 📚 Add a textbook (or grab one from the Book Store)</div>
                <div>2. ⚡ Hit <b>Power Hour</b> — swipe through every topic with quick checks</div>
                <div>3. 🃏 Review flashcards tomorrow to keep your 🔥 streak</div>
            </div>
        </div>,
    ];

    return (
        <div className={`fixed inset-0 z-[9999] flex items-center justify-center ${fullScreen ? 'bg-white' : 'bg-[#182B22]/50 backdrop-blur-md p-3 md:p-6'}`}>
            <motion.div
                initial={{ opacity: 0, y: 30, scale: 0.97 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                className={fullScreen
                    ? 'bg-white w-full h-[100dvh] flex flex-col overflow-hidden pt-[var(--sat)] pb-[var(--sab)]'
                    : 'bg-white rounded-3xl shadow-2xl w-full max-w-2xl max-h-[94vh] flex flex-col overflow-hidden'}
            >
                <div className="flex items-center gap-2 px-6 pt-5">
                    {Array.from({ length: STEPS + 1 }).map((_, i) => (
                        <div key={i} className={`h-1.5 rounded-full transition-all duration-300 ${i <= step ? 'bg-[#1E5C42] flex-[2]' : 'bg-[#E6D5CC] flex-1'}`} />
                    ))}
                    {step < STEPS && (
                        <button onClick={skip} className="ml-3 text-xs text-[#5E5046] hover:text-[#163628] whitespace-nowrap">Skip</button>
                    )}
                </div>

                <div className="flex-1 overflow-y-auto px-6 py-5">
                    <AnimatePresence mode="wait">
                        <motion.div
                            key={step}
                            initial={{ opacity: 0, x: 40 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: -40 }}
                            transition={{ duration: 0.22 }}
                        >
                            {screens[step]}
                        </motion.div>
                    </AnimatePresence>
                </div>

                <div className="flex items-center justify-between gap-3 px-6 py-4 border-t border-[#E6D5CC]">
                    {step > 0 ? (
                        <button onClick={() => setStep(step - 1)} className="flex items-center gap-1.5 px-4 py-2.5 rounded-xl text-[#5E5046] hover:bg-[#FDF6F0]">
                            <ArrowLeft className="h-4 w-4" /> Back
                        </button>
                    ) : <span />}
                    {step < STEPS ? (
                        <button
                            disabled={!canNext}
                            onClick={() => setStep(step + 1)}
                            className="flex items-center gap-2 px-6 py-3 rounded-xl bg-[#1E5C42] text-white font-semibold hover:bg-[#163628] disabled:opacity-40 shadow-lg shadow-[#1E5C42]/30 active:scale-95 transition-all"
                        >
                            {step === 0 ? "Let's go" : 'Next'} <ArrowRight className="h-4 w-4" />
                        </button>
                    ) : (
                        <button
                            onClick={finish}
                            className="flex items-center gap-2 px-6 py-3 rounded-xl bg-[#1E5C42] text-white font-semibold hover:bg-[#163628] shadow-lg shadow-[#1E5C42]/30 active:scale-95 transition-all"
                        >
                            <Sparkles className="h-4 w-4" /> Start learning <Check className="h-4 w-4" />
                        </button>
                    )}
                </div>
            </motion.div>
        </div>
    );
};

export default Onboarding;
