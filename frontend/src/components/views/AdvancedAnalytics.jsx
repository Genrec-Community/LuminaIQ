import React, { useState, useEffect } from 'react';
import {
    BarChart3, TrendingUp, Clock, Target, Brain,
    BookOpen, Calendar, Award, Flame, ChevronDown,
    ChevronUp, Zap, CheckCircle, XCircle, Activity,
    PieChart, Timer, Star, Trophy, ArrowUp, ArrowDown
} from 'lucide-react';
import { getPerformance, getLearningDashboard, getWeakTopics, getPomodoro, getStreak } from '../../api';
import { getActivityHeatmap, getAccuracyTrend, getMaxDailyActivity, fetchActivity } from '../../utils/studyActivity';

const AdvancedAnalytics = ({ projectId, documents = [], bookIsolation = true }) => {
    const [selectedBook, setSelectedBook] = useState('all');
    const [loading, setLoading] = useState(true);
    const [analytics, setAnalytics] = useState(null);
    const [timeRange, setTimeRange] = useState('week'); // 'today', 'week', 'month', 'all'
    const [expandedSection, setExpandedSection] = useState('overview');
    const [activityData, setActivityData] = useState({});

    useEffect(() => {
        loadAnalytics();
    }, [projectId, selectedBook]);

    const loadAnalytics = async () => {
        setLoading(true);
        try {
            // Load performance data
            const perfData = await getPerformance(projectId);
            const dashData = await getLearningDashboard(projectId);
            const weakData = await getWeakTopics(projectId, 10, 0.2);

            // Load pomodoro data from API
            const docId = bookIsolation && selectedBook !== 'all' ? selectedBook : null;
            const studyTime = await getPomodoro(projectId, docId);

            // Load streak data from API
            const streakData = await getStreak(projectId);

            // Load activity data for accuracy trend
            const actData = await fetchActivity(projectId, 90);
            setActivityData(actData);

            // Process performance by book if isolation enabled
            let bookPerformance = {};
            if (bookIsolation && perfData.performance) {
                documents.forEach(doc => {
                    bookPerformance[doc.id] = {
                        name: doc.filename,
                        topics: [],
                        totalCorrect: 0,
                        totalWrong: 0,
                        accuracy: 0,
                    };
                });

                // This would need backend support to filter by document
                // For now, we'll show aggregate data
            }

            setAnalytics({
                performance: perfData.performance || [],
                dashboard: dashData,
                weakTopics: weakData.weak_topics || [],
                studyTime: studyTime,
                streak: streakData,
                bookPerformance,
            });
        } catch (error) {
            console.error('Failed to load analytics:', error);
        } finally {
            setLoading(false);
        }
    };

    // Calculate stats
    const getStats = () => {
        if (!analytics) return null;

        const perf = analytics.performance || [];
        const totalCorrect = perf.reduce((sum, p) => sum + (p.correct_count || 0), 0);
        const totalWrong = perf.reduce((sum, p) => sum + (p.wrong_count || 0), 0);
        const totalAttempts = totalCorrect + totalWrong;
        const accuracy = totalAttempts > 0 ? Math.round((totalCorrect / totalAttempts) * 100) : 0;

        // Calculate topic mastery
        const masteredTopics = perf.filter(p => {
            const total = (p.correct_count || 0) + (p.wrong_count || 0);
            const acc = total > 0 ? (p.correct_count / total) * 100 : 0;
            return acc >= 80 && total >= 5;
        }).length;

        return {
            totalTopics: perf.length,
            masteredTopics,
            totalCorrect,
            totalWrong,
            totalAttempts,
            accuracy,
            studySessions: analytics.studyTime?.sessions || 0,
            focusTime: analytics.studyTime?.focusTime || 0,
            streak: analytics.streak?.current || 0,
            longestStreak: analytics.streak?.longest || 0,
        };
    };

    const stats = getStats();

    const formatTime = (seconds) => {
        const hours = Math.floor(seconds / 3600);
        const mins = Math.floor((seconds % 3600) / 60);
        if (hours > 0) return `${hours}h ${mins}m`;
        return `${mins}m`;
    };

    const StatCard = ({ icon: Icon, label, value, subValue, color, trend }) => (
        <div className="bg-white rounded-xl border border-[#E6D5CC] p-4 hover:shadow-md transition-shadow">
            <div className="flex items-start justify-between">
                <div className={`h-10 w-10 rounded-xl ${color} flex items-center justify-center`}>
                    <Icon className="h-5 w-5 text-white" />
                </div>
                {trend && (
                    <div className={`flex items-center gap-1 text-xs font-medium ${
                        trend > 0 ? 'text-green-600' : 'text-red-500'
                    }`}>
                        {trend > 0 ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />}
                        {Math.abs(trend)}%
                    </div>
                )}
            </div>
            <p className="text-2xl font-bold text-[#4A3B32] mt-3">{value}</p>
            <p className="text-sm text-[#8a6a5c]">{label}</p>
            {subValue && <p className="text-xs text-[#C8A288] mt-1">{subValue}</p>}
        </div>
    );

    const ProgressBar = ({ value, max, color = 'bg-[#C8A288]', showLabel = true }) => (
        <div className="w-full">
            <div className="h-2 bg-[#E6D5CC] rounded-full overflow-hidden">
                <div
                    className={`h-full ${color} rounded-full transition-all duration-500`}
                    style={{ width: `${Math.min((value / max) * 100, 100)}%` }}
                />
            </div>
            {showLabel && (
                <div className="flex justify-between text-xs text-[#8a6a5c] mt-1">
                    <span>{value}</span>
                    <span>{max}</span>
                </div>
            )}
        </div>
    );

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <div className="text-center">
                    <div className="relative w-16 h-16 mx-auto mb-4">
                        <div className="absolute inset-0 border-4 border-[#E6D5CC] rounded-full" />
                        <div className="absolute inset-0 border-4 border-[#C8A288] rounded-full border-t-transparent animate-spin" />
                        <BarChart3 className="absolute inset-0 m-auto h-6 w-6 text-[#C8A288]" />
                    </div>
                    <p className="text-[#8a6a5c]">Loading analytics...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="h-full overflow-y-auto p-4 md:p-6 space-y-6">
            {/* Header */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                    <h2 className="text-2xl font-bold text-[#4A3B32] flex items-center gap-2">
                        <BarChart3 className="h-7 w-7 text-[#C8A288]" />
                        Learning Analytics
                    </h2>
                    <p className="text-[#8a6a5c]">Track your progress and identify areas to improve</p>
                </div>

                {/* Book Selector (if isolation enabled) */}
                {bookIsolation && documents.length > 1 && (
                    <select
                        value={selectedBook}
                        onChange={(e) => setSelectedBook(e.target.value)}
                        className="px-4 py-2 bg-white border border-[#E6D5CC] rounded-xl focus:ring-2 focus:ring-[#C8A288] text-[#4A3B32] font-medium"
                    >
                        <option value="all">All Books</option>
                        {documents.map(doc => (
                            <option key={doc.id} value={doc.id}>
                                {doc.filename.length > 30 ? doc.filename.substring(0, 27) + '...' : doc.filename}
                            </option>
                        ))}
                    </select>
                )}
            </div>

            {/* Streak Banner */}
            {stats?.streak > 0 && (
                <div className="bg-gradient-to-r from-orange-500 to-amber-500 text-white rounded-2xl p-4 flex items-center gap-4">
                    <div className="h-14 w-14 bg-white/20 rounded-xl flex items-center justify-center backdrop-blur-sm">
                        <Flame className="h-8 w-8" />
                    </div>
                    <div className="flex-1">
                        <p className="text-2xl font-bold">{stats.streak} Day Streak!</p>
                        <p className="text-sm opacity-90">Keep it up! Your longest streak: {stats.longestStreak} days</p>
                    </div>
                    <Trophy className="h-10 w-10 opacity-50" />
                </div>
            )}

            {/* Main Stats Grid */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <StatCard
                    icon={Target}
                    label="Accuracy"
                    value={`${stats?.accuracy || 0}%`}
                    subValue={`${stats?.totalCorrect || 0} correct answers`}
                    color="bg-green-500"
                    trend={getAccuracyTrend(activityData, 7)}
                />
                <StatCard
                    icon={BookOpen}
                    label="Topics Studied"
                    value={stats?.totalTopics || 0}
                    subValue={`${stats?.masteredTopics || 0} mastered`}
                    color="bg-blue-500"
                />
                <StatCard
                    icon={Timer}
                    label="Focus Time"
                    value={formatTime(stats?.focusTime || 0)}
                    subValue={`${stats?.studySessions || 0} sessions`}
                    color="bg-purple-500"
                />
                <StatCard
                    icon={Zap}
                    label="Questions"
                    value={stats?.totalAttempts || 0}
                    subValue={`${stats?.totalWrong || 0} to review`}
                    color="bg-amber-500"
                />
            </div>

            {/* Performance Overview */}
            <div className="bg-white rounded-2xl border border-[#E6D5CC] overflow-hidden">
                <button
                    onClick={() => setExpandedSection(expandedSection === 'overview' ? '' : 'overview')}
                    className="w-full p-4 flex items-center justify-between hover:bg-[#FDF6F0] transition-colors"
                >
                    <div className="flex items-center gap-3">
                        <div className="h-10 w-10 bg-[#C8A288]/20 rounded-xl flex items-center justify-center">
                            <Activity className="h-5 w-5 text-[#C8A288]" />
                        </div>
                        <div className="text-left">
                            <h3 className="font-bold text-[#4A3B32]">Performance Overview</h3>
                            <p className="text-sm text-[#8a6a5c]">Topic-by-topic breakdown</p>
                        </div>
                    </div>
                    {expandedSection === 'overview' ? (
                        <ChevronUp className="h-5 w-5 text-[#8a6a5c]" />
                    ) : (
                        <ChevronDown className="h-5 w-5 text-[#8a6a5c]" />
                    )}
                </button>

                {expandedSection === 'overview' && (
                    <div className="p-4 border-t border-[#E6D5CC] space-y-3">
                        {analytics?.performance?.length > 0 ? (
                            analytics.performance.slice(0, 10).map((topic, idx) => {
                                const total = (topic.correct_count || 0) + (topic.wrong_count || 0);
                                const accuracy = total > 0 ? Math.round((topic.correct_count / total) * 100) : 0;
                                const isMastered = accuracy >= 80 && total >= 5;

                                return (
                                    <div key={idx} className="p-3 bg-[#FDF6F0] rounded-xl">
                                        <div className="flex items-center justify-between mb-2">
                                            <div className="flex items-center gap-2">
                                                {isMastered ? (
                                                    <Star className="h-4 w-4 text-amber-500 fill-amber-500" />
                                                ) : accuracy >= 60 ? (
                                                    <CheckCircle className="h-4 w-4 text-green-500" />
                                                ) : (
                                                    <XCircle className="h-4 w-4 text-red-500" />
                                                )}
                                                <span className="font-medium text-[#4A3B32] truncate max-w-[200px]">
                                                    {topic.topic}
                                                </span>
                                            </div>
                                            <span className={`font-bold ${
                                                accuracy >= 80 ? 'text-green-600' :
                                                accuracy >= 60 ? 'text-amber-600' : 'text-red-600'
                                            }`}>
                                                {accuracy}%
                                            </span>
                                        </div>
                                        <ProgressBar
                                            value={topic.correct_count || 0}
                                            max={total || 1}
                                            color={accuracy >= 80 ? 'bg-green-500' : accuracy >= 60 ? 'bg-amber-500' : 'bg-red-500'}
                                            showLabel={false}
                                        />
                                        <div className="flex justify-between text-xs text-[#8a6a5c] mt-1">
                                            <span>{topic.correct_count || 0} correct</span>
                                            <span>{topic.wrong_count || 0} wrong</span>
                                        </div>
                                    </div>
                                );
                            })
                        ) : (
                            <div className="text-center py-8 text-[#8a6a5c]">
                                <Brain className="h-12 w-12 mx-auto mb-3 opacity-50" />
                                <p>No quiz data yet. Complete some quizzes to see your performance!</p>
                            </div>
                        )}
                    </div>
                )}
            </div>

            {/* Weak Topics */}
            <div className="bg-white rounded-2xl border border-[#E6D5CC] overflow-hidden">
                <button
                    onClick={() => setExpandedSection(expandedSection === 'weak' ? '' : 'weak')}
                    className="w-full p-4 flex items-center justify-between hover:bg-[#FDF6F0] transition-colors"
                >
                    <div className="flex items-center gap-3">
                        <div className="h-10 w-10 bg-red-100 rounded-xl flex items-center justify-center">
                            <Target className="h-5 w-5 text-red-500" />
                        </div>
                        <div className="text-left">
                            <h3 className="font-bold text-[#4A3B32]">Areas to Improve</h3>
                            <p className="text-sm text-[#8a6a5c]">{analytics?.weakTopics?.length || 0} topics need attention</p>
                        </div>
                    </div>
                    {expandedSection === 'weak' ? (
                        <ChevronUp className="h-5 w-5 text-[#8a6a5c]" />
                    ) : (
                        <ChevronDown className="h-5 w-5 text-[#8a6a5c]" />
                    )}
                </button>

                {expandedSection === 'weak' && (
                    <div className="p-4 border-t border-[#E6D5CC] space-y-3">
                        {analytics?.weakTopics?.length > 0 ? (
                            analytics.weakTopics.map((topic, idx) => (
                                <div key={idx} className="p-3 bg-red-50 rounded-xl border border-red-100">
                                    <div className="flex items-center justify-between">
                                        <span className="font-medium text-[#4A3B32]">{topic.topic}</span>
                                        <span className="text-sm text-red-600 font-medium">
                                            {Math.round((1 - topic.weakness_score) * 100)}% accuracy
                                        </span>
                                    </div>
                                    <p className="text-sm text-[#8a6a5c] mt-1">{topic.recommendation}</p>
                                </div>
                            ))
                        ) : (
                            <div className="text-center py-8 text-[#8a6a5c]">
                                <Award className="h-12 w-12 mx-auto mb-3 opacity-50" />
                                <p>Great job! No weak topics detected.</p>
                            </div>
                        )}
                    </div>
                )}
            </div>

            {/* Study Calendar Heatmap — real activity data */}
            <StudyActivityHeatmap projectId={projectId} />
        </div>
    );
};

/**
 * StudyActivityHeatmap — Renders real activity data from API
 */
const StudyActivityHeatmap = ({ projectId }) => {
    const [heatmapRange, setHeatmapRange] = useState(7); // 7, 14, or 30 days
    const [activityData, setActivityData] = useState({});

    useEffect(() => {
        const load = async () => {
            try {
                const data = await fetchActivity(projectId, 90);
                setActivityData(data);
            } catch (err) {
                console.warn('Failed to load activity data:', err);
            }
        };
        load();
    }, [projectId]);

    const heatmapData = getActivityHeatmap(activityData, heatmapRange);
    const maxActivity = getMaxDailyActivity(activityData);

    const getIntensityClass = (total) => {
        if (total === 0) return 'bg-[#E6D5CC]';
        const ratio = total / maxActivity;
        if (ratio > 0.7) return 'bg-green-500';
        if (ratio > 0.4) return 'bg-green-300';
        return 'bg-green-100';
    };

    const totalActivities = heatmapData.reduce((s, d) => s + d.total, 0);
    const activeDays = heatmapData.filter(d => d.total > 0).length;

    return (
        <div className="bg-white rounded-2xl border border-[#E6D5CC] p-4">
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                    <div className="h-10 w-10 bg-[#C8A288]/20 rounded-xl flex items-center justify-center">
                        <Calendar className="h-5 w-5 text-[#C8A288]" />
                    </div>
                    <div>
                        <h3 className="font-bold text-[#4A3B32]">Study Activity</h3>
                        <p className="text-sm text-[#8a6a5c]">
                            {totalActivities > 0
                                ? `${totalActivities} activities across ${activeDays} day${activeDays !== 1 ? 's' : ''}`
                                : 'No activity recorded yet'}
                        </p>
                    </div>
                </div>

                {/* Range selector */}
                <div className="flex gap-1">
                    {[
                        { label: '7d', value: 7 },
                        { label: '14d', value: 14 },
                        { label: '30d', value: 30 },
                    ].map(({ label, value }) => (
                        <button
                            key={value}
                            onClick={() => setHeatmapRange(value)}
                            className={`px-2.5 py-1 text-xs font-medium rounded-lg transition-colors ${
                                heatmapRange === value
                                    ? 'bg-[#C8A288] text-white'
                                    : 'text-[#8a6a5c] hover:bg-[#FDF6F0]'
                            }`}
                        >
                            {label}
                        </button>
                    ))}
                </div>
            </div>

            {/* Heatmap grid */}
            <div className={`grid gap-2 ${
                heatmapRange <= 7 ? 'grid-cols-7' :
                heatmapRange <= 14 ? 'grid-cols-7' : 'grid-cols-10'
            }`}>
                {heatmapData.map((day) => (
                    <div key={day.date} className="text-center group relative">
                        <p className="text-xs text-[#8a6a5c] mb-1">{day.dayName}</p>
                        <div
                            className={`h-8 rounded-lg ${getIntensityClass(day.total)} transition-all hover:ring-2 hover:ring-[#C8A288]/40 cursor-default`}
                        />
                        {/* Tooltip on hover */}
                        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 hidden group-hover:block z-10">
                            <div className="bg-[#4A3B32] text-white text-xs rounded-lg px-3 py-2 whitespace-nowrap shadow-lg">
                                <p className="font-medium">{day.date}</p>
                                {day.total > 0 ? (
                                    <div className="mt-1 space-y-0.5 text-[#E6D5CC]">
                                        {day.quiz > 0 && <p>{day.quiz} quiz{day.quiz !== 1 ? 'zes' : ''}</p>}
                                        {day.review > 0 && <p>{day.review} review{day.review !== 1 ? 's' : ''}</p>}
                                        {day.notes > 0 && <p>{day.notes} note{day.notes !== 1 ? 's' : ''}</p>}
                                        {day.qa > 0 && <p>{day.qa} Q&A</p>}
                                        {day.pomodoro > 0 && <p>{day.pomodoro} pomodoro{day.pomodoro !== 1 ? 's' : ''}</p>}
                                        {day.chat > 0 && <p>{day.chat} chat{day.chat !== 1 ? 's' : ''}</p>}
                                        {day.exam > 0 && <p>{day.exam} exam prep{day.exam !== 1 ? 's' : ''}</p>}
                                        {day.path > 0 && <p>{day.path} learning path{day.path !== 1 ? 's' : ''}</p>}
                                        {day.knowledge_graph > 0 && <p>{day.knowledge_graph} graph exploration{day.knowledge_graph !== 1 ? 's' : ''}</p>}
                                    </div>
                                ) : (
                                    <p className="mt-1 text-[#E6D5CC]">No activity</p>
                                )}
                            </div>
                        </div>
                    </div>
                ))}
            </div>

            {/* Legend */}
            <div className="flex items-center justify-end gap-2 mt-3">
                <span className="text-xs text-[#8a6a5c]">Less</span>
                <div className="flex gap-1">
                    <div className="h-3 w-3 rounded bg-[#E6D5CC]" />
                    <div className="h-3 w-3 rounded bg-green-100" />
                    <div className="h-3 w-3 rounded bg-green-300" />
                    <div className="h-3 w-3 rounded bg-green-500" />
                </div>
                <span className="text-xs text-[#8a6a5c]">More</span>
            </div>
        </div>
    );
};

export default AdvancedAnalytics;
