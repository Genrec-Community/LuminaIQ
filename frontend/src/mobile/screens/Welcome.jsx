import React, { useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, Check, X, FileUp, Sparkles, Flame } from 'lucide-react';
import { tap, notify } from '../device';
import logo from '../logo.png';

export const WELCOMED_KEY = 'lumina_app_welcomed';

/*
 * First launch, designed around three ideas:
 *  1. Continuity: the logo from the splash screen stays put and the story starts from it.
 *  2. Value before the ask: a real question to answer (a small win) before any sign-up.
 *  3. Low effort: three screens, one obvious button each, and a way out at every step.
 */

const DEMO = {
    q: 'You read a page today. Without reviewing it, how much will you remember in a week?',
    options: [
        { id: 'a', text: 'Almost all of it' },
        { id: 'b', text: 'About half' },
        { id: 'c', text: 'Only a small part', right: true },
    ],
    why: 'The forgetting curve: most of what we read fades within days unless we recall it. Quick questions like this one are how Lumina IQ makes it stick.',
};

const Brand = () => (
    <div className="flex flex-1 flex-col items-center justify-center text-center">
        <motion.img
            src={logo}
            alt=""
            className="h-28 w-28"
            initial={{ scale: 0.85, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ type: 'spring', damping: 14, stiffness: 140 }}
        />
        <motion.h1 className="mt-8 text-[34px] font-extrabold leading-[1.08] tracking-tight"
            initial={{ y: 14, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ delay: 0.15 }}>
            Your books,<br />turned into a<br /><span style={{ color: 'var(--m-accent-text)' }}>daily habit.</span>
        </motion.h1>
        <motion.p className="mt-4 max-w-xs text-[16px] leading-relaxed" style={{ color: 'var(--m-muted)' }}
            initial={{ y: 14, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ delay: 0.25 }}>
            Five minutes a day of quick questions from your own study material. That's it.
        </motion.p>
    </div>
);

const Demo = ({ picked, onPick }) => {
    const done = picked != null;
    return (
        <div className="flex flex-1 flex-col justify-center">
            <p className="text-[13px] font-bold uppercase tracking-[0.14em]" style={{ color: 'var(--m-accent-text)' }}>Try one</p>
            <div className="mt-3 overflow-hidden rounded-[26px] p-5 text-white shadow-xl"
                style={{ background: 'radial-gradient(120% 80% at 90% 0%, #8f6a52cc 0%, transparent 60%), #0F1D16' }}>
                <p className="text-[18px] font-bold leading-snug">{DEMO.q}</p>
                <div className="mt-4 space-y-2.5">
                    {DEMO.options.map((o) => {
                        const isPicked = picked === o.id;
                        const showRight = done && o.right;
                        const showWrong = isPicked && !o.right;
                        return (
                            <motion.button
                                key={o.id}
                                onClick={() => onPick(o)}
                                disabled={done}
                                animate={showWrong ? { x: [0, -7, 7, -4, 4, 0] } : {}}
                                className="m-pressable flex w-full items-center gap-3 rounded-2xl px-4 py-3.5 text-left text-[15px] font-semibold"
                                style={{
                                    background: showRight ? 'rgba(34,197,94,0.9)' : showWrong ? 'rgba(239,68,68,0.85)' : 'rgba(255,255,255,0.12)',
                                    border: `1px solid ${showRight ? '#4ade80' : showWrong ? '#f87171' : 'rgba(255,255,255,0.16)'}`,
                                    opacity: done && !showRight && !isPicked ? 0.5 : 1,
                                }}
                            >
                                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-black/25">
                                    {showRight ? <Check className="h-4 w-4" strokeWidth={3} /> : showWrong ? <X className="h-4 w-4" strokeWidth={3} /> : null}
                                </span>
                                {o.text}
                            </motion.button>
                        );
                    })}
                </div>
                <AnimatePresence>
                    {done && (
                        <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} className="overflow-hidden">
                            <p className="mt-4 text-[14px] leading-relaxed text-white/80">{DEMO.why}</p>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
            <AnimatePresence>
                {done && (
                    <motion.p initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}
                        className="mt-4 flex items-center gap-2 text-[14px] font-semibold" style={{ color: 'var(--m-accent-text)' }}>
                        <Sparkles className="h-4 w-4" /> That was your first rep. Your brain just got a little stickier.
                    </motion.p>
                )}
            </AnimatePresence>
        </div>
    );
};

const STEPS = [
    { icon: FileUp, title: 'Add any book or notes', body: 'PDFs, scanned pages, Word or pasted text.' },
    { icon: Sparkles, title: 'We read it in about a minute', body: 'Topics, questions and flashcards, made from your material.' },
    { icon: Flame, title: 'Swipe a few minutes a day', body: 'Short sessions, a gentle reminder, a streak you will want to keep.' },
];

const How = () => (
    <div className="flex flex-1 flex-col justify-center">
        <h1 className="text-[30px] font-extrabold leading-tight tracking-tight">How it works</h1>
        <div className="mt-7 space-y-5">
            {STEPS.map((s, i) => (
                <motion.div key={s.title} className="flex gap-4"
                    initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.08 * i }}>
                    <div className="relative flex flex-col items-center">
                        <span className="flex h-12 w-12 items-center justify-center rounded-2xl text-white" style={{ background: 'var(--m-accent)' }}>
                            <s.icon className="h-6 w-6" />
                        </span>
                        {i < STEPS.length - 1 && <span className="mt-1 w-0.5 flex-1 rounded" style={{ background: 'var(--m-border)' }} />}
                    </div>
                    <div className="pb-2">
                        <p className="text-[17px] font-bold">{s.title}</p>
                        <p className="mt-0.5 text-[14px] leading-relaxed" style={{ color: 'var(--m-muted)' }}>{s.body}</p>
                    </div>
                </motion.div>
            ))}
        </div>
        <p className="mt-6 text-[13px]" style={{ color: 'var(--m-muted)' }}>Free to start. No card needed.</p>
    </div>
);

const Welcome = () => {
    const navigate = useNavigate();
    const [i, setI] = useState(0);
    const [picked, setPicked] = useState(null);
    const dir = useRef(1);
    const last = i === 2;

    const go = (n) => {
        if (n < 0 || n > 2) return;
        dir.current = n > i ? 1 : -1;
        tap();
        setI(n);
    };
    const finish = (to = '/signin') => {
        tap('medium');
        try { localStorage.setItem(WELCOMED_KEY, '1'); } catch { /* ignore */ }
        navigate(to, { replace: true });
    };
    const pick = (o) => {
        setPicked(o.id);
        notify(o.right ? 'success' : 'error');
    };

    const cta = i === 0 ? 'Get started' : i === 1 ? (picked ? 'Continue' : 'Skip this') : 'Create my free account';

    return (
        <div className="m-app m-shell relative flex min-h-[100dvh] flex-col overflow-hidden m-safe-top m-safe-bottom">
            <div className="pointer-events-none absolute inset-0" style={{ background: 'radial-gradient(110% 55% at 50% 0%, color-mix(in srgb, var(--m-accent) 22%, transparent) 0%, transparent 70%)' }} />

            <div className="relative flex h-14 items-center justify-between px-6">
                <div className="flex gap-1.5" aria-label={`Step ${i + 1} of 3`}>
                    {[0, 1, 2].map((n) => (
                        <span key={n} className="h-1.5 rounded-full transition-all duration-300"
                            style={{ width: n === i ? 22 : 6, background: n <= i ? 'var(--m-accent)' : 'var(--m-border)' }} />
                    ))}
                </div>
                {!last && <button onClick={() => finish()} className="m-pressable px-2 py-1 text-[14px] font-semibold" style={{ color: 'var(--m-muted)' }}>Skip</button>}
            </div>

            <motion.div
                className="relative flex flex-1 flex-col px-7"
                drag="x" dragConstraints={{ left: 0, right: 0 }} dragElastic={0.2}
                onDragEnd={(_, info) => {
                    if (info.offset.x < -60) (last ? finish() : go(i + 1));
                    else if (info.offset.x > 60) go(i - 1);
                }}
            >
                <AnimatePresence mode="wait" custom={dir.current}>
                    <motion.div key={i} className="flex flex-1 flex-col"
                        initial={{ x: 50 * dir.current, opacity: 0 }} animate={{ x: 0, opacity: 1 }} exit={{ x: -50 * dir.current, opacity: 0 }}
                        transition={{ duration: 0.25, ease: [0.2, 0.8, 0.2, 1] }}>
                        {i === 0 && <Brand />}
                        {i === 1 && <Demo picked={picked} onPick={pick} />}
                        {i === 2 && <How />}
                    </motion.div>
                </AnimatePresence>
            </motion.div>

            <div className="relative space-y-2 px-7 pb-7 pt-4">
                <motion.button
                    onClick={() => (last ? finish() : go(i + 1))}
                    whileTap={{ scale: 0.97 }}
                    className="flex h-14 w-full items-center justify-center gap-2 rounded-2xl text-[17px] font-bold text-white"
                    style={{
                        background: i === 1 && !picked ? 'transparent' : 'linear-gradient(135deg, var(--m-accent), var(--m-accent-deep))',
                        color: i === 1 && !picked ? 'var(--m-muted)' : '#fff',
                        boxShadow: i === 1 && !picked ? 'none' : '0 14px 28px -12px color-mix(in srgb, var(--m-accent) 80%, transparent)',
                    }}
                >
                    {cta} {!(i === 1 && !picked) && <ArrowRight className="h-5 w-5" />}
                </motion.button>
                {i === 0 && (
                    <button onClick={() => finish()} className="m-pressable h-11 w-full text-[14px] font-semibold" style={{ color: 'var(--m-muted)' }}>
                        I already have an account
                    </button>
                )}
            </div>
        </div>
    );
};

export default Welcome;
