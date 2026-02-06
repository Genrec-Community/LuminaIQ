import React, { useState, useEffect } from 'react';
import { 
    Brain, BookOpen, Clock, CheckCircle, AlertTriangle, 
    Loader2, RefreshCw, Star, TrendingUp, Calendar,
    BookMarked, RotateCcw, AlertCircle
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { 
    getLearningDashboard, 
    getDueCards, 
    recordReview, 
    getWeakTopics
} from '../../api';
import { useToast } from '../../context/ToastContext';

const StudyDashboard = ({ projectId, availableTopics }) => {
    const toast = useToast();
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [dashboard, setDashboard] = useState(null);
    const [activeTab, setActiveTab] = useState('overview'); // 'overview' | 'review' | 'weak'
    
    // Review Session State
    const [reviewSession, setReviewSession] = useState(false);
    const [currentCard, setCurrentCard] = useState(null);
    const [showAnswer, setShowAnswer] = useState(false);
    const [reviewCards, setReviewCards] = useState([]);
    const [reviewIndex, setReviewIndex] = useState(0);
    const [submittingReview, setSubmittingReview] = useState(false);

    useEffect(() => {
        loadDashboard();
    }, [projectId]);

    const loadDashboard = async () => {
        setLoading(true);
        setError(null);
        try {
            const data = await getLearningDashboard(projectId);
            setDashboard(data);
        } catch (err) {
            console.error('Failed to load dashboard:', err);
            setError(err.response?.data?.detail || err.message || 'Failed to load dashboard');
        } finally {
            setLoading(false);
        }
    };

    const startReviewSession = async () => {
        try {
            const data = await getDueCards(projectId, 20);
            if (data.due_cards && data.due_cards.length > 0) {
                setReviewCards(data.due_cards);
                setCurrentCard(data.due_cards[0]);
                setReviewIndex(0);
                setShowAnswer(false);
                setReviewSession(true);
            } else {
                toast.info('No cards due for review!');
            }
        } catch (error) {
            console.error('Failed to load review cards:', error);
        }
    };

    const handleReviewResponse = async (quality) => {
        if (!currentCard || submittingReview) return;
        
        setSubmittingReview(true);
        try {
            await recordReview(currentCard.id, quality);
            
            // Move to next card
            const nextIndex = reviewIndex + 1;
            if (nextIndex < reviewCards.length) {
                setReviewIndex(nextIndex);
                setCurrentCard(reviewCards[nextIndex]);
                setShowAnswer(false);
            } else {
                // Session complete
                setReviewSession(false);
                loadDashboard(); // Refresh stats
            }
        } catch (error) {
            console.error('Failed to record review:', error);
        } finally {
            setSubmittingReview(false);
        }
    };

    // Loading State
    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center h-64 gap-4">
                <div className="relative">
                    <div className="h-16 w-16 border-4 border-[#E6D5CC] rounded-full"></div>
                    <div className="absolute inset-0 h-16 w-16 border-4 border-[#C8A288] rounded-full border-t-transparent animate-spin"></div>
                    <Brain className="absolute inset-0 m-auto h-6 w-6 text-[#C8A288]" />
                </div>
                <p className="text-[#8a6a5c] font-medium">Loading your study dashboard...</p>
            </div>
        );
    }

    // Error State
    if (error) {
        return (
            <div className="flex flex-col items-center justify-center h-64 gap-4 p-8">
                <div className="p-4 bg-red-50 rounded-full">
                    <AlertCircle className="h-12 w-12 text-red-400" />
                </div>
                <h3 className="text-xl font-bold text-[#4A3B32]">Failed to Load Dashboard</h3>
                <p className="text-[#8a6a5c] text-center max-w-md">{error}</p>
                <button
                    onClick={loadDashboard}
                    className="mt-2 px-6 py-3 bg-[#C8A288] text-white rounded-xl font-bold hover:bg-[#B08B72] transition-colors flex items-center gap-2"
                >
                    <RefreshCw className="h-5 w-5" />
                    Try Again
                </button>
            </div>
        );
    }

    // Empty State - No Performance Data Yet
    if (!dashboard || !dashboard.overall || dashboard.overall.total_topics_studied === 0) {
        return (
            <div className="flex flex-col items-center justify-center h-full min-h-[400px] p-8">
                <div className="max-w-md text-center">
                    <div className="inline-flex items-center justify-center p-6 bg-gradient-to-br from-[#FDF6F0] to-white rounded-3xl shadow-sm border border-[#E6D5CC] mb-6">
                        <Brain className="h-16 w-16 text-[#C8A288]" />
                    </div>
                    <h2 className="text-2xl font-bold text-[#4A3B32] mb-3">Start Your Learning Journey!</h2>
                    <p className="text-[#8a6a5c] mb-8 leading-relaxed">
                        Your study dashboard will show your progress, weak topics, and spaced repetition cards once you start taking quizzes.
                    </p>
                    
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
                        <div className="bg-white p-4 rounded-xl border border-[#E6D5CC]">
                            <div className="h-10 w-10 bg-purple-100 rounded-lg flex items-center justify-center mx-auto mb-2">
                                <CheckCircle className="h-5 w-5 text-purple-600" />
                            </div>
                            <p className="text-sm font-bold text-[#4A3B32]">Take Quizzes</p>
                            <p className="text-xs text-[#8a6a5c]">Answer MCQ questions</p>
                        </div>
                        <div className="bg-white p-4 rounded-xl border border-[#E6D5CC]">
                            <div className="h-10 w-10 bg-blue-100 rounded-lg flex items-center justify-center mx-auto mb-2">
                                <TrendingUp className="h-5 w-5 text-blue-600" />
                            </div>
                            <p className="text-sm font-bold text-[#4A3B32]">Track Progress</p>
                            <p className="text-xs text-[#8a6a5c]">See your improvement</p>
                        </div>
                        <div className="bg-white p-4 rounded-xl border border-[#E6D5CC]">
                            <div className="h-10 w-10 bg-green-100 rounded-lg flex items-center justify-center mx-auto mb-2">
                                <Star className="h-5 w-5 text-green-600" />
                            </div>
                            <p className="text-sm font-bold text-[#4A3B32]">Master Topics</p>
                            <p className="text-xs text-[#8a6a5c]">Achieve 80%+ accuracy</p>
                        </div>
                    </div>
                    
                    <p className="text-sm text-[#8a6a5c]">
                        Go to <span className="font-bold text-[#C8A288]">Answer Quiz</span> or <span className="font-bold text-[#C8A288]">Learning Path</span> to begin!
                    </p>
                </div>
            </div>
        );
    }

    // Review Session View
    if (reviewSession && currentCard) {
        return (
            <div className="max-w-2xl mx-auto p-4">
                {/* Progress */}
                <div className="flex justify-between items-center mb-6">
                    <div>
                        <h3 className="text-lg font-bold text-[#4A3B32]">Review Session</h3>
                        <p className="text-sm text-[#8a6a5c]">Card {reviewIndex + 1} of {reviewCards.length}</p>
                    </div>
                    <button
                        onClick={() => setReviewSession(false)}
                        className="text-[#8a6a5c] hover:text-[#4A3B32]"
                    >
                        Exit
                    </button>
                </div>
                
                <div className="h-2 w-full bg-[#E6D5CC]/30 rounded-full mb-8 overflow-hidden">
                    <div
                        className="h-full bg-[#C8A288] transition-all duration-300"
                        style={{ width: `${((reviewIndex + 1) / reviewCards.length) * 100}%` }}
                    />
                </div>

                {/* Card */}
                <div className="bg-white rounded-2xl border border-[#E6D5CC] shadow-sm p-6 mb-6">
                    <div className="text-xs font-bold text-[#8a6a5c] uppercase mb-2">{currentCard.topic}</div>
                    
                    <div className="prose prose-lg max-w-none text-[#4A3B32] mb-6">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {currentCard.question}
                        </ReactMarkdown>
                    </div>

                    {!showAnswer ? (
                        <button
                            onClick={() => setShowAnswer(true)}
                            className="w-full py-3 bg-[#C8A288] text-white rounded-xl font-bold hover:bg-[#B08B72] transition-colors"
                        >
                            Show Answer
                        </button>
                    ) : (
                        <div className="space-y-4">
                            <div className="bg-[#FDF6F0] rounded-xl p-4 prose prose-sm max-w-none">
                                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                    {currentCard.answer}
                                </ReactMarkdown>
                            </div>
                            
                            <div className="text-center text-sm text-[#8a6a5c] mb-2">
                                How well did you remember?
                            </div>
                            
                            <div className="grid grid-cols-3 gap-2">
                                <button
                                    onClick={() => handleReviewResponse(1)}
                                    disabled={submittingReview}
                                    className="py-3 bg-red-100 text-red-700 rounded-xl font-bold hover:bg-red-200 transition-colors disabled:opacity-50"
                                >
                                    Again
                                </button>
                                <button
                                    onClick={() => handleReviewResponse(3)}
                                    disabled={submittingReview}
                                    className="py-3 bg-yellow-100 text-yellow-700 rounded-xl font-bold hover:bg-yellow-200 transition-colors disabled:opacity-50"
                                >
                                    Hard
                                </button>
                                <button
                                    onClick={() => handleReviewResponse(5)}
                                    disabled={submittingReview}
                                    className="py-3 bg-green-100 text-green-700 rounded-xl font-bold hover:bg-green-200 transition-colors disabled:opacity-50"
                                >
                                    Easy
                                </button>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        );
    }

    return (
        <div className="max-w-4xl mx-auto p-4 space-y-6">
            {/* Header */}
            <div className="flex justify-between items-center">
                <div>
                    <h2 className="text-2xl font-bold text-[#4A3B32]">Study Dashboard</h2>
                    <p className="text-[#8a6a5c]">Track your learning progress</p>
                </div>
                <button
                    onClick={loadDashboard}
                    className="p-2 hover:bg-[#E6D5CC]/30 rounded-lg text-[#8a6a5c]"
                >
                    <RefreshCw className="h-5 w-5" />
                </button>
            </div>

            {/* Quick Stats */}
            {dashboard?.overall && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="bg-white rounded-xl border border-[#E6D5CC] p-4">
                        <div className="flex items-center gap-2 text-[#8a6a5c] mb-1">
                            <BookOpen className="h-4 w-4" />
                            <span className="text-xs font-bold uppercase">Topics Studied</span>
                        </div>
                        <div className="text-2xl font-black text-[#4A3B32]">
                            {dashboard.overall.total_topics_studied}
                        </div>
                    </div>
                    
                    <div className="bg-white rounded-xl border border-[#E6D5CC] p-4">
                        <div className="flex items-center gap-2 text-[#8a6a5c] mb-1">
                            <CheckCircle className="h-4 w-4" />
                            <span className="text-xs font-bold uppercase">Questions</span>
                        </div>
                        <div className="text-2xl font-black text-[#4A3B32]">
                            {dashboard.overall.total_questions_attempted}
                        </div>
                    </div>
                    
                    <div className="bg-white rounded-xl border border-[#E6D5CC] p-4">
                        <div className="flex items-center gap-2 text-[#8a6a5c] mb-1">
                            <TrendingUp className="h-4 w-4" />
                            <span className="text-xs font-bold uppercase">Accuracy</span>
                        </div>
                        <div className="text-2xl font-black text-green-600">
                            {dashboard.overall.overall_accuracy}%
                        </div>
                    </div>
                    
                    <div className="bg-white rounded-xl border border-[#E6D5CC] p-4">
                        <div className="flex items-center gap-2 text-[#8a6a5c] mb-1">
                            <Calendar className="h-4 w-4" />
                            <span className="text-xs font-bold uppercase">Due Today</span>
                        </div>
                        <div className="text-2xl font-black text-purple-600">
                            {dashboard.review_stats?.due_today || 0}
                        </div>
                    </div>
                </div>
            )}

            {/* Tabs */}
            <div className="flex gap-2 border-b border-[#E6D5CC] pb-2 overflow-x-auto">
                {[
                    { id: 'overview', label: 'Overview', icon: Brain },
                    { id: 'review', label: 'Review Cards', icon: RotateCcw },
                    { id: 'weak', label: 'Weak Topics', icon: AlertTriangle }
                ].map(({ id, label, icon: Icon }) => (
                    <button
                        key={id}
                        onClick={() => {
                            setActiveTab(id);
                        }}
                        className={`px-4 py-2 rounded-lg font-medium text-sm flex items-center gap-2 transition-colors whitespace-nowrap ${
                            activeTab === id
                                ? 'bg-[#C8A288] text-white'
                                : 'text-[#8a6a5c] hover:bg-[#FDF6F0]'
                        }`}
                    >
                        <Icon className="h-4 w-4" />
                        {label}
                    </button>
                ))}
            </div>

            {/* Tab Content */}
            {activeTab === 'overview' && (
                <div className="space-y-6">
                    {/* Due for Review */}
                    {dashboard?.review_stats && (dashboard.review_stats.due_today > 0 || dashboard.review_stats.overdue > 0) && (
                        <div className="bg-purple-50 border border-purple-200 rounded-xl p-6">
                            <div className="flex justify-between items-center">
                                <div>
                                    <h3 className="font-bold text-purple-800 flex items-center gap-2">
                                        <Clock className="h-5 w-5" />
                                        Cards Due for Review
                                    </h3>
                                    <p className="text-purple-600 text-sm mt-1">
                                        {dashboard.review_stats.due_today} due today, {dashboard.review_stats.overdue} overdue
                                    </p>
                                </div>
                                <button
                                    onClick={startReviewSession}
                                    className="px-6 py-3 bg-purple-600 text-white rounded-xl font-bold hover:bg-purple-700 transition-colors"
                                >
                                    Start Review
                                </button>
                            </div>
                        </div>
                    )}

                    {/* Review Stats */}
                    {dashboard?.review_stats && (
                        <div className="bg-white rounded-xl border border-[#E6D5CC] p-6">
                            <h3 className="font-bold text-[#4A3B32] mb-4 flex items-center gap-2">
                                <BookMarked className="h-5 w-5 text-[#C8A288]" />
                                Spaced Repetition Progress
                            </h3>
                            <div className="grid grid-cols-3 gap-4 text-center">
                                <div>
                                    <div className="text-2xl font-black text-blue-600">{dashboard.review_stats.new}</div>
                                    <div className="text-xs text-[#8a6a5c] uppercase font-bold">New</div>
                                </div>
                                <div>
                                    <div className="text-2xl font-black text-yellow-600">{dashboard.review_stats.learning}</div>
                                    <div className="text-xs text-[#8a6a5c] uppercase font-bold">Learning</div>
                                </div>
                                <div>
                                    <div className="text-2xl font-black text-green-600">{dashboard.review_stats.mastered}</div>
                                    <div className="text-xs text-[#8a6a5c] uppercase font-bold">Mastered</div>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Weak Topics Summary */}
                    {dashboard?.weak_topics?.length > 0 && (
                        <div className="bg-white rounded-xl border border-[#E6D5CC] p-6">
                            <h3 className="font-bold text-[#4A3B32] mb-4 flex items-center gap-2">
                                <AlertTriangle className="h-5 w-5 text-orange-500" />
                                Topics to Focus On
                            </h3>
                            <div className="space-y-3">
                                {dashboard.weak_topics.slice(0, 3).map((topic, idx) => (
                                    <div key={idx} className="flex items-center justify-between p-3 bg-[#FDF6F0] rounded-lg">
                                        <span className="font-medium text-[#4A3B32]">{topic.topic}</span>
                                        <span className={`text-sm font-bold ${
                                            topic.weakness_score >= 0.7 ? 'text-red-600' :
                                            topic.weakness_score >= 0.5 ? 'text-orange-600' :
                                            'text-yellow-600'
                                        }`}>
                                            {Math.round(topic.weakness_score * 100)}% weak
                                        </span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            )}

            {activeTab === 'review' && (
                <div className="space-y-4">
                    {dashboard?.review_stats?.total_cards === 0 ? (
                        <div className="text-center py-12 bg-[#FDF6F0] rounded-xl">
                            <BookMarked className="h-12 w-12 text-[#C8A288] mx-auto mb-4" />
                            <h3 className="font-bold text-[#4A3B32] mb-2">No Review Cards Yet</h3>
                            <p className="text-[#8a6a5c]">
                                Take a quiz and create review cards from your wrong answers!
                            </p>
                        </div>
                    ) : (
                        <>
                            <div className="bg-white rounded-xl border border-[#E6D5CC] p-6">
                                <div className="flex justify-between items-center">
                                    <div>
                                        <h3 className="font-bold text-[#4A3B32]">
                                            {dashboard.review_stats.total_cards} Total Cards
                                        </h3>
                                        <p className="text-sm text-[#8a6a5c]">
                                            {dashboard.review_stats.due_today + dashboard.review_stats.overdue} ready for review
                                        </p>
                                    </div>
                                    <button
                                        onClick={startReviewSession}
                                        disabled={dashboard.review_stats.due_today + dashboard.review_stats.overdue === 0}
                                        className="px-6 py-3 bg-[#C8A288] text-white rounded-xl font-bold hover:bg-[#B08B72] transition-colors disabled:opacity-50"
                                    >
                                        Start Review
                                    </button>
                                </div>
                            </div>
                            
                            {dashboard?.due_cards?.map((card, idx) => (
                                <div key={card.id} className="bg-white rounded-xl border border-[#E6D5CC] p-4">
                                    <div className="flex justify-between items-start">
                                        <div>
                                            <div className="text-xs font-bold text-[#8a6a5c] uppercase">{card.topic}</div>
                                            <div className="text-[#4A3B32] mt-1 line-clamp-2">{card.question}</div>
                                        </div>
                                        {card.overdue_days > 0 && (
                                            <span className="text-xs bg-red-100 text-red-700 px-2 py-1 rounded-full">
                                                {card.overdue_days}d overdue
                                            </span>
                                        )}
                                    </div>
                                </div>
                            ))}
                        </>
                    )}
                </div>
            )}

            {activeTab === 'weak' && (
                <div className="space-y-4">
                    {dashboard?.weak_topics?.length === 0 ? (
                        <div className="text-center py-12 bg-[#FDF6F0] rounded-xl">
                            <Star className="h-12 w-12 text-[#C8A288] mx-auto mb-4" />
                            <h3 className="font-bold text-[#4A3B32] mb-2">No Weak Topics Detected</h3>
                            <p className="text-[#8a6a5c]">
                                Take more quizzes to identify areas that need improvement.
                            </p>
                        </div>
                    ) : (
                        dashboard?.weak_topics?.map((topic, idx) => (
                            <div key={idx} className={`bg-white rounded-xl border p-4 ${
                                topic.weakness_score >= 0.7 ? 'border-red-200' :
                                topic.weakness_score >= 0.5 ? 'border-orange-200' :
                                'border-yellow-200'
                            }`}>
                                <div className="flex justify-between items-start mb-2">
                                    <h4 className="font-bold text-[#4A3B32]">{topic.topic}</h4>
                                    <span className={`text-sm font-bold px-3 py-1 rounded-full ${
                                        topic.weakness_score >= 0.7 ? 'bg-red-100 text-red-700' :
                                        topic.weakness_score >= 0.5 ? 'bg-orange-100 text-orange-700' :
                                        'bg-yellow-100 text-yellow-700'
                                    }`}>
                                        {Math.round(topic.weakness_score * 100)}% weak
                                    </span>
                                </div>
                                <div className="text-sm text-[#8a6a5c] mb-2">
                                    {topic.correct_count} correct, {topic.wrong_count} wrong
                                </div>
                                <p className="text-sm text-[#4A3B32] bg-[#FDF6F0] p-3 rounded-lg">
                                    {topic.recommendation}
                                </p>
                            </div>
                        ))
                    )}
                </div>
            )}
        </div>
    );
};

export default StudyDashboard;
