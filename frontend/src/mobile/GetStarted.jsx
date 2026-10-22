import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Check, X } from 'lucide-react';
import { tap } from './device';

const TOTAL_KEY = 'lumina_total_answered';
const DISMISS_KEY = 'lumina_getstarted_done';

/** Questions answered on this phone, ever (drives the first-week checklist). */
export const totalAnswered = () => {
    try { return Number(localStorage.getItem(TOTAL_KEY) || 0); } catch { return 0; }
};
export const addAnswered = (n = 1) => {
    try { localStorage.setItem(TOTAL_KEY, String(totalAnswered() + n)); } catch { /* ignore */ }
};

/**
 * "Get started" checklist for new users. The first step is already ticked
 * (people finish what they've already started), each step is one tap away,
 * and it disappears for good once everything is done or it's dismissed.
 */
const GetStarted = ({ hasBook, reminderOn, onAddBook, onFeed, onReminder }) => {
    const [hidden, setHidden] = useState(() => { try { return localStorage.getItem(DISMISS_KEY) === '1'; } catch { return false; } });
    const answered = totalAnswered();
    const steps = [
        { id: 'account', label: 'Create your account', done: true },
        { id: 'book', label: 'Add your first book', done: hasBook, action: onAddBook, cta: 'Add' },
        { id: 'feed', label: 'Answer 5 questions in Learn', done: answered >= 5, action: onFeed, cta: 'Go', hint: answered ? `${Math.min(answered, 5)}/5` : null },
        { id: 'remind', label: 'Turn on a daily reminder', done: reminderOn, action: onReminder, cta: 'Set' },
    ];
    const done = steps.filter((s) => s.done).length;
    const all = done === steps.length;

    const dismiss = () => {
        tap();
        try { localStorage.setItem(DISMISS_KEY, '1'); } catch { /* ignore */ }
        setHidden(true);
    };

    if (hidden) return null;
    return (
        <AnimatePresence>
            <motion.section initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="m-card p-4">
                <div className="flex items-center gap-3">
                    <div className="min-w-0 flex-1">
                        <p className="text-[16px] font-extrabold">{all ? 'You are all set up! 🎉' : 'Get started'}</p>
                        <p className="text-[12.5px]" style={{ color: 'var(--m-muted)' }}>{all ? 'That is the hardest part done.' : `${done} of ${steps.length} done · about 3 minutes`}</p>
                    </div>
                    <button onClick={dismiss} aria-label="Hide checklist" className="m-pressable rounded-full p-1.5" style={{ color: 'var(--m-muted)' }}><X className="h-4 w-4" /></button>
                </div>
                <div className="mt-3 h-1.5 overflow-hidden rounded-full" style={{ background: 'var(--m-soft)' }}>
                    <motion.div className="h-full rounded-full" style={{ background: 'var(--m-accent)' }} initial={{ width: 0 }} animate={{ width: `${(done / steps.length) * 100}%` }} transition={{ duration: 0.8, ease: 'easeOut' }} />
                </div>
                {!all && (
                    <div className="mt-3 space-y-1">
                        {steps.map((s) => (
                            <button key={s.id} disabled={s.done} onClick={() => { tap(); s.action?.(); }}
                                className="m-pressable flex w-full items-center gap-3 rounded-xl px-1 py-2 text-left disabled:active:scale-100">
                                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full"
                                    style={{ background: s.done ? 'var(--m-accent)' : 'transparent', border: s.done ? 'none' : '2px solid var(--m-border)' }}>
                                    {s.done && <Check className="h-3.5 w-3.5 text-white" strokeWidth={3.5} />}
                                </span>
                                <span className={`flex-1 text-[14.5px] ${s.done ? 'line-through opacity-50' : 'font-semibold'}`}>{s.label}</span>
                                {s.hint && !s.done && <span className="text-[12px] font-semibold tabular-nums" style={{ color: 'var(--m-muted)' }}>{s.hint}</span>}
                                {!s.done && s.cta && <span className="rounded-full px-3 py-1 text-[12.5px] font-bold" style={{ background: 'color-mix(in srgb, var(--m-accent) 16%, transparent)', color: 'var(--m-accent-text)' }}>{s.cta}</span>}
                            </button>
                        ))}
                    </div>
                )}
            </motion.section>
        </AnimatePresence>
    );
};

export default GetStarted;
