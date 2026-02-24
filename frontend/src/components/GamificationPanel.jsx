import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Trophy, Star, Zap, Target, Award, Crown,
    Shield, TrendingUp, BookOpen, Brain, Timer,
    MessageSquare, FileText, Map, CheckCircle,
    Rocket, X, ChevronRight, Lock, Sparkles
} from 'lucide-react';
import { useGamification } from '../context/GamificationContext';

// Icon mapping for badges
const BADGE_ICONS = {
    'rocket': Rocket,
    'check-circle': CheckCircle,
    'award': Award,
    'target': Target,
    'map': Map,
    'star': Star,
    'trophy': Trophy,
    'timer': Timer,
    'brain': Brain,
    'file-text': FileText,
    'book-open': BookOpen,
    'repeat': TrendingUp,
    'message-square': MessageSquare,
    'trending-up': TrendingUp,
    'shield': Shield,
    'crown': Crown,
    'zap': Zap,
};

// Badge category colors
const CATEGORY_COLORS = {
    milestone: { bg: 'from-blue-400 to-blue-600', ring: 'ring-blue-300', text: 'text-blue-600', light: 'bg-blue-50' },
    achievement: { bg: 'from-amber-400 to-amber-600', ring: 'ring-amber-300', text: 'text-amber-600', light: 'bg-amber-50' },
    habit: { bg: 'from-emerald-400 to-emerald-600', ring: 'ring-emerald-300', text: 'text-emerald-600', light: 'bg-emerald-50' },
    level: { bg: 'from-purple-400 to-purple-600', ring: 'ring-purple-300', text: 'text-purple-600', light: 'bg-purple-50' },
    xp: { bg: 'from-rose-400 to-rose-600', ring: 'ring-rose-300', text: 'text-rose-600', light: 'bg-rose-50' },
};

const GamificationPanel = ({ onClose }) => {
    const { data } = useGamification();
    const [activeView, setActiveView] = useState('overview'); // overview, badges, levels

    if (!data) {
        return (
            <div className="w-[420px] max-h-[85vh] bg-white rounded-2xl shadow-2xl border border-[#E6D5CC] p-6 flex items-center justify-center">
                <div className="flex flex-col items-center gap-3">
                    <div className="h-10 w-10 border-3 border-[#C8A288] border-t-transparent rounded-full animate-spin" />
                    <p className="text-sm text-[#8a6a5c]">Loading achievements...</p>
                </div>
            </div>
        );
    }

    const earnedBadgeIds = new Set((data.badges || []).map(b => b.id));
    const allBadges = data.all_badges || [];
    const allLevels = data.all_levels || [];
    const stats = data.stats || {};

    return (
        <motion.div
            initial={{ opacity: 0, y: 10, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, scale: 0.97 }}
            transition={{ duration: 0.25, ease: 'easeOut' }}
            className="w-[420px] max-h-[85vh] bg-white rounded-2xl shadow-2xl border border-[#E6D5CC] overflow-hidden flex flex-col"
        >
            {/* Header — Level Card */}
            <div className="relative overflow-hidden">
                {/* Gradient background */}
                <div className="bg-gradient-to-br from-[#C8A288] via-[#B08B72] to-[#8a6a5c] px-6 pt-5 pb-6">
                    {/* Decorative circles */}
                    <div className="absolute top-0 right-0 w-32 h-32 bg-white/5 rounded-full -translate-y-1/2 translate-x-1/2" />
                    <div className="absolute bottom-0 left-0 w-24 h-24 bg-white/5 rounded-full translate-y-1/2 -translate-x-1/2" />
                    
                    <div className="relative z-10">
                        <div className="flex justify-between items-start mb-4">
                            <div className="flex items-center gap-3">
                                {/* Level badge */}
                                <div className="relative">
                                    <div className="h-14 w-14 bg-white/20 backdrop-blur-sm rounded-2xl flex items-center justify-center border border-white/30 shadow-lg">
                                        <span className="text-2xl font-black text-white">{data.level}</span>
                                    </div>
                                    <div className="absolute -bottom-1 -right-1 h-5 w-5 bg-yellow-400 rounded-full flex items-center justify-center shadow-md">
                                        <Star className="h-3 w-3 text-yellow-800 fill-yellow-800" />
                                    </div>
                                </div>
                                <div>
                                    <h3 className="text-lg font-bold text-white">{data.level_title}</h3>
                                    <p className="text-white/70 text-xs font-medium">Level {data.level}</p>
                                </div>
                            </div>
                            <button
                                onClick={onClose}
                                className="p-1.5 hover:bg-white/10 rounded-lg transition-colors text-white/70 hover:text-white"
                            >
                                <X className="h-5 w-5" />
                            </button>
                        </div>

                        {/* XP Progress Bar */}
                        <div className="space-y-2">
                            <div className="flex justify-between items-center text-xs">
                                <span className="text-white/80 font-semibold flex items-center gap-1.5">
                                    <Zap className="h-3.5 w-3.5 text-yellow-300" />
                                    {data.total_xp.toLocaleString()} XP Total
                                </span>
                                {data.next_level && (
                                    <span className="text-white/60">
                                        {data.xp_in_level}/{data.xp_needed} to Level {data.next_level.level}
                                    </span>
                                )}
                            </div>
                            <div className="h-3 bg-black/20 rounded-full overflow-hidden backdrop-blur-sm">
                                <motion.div
                                    initial={{ width: 0 }}
                                    animate={{ width: `${data.level_progress || 0}%` }}
                                    transition={{ duration: 1.2, ease: 'easeOut', delay: 0.3 }}
                                    className="h-full bg-gradient-to-r from-yellow-300 via-yellow-400 to-amber-400 rounded-full relative"
                                >
                                    <div className="absolute inset-0 bg-gradient-to-b from-white/30 to-transparent rounded-full" />
                                    {/* Shimmer effect */}
                                    <motion.div
                                        animate={{ x: ['-100%', '200%'] }}
                                        transition={{ duration: 2, repeat: Infinity, repeatDelay: 3 }}
                                        className="absolute inset-0 bg-gradient-to-r from-transparent via-white/40 to-transparent rounded-full"
                                    />
                                </motion.div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Tab Navigation */}
            <div className="flex border-b border-[#E6D5CC]/50 px-2 pt-2 bg-[#FDF6F0]/50">
                {[
                    { id: 'overview', label: 'Overview', icon: TrendingUp },
                    { id: 'badges', label: `Badges (${data.badges?.length || 0}/${allBadges.length})`, icon: Award },
                    { id: 'levels', label: 'Levels', icon: Crown },
                ].map(tab => (
                    <button
                        key={tab.id}
                        onClick={() => setActiveView(tab.id)}
                        className={`flex items-center gap-1.5 px-4 py-2.5 text-xs font-semibold rounded-t-lg transition-all flex-1 justify-center ${
                            activeView === tab.id
                                ? 'bg-white text-[#4A3B32] border border-[#E6D5CC]/50 border-b-white -mb-px shadow-sm'
                                : 'text-[#8a6a5c] hover:text-[#4A3B32] hover:bg-white/50'
                        }`}
                    >
                        <tab.icon className="h-3.5 w-3.5" />
                        {tab.label}
                    </button>
                ))}
            </div>

            {/* Content Area */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar">
                <AnimatePresence mode="wait">
                    {activeView === 'overview' && (
                        <motion.div
                            key="overview"
                            initial={{ opacity: 0, x: -10 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: 10 }}
                            className="space-y-4"
                        >
                            {/* Quick Stats Grid */}
                            <div className="grid grid-cols-3 gap-2">
                                <StatCard icon={CheckCircle} label="Quizzes" value={stats.quizzes_completed || 0} color="blue" />
                                <StatCard icon={Star} label="Perfect" value={stats.perfect_scores || 0} color="amber" />
                                <StatCard icon={Target} label="Questions" value={stats.questions_answered || 0} color="emerald" />
                                <StatCard icon={Timer} label="Pomodoros" value={stats.pomodoros_completed || 0} color="purple" />
                                <StatCard icon={FileText} label="Notes" value={stats.notes_generated || 0} color="rose" />
                                <StatCard icon={Brain} label="Reviews" value={stats.reviews_completed || 0} color="cyan" />
                            </div>

                            {/* Recent Badges */}
                            <div>
                                <h4 className="text-sm font-bold text-[#4A3B32] mb-2 flex items-center gap-1.5">
                                    <Award className="h-4 w-4 text-[#C8A288]" />
                                    Recent Badges
                                </h4>
                                {data.badges && data.badges.length > 0 ? (
                                    <div className="grid grid-cols-2 gap-2">
                                        {data.badges.slice(-4).reverse().map((badge, i) => (
                                            <BadgeMini key={badge.id || i} badge={badge} earned />
                                        ))}
                                    </div>
                                ) : (
                                    <div className="bg-[#FDF6F0] rounded-xl p-4 text-center">
                                        <Award className="h-8 w-8 text-[#E6D5CC] mx-auto mb-2" />
                                        <p className="text-xs text-[#8a6a5c]">Complete activities to earn badges!</p>
                                    </div>
                                )}
                            </div>

                            {/* Next Milestones */}
                            <div>
                                <h4 className="text-sm font-bold text-[#4A3B32] mb-2 flex items-center gap-1.5">
                                    <Rocket className="h-4 w-4 text-[#C8A288]" />
                                    Next Milestones
                                </h4>
                                <div className="space-y-1.5">
                                    {getNextMilestones(stats, data.total_xp, data.level, earnedBadgeIds, allBadges).map((m, i) => (
                                        <MilestoneRow key={i} milestone={m} />
                                    ))}
                                </div>
                            </div>
                        </motion.div>
                    )}

                    {activeView === 'badges' && (
                        <motion.div
                            key="badges"
                            initial={{ opacity: 0, x: -10 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: 10 }}
                            className="space-y-4"
                        >
                            {Object.entries(groupByCategory(allBadges)).map(([category, badges]) => (
                                <div key={category}>
                                    <h4 className="text-xs font-bold text-[#8a6a5c] uppercase tracking-wider mb-2">
                                        {category}
                                    </h4>
                                    <div className="grid grid-cols-2 gap-2">
                                        {badges.map((badge) => (
                                            <BadgeCard
                                                key={badge.id}
                                                badge={badge}
                                                earned={earnedBadgeIds.has(badge.id)}
                                            />
                                        ))}
                                    </div>
                                </div>
                            ))}
                        </motion.div>
                    )}

                    {activeView === 'levels' && (
                        <motion.div
                            key="levels"
                            initial={{ opacity: 0, x: -10 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: 10 }}
                            className="space-y-2"
                        >
                            {allLevels.map((lvl, i) => {
                                const isCurrentLevel = lvl.level === data.level;
                                const isUnlocked = data.level >= lvl.level;
                                const nextLvl = allLevels[i + 1];

                                return (
                                    <motion.div
                                        key={lvl.level}
                                        initial={{ opacity: 0, y: 10 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        transition={{ delay: i * 0.04 }}
                                        className={`flex items-center gap-3 p-3 rounded-xl border transition-all ${
                                            isCurrentLevel
                                                ? 'bg-gradient-to-r from-[#FDF6F0] to-amber-50/50 border-[#C8A288] shadow-md shadow-[#C8A288]/10'
                                                : isUnlocked
                                                    ? 'bg-white border-[#E6D5CC]/50'
                                                    : 'bg-gray-50/50 border-gray-100 opacity-60'
                                        }`}
                                    >
                                        {/* Level Number */}
                                        <div className={`h-10 w-10 rounded-xl flex items-center justify-center font-bold text-sm shrink-0 ${
                                            isCurrentLevel
                                                ? 'bg-gradient-to-br from-[#C8A288] to-[#8a6a5c] text-white shadow-md shadow-[#C8A288]/30'
                                                : isUnlocked
                                                    ? 'bg-[#E6D5CC] text-[#4A3B32]'
                                                    : 'bg-gray-200 text-gray-400'
                                        }`}>
                                            {isUnlocked ? lvl.level : <Lock className="h-4 w-4" />}
                                        </div>

                                        {/* Level Info */}
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center gap-2">
                                                <p className={`text-sm font-bold truncate ${isUnlocked ? 'text-[#4A3B32]' : 'text-gray-400'}`}>
                                                    {lvl.title}
                                                </p>
                                                {isCurrentLevel && (
                                                    <span className="text-[9px] font-bold uppercase bg-[#C8A288] text-white px-1.5 py-0.5 rounded-full tracking-wider">
                                                        Current
                                                    </span>
                                                )}
                                            </div>
                                            <p className="text-[11px] text-[#8a6a5c]">
                                                {lvl.xp_required.toLocaleString()} XP required
                                            </p>

                                            {/* Progress bar for current level */}
                                            {isCurrentLevel && nextLvl && (
                                                <div className="mt-1.5 h-1.5 bg-[#E6D5CC] rounded-full overflow-hidden">
                                                    <motion.div
                                                        initial={{ width: 0 }}
                                                        animate={{ width: `${data.level_progress || 0}%` }}
                                                        transition={{ duration: 1, delay: 0.5 }}
                                                        className="h-full bg-gradient-to-r from-[#C8A288] to-amber-400 rounded-full"
                                                    />
                                                </div>
                                            )}
                                        </div>

                                        {/* Checkmark / lock icon */}
                                        {isUnlocked && !isCurrentLevel && (
                                            <CheckCircle className="h-5 w-5 text-emerald-400 shrink-0" />
                                        )}
                                        {isCurrentLevel && (
                                            <Sparkles className="h-5 w-5 text-amber-400 shrink-0" />
                                        )}
                                    </motion.div>
                                );
                            })}
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        </motion.div>
    );
};

// ===================== Sub-Components =====================

const StatCard = ({ icon: Icon, label, value, color }) => {
    const colorMap = {
        blue: 'bg-blue-50 text-blue-600',
        amber: 'bg-amber-50 text-amber-600',
        emerald: 'bg-emerald-50 text-emerald-600',
        purple: 'bg-purple-50 text-purple-600',
        rose: 'bg-rose-50 text-rose-600',
        cyan: 'bg-cyan-50 text-cyan-600',
    };
    const c = colorMap[color] || colorMap.blue;

    return (
        <div className="bg-[#FDF6F0] rounded-xl p-3 text-center border border-[#E6D5CC]/30">
            <div className={`h-8 w-8 rounded-lg ${c} flex items-center justify-center mx-auto mb-1.5`}>
                <Icon className="h-4 w-4" />
            </div>
            <p className="text-lg font-black text-[#4A3B32]">{value}</p>
            <p className="text-[10px] text-[#8a6a5c] font-medium">{label}</p>
        </div>
    );
};

const BadgeMini = ({ badge, earned }) => {
    const category = badge.category || 'milestone';
    const colors = CATEGORY_COLORS[category] || CATEGORY_COLORS.milestone;
    const Icon = BADGE_ICONS[badge.icon] || Award;

    return (
        <div className={`flex items-center gap-2.5 p-2.5 rounded-xl border ${
            earned ? `${colors.light} border-${category === 'achievement' ? 'amber' : category === 'habit' ? 'emerald' : 'blue'}-200/50` : 'bg-gray-50 border-gray-100'
        }`}>
            <div className={`h-9 w-9 rounded-lg bg-gradient-to-br ${colors.bg} flex items-center justify-center shrink-0 shadow-sm`}>
                <Icon className="h-4 w-4 text-white" />
            </div>
            <div className="min-w-0">
                <p className="text-xs font-bold text-[#4A3B32] truncate">{badge.title}</p>
                <p className="text-[10px] text-[#8a6a5c] truncate">{badge.description}</p>
            </div>
        </div>
    );
};

const BadgeCard = ({ badge, earned }) => {
    const category = badge.category || 'milestone';
    const colors = CATEGORY_COLORS[category] || CATEGORY_COLORS.milestone;
    const Icon = BADGE_ICONS[badge.icon] || Award;

    return (
        <motion.div
            whileHover={earned ? { scale: 1.03 } : {}}
            className={`relative p-3 rounded-xl border text-center transition-all ${
                earned
                    ? `${colors.light} border-transparent shadow-sm`
                    : 'bg-gray-50/50 border-gray-100'
            }`}
        >
            {/* Badge icon */}
            <div className={`h-11 w-11 rounded-xl mx-auto mb-2 flex items-center justify-center ${
                earned
                    ? `bg-gradient-to-br ${colors.bg} shadow-md`
                    : 'bg-gray-200'
            }`}>
                {earned ? (
                    <Icon className="h-5 w-5 text-white" />
                ) : (
                    <Lock className="h-4 w-4 text-gray-400" />
                )}
            </div>

            <p className={`text-xs font-bold truncate ${earned ? 'text-[#4A3B32]' : 'text-gray-400'}`}>
                {badge.title}
            </p>
            <p className={`text-[10px] leading-tight mt-0.5 ${earned ? 'text-[#8a6a5c]' : 'text-gray-300'}`}>
                {badge.description}
            </p>

            {/* Earned sparkle */}
            {earned && (
                <div className="absolute -top-1 -right-1">
                    <div className={`h-5 w-5 rounded-full bg-gradient-to-br ${colors.bg} flex items-center justify-center shadow-sm`}>
                        <CheckCircle className="h-3 w-3 text-white" />
                    </div>
                </div>
            )}
        </motion.div>
    );
};

const MilestoneRow = ({ milestone }) => {
    const progress = Math.min(Math.round((milestone.current / milestone.target) * 100), 100);

    return (
        <div className="flex items-center gap-3 p-2.5 bg-[#FDF6F0] rounded-xl border border-[#E6D5CC]/30">
            <div className="h-8 w-8 rounded-lg bg-[#E6D5CC]/50 flex items-center justify-center shrink-0">
                <milestone.icon className="h-4 w-4 text-[#C8A288]" />
            </div>
            <div className="flex-1 min-w-0">
                <div className="flex justify-between items-center mb-1">
                    <p className="text-xs font-semibold text-[#4A3B32] truncate">{milestone.title}</p>
                    <span className="text-[10px] text-[#8a6a5c] font-medium shrink-0 ml-2">
                        {milestone.current}/{milestone.target}
                    </span>
                </div>
                <div className="h-1.5 bg-[#E6D5CC] rounded-full overflow-hidden">
                    <div
                        className="h-full bg-gradient-to-r from-[#C8A288] to-amber-400 rounded-full transition-all duration-500"
                        style={{ width: `${progress}%` }}
                    />
                </div>
            </div>
        </div>
    );
};

// ===================== Helpers =====================

function groupByCategory(badges) {
    const groups = {};
    for (const badge of badges) {
        const cat = badge.category || 'other';
        if (!groups[cat]) groups[cat] = [];
        groups[cat].push(badge);
    }
    return groups;
}

function getNextMilestones(stats, totalXP, level, earnedIds, allBadges) {
    const milestones = [];

    // Find unearned badges and calculate progress toward them
    const milestoneMap = [
        { id: 'first_quiz', stat: 'quizzes_completed', target: 1, icon: Rocket, title: 'Complete first quiz' },
        { id: 'quizzes_10', stat: 'quizzes_completed', target: 10, icon: CheckCircle, title: 'Complete 10 quizzes' },
        { id: 'quizzes_50', stat: 'quizzes_completed', target: 50, icon: Award, title: 'Complete 50 quizzes' },
        { id: 'perfect_score', stat: 'perfect_scores', target: 1, icon: Star, title: 'Score 100% on a quiz' },
        { id: 'questions_100', stat: 'questions_answered', target: 100, icon: Target, title: 'Answer 100 questions' },
        { id: 'focus_10', stat: 'pomodoros_completed', target: 10, icon: Timer, title: 'Complete 10 Pomodoros' },
        { id: 'notes_10', stat: 'notes_generated', target: 10, icon: FileText, title: 'Generate 10 notes' },
        { id: 'reviews_50', stat: 'reviews_completed', target: 50, icon: Brain, title: 'Review 50 flashcards' },
        { id: 'xp_1000', stat: null, target: 1000, icon: Zap, title: 'Earn 1,000 XP' },
    ];

    for (const m of milestoneMap) {
        if (earnedIds.has(m.id)) continue;
        const current = m.stat ? (stats[m.stat] || 0) : totalXP;
        if (current < m.target) {
            milestones.push({ ...m, current });
        }
        if (milestones.length >= 3) break;
    }

    return milestones;
}

export default GamificationPanel;
