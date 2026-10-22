import React, { useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import { tap } from '../device';

export const WELCOMED_KEY = 'lumina_app_welcomed';

const SLIDES = [
    {
        art: ['📚', '✨'],
        title: 'Drop in any book.',
        body: 'PDFs, notes, even scanned textbooks. LuminaIQ reads every page for you in about a minute.',
        tint: '#C8A288',
    },
    {
        art: ['🔥', '🃏'],
        title: 'Scroll, but you get smarter.',
        body: 'A never-ending feed of quick questions and flashcards made from your own books. Swipe up for the next one.',
        tint: '#e07a5f',
    },
    {
        art: ['🧠', '💬'],
        title: 'Your own study buddy.',
        body: 'Ask anything about your books and get answers with the exact page. Mind maps, notes and quizzes in one tap.',
        tint: '#7c6fd6',
    },
    {
        art: ['🏆', '📈'],
        title: 'Two minutes a day. Streaks that stick.',
        body: 'Daily goals, XP and gentle reminders keep you going. Exam tomorrow? Exam Tonight mode has a plan.',
        tint: '#2f9e7a',
    },
];

const Art = ({ art, tint, index }) => (
    <div className="relative mx-auto flex h-64 w-64 items-center justify-center">
        <motion.div
            className="absolute inset-0 rounded-[64px]"
            style={{ background: `radial-gradient(circle at 30% 30%, ${tint}55, ${tint}10 70%)` }}
            animate={{ rotate: [0, 6, -4, 0], scale: [1, 1.04, 0.98, 1] }}
            transition={{ duration: 8, repeat: Infinity, ease: 'easeInOut' }}
        />
        <motion.span
            key={`a${index}`}
            className="relative text-[110px] drop-shadow-xl"
            initial={{ scale: 0.4, rotate: -20, opacity: 0 }}
            animate={{ scale: 1, rotate: 0, opacity: 1 }}
            transition={{ type: 'spring', damping: 12, stiffness: 160 }}
        >
            {art[0]}
        </motion.span>
        <motion.span
            key={`b${index}`}
            className="absolute right-4 top-6 text-5xl"
            initial={{ y: 30, opacity: 0 }}
            animate={{ y: [0, -10, 0], opacity: 1 }}
            transition={{ y: { duration: 3, repeat: Infinity, ease: 'easeInOut' }, opacity: { delay: 0.2 } }}
        >
            {art[1]}
        </motion.span>
    </div>
);

/** First launch: four swipeable slides, then straight to sign-in. */
const Welcome = () => {
    const navigate = useNavigate();
    const [i, setI] = useState(0);
    const dir = useRef(1);
    const last = i === SLIDES.length - 1;
    const s = SLIDES[i];

    const go = (n) => {
        if (n < 0 || n >= SLIDES.length) return;
        dir.current = n > i ? 1 : -1;
        tap();
        setI(n);
    };
    const finish = () => {
        tap('medium');
        try { localStorage.setItem(WELCOMED_KEY, '1'); } catch { /* ignore */ }
        navigate('/signin', { replace: true });
    };

    return (
        <div className="m-app relative flex min-h-[100dvh] flex-col overflow-hidden m-safe-top m-safe-bottom">
            <motion.div className="pointer-events-none absolute inset-0" animate={{ background: `radial-gradient(120% 70% at 50% 0%, ${s.tint}33 0%, transparent 60%)` }} transition={{ duration: 0.6 }} />
            <div className="relative flex items-center justify-between px-6 pt-4">
                <span className="text-lg font-extrabold tracking-tight">LuminaIQ</span>
                {!last && <button onClick={finish} className="m-pressable rounded-full px-3 py-1.5 text-sm font-semibold" style={{ color: 'var(--m-muted)' }}>Skip</button>}
            </div>

            <motion.div
                className="relative flex flex-1 flex-col justify-center px-8"
                drag="x"
                dragConstraints={{ left: 0, right: 0 }}
                dragElastic={0.25}
                onDragEnd={(_, info) => {
                    if (info.offset.x < -60) (last ? finish() : go(i + 1));
                    else if (info.offset.x > 60) go(i - 1);
                }}
            >
                <AnimatePresence mode="wait" custom={dir.current}>
                    <motion.div
                        key={i}
                        custom={dir.current}
                        initial={{ x: 60 * dir.current, opacity: 0 }}
                        animate={{ x: 0, opacity: 1 }}
                        exit={{ x: -60 * dir.current, opacity: 0 }}
                        transition={{ duration: 0.28, ease: [0.2, 0.8, 0.2, 1] }}
                    >
                        <Art art={s.art} tint={s.tint} index={i} />
                        <h1 className="mt-10 text-[32px] font-extrabold leading-[1.1] tracking-tight">{s.title}</h1>
                        <p className="mt-4 text-[16px] leading-relaxed" style={{ color: 'var(--m-muted)' }}>{s.body}</p>
                    </motion.div>
                </AnimatePresence>
            </motion.div>

            <div className="relative px-8 pb-8">
                <div className="mb-6 flex gap-2">
                    {SLIDES.map((_, n) => (
                        <button key={n} onClick={() => go(n)} aria-label={`Slide ${n + 1}`} className="h-2 rounded-full transition-all duration-300"
                            style={{ width: n === i ? 28 : 8, background: n === i ? s.tint : 'var(--m-border)' }} />
                    ))}
                </div>
                <button
                    onClick={() => (last ? finish() : go(i + 1))}
                    className="m-pressable flex h-14 w-full items-center justify-center gap-2 rounded-2xl text-[17px] font-bold text-white"
                    style={{ background: s.tint, boxShadow: `0 14px 28px -12px ${s.tint}` }}
                >
                    {last ? 'Get started' : 'Next'} <ArrowRight className="h-5 w-5" />
                </button>
            </div>
        </div>
    );
};

export default Welcome;
