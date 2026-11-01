import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Trophy, Star, Zap, Target, Award, Crown,
    Shield, TrendingUp, BookOpen, Brain, Timer,
    MessageSquare, FileText, Map, CheckCircle,
    Rocket, Lock, Sparkles, X
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

// Badge category colors — earthy palette compatible
const CATEGORY_COLORS = {
    milestone: { bg: 'from-blue-400 to-blue-600', text: 'text-blue-600', light: 'bg-blue-50', border: 'border-blue-200/50' },
    achievement: { bg: 'from-amber-400 to-amber-600', text: 'text-amber-600', light: 'bg-amber-50', border: 'border-amber-200/50' },
    habit: { bg: 'from-emerald-400 to-emerald-600', text: 'text-emerald-600', light: 'bg-emerald-50', border: 'border-emerald-200/50' },
    level: { bg: 'from-purple-400 to-purple-600', text: 'text-purple-600', light: 'bg-purple-50', border: 'border-purple-200/50' },
    xp: { bg: 'from-rose-400 to-rose-600', text: 'text-rose-600', light: 'bg-rose-50', border: 'border-rose-200/50' },
};

/**
 * GamificationPanel — Floating popup triggered from the header toolbar.
 * 420px wide, close button, tabs for Overview / Badges / Levels.
 */
const GamificationPanel = ({ onClose }) => {
    const { data } = useGamification();
    const [activeTab, setActiveTab] = useState('overview');

    if (!data) {
        return (
            <div className="w-[420px] bg-white rounded-2xl shadow-2xl border border-[#E6D5CC] p-8 flex flex-col items-center gap-3">
                <div className="h-10 w-10 border-3 border-[#1E5C42] border-t-transparent rounded-full animate-spin" />
                <p className="text-sm text-[#5E5046]">Loading progress...</p>
            </div>
        );
    }

    const earnedBadgeIds = new Set((data.badges || []).map(b => b.id));
    const allBadges = data.all_badges || [];
    const allLevels = data.all_levels || [];
    const stats = data.stats || {};
    const earnedCount = data.badges?.length || 0;

    const tabs = [
        { id: 'overview', label: 'Overview', icon: TrendingUp },
        { id: 'badges', label: `Badges (${earnedCount})`, icon: Award },
        { id: 'levels', label: 'Levels', icon: Crown },
    ];

    return (
        <div className="w-[420px] max-h-[85vh] bg-white rounded-2xl shadow-2xl border border-[#E6D5CC] flex flex-col overflow-hidden">
            {/* Header with gradient */}
            <div className="relative overflow-hidden shrink-0">
                <div className="bg-gradient-to-br from-[#1E5C42] via-[#163628] to-[#5E5046] px-5 pt-4 pb-4">
                    {/* Decorative circles */}
                    <div className="absolute top-0 right-0 w-32 h-32 bg-white/5 rounded-full -translate-y-1/2 translate-x-1/2" />
                    <div className="absolute bottom-0 left-0 w-20 h-20 bg-white/5 rounded-full translate-y-1/2 -translate-x-1/2" />

                    <div className="relative z-10">
                        {/* Title + Close */}
                        <div className="flex items-center justify-between mb-3">
                            <div className="flex items-center gap-2">
                                <Trophy className="h-5 w-5 text-yellow-300" />
                                <h3 className="text-white font-bold text-base">Your Progress</h3>
                            </div>
                            <button
                                onClick={onClose}
                                className="p-1.5 hover:bg-white/20 rounded-lg transition-colors"
                            >
                                <X className="h-4 w-4 text-white/80" />
                            </button>
                        </div>

                        {/* Level + XP */}
                        <div className="flex items-center gap-3 mb-3">
                            <div className="relative">
                                <div className="h-14 w-14 bg-white/20 backdrop-blur-sm rounded-xl flex items-center justify-center border border-white/30 shadow-lg">
                                    <span className="text-2xl font-black text-white">{data.level}</span>
                                </div>
                                <div className="absolute -bottom-1 -right-1 h-5 w-5 bg-yellow-400 rounded-full flex items-center justify-center shadow-md">
                                    <Star className="h-3 w-3 text-yellow-800 fill-yellow-800" />
                                </div>
                            </div>
                            <div className="flex-1 min-w-0">
                                <h4 className="text-base font-bold text-white truncate">{data.level_title}</h4>
                                <p className="text-white/70 text-sm font-medium flex items-center gap-1">
                                    <Zap className="h-3.5 w-3.5 text-yellow-300" />
                                    {data.total_xp?.toLocaleString()} XP
                                </p>
                            </div>
                        </div>

                        {/* XP Progress Bar */}
                        <div className="space-y-1.5">
                            <div className="flex justify-between items-center text-xs">
                                <span className="text-white/70 font-medium">Progress</span>
                                {data.next_level && (
                                    <span className="text-white/60">
                                        {data.xp_in_level}/{data.xp_needed} to Lv.{data.next_level.level}
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
                                    <motion.div
                                        animate={{ x: ['-100%', '200%'] }}
                                        transition={{ duration: 2, repeat: Infinity, repeatDelay: 4 }}
                                        className="absolute inset-0 bg-gradient-to-r from-transparent via-white/40 to-transparent rounded-full"
                                    />
                                </motion.div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Tab Bar */}
            <div className="flex border-b border-[#E6D5CC] bg-[#FDF6F0]/50 shrink-0">
                {tabs.map(tab => {
                    const Icon = tab.icon;
                    const isActive = activeTab === tab.id;
                    return (
                        <button
                            key={tab.id}
                            onClick={() => setActiveTab(tab.id)}
                            className={`flex-1 flex items-center justify-center gap-1.5 py-3 text-xs font-bold transition-all border-b-2 ${
                                isActive
                                    ? 'border-[#1E5C42] text-[#1E5C42] bg-white'
                                    : 'border-transparent text-[#5E5046] hover:text-[#163628] hover:bg-white/50'
                            }`}
                        >
                            <Icon className="h-3.5 w-3.5" />
                            {tab.label}
                        </button>
                    );
                })}
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto p-4 custom-scrollbar">
                {activeTab === 'overview' && renderOverview(stats, data, earnedBadgeIds, allBadges)}
                {activeTab === 'badges' && renderBadges(data.badges || [], allBadges, earnedBadgeIds)}
                {activeTab === 'levels' && renderLevels(data, allLevels)}
            </div>
        </div>
    );
};

// ===================== Tab Renderers =====================

/** Today's adaptive goal: answer N questions, starting with the weakest topic. */
export const DailyGoalCard = ({ goal, compact = false }) => {
    if (!goal) return null;
    const pct = goal.target ? Math.round((100 * goal.progress) / goal.target) : 0;
    const f = goal.focus || {};
    return (
        <div className="rounded-xl border border-[#E6D5CC] bg-[#FDF6F0] px-4 py-3">
            <div className="flex items-center justify-between gap-2">
                <p className="text-sm font-bold text-[#163628]">
                    {goal.completed ? "Today's goal: done ✓" : `Today's goal: answer ${goal.target} questions`}
                </p>
                <span className="text-xs font-semibold tabular-nums text-[#5E5046]">{goal.progress}/{goal.target}</span>
            </div>
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-[#E6D5CC]" role="progressbar"
                aria-valuemin={0} aria-valuemax={goal.target} aria-valuenow={goal.progress} aria-label="Daily goal progress">
                <div className="h-full rounded-full bg-[#1E5C42] transition-all" style={{ width: `${Math.min(100, pct)}%` }} />
            </div>
            {!compact && !goal.completed && (f.topic || f.due_reviews) ? (
                <p className="mt-1.5 text-[11px] text-[#5E5046]">
                    {f.topic ? <>Start with <span className="font-semibold">{f.topic}</span>. </> : null}
                    {f.due_reviews ? `${f.due_reviews} review${f.due_reviews === 1 ? '' : 's'} due.` : ''}
                </p>
            ) : null}
        </div>
    );
};

/** This week's class board (Class 5-10, when the class has it switched on). */
const Leaderboard = () => {
    const [board, setBoard] = useState(null);
    React.useEffect(() => {
        let alive = true;
        import('../api').then(({ getLeaderboard }) => getLeaderboard()).then((b) => { if (alive) setBoard(b); }).catch(() => {});
        return () => { alive = false; };
    }, []);
    if (!board?.enabled || !board.rows?.length) return null;
    return (
        <div>
            <h4 className="text-[10px] font-bold text-[#5E5046] uppercase tracking-wider mb-2">Your class this week</h4>
            <ol className="space-y-1">
                {board.rows.map((r) => (
                    <li key={`${r.rank}-${r.name}`} className={`flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm ${r.me ? 'bg-amber-50 font-bold' : ''}`}>
                        <span className="w-6 text-[#5E5046] tabular-nums">{r.rank}.</span>
                        <span className="flex-1 text-[#163628]">{r.me ? `${r.name} (you)` : r.name}</span>
                        <span className="tabular-nums text-[#1E5C42]">{r.xp} XP</span>
                    </li>
                ))}
            </ol>
        </div>
    );
};

function renderOverview(stats, data, earnedBadgeIds, allBadges) {
    const streakDays = data.streak_days ?? 0;
    const style = data.style || 'quiet';
    const goal = data.daily_goal;
    const days = goal?.focus?.days_to_exam;
    const milestones = getNextMilestones(stats, data.total_xp, data.level, earnedBadgeIds, allBadges);
    const Milestones = (
        <div>
            <h4 className="text-[10px] font-bold text-[#5E5046] uppercase tracking-wider mb-2">Next milestones</h4>
            <div className="space-y-2">
                {milestones.map((m, i) => <MilestoneRow key={i} milestone={m} />)}
                {milestones.length === 0 && (
                    <p className="py-3 text-center text-sm font-semibold text-[#163628]">Every milestone reached.</p>
                )}
            </div>
        </div>
    );

    // Research: milestones only, no streaks or confetti
    if (style === 'milestones') {
        return <div className="space-y-4">{Milestones}</div>;
    }

    const Streak = (
        <div className="flex items-center gap-3 px-4 py-3 rounded-xl"
            style={{ background: 'linear-gradient(135deg, #3a2208 0%, #5a3210 100%)', border: '1px solid rgba(200,162,136,0.25)' }}>
            <span className="text-2xl" role="img" aria-label="flame">🔥</span>
            <div className="flex-1">
                <p className="text-white font-black text-lg leading-none">{streakDays} day{streakDays !== 1 ? 's' : ''} of learning</p>
                <p className="text-amber-100/80 text-[11px] font-medium mt-0.5">
                    {streakDays === 0 ? 'Learn something today to start a streak.'
                        : data.freeze_available ? 'Miss a day? Your weekly freeze keeps the streak going.'
                            : "This week's freeze is used. Keep going tomorrow!"}
                </p>
            </div>
        </div>
    );

    return (
        <div className="space-y-4">
            {style === 'exam' && days != null && (
                <div className="rounded-xl bg-[#163628] px-4 py-3 text-white">
                    <p className="text-2xl font-black leading-none">{days === 0 ? 'Exam today' : `${days} day${days === 1 ? '' : 's'}`}</p>
                    <p className="mt-0.5 text-xs text-white/70">{days === 0 ? 'You’ve got this.' : 'to your exam'}</p>
                </div>
            )}
            <DailyGoalCard goal={goal} />
            {style !== 'quiet' && Streak}
            <div>
                <h4 className="text-[10px] font-bold text-[#5E5046] uppercase tracking-wider mb-2">Learning</h4>
                <div className="grid grid-cols-2 gap-2">
                    <StatCard icon={TrendingUp} label="Mastery points" value={stats.mastery_points || 0} color="emerald" />
                    <StatCard icon={CheckCircle} label="Mistakes fixed" value={stats.mistakes_fixed || 0} color="blue" />
                    <StatCard icon={Brain} label="Reviews on time" value={stats.reviews_on_time || 0} color="cyan" />
                    <StatCard icon={Target} label="Goals reached" value={stats.goals_met || 0} color="amber" />
                </div>
                {style === 'quiet' && streakDays > 0 && (
                    <p className="mt-2 text-xs text-[#5E5046]">{streakDays}-day learning streak · best {data.best_streak}</p>
                )}
            </div>
            {style === 'playful' && data.leaderboard && <Leaderboard />}
            {style !== 'quiet' && Milestones}
        </div>
    );
}

function renderBadges(earnedBadges, allBadges, earnedBadgeIds) {
    return (
        <div className="space-y-4">
            {/* Earned Badges */}
            {earnedBadges.length > 0 && (
                <div>
                    <h4 className="text-[10px] font-bold text-[#5E5046] uppercase tracking-wider mb-2">
                        Recently Earned
                    </h4>
                    <div className="grid grid-cols-2 gap-2">
                        {earnedBadges.slice(-4).reverse().map((badge, i) => (
                            <BadgeMini key={badge.id || i} badge={badge} earned />
                        ))}
                    </div>
                </div>
            )}

            {/* All Badges by Category */}
            {Object.entries(groupByCategory(allBadges)).map(([category, badges]) => (
                <div key={category}>
                    <h4 className="text-[10px] font-bold text-[#5E5046] uppercase tracking-wider mb-2 capitalize">
                        {category}
                    </h4>
                    <div className="grid grid-cols-3 gap-2">
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
        </div>
    );
}

function renderLevels(data, allLevels) {
    return (
        <div className="space-y-2">
            {allLevels.map((lvl, i) => {
                const isCurrentLevel = lvl.level === data.level;
                const isUnlocked = data.level >= lvl.level;
                const nextLvl = allLevels[i + 1];

                return (
                    <div
                        key={lvl.level}
                        className={`flex items-center gap-3 p-3 rounded-xl border transition-all ${
                            isCurrentLevel
                                ? 'bg-gradient-to-r from-[#FDF6F0] to-amber-50/50 border-[#1E5C42] shadow-sm'
                                : isUnlocked
                                    ? 'bg-white border-[#E6D5CC]/50'
                                    : 'bg-gray-50/50 border-gray-100 opacity-50'
                        }`}
                    >
                        {/* Level Number */}
                        <div className={`h-10 w-10 rounded-lg flex items-center justify-center font-bold text-sm shrink-0 ${
                            isCurrentLevel
                                ? 'bg-gradient-to-br from-[#1E5C42] to-[#5E5046] text-white shadow-sm'
                                : isUnlocked
                                    ? 'bg-[#E6D5CC] text-[#163628]'
                                    : 'bg-gray-200 text-gray-400'
                        }`}>
                            {isUnlocked ? lvl.level : <Lock className="h-3.5 w-3.5" />}
                        </div>

                        {/* Level Info */}
                        <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-1.5">
                                <p className={`text-sm font-bold truncate ${isUnlocked ? 'text-[#163628]' : 'text-gray-400'}`}>
                                    {lvl.title}
                                </p>
                                {isCurrentLevel && (
                                    <Sparkles className="h-3.5 w-3.5 text-amber-400 shrink-0" />
                                )}
                            </div>
                            <p className="text-[11px] text-[#5E5046]">
                                {lvl.xp_required.toLocaleString()} XP
                            </p>

                            {/* Progress bar for current level */}
                            {isCurrentLevel && nextLvl && (
                                <div className="mt-1.5 h-1.5 bg-[#E6D5CC] rounded-full overflow-hidden">
                                    <motion.div
                                        initial={{ width: 0 }}
                                        animate={{ width: `${data.level_progress || 0}%` }}
                                        transition={{ duration: 1, delay: 0.5 }}
                                        className="h-full bg-gradient-to-r from-[#1E5C42] to-amber-400 rounded-full"
                                    />
                                </div>
                            )}
                        </div>

                        {/* Status icon */}
                        {isUnlocked && !isCurrentLevel && (
                            <CheckCircle className="h-5 w-5 text-emerald-400 shrink-0" />
                        )}
                    </div>
                );
            })}
        </div>
    );
}

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
            <p className="text-base font-black text-[#163628]">{value}</p>
            <p className="text-[10px] text-[#5E5046] font-medium">{label}</p>
        </div>
    );
};

const BadgeMini = ({ badge, earned }) => {
    const category = badge.category || 'milestone';
    const colors = CATEGORY_COLORS[category] || CATEGORY_COLORS.milestone;
    const Icon = BADGE_ICONS[badge.icon] || Award;

    return (
        <div className={`flex items-center gap-2.5 p-2.5 rounded-xl border ${
            earned ? `${colors.light} ${colors.border}` : 'bg-gray-50 border-gray-100'
        }`}>
            <div className={`h-8 w-8 rounded-lg bg-gradient-to-br ${colors.bg} flex items-center justify-center shrink-0 shadow-sm`}>
                <Icon className="h-4 w-4 text-white" />
            </div>
            <div className="min-w-0">
                <p className="text-xs font-bold text-[#163628] truncate">{badge.title}</p>
                <p className="text-[10px] text-[#5E5046] truncate">{badge.description}</p>
            </div>
        </div>
    );
};

const BadgeCard = ({ badge, earned }) => {
    const category = badge.category || 'milestone';
    const colors = CATEGORY_COLORS[category] || CATEGORY_COLORS.milestone;
    const Icon = BADGE_ICONS[badge.icon] || Award;

    return (
        <div
            className={`relative p-2.5 rounded-xl border text-center transition-all ${
                earned
                    ? `${colors.light} border-transparent shadow-sm`
                    : 'bg-gray-50/50 border-gray-100'
            }`}
        >
            <div className={`h-10 w-10 rounded-lg mx-auto mb-1.5 flex items-center justify-center ${
                earned
                    ? `bg-gradient-to-br ${colors.bg} shadow-sm`
                    : 'bg-gray-200'
            }`}>
                {earned ? (
                    <Icon className="h-5 w-5 text-white" />
                ) : (
                    <Lock className="h-3.5 w-3.5 text-gray-400" />
                )}
            </div>

            <p className={`text-[11px] font-bold truncate ${earned ? 'text-[#163628]' : 'text-gray-400'}`}>
                {badge.title}
            </p>
            <p className={`text-[9px] leading-tight mt-0.5 ${earned ? 'text-[#5E5046]' : 'text-gray-300'}`}>
                {badge.description}
            </p>

            {earned && (
                <div className="absolute -top-1 -right-1">
                    <div className={`h-5 w-5 rounded-full bg-gradient-to-br ${colors.bg} flex items-center justify-center shadow-sm`}>
                        <CheckCircle className="h-3 w-3 text-white" />
                    </div>
                </div>
            )}
        </div>
    );
};

const MilestoneRow = ({ milestone }) => {
    const progress = Math.min(Math.round((milestone.current / milestone.target) * 100), 100);

    return (
        <div className="flex items-center gap-3 p-3 bg-[#FDF6F0] rounded-xl border border-[#E6D5CC]/30">
            <div className="h-8 w-8 rounded-lg bg-[#E6D5CC]/50 flex items-center justify-center shrink-0">
                <milestone.icon className="h-4 w-4 text-[#1E5C42]" />
            </div>
            <div className="flex-1 min-w-0">
                <div className="flex justify-between items-center mb-1">
                    <p className="text-xs font-semibold text-[#163628] truncate">{milestone.title}</p>
                    <span className="text-[10px] text-[#5E5046] font-medium shrink-0 ml-2">
                        {milestone.current}/{milestone.target}
                    </span>
                </div>
                <div className="h-1.5 bg-[#E6D5CC] rounded-full overflow-hidden">
                    <div
                        className="h-full bg-gradient-to-r from-[#1E5C42] to-amber-400 rounded-full transition-all duration-500"
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

function getNextMilestones(stats, totalXP, level, earnedIds) {
    const milestoneMap = [
        { id: 'first_gain', stat: 'mastery_points', target: 1, icon: Rocket, title: 'Raise your mastery of a topic' },
        { id: 'mastery_100', stat: 'mastery_points', target: 100, icon: TrendingUp, title: 'Gain 100 mastery points' },
        { id: 'mistakes_10', stat: 'mistakes_fixed', target: 10, icon: CheckCircle, title: 'Fix 10 questions you got wrong' },
        { id: 'goals_7', stat: 'goals_met', target: 7, icon: Target, title: 'Reach your daily goal 7 times' },
        { id: 'reviews_50', stat: 'reviews_on_time', target: 50, icon: Brain, title: 'Do 50 reviews on time' },
        { id: 'plan_10', stat: 'plan_steps', target: 10, icon: Map, title: 'Complete 10 learning-path topics' },
        { id: 'mastery_500', stat: 'mastery_points', target: 500, icon: Award, title: 'Gain 500 mastery points' },
    ];
    const out = [];
    for (const m of milestoneMap) {
        if (earnedIds.has(m.id)) continue;
        const current = stats[m.stat] || 0;
        if (current < m.target) out.push({ ...m, current });
        if (out.length >= 3) break;
    }
    return out;
}

export default GamificationPanel;
