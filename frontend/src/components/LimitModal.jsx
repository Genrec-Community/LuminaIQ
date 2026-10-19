import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Sparkles, X, Clock, Crown } from 'lucide-react';
import { LIMIT_EVENT, formatReset } from '../utils/plan';

const NEXT_PLAN = {
    free: { key: 'scholar', name: 'Scholar', pitch: '6× more chat, 15 books and 15 Visual Lab builds a month' },
    scholar: { key: 'topper', name: 'Topper', pitch: 'Deep answers, unlimited books and 40 Visual Lab builds a month' },
};

/**
 * Global "you've reached your plan's limit" prompt. Any API call that comes
 * back 402 limit_reached opens it (see api.js), so features don't each need
 * their own handling.
 */
const LimitModal = () => {
    const navigate = useNavigate();
    const [detail, setDetail] = useState(null);

    useEffect(() => {
        const onLimit = (e) => setDetail(e.detail);
        window.addEventListener(LIMIT_EVENT, onLimit);
        return () => window.removeEventListener(LIMIT_EVENT, onLimit);
    }, []);

    // Deep answers are a Topper feature, whatever plan the student is on now
    const next = detail
        ? (detail.feature === 'deep' && detail.plan !== 'topper' ? NEXT_PLAN.scholar : NEXT_PLAN[detail.plan])
        : null;
    const close = () => setDetail(null);

    return (
        <AnimatePresence>
            {detail && (
                <motion.div className="fixed inset-0 z-[80] flex items-end sm:items-center justify-center bg-black/40 p-4"
                    initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={close}>
                    <motion.div role="dialog" aria-modal="true" aria-labelledby="limit-title"
                        className="relative w-full max-w-md rounded-3xl border border-[#E6D5CC] bg-white p-6 shadow-2xl"
                        initial={{ y: 30, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: 30, opacity: 0 }}
                        onClick={(e) => e.stopPropagation()}>
                        <button onClick={close} className="absolute right-4 top-4 rounded-full p-1.5 text-[#8a6a5c] hover:bg-[#FDF6F0]" aria-label="Close">
                            <X className="h-5 w-5" />
                        </button>
                        <div className="h-12 w-12 rounded-2xl bg-[#FDF6F0] flex items-center justify-center">
                            <Sparkles className="h-6 w-6 text-[#C8A288]" />
                        </div>
                        <h2 id="limit-title" className="mt-4 text-xl font-bold text-[#4A3B32]">
                            {detail.limit === 0 ? 'Unlock this with an upgrade' : "You've hit your limit"}
                        </h2>
                        <p className="mt-1 text-[#4A3B32]">{detail.message}</p>
                        {detail.resets_at && (
                            <p className="mt-2 text-sm text-[#8a6a5c] flex items-center gap-1.5">
                                <Clock className="h-4 w-4" /> {formatReset(detail.resets_at)}
                            </p>
                        )}
                        {next ? (
                            <div className="mt-4 rounded-2xl border border-[#E6D5CC] bg-[#FDF6F0] p-4">
                                <div className="flex items-center gap-2 font-semibold text-[#4A3B32]">
                                    <Crown className="h-4 w-4 text-[#C8A288]" /> {next.name}
                                </div>
                                <p className="text-sm text-[#8a6a5c] mt-0.5">{next.pitch}.</p>
                            </div>
                        ) : (
                            <p className="mt-4 text-sm text-[#8a6a5c]">This limit keeps the service fair for everyone. It resets automatically.</p>
                        )}
                        <div className="mt-5 flex flex-col sm:flex-row gap-2">
                            {next && (
                                <button onClick={() => { close(); navigate(`/pricing?plan=${next.key}`); }}
                                    className="flex-1 rounded-2xl bg-[#C8A288] px-4 py-3 font-semibold text-white hover:bg-[#B08B72]">
                                    See {next.name}
                                </button>
                            )}
                            <button onClick={close}
                                className="flex-1 rounded-2xl border-2 border-[#E6D5CC] px-4 py-3 font-semibold text-[#4A3B32] hover:border-[#C8A288]">
                                Maybe later
                            </button>
                        </div>
                    </motion.div>
                </motion.div>
            )}
        </AnimatePresence>
    );
};

export default LimitModal;
