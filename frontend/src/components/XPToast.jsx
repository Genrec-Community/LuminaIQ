import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Zap, Award, TrendingUp, Star } from 'lucide-react';
import { useGamification } from '../context/GamificationContext';

const ACTIVITY_LABELS = {
    quiz: 'Quiz Completed',
    review: 'Card Reviewed',
    notes: 'Notes Generated',
    qa: 'Q&A Studied',
    chat: 'Chat Message',
    pomodoro: 'Pomodoro Done',
    path: 'Path Progress',
    exam: 'Exam Practice',
    knowledge_graph: 'Graph Explored',
};

const XPToast = () => {
    const { xpEvents, dismissXpEvent } = useGamification();

    return (
        <div className="fixed top-4 left-1/2 -translate-x-1/2 z-[110] flex flex-col items-center gap-2 pointer-events-none">
            <AnimatePresence>
                {xpEvents.map((event) => (
                    <motion.div
                        key={event.id}
                        initial={{ opacity: 0, y: -30, scale: 0.8 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: -20, scale: 0.9 }}
                        transition={{ type: 'spring', stiffness: 400, damping: 25 }}
                        className="pointer-events-auto"
                    >
                        {/* Level Up Special Toast */}
                        {event.leveled_up ? (
                            <motion.div
                                className="relative bg-gradient-to-r from-amber-500 via-yellow-500 to-amber-500 text-white rounded-2xl shadow-2xl shadow-amber-500/30 px-6 py-4 flex items-center gap-4 min-w-[320px] overflow-hidden"
                            >
                                {/* Shimmer effect */}
                                <motion.div
                                    animate={{ x: ['-100%', '200%'] }}
                                    transition={{ duration: 1.5, repeat: 2 }}
                                    className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent"
                                />
                                
                                <div className="relative">
                                    <motion.div
                                        animate={{ rotate: [0, 10, -10, 0], scale: [1, 1.2, 1] }}
                                        transition={{ duration: 0.6, delay: 0.3 }}
                                        className="h-12 w-12 bg-white/20 backdrop-blur-sm rounded-xl flex items-center justify-center border border-white/30"
                                    >
                                        <TrendingUp className="h-6 w-6" />
                                    </motion.div>
                                    {/* Particle dots */}
                                    {[...Array(6)].map((_, i) => (
                                        <motion.div
                                            key={i}
                                            initial={{ opacity: 0, scale: 0 }}
                                            animate={{
                                                opacity: [0, 1, 0],
                                                scale: [0, 1, 0],
                                                x: [0, (Math.random() - 0.5) * 60],
                                                y: [0, (Math.random() - 0.5) * 60],
                                            }}
                                            transition={{ duration: 1, delay: 0.2 + i * 0.1 }}
                                            className="absolute top-1/2 left-1/2 h-2 w-2 bg-yellow-200 rounded-full"
                                        />
                                    ))}
                                </div>

                                <div className="relative z-10">
                                    <p className="text-sm font-black uppercase tracking-wider">Level Up!</p>
                                    <p className="text-lg font-bold">
                                        Level {event.new_level} — {event.new_level_title}
                                    </p>
                                    <p className="text-xs text-white/80 font-medium">
                                        +{event.xp_earned} XP earned
                                    </p>
                                </div>

                                <motion.div
                                    animate={{ rotate: 360 }}
                                    transition={{ duration: 2, ease: 'linear', repeat: Infinity }}
                                    className="ml-auto"
                                >
                                    <Star className="h-6 w-6 text-yellow-200 fill-yellow-200" />
                                </motion.div>
                            </motion.div>
                        ) : (
                            /* Regular XP Toast */
                            <motion.div
                                className="relative bg-white rounded-xl shadow-xl shadow-black/10 border border-[#E6D5CC] px-5 py-3 flex items-center gap-3 min-w-[240px] overflow-hidden"
                                onClick={() => dismissXpEvent(event.id)}
                            >
                                {/* Accent bar */}
                                <div className="absolute left-0 top-0 bottom-0 w-1 bg-gradient-to-b from-[#C8A288] to-amber-400 rounded-l-xl" />

                                <motion.div
                                    initial={{ scale: 0, rotate: -180 }}
                                    animate={{ scale: 1, rotate: 0 }}
                                    transition={{ type: 'spring', stiffness: 300, delay: 0.1 }}
                                    className="h-9 w-9 rounded-lg bg-gradient-to-br from-amber-400 to-amber-500 flex items-center justify-center shadow-md shadow-amber-400/30 shrink-0"
                                >
                                    <Zap className="h-4.5 w-4.5 text-white" />
                                </motion.div>

                                <div>
                                    <motion.p
                                        initial={{ opacity: 0, x: 10 }}
                                        animate={{ opacity: 1, x: 0 }}
                                        transition={{ delay: 0.15 }}
                                        className="text-sm font-bold text-[#4A3B32]"
                                    >
                                        +{event.xp_earned} XP
                                    </motion.p>
                                    <p className="text-[11px] text-[#8a6a5c] font-medium">
                                        {ACTIVITY_LABELS[event.activity] || 'Activity'}
                                    </p>
                                </div>

                                {/* Floating +XP number animation */}
                                <motion.span
                                    initial={{ opacity: 1, y: 0 }}
                                    animate={{ opacity: 0, y: -25 }}
                                    transition={{ duration: 1.5, delay: 0.5 }}
                                    className="absolute right-4 top-1 text-xs font-black text-amber-400"
                                >
                                    +{event.xp_earned}
                                </motion.span>
                            </motion.div>
                        )}

                        {/* New Badge Toast */}
                        {event.new_badges && event.new_badges.length > 0 && (
                            <motion.div
                                initial={{ opacity: 0, y: 10, scale: 0.9 }}
                                animate={{ opacity: 1, y: 0, scale: 1 }}
                                transition={{ delay: 0.5 }}
                                className="mt-1 bg-gradient-to-r from-purple-500 to-indigo-600 text-white rounded-xl shadow-xl shadow-purple-500/20 px-5 py-3 flex items-center gap-3 min-w-[260px]"
                            >
                                <motion.div
                                    animate={{ rotate: [0, 15, -15, 0] }}
                                    transition={{ duration: 0.5, delay: 0.8, repeat: 2 }}
                                    className="h-9 w-9 bg-white/20 rounded-lg flex items-center justify-center backdrop-blur-sm border border-white/20"
                                >
                                    <Award className="h-5 w-5" />
                                </motion.div>
                                <div>
                                    <p className="text-xs font-black uppercase tracking-wider text-white/80">Badge Unlocked!</p>
                                    <p className="text-sm font-bold">{event.new_badges[0].title}</p>
                                </div>
                            </motion.div>
                        )}
                    </motion.div>
                ))}
            </AnimatePresence>
        </div>
    );
};

export default XPToast;
