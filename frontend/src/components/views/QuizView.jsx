import React, { useState, useEffect } from 'react';
import { HelpCircle, FileText, LogOut, CheckSquare, X, ChevronDown, Loader2, BookMarked, Brain, Zap, Sparkles, ArrowLeft, Target, Trophy, AlertTriangle } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { generateMCQ, generateSubjectiveTest, submitEvaluation, submitSubjectiveTest, generateNotes, recordPerformance, createCardsFromQuiz, getSuggestedTopic } from '../../api';
import { useToast } from '../../context/ToastContext';

const QuizView = ({ 
    projectId, 
    availableTopics, 
    selectedDocuments,
    // Learning Path integration props
    preSelectedTopic = null,
    preSelectedMode = null,
    cameFromPath = false,
    onReturnToPath = null,
    onQuizComplete = null,
    onQuizActiveChange = null // NEW: Callback to notify parent when quiz is active
}) => {
    const toast = useToast();
    const [quizMode, setQuizMode] = useState('mcq'); // 'mcq' | 'subjective' | 'both'

    // MCQ State
    const [mcqTopic, setMcqTopic] = useState('');
    const [mcqTopicSelection, setMcqTopicSelection] = useState('');
    const [mcqNumQuestions, setMcqNumQuestions] = useState(5);
    const [mcqDifficulty, setMcqDifficulty] = useState('medium'); // 'easy' | 'medium' | 'hard'
    const [mcqTest, setMcqTest] = useState(null);
    const [mcqLoading, setMcqLoading] = useState(false);
    const [mcqUserAnswers, setMcqUserAnswers] = useState({});
    const [mcqSubmitted, setMcqSubmitted] = useState(false);
    const [mcqScore, setMcqScore] = useState(null);
    const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
    
    // Performance & Review Cards State
    const [savingPerformance, setSavingPerformance] = useState(false);
    const [performanceSaved, setPerformanceSaved] = useState(false);
    const [creatingCards, setCreatingCards] = useState(false);
    const [cardsCreated, setCardsCreated] = useState(null);
    
    // Suggested Topic State
    const [suggestedTopic, setSuggestedTopic] = useState(null);
    const [loadingSuggestion, setLoadingSuggestion] = useState(false);

    // Eval (Subjective) State
    const [evalTopic, setEvalTopic] = useState('');
    const [evalTopicSelection, setEvalTopicSelection] = useState('');
    const [evalNumQuestions, setEvalNumQuestions] = useState(3);
    const [evalTest, setEvalTest] = useState(null);
    const [evalUserAnswers, setEvalUserAnswers] = useState({});
    const [evalResult, setEvalResult] = useState(null);
    const [evalLoading, setEvalLoading] = useState(false);
    
    // Combined Mode State (MCQ + Subjective)
    const [bothModePhase, setBothModePhase] = useState('mcq'); // 'mcq' | 'subjective' | 'results'
    const [bothMcqScore, setBothMcqScore] = useState(null);
    const [bothSubjectiveScore, setBothSubjectiveScore] = useState(null);
    const [bothCombinedScore, setBothCombinedScore] = useState(null);
    
    // Notify parent when quiz is active (loading or test exists)
    useEffect(() => {
        if (onQuizActiveChange) {
            const isActive = mcqLoading || evalLoading || mcqTest !== null || evalTest !== null;
            onQuizActiveChange(isActive);
        }
    }, [mcqLoading, evalLoading, mcqTest, evalTest, onQuizActiveChange]);
    
    // Handle pre-selected topic from Learning Path
    useEffect(() => {
        if (preSelectedTopic) {
            setMcqTopic(preSelectedTopic);
            setMcqTopicSelection(preSelectedTopic);
            setEvalTopic(preSelectedTopic);
            setEvalTopicSelection(preSelectedTopic);
            
            // Set mode based on preSelectedMode
            if (preSelectedMode === 'mcq') {
                setQuizMode('mcq');
                setMcqNumQuestions(10);
            } else if (preSelectedMode === 'subjective') {
                setQuizMode('subjective');
                setEvalNumQuestions(2);
            } else if (preSelectedMode === 'both') {
                setQuizMode('both');
                setMcqNumQuestions(5);
                setEvalNumQuestions(2);
            }
        }
    }, [preSelectedTopic, preSelectedMode]);
    
    // Load suggested topic on mount (only if not coming from path)
    useEffect(() => {
        if (!cameFromPath) {
            loadSuggestedTopic();
        }
    }, [projectId, cameFromPath]);
    
    const loadSuggestedTopic = async () => {
        setLoadingSuggestion(true);
        try {
            const data = await getSuggestedTopic(projectId);
            setSuggestedTopic(data);
        } catch (error) {
            console.log('No suggestion available:', error);
        } finally {
            setLoadingSuggestion(false);
        }
    };
    
    const useSuggestedTopic = () => {
        if (suggestedTopic?.suggested_topic) {
            setMcqTopic(suggestedTopic.suggested_topic);
            setMcqTopicSelection(suggestedTopic.suggested_topic);
            setEvalTopic(suggestedTopic.suggested_topic);
            setEvalTopicSelection(suggestedTopic.suggested_topic);
        }
    };

    // ==================== MCQ HANDLERS ====================
    
    const handleGenerateMCQ = async () => {
        setMcqLoading(true);
        setMcqTest(null);
        setMcqScore(null);
        setMcqUserAnswers({});
        setMcqSubmitted(false);
        setCurrentQuestionIndex(0);
        setPerformanceSaved(false);
        setCardsCreated(null);

        try {
            const numQ = quizMode === 'both' ? 5 : mcqNumQuestions;
            const data = await generateMCQ(projectId, mcqTopic, numQ, selectedDocuments, mcqDifficulty);
            setMcqTest(data);
        } catch (error) {
            console.error("MCQ gen error", error);
            toast.error("Failed to generate quiz. Please try again.");
        } finally {
            setMcqLoading(false);
        }
    };

    const handleOptionSelect = (qIndex, option) => {
        if (mcqSubmitted) return;
        setMcqUserAnswers(prev => ({ ...prev, [qIndex]: option }));
    };

    const handleSubmitMCQ = async () => {
        let score = 0;
        const feedbackData = [];
        
        mcqTest.questions.forEach((q, i) => {
            const isCorrect = mcqUserAnswers[i] === q.correct_answer;
            if (isCorrect) score++;
            
            feedbackData.push({
                question: q.question,
                correct_answer: q.correct_answer,
                user_answer: mcqUserAnswers[i],
                is_correct: isCorrect,
                explanation: q.explanation
            });
        });
        
        const total = mcqTest.questions.length;
        const wrong = total - score;
        const percentage = (score / total) * 100;
        
        const scoreData = {
            score,
            total,
            percentage,
            feedback: feedbackData
        };
        
        setMcqScore(scoreData);
        setMcqSubmitted(true);
        
        // If in 'both' mode, store MCQ score and move to subjective
        if (quizMode === 'both') {
            setBothMcqScore(scoreData);
            // Auto-generate subjective questions
            handleGenerateSubjectiveForBoth();
            return;
        }
        
        // Save performance to backend
        const topic = mcqTest.topic || mcqTopic || 'General Quiz';
        setSavingPerformance(true);
        try {
            await recordPerformance(projectId, topic, score, wrong);
            setPerformanceSaved(true);
            
            // Notify parent about quiz completion
            if (onQuizComplete) {
                const passed = percentage >= 80;
                onQuizComplete(topic, percentage, passed);
            }
        } catch (error) {
            console.error('Failed to save performance:', error);
        } finally {
            setSavingPerformance(false);
        }
    };
    
    const handleCreateReviewCards = async () => {
        if (!mcqScore || !mcqScore.feedback) return;
        
        const topic = mcqTest.topic || mcqTopic || 'General Quiz';
        const wrongQuestions = mcqScore.feedback.filter(f => !f.is_correct);
        
        if (wrongQuestions.length === 0) {
            toast.info('No wrong answers to create review cards from!');
            return;
        }
        
        setCreatingCards(true);
        try {
            const result = await createCardsFromQuiz(projectId, topic, mcqScore.feedback, true);
            setCardsCreated(result.cards_created);
        } catch (error) {
            console.error('Failed to create review cards:', error);
            toast.error('Failed to create review cards');
        } finally {
            setCreatingCards(false);
        }
    };

    const handleRetest = () => {
        setMcqUserAnswers({});
        setMcqSubmitted(false);
        setMcqScore(null);
        setCurrentQuestionIndex(0);
        setPerformanceSaved(false);
        setCardsCreated(null);
    };

    const handleClearMCQ = () => {
        setMcqTest(null);
        if (!cameFromPath) {
            setMcqTopic('');
            setMcqTopicSelection('');
        }
        setMcqNumQuestions(5);
        setMcqDifficulty('medium');
        setMcqUserAnswers({});
        setMcqSubmitted(false);
        setMcqScore(null);
        setCurrentQuestionIndex(0);
        setPerformanceSaved(false);
        setCardsCreated(null);
        
        // Reset both mode state
        setBothModePhase('mcq');
        setBothMcqScore(null);
        setBothSubjectiveScore(null);
        setBothCombinedScore(null);
        setEvalTest(null);
        setEvalResult(null);
        setEvalUserAnswers({});
    };

    // ==================== SUBJECTIVE HANDLERS ====================
    
    const handleGenerateSubjectiveTest = async () => {
        setEvalLoading(true);
        setEvalTest(null);
        setEvalResult(null);
        setEvalUserAnswers({});

        if (selectedDocuments.length === 0) {
            toast.warning('Please select at least one document to generate a subjective test.');
            setEvalLoading(false);
            return;
        }

        try {
            const numQ = quizMode === 'both' ? 2 : evalNumQuestions;
            const data = await generateSubjectiveTest(projectId, evalTopic, numQ, selectedDocuments);
            setEvalTest(data);
        } catch (error) {
            console.error("Subjective test gen error", error);
            toast.error('Failed to generate subjective test');
        } finally {
            setEvalLoading(false);
        }
    };
    
    const handleGenerateSubjectiveForBoth = async () => {
        setEvalLoading(true);
        setBothModePhase('subjective');
        
        try {
            const data = await generateSubjectiveTest(projectId, mcqTopic, 2, selectedDocuments);
            setEvalTest(data);
            setEvalUserAnswers({});
            setEvalResult(null);
        } catch (error) {
            console.error("Subjective test gen error", error);
            toast.error('Failed to generate subjective questions');
        } finally {
            setEvalLoading(false);
        }
    };

    const handleSubjectiveAnswerChange = (qId, text) => {
        setEvalUserAnswers(prev => ({ ...prev, [qId]: text }));
    };

    const handleSubmitSubjectiveTest = async () => {
        setEvalLoading(true);
        try {
            const answersPayload = {};
            Object.keys(evalUserAnswers).forEach(qId => {
                answersPayload[parseInt(qId)] = evalUserAnswers[qId];
            });

            const data = await submitSubjectiveTest(evalTest.test_id, answersPayload);
            setEvalResult(data);
            
            // If in 'both' mode, calculate combined score
            if (quizMode === 'both') {
                setBothSubjectiveScore(data);
                calculateCombinedScore(bothMcqScore, data);
                setBothModePhase('results');
            } else {
                // Save performance for standalone subjective
                const topic = evalTest.topic || evalTopic || 'General Quiz';
                const subjectivePercent = data.percentage || 0;
                const passed = subjectivePercent >= 80;
                
                try {
                    // Convert to correct/wrong for consistency
                    const correctEquiv = Math.round((subjectivePercent / 100) * evalTest.questions.length);
                    const wrongEquiv = evalTest.questions.length - correctEquiv;
                    await recordPerformance(projectId, topic, correctEquiv, wrongEquiv);
                    
                    if (onQuizComplete) {
                        onQuizComplete(topic, subjectivePercent, passed);
                    }
                } catch (error) {
                    console.error('Failed to save performance:', error);
                }
            }
        } catch (error) {
            console.error("Submit subjective error", error);
            toast.error('Failed to submit answers');
        } finally {
            setEvalLoading(false);
        }
    };
    
    const calculateCombinedScore = (mcqScoreData, subjectiveResult) => {
        // MCQ: 5 questions worth 60% (12% each)
        // Subjective: 2 questions worth 40% (20% each)
        const mcqPercent = mcqScoreData.percentage * 0.6;
        const subjectivePercent = (subjectiveResult.percentage || 0) * 0.4;
        const combined = mcqPercent + subjectivePercent;
        
        const passed = combined >= 80;
        
        setBothCombinedScore({
            mcqScore: mcqScoreData.score,
            mcqTotal: mcqScoreData.total,
            mcqPercent: mcqScoreData.percentage,
            subjectiveScore: subjectiveResult.total_score,
            subjectiveMax: subjectiveResult.max_score,
            subjectivePercent: subjectiveResult.percentage,
            combined: Math.round(combined),
            passed
        });
        
        // Save to backend and notify parent
        const topic = mcqTest?.topic || mcqTopic || 'General Quiz';
        const totalCorrect = mcqScoreData.score + Math.round((subjectiveResult.total_score / subjectiveResult.max_score) * 2);
        const totalWrong = (mcqScoreData.total - mcqScoreData.score) + Math.round(((subjectiveResult.max_score - subjectiveResult.total_score) / subjectiveResult.max_score) * 2);
        
        recordPerformance(projectId, topic, totalCorrect, totalWrong).catch(console.error);
        
        if (onQuizComplete) {
            onQuizComplete(topic, combined, passed);
        }
    };

    const handleResetSubjectiveTest = () => {
        setEvalTest(null);
        if (!cameFromPath) {
            setEvalTopic('');
            setEvalTopicSelection('');
        }
        setEvalNumQuestions(3);
        setEvalUserAnswers({});
        setEvalResult(null);
    };

    const handleResetAll = () => {
        handleClearMCQ();
        handleResetSubjectiveTest();
    };

    // ==================== RENDER HELPERS ====================
    
    // Render the "Return to Learning Path" button
    const renderReturnButton = () => {
        if (!cameFromPath || !onReturnToPath) return null;
        
        return (
            <button
                onClick={onReturnToPath}
                className="flex items-center gap-2 px-4 py-2 text-[#C8A288] hover:bg-[#FDF6F0] rounded-lg font-medium transition-colors"
            >
                <ArrowLeft className="h-4 w-4" />
                Back to Learning Path
            </button>
        );
    };
    
    // Pre-selected topic banner
    const renderPreSelectedBanner = () => {
        if (!cameFromPath || !preSelectedTopic) return null;
        
        return (
            <div className="bg-gradient-to-r from-purple-50 to-indigo-50 border border-purple-200 rounded-xl p-4 mb-6">
                <div className="flex items-center gap-3">
                    <div className="p-2 bg-purple-100 rounded-lg">
                        <Target className="h-5 w-5 text-purple-600" />
                    </div>
                    <div className="flex-1">
                        <p className="text-sm font-bold text-purple-800">Learning Path Quiz</p>
                        <p className="text-sm text-purple-600">Topic: {preSelectedTopic}</p>
                    </div>
                    <div className="text-xs text-purple-500">
                        Score 80%+ to complete
                    </div>
                </div>
            </div>
        );
    };

    return (
        <div className="h-full flex flex-col relative w-full">
            {/* Full-screen Loading State for MCQ */}
            {mcqLoading && (
                <div className="h-full flex flex-col items-center justify-center animate-in fade-in duration-300">
                    <div className="relative mb-6">
                        <div className="h-20 w-20 border-4 border-[#E6D5CC] rounded-full"></div>
                        <div className="absolute inset-0 h-20 w-20 border-4 border-[#C8A288] rounded-full border-t-transparent animate-spin"></div>
                        <CheckSquare className="absolute inset-0 m-auto h-8 w-8 text-[#C8A288]" />
                    </div>
                    <h3 className="text-xl font-bold text-[#4A3B32] mb-2">Generating Quiz</h3>
                    <p className="text-[#8a6a5c] text-center max-w-xs">
                        Creating questions about <span className="font-semibold">{mcqTopic || 'your documents'}</span>...
                    </p>
                    <div className="flex gap-1.5 mt-6">
                        <div className="h-2 w-2 bg-[#C8A288] rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                        <div className="h-2 w-2 bg-[#C8A288] rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                        <div className="h-2 w-2 bg-[#C8A288] rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                    </div>
                </div>
            )}

            {/* Full-screen Loading State for Subjective */}
            {evalLoading && (
                <div className="h-full flex flex-col items-center justify-center animate-in fade-in duration-300">
                    <div className="relative mb-6">
                        <div className="h-20 w-20 border-4 border-[#E6D5CC] rounded-full"></div>
                        <div className="absolute inset-0 h-20 w-20 border-4 border-[#C8A288] rounded-full border-t-transparent animate-spin"></div>
                        <FileText className="absolute inset-0 m-auto h-8 w-8 text-[#C8A288]" />
                    </div>
                    <h3 className="text-xl font-bold text-[#4A3B32] mb-2">
                        {bothModePhase === 'subjective' ? 'Loading Subjective Questions' : evalResult ? 'Evaluating Answers' : 'Generating Questions'}
                    </h3>
                    <div className="flex gap-1.5 mt-6">
                        <div className="h-2 w-2 bg-[#C8A288] rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                        <div className="h-2 w-2 bg-[#C8A288] rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                        <div className="h-2 w-2 bg-[#C8A288] rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                    </div>
                </div>
            )}

            {/* Main Content - Only show when not loading */}
            {!mcqLoading && !evalLoading && (
            <div className="flex-1 overflow-y-auto w-full max-w-3xl mx-auto pb-24 custom-scrollbar p-2 md:p-8">
                
                {/* Return to Path Button (if came from path) */}
                {cameFromPath && !mcqTest && !evalTest && (
                    <div className="mb-4">
                        {renderReturnButton()}
                    </div>
                )}

                {/* ==================== BOTH MODE ==================== */}
                {quizMode === 'both' && (
                    <>
                        {/* Setup Phase */}
                        {!mcqTest && bothModePhase === 'mcq' && (
                            <div className="mt-8 text-center animate-in fade-in slide-in-from-bottom-4">
                                <div className="inline-flex items-center justify-center p-4 bg-white rounded-2xl shadow-sm border border-[#E6D5CC] mb-6">
                                    <Brain className="h-8 w-8 text-[#C8A288]" />
                                </div>
                                <h3 className="text-2xl font-bold mb-2 text-[#4A3B32]">Complete Quiz</h3>
                                <p className="text-[#8a6a5c] mb-8">5 MCQ + 2 Subjective Questions</p>
                                
                                {renderPreSelectedBanner()}

                                <div className="max-w-md mx-auto space-y-5 bg-white p-6 md:p-8 rounded-3xl border border-[#E6D5CC] shadow-sm text-left">
                                    <div>
                                        <label className="block text-sm font-bold mb-2 text-[#4A3B32] uppercase tracking-wide opacity-80">Topic</label>
                                        {cameFromPath ? (
                                            <div className="px-5 py-3.5 bg-[#FDF6F0] rounded-xl text-[#4A3B32] font-medium">
                                                {mcqTopic}
                                            </div>
                                        ) : availableTopics.length > 0 ? (
                                            <div className="relative">
                                                <select
                                                    value={mcqTopicSelection}
                                                    onChange={(e) => {
                                                        const val = e.target.value;
                                                        setMcqTopicSelection(val);
                                                        setEvalTopicSelection(val);
                                                        if (val !== '__custom__') {
                                                            setMcqTopic(val);
                                                            setEvalTopic(val);
                                                        } else {
                                                            setMcqTopic('');
                                                            setEvalTopic('');
                                                        }
                                                    }}
                                                    className="w-full px-5 py-3.5 bg-[#FDF6F0] border-0 rounded-xl focus:ring-2 focus:ring-[#C8A288] text-[#4A3B32] font-medium appearance-none"
                                                >
                                                    <option value="">Select a topic...</option>
                                                    {availableTopics.map((topic, idx) => (
                                                        <option key={idx} value={topic}>{topic}</option>
                                                    ))}
                                                    <option value="__custom__">Custom Topic...</option>
                                                </select>
                                                <ChevronDown className="absolute right-4 top-1/2 -translate-y-1/2 h-4 w-4 text-[#8a6a5c] pointer-events-none" />
                                            </div>
                                        ) : (
                                            <input
                                                type="text"
                                                value={mcqTopic}
                                                onChange={(e) => {
                                                    setMcqTopic(e.target.value);
                                                    setEvalTopic(e.target.value);
                                                }}
                                                placeholder="e.g., Thermodynamics"
                                                className="w-full px-5 py-3.5 bg-[#FDF6F0] border-0 rounded-xl focus:ring-2 focus:ring-[#C8A288]"
                                            />
                                        )}
                                    </div>
                                    
                                    <div>
                                        <label className="block text-sm font-bold mb-2 text-[#4A3B32] uppercase tracking-wide opacity-80">Difficulty</label>
                                        <div className="flex gap-2">
                                            {[
                                                { value: 'easy', label: 'Easy', icon: Zap, color: 'text-green-600 bg-green-50 border-green-200' },
                                                { value: 'medium', label: 'Medium', icon: Brain, color: 'text-yellow-600 bg-yellow-50 border-yellow-200' },
                                                { value: 'hard', label: 'Hard', icon: BookMarked, color: 'text-red-600 bg-red-50 border-red-200' }
                                            ].map(({ value, label, icon: Icon, color }) => (
                                                <button
                                                    key={value}
                                                    type="button"
                                                    onClick={() => setMcqDifficulty(value)}
                                                    className={`flex-1 py-3 px-4 rounded-xl border-2 font-bold text-sm transition-all flex items-center justify-center gap-2 ${
                                                        mcqDifficulty === value 
                                                            ? `${color} border-current` 
                                                            : 'bg-[#FDF6F0] border-transparent text-[#8a6a5c] hover:bg-white'
                                                    }`}
                                                >
                                                    <Icon className="h-4 w-4" />
                                                    {label}
                                                </button>
                                            ))}
                                        </div>
                                    </div>

                                    <button
                                        onClick={handleGenerateMCQ}
                                        disabled={mcqLoading || !mcqTopic}
                                        className="w-full py-4 bg-[#C8A288] text-white rounded-xl hover:bg-[#B08B72] font-bold shadow-lg shadow-[#C8A288]/20 disabled:opacity-50 transition-all active:scale-[0.98] mt-2 flex items-center justify-center gap-2"
                                    >
                                        <Brain className="h-5 w-5" />
                                        Start Complete Quiz
                                    </button>
                                </div>
                            </div>
                        )}
                        
                        {/* MCQ Phase */}
                        {mcqTest && bothModePhase === 'mcq' && !mcqSubmitted && (
                            <div className="pb-20 h-full flex flex-col">
                                <div className="flex justify-between items-center mb-6 px-2">
                                    <div>
                                        <h3 className="text-xl font-bold text-[#4A3B32]">{mcqTest.topic || 'Complete'} Quiz</h3>
                                        <p className="text-xs text-[#8a6a5c] font-bold uppercase tracking-wider mt-1">
                                            Part 1: MCQ • Question {currentQuestionIndex + 1} of {mcqTest.questions.length}
                                        </p>
                                    </div>
                                    <button onClick={handleClearMCQ} className="p-2 hover:bg-[#E6D5CC]/30 rounded-lg text-[#8a6a5c]">
                                        <X className="h-5 w-5" />
                                    </button>
                                </div>

                                <div className="h-2 w-full bg-[#E6D5CC]/30 rounded-full mb-8 overflow-hidden mx-2">
                                    <div
                                        className="h-full bg-[#C8A288] transition-all duration-500 ease-out rounded-full"
                                        style={{ width: `${((currentQuestionIndex + 1) / mcqTest.questions.length) * 50}%` }}
                                    />
                                </div>

                                <div className="flex-1 flex flex-col animate-in fade-in slide-in-from-right-4 duration-300 px-2" key={currentQuestionIndex}>
                                    <div className="bg-white p-6 md:p-8 rounded-3xl border border-[#E6D5CC] shadow-sm mb-6">
                                        <div className="prose prose-lg max-w-none text-[#4A3B32] font-medium mb-6">
                                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                                {mcqTest.questions[currentQuestionIndex].question}
                                            </ReactMarkdown>
                                        </div>

                                        <div className="space-y-3">
                                            {mcqTest.questions[currentQuestionIndex].options.map((opt, idx) => {
                                                const isSelected = mcqUserAnswers[currentQuestionIndex] === opt.option;
                                                return (
                                                    <button
                                                        key={idx}
                                                        onClick={() => handleOptionSelect(currentQuestionIndex, opt.option)}
                                                        className={`w-full text-left p-4 rounded-xl border-2 transition-all duration-200 flex items-center gap-4 group ${isSelected
                                                            ? 'bg-[#FDF6F0] border-[#C8A288] shadow-sm'
                                                            : 'bg-white border-transparent hover:bg-gray-50 hover:border-gray-200'
                                                        }`}
                                                    >
                                                        <div className={`h-8 w-8 rounded-full border-2 flex items-center justify-center font-bold text-sm transition-colors ${isSelected
                                                            ? 'bg-[#C8A288] border-[#C8A288] text-white'
                                                            : 'bg-white border-[#E6D5CC] text-[#8a6a5c] group-hover:border-[#C8A288]'
                                                        }`}>
                                                            {opt.option}
                                                        </div>
                                                        <span className={`text-[#4A3B32] font-medium ${isSelected ? 'opacity-100' : 'opacity-80'}`}>
                                                            {opt.text}
                                                        </span>
                                                    </button>
                                                );
                                            })}
                                        </div>
                                    </div>

                                    <div className="flex justify-between items-center mt-auto pb-4">
                                        <button
                                            onClick={() => setCurrentQuestionIndex(prev => Math.max(0, prev - 1))}
                                            disabled={currentQuestionIndex === 0}
                                            className="px-6 py-3 rounded-xl font-bold text-[#8a6a5c] disabled:opacity-30 hover:bg-[#FDF6F0] transition-colors"
                                        >
                                            Previous
                                        </button>

                                        {currentQuestionIndex === mcqTest.questions.length - 1 ? (
                                            <button
                                                onClick={handleSubmitMCQ}
                                                disabled={Object.keys(mcqUserAnswers).length !== mcqTest.questions.length}
                                                className="px-8 py-3 bg-[#C8A288] text-white rounded-xl font-bold shadow-lg shadow-[#C8A288]/20 hover:bg-[#B08B72] transition-colors disabled:opacity-50"
                                            >
                                                Continue to Subjective
                                            </button>
                                        ) : (
                                            <button
                                                onClick={() => setCurrentQuestionIndex(prev => Math.min(mcqTest.questions.length - 1, prev + 1))}
                                                className="px-8 py-3 bg-[#4A3B32] text-white rounded-xl font-bold hover:bg-[#2e2520] transition-colors flex items-center gap-2"
                                            >
                                                Next <ChevronDown className="h-4 w-4 -rotate-90" />
                                            </button>
                                        )}
                                    </div>
                                </div>
                            </div>
                        )}
                        
                        {/* Subjective Phase */}
                        {bothModePhase === 'subjective' && evalTest && !evalResult && (
                            <div className="space-y-8 pb-20 px-2">
                                <div className="flex justify-between items-center">
                                    <div>
                                        <h3 className="text-xl font-bold text-[#4A3B32]">{evalTest.topic || 'Complete'} Quiz</h3>
                                        <p className="text-xs text-[#8a6a5c] font-bold uppercase tracking-wider mt-1">
                                            Part 2: Subjective • {evalTest.questions.length} Questions
                                        </p>
                                    </div>
                                </div>
                                
                                <div className="h-2 w-full bg-[#E6D5CC]/30 rounded-full overflow-hidden">
                                    <div className="h-full bg-[#C8A288] rounded-full" style={{ width: '75%' }} />
                                </div>
                                
                                <div className="bg-green-50 border border-green-200 rounded-xl p-4">
                                    <div className="flex items-center gap-2 text-green-700">
                                        <CheckSquare className="h-5 w-5" />
                                        <span className="font-bold">MCQ Complete!</span>
                                        <span className="text-sm">Score: {bothMcqScore?.score}/{bothMcqScore?.total} ({Math.round(bothMcqScore?.percentage || 0)}%)</span>
                                    </div>
                                </div>

                                {evalTest.questions.map((q, i) => (
                                    <div key={q.id} className="p-6 bg-[#FDF6F0] rounded-2xl border border-[#E6D5CC] shadow-sm">
                                        <div className="font-bold text-lg mb-4 flex gap-2">
                                            <span>{i + 1}.</span>
                                            <div className="prose prose-sm max-w-none">
                                                <ReactMarkdown remarkPlugins={[remarkGfm]}>{q.question}</ReactMarkdown>
                                            </div>
                                        </div>
                                        <textarea
                                            value={evalUserAnswers[q.id] || ''}
                                            onChange={(e) => handleSubjectiveAnswerChange(q.id, e.target.value)}
                                            rows={4}
                                            className="w-full px-4 py-3 bg-white border border-[#E6D5CC] rounded-xl focus:ring-2 focus:ring-[#C8A288] outline-none resize-none"
                                            placeholder="Type your answer here..."
                                        />
                                    </div>
                                ))}

                                <div className="pt-4 pb-8">
                                    <button
                                        onClick={handleSubmitSubjectiveTest}
                                        disabled={evalLoading || Object.keys(evalUserAnswers).length !== evalTest.questions.length}
                                        className="w-full py-4 bg-[#C8A288] text-white rounded-xl hover:bg-[#B08B72] font-bold text-lg shadow-sm disabled:opacity-50 transition-all"
                                    >
                                        Submit Complete Quiz
                                    </button>
                                </div>
                            </div>
                        )}
                        
                        {/* Combined Results Phase */}
                        {bothModePhase === 'results' && bothCombinedScore && (
                            <div className="animate-in fade-in zoom-in-95 duration-300 px-2 py-8">
                                <div className={`p-8 rounded-3xl text-center mb-8 ${
                                    bothCombinedScore.passed 
                                        ? 'bg-gradient-to-br from-green-500 to-emerald-500 text-white' 
                                        : 'bg-gradient-to-br from-orange-400 to-red-400 text-white'
                                }`}>
                                    {bothCombinedScore.passed ? (
                                        <Trophy className="h-16 w-16 mx-auto mb-4" />
                                    ) : (
                                        <AlertTriangle className="h-16 w-16 mx-auto mb-4" />
                                    )}
                                    <div className="text-5xl font-bold mb-2">{bothCombinedScore.combined}%</div>
                                    <p className="text-lg opacity-90 mb-4">
                                        {bothCombinedScore.passed ? 'Topic Completed!' : 'Need 80% to complete this topic'}
                                    </p>
                                    
                                    <div className="grid grid-cols-2 gap-4 max-w-xs mx-auto text-sm">
                                        <div className="bg-white/20 rounded-lg p-3">
                                            <div className="font-bold">{bothCombinedScore.mcqScore}/{bothCombinedScore.mcqTotal}</div>
                                            <div className="opacity-80">MCQ ({Math.round(bothCombinedScore.mcqPercent)}%)</div>
                                        </div>
                                        <div className="bg-white/20 rounded-lg p-3">
                                            <div className="font-bold">{bothCombinedScore.subjectiveScore}/{bothCombinedScore.subjectiveMax}</div>
                                            <div className="opacity-80">Subjective ({Math.round(bothCombinedScore.subjectivePercent)}%)</div>
                                        </div>
                                    </div>
                                </div>

                                <div className="flex flex-col sm:flex-row justify-center gap-3">
                                    {cameFromPath && onReturnToPath && (
                                        <button
                                            onClick={onReturnToPath}
                                            className="px-8 py-3 bg-[#C8A288] text-white rounded-xl hover:bg-[#B08B72] font-bold transition-colors flex items-center justify-center gap-2"
                                        >
                                            <ArrowLeft className="h-5 w-5" />
                                            Back to Learning Path
                                        </button>
                                    )}
                                    <button
                                        onClick={handleResetAll}
                                        className="px-8 py-3 bg-[#FDF6F0] text-[#4A3B32] rounded-xl hover:bg-[#E6D5CC] font-bold transition-colors border border-[#E6D5CC]"
                                    >
                                        New Quiz
                                    </button>
                                </div>
                            </div>
                        )}
                    </>
                )}

                {/* ==================== MCQ ONLY MODE ==================== */}
                {quizMode === 'mcq' && (
                    <>
                        {!mcqTest ? (
                            <div className="mt-8 text-center animate-in fade-in slide-in-from-bottom-4">
                                <div className="inline-flex items-center justify-center p-4 bg-white rounded-2xl shadow-sm border border-[#E6D5CC] mb-6">
                                    <HelpCircle className="h-8 w-8 text-[#C8A288]" />
                                </div>
                                <h3 className="text-2xl font-bold mb-2 text-[#4A3B32]">Generate Quiz</h3>
                                <p className="text-[#8a6a5c] mb-8">Create a personalized multiple-choice quiz from your documents.</p>

                                {renderPreSelectedBanner()}

                                <div className="max-w-md mx-auto space-y-5 bg-white p-6 md:p-8 rounded-3xl border border-[#E6D5CC] shadow-sm text-left">
                                    {/* Suggested Topic Banner */}
                                    {!cameFromPath && suggestedTopic?.suggested_topic && !mcqTopic && (
                                        <div className="bg-gradient-to-r from-purple-50 to-indigo-50 border border-purple-200 rounded-xl p-4 -mt-2 animate-in fade-in">
                                            <div className="flex items-start gap-3">
                                                <div className="p-2 bg-purple-100 rounded-lg">
                                                    <Sparkles className="h-5 w-5 text-purple-600" />
                                                </div>
                                                <div className="flex-1 min-w-0">
                                                    <p className="text-sm font-bold text-purple-800">Suggested Next Topic</p>
                                                    <p className="text-sm text-purple-600 truncate">{suggestedTopic.suggested_topic}</p>
                                                    <p className="text-xs text-purple-500 mt-1">{suggestedTopic.reason}</p>
                                                </div>
                                                <button
                                                    onClick={useSuggestedTopic}
                                                    className="px-3 py-1.5 bg-purple-600 text-white text-sm font-bold rounded-lg hover:bg-purple-700 transition-colors whitespace-nowrap"
                                                >
                                                    Use This
                                                </button>
                                            </div>
                                        </div>
                                    )}
                                    
                                    <div>
                                        <label className="block text-sm font-bold mb-2 text-[#4A3B32] uppercase tracking-wide opacity-80">Topic</label>
                                        {cameFromPath ? (
                                            <div className="px-5 py-3.5 bg-[#FDF6F0] rounded-xl text-[#4A3B32] font-medium">
                                                {mcqTopic}
                                            </div>
                                        ) : availableTopics.length > 0 ? (
                                            <div className="relative">
                                                <select
                                                    value={mcqTopicSelection}
                                                    onChange={(e) => {
                                                        const val = e.target.value;
                                                        setMcqTopicSelection(val);
                                                        if (val !== '__custom__') setMcqTopic(val);
                                                        else setMcqTopic('');
                                                    }}
                                                    className="w-full px-5 py-3.5 bg-[#FDF6F0] border-0 rounded-xl focus:ring-2 focus:ring-[#C8A288] text-[#4A3B32] font-medium appearance-none"
                                                >
                                                    <option value="">Select a topic...</option>
                                                    {availableTopics.map((topic, idx) => (
                                                        <option key={idx} value={topic}>{topic}</option>
                                                    ))}
                                                    <option value="__custom__">Custom Topic...</option>
                                                </select>
                                                <ChevronDown className="absolute right-4 top-1/2 -translate-y-1/2 h-4 w-4 text-[#8a6a5c] pointer-events-none" />
                                                {mcqTopicSelection === '__custom__' && (
                                                    <input
                                                        type="text"
                                                        value={mcqTopic}
                                                        onChange={(e) => setMcqTopic(e.target.value)}
                                                        placeholder="Enter custom topic..."
                                                        className="w-full px-5 py-3.5 bg-[#FDF6F0] border-0 rounded-xl focus:ring-2 focus:ring-[#C8A288] mt-3 animate-in fade-in"
                                                        autoFocus
                                                    />
                                                )}
                                            </div>
                                        ) : (
                                            <input
                                                type="text"
                                                value={mcqTopic}
                                                onChange={(e) => setMcqTopic(e.target.value)}
                                                placeholder="e.g., Thermodynamics"
                                                className="w-full px-5 py-3.5 bg-[#FDF6F0] border-0 rounded-xl focus:ring-2 focus:ring-[#C8A288]"
                                            />
                                        )}
                                    </div>

                                    <div>
                                        <label className="block text-sm font-bold mb-2 text-[#4A3B32] uppercase tracking-wide opacity-80">Questions</label>
                                        <div className="relative">
                                            <select
                                                value={mcqNumQuestions}
                                                onChange={(e) => setMcqNumQuestions(e.target.value)}
                                                className="w-full px-5 py-3.5 bg-[#FDF6F0] border-0 rounded-xl focus:ring-2 focus:ring-[#C8A288] text-[#4A3B32] font-medium appearance-none"
                                            >
                                                {[3, 5, 10, 15, 20].map(num => (
                                                    <option key={num} value={num}>{num} Questions</option>
                                                ))}
                                            </select>
                                            <ChevronDown className="absolute right-4 top-1/2 -translate-y-1/2 h-4 w-4 text-[#8a6a5c] pointer-events-none" />
                                        </div>
                                    </div>
                                    
                                    <div>
                                        <label className="block text-sm font-bold mb-2 text-[#4A3B32] uppercase tracking-wide opacity-80">Difficulty</label>
                                        <div className="flex gap-2">
                                            {[
                                                { value: 'easy', label: 'Easy', icon: Zap, color: 'text-green-600 bg-green-50 border-green-200' },
                                                { value: 'medium', label: 'Medium', icon: Brain, color: 'text-yellow-600 bg-yellow-50 border-yellow-200' },
                                                { value: 'hard', label: 'Hard', icon: BookMarked, color: 'text-red-600 bg-red-50 border-red-200' }
                                            ].map(({ value, label, icon: Icon, color }) => (
                                                <button
                                                    key={value}
                                                    type="button"
                                                    onClick={() => setMcqDifficulty(value)}
                                                    className={`flex-1 py-3 px-4 rounded-xl border-2 font-bold text-sm transition-all flex items-center justify-center gap-2 ${
                                                        mcqDifficulty === value 
                                                            ? `${color} border-current` 
                                                            : 'bg-[#FDF6F0] border-transparent text-[#8a6a5c] hover:bg-white'
                                                    }`}
                                                >
                                                    <Icon className="h-4 w-4" />
                                                    {label}
                                                </button>
                                            ))}
                                        </div>
                                    </div>

                                    <button
                                        onClick={handleGenerateMCQ}
                                        disabled={mcqLoading}
                                        className="w-full py-4 bg-[#C8A288] text-white rounded-xl hover:bg-[#B08B72] font-bold shadow-lg shadow-[#C8A288]/20 disabled:opacity-50 transition-all active:scale-[0.98] mt-2 flex items-center justify-center gap-2"
                                    >
                                        {mcqLoading ? <Loader2 className="h-5 w-5 animate-spin" /> : <CheckSquare className="h-5 w-5" />}
                                        {mcqLoading ? 'Generating...' : 'Start Quiz'}
                                    </button>
                                </div>
                            </div>
                        ) : (
                            <div className="pb-20 h-full flex flex-col">
                                {/* Quiz Header */}
                                <div className="flex justify-between items-center mb-6 px-2">
                                    <div>
                                        <h3 className="text-xl font-bold text-[#4A3B32]">{mcqTest.topic || 'General'} Quiz</h3>
                                        <p className="text-xs text-[#8a6a5c] font-bold uppercase tracking-wider mt-1">
                                            Question {currentQuestionIndex + 1} of {mcqTest.questions.length}
                                        </p>
                                    </div>
                                    <button
                                        onClick={handleClearMCQ}
                                        className="p-2 hover:bg-[#E6D5CC]/30 rounded-lg text-[#8a6a5c] transition-colors"
                                        title="Exit Quiz"
                                    >
                                        <X className="h-5 w-5" />
                                    </button>
                                </div>

                                {/* Progress Bar */}
                                <div className="h-2 w-full bg-[#E6D5CC]/30 rounded-full mb-8 overflow-hidden mx-2">
                                    <div
                                        className="h-full bg-[#C8A288] transition-all duration-500 ease-out rounded-full"
                                        style={{ width: `${((currentQuestionIndex + 1) / mcqTest.questions.length) * 100}%` }}
                                    />
                                </div>

                                {mcqScore ? (
                                    /* Result View */
                                    <div className="animate-in fade-in zoom-in-95 duration-300 px-2">
                                        <div className="bg-white p-8 rounded-3xl border border-[#E6D5CC] shadow-lg text-center mb-8 relative overflow-hidden">
                                            <div className="absolute top-0 left-0 w-full h-2 bg-gradient-to-r from-[#C8A288] to-[#FDF6F0]" />
                                            <h4 className="text-2xl font-bold text-[#4A3B32] mb-2">Quiz Complete!</h4>
                                            <div className="relative inline-block my-6">
                                                <div className={`h-32 w-32 rounded-full border-8 flex items-center justify-center ${
                                                    mcqScore.percentage >= 80 ? 'border-green-200' : 'border-[#FDF6F0]'
                                                }`}>
                                                    <span className={`text-4xl font-black ${
                                                        mcqScore.percentage >= 80 ? 'text-green-600' : 'text-[#C8A288]'
                                                    }`}>{Math.round(mcqScore.percentage)}%</span>
                                                </div>
                                            </div>
                                            <p className="text-[#8a6a5c] mb-4 font-medium">You got {mcqScore.score} out of {mcqScore.total} questions correct.</p>
                                            
                                            {cameFromPath && (
                                                <p className={`text-sm font-bold mb-4 ${mcqScore.percentage >= 80 ? 'text-green-600' : 'text-orange-600'}`}>
                                                    {mcqScore.percentage >= 80 ? '✓ Topic completed!' : 'Need 80% to complete this topic'}
                                                </p>
                                            )}
                                            
                                            {/* Performance Saved Indicator */}
                                            {savingPerformance ? (
                                                <p className="text-xs text-[#8a6a5c] flex items-center justify-center gap-1 mb-4">
                                                    <Loader2 className="h-3 w-3 animate-spin" /> Saving progress...
                                                </p>
                                            ) : performanceSaved ? (
                                                <p className="text-xs text-green-600 flex items-center justify-center gap-1 mb-4">
                                                    <CheckSquare className="h-3 w-3" /> Progress saved!
                                                </p>
                                            ) : null}

                                            <div className="flex flex-col sm:flex-row justify-center gap-3 mb-4">
                                                {cameFromPath && onReturnToPath && (
                                                    <button
                                                        onClick={onReturnToPath}
                                                        className="px-8 py-3 bg-[#C8A288] text-white rounded-xl hover:bg-[#B08B72] font-bold transition-colors flex items-center justify-center gap-2"
                                                    >
                                                        <ArrowLeft className="h-5 w-5" />
                                                        Back to Learning Path
                                                    </button>
                                                )}
                                                <button
                                                    onClick={handleRetest}
                                                    className="px-8 py-3 bg-[#FDF6F0] text-[#4A3B32] rounded-xl hover:bg-[#E6D5CC] font-bold transition-colors border border-transparent hover:border-[#C8A288]"
                                                >
                                                    Retest
                                                </button>
                                                <button
                                                    onClick={handleClearMCQ}
                                                    className="px-8 py-3 bg-[#4A3B32] text-white rounded-xl hover:bg-[#2e2520] font-bold transition-colors"
                                                >
                                                    New Quiz
                                                </button>
                                            </div>
                                            
                                            {/* Create Review Cards Button */}
                                            {mcqScore.score < mcqScore.total && (
                                                <div className="pt-4 border-t border-[#E6D5CC]">
                                                    {cardsCreated !== null ? (
                                                        <p className="text-sm text-green-600 flex items-center justify-center gap-2">
                                                            <BookMarked className="h-4 w-4" />
                                                            {cardsCreated} review cards created for spaced repetition!
                                                        </p>
                                                    ) : (
                                                        <button
                                                            onClick={handleCreateReviewCards}
                                                            disabled={creatingCards}
                                                            className="px-6 py-2 bg-purple-100 text-purple-700 rounded-lg hover:bg-purple-200 font-medium transition-colors text-sm flex items-center justify-center gap-2 mx-auto"
                                                        >
                                                            {creatingCards ? (
                                                                <>
                                                                    <Loader2 className="h-4 w-4 animate-spin" />
                                                                    Creating cards...
                                                                </>
                                                            ) : (
                                                                <>
                                                                    <BookMarked className="h-4 w-4" />
                                                                    Create Review Cards ({mcqScore.total - mcqScore.score} wrong answers)
                                                                </>
                                                            )}
                                                        </button>
                                                    )}
                                                </div>
                                            )}
                                        </div>

                                        {/* Review Answers */}
                                        <div className="space-y-4">
                                            <h4 className="font-bold text-[#4A3B32] px-2 mb-2">Review Answers</h4>
                                            {mcqTest.questions.map((q, i) => {
                                                const isCorrect = mcqUserAnswers[i] === q.correct_answer;
                                                const userAnswerOption = q.options.find(opt => opt.option === mcqUserAnswers[i]);
                                                const correctAnswerOption = q.options.find(opt => opt.option === q.correct_answer);

                                                return (
                                                    <div key={i} className={`p-5 rounded-xl border ${isCorrect
                                                        ? 'bg-green-50 border-green-200'
                                                        : 'bg-red-50 border-red-200'
                                                    }`}>
                                                        <div className="flex gap-2 mb-3">
                                                            <span className="font-bold text-xs opacity-50 mt-1">Q{i + 1}</span>
                                                            <div className="text-sm font-medium flex-1">
                                                                <ReactMarkdown remarkPlugins={[remarkGfm]}>{q.question}</ReactMarkdown>
                                                            </div>
                                                            {isCorrect
                                                                ? <CheckSquare className="h-5 w-5 text-green-600 flex-shrink-0" />
                                                                : <X className="h-5 w-5 text-red-500 flex-shrink-0" />
                                                            }
                                                        </div>

                                                        <div className="ml-6 space-y-2 text-sm">
                                                            <div className={`flex items-start gap-2 ${isCorrect ? 'text-green-700' : 'text-red-600'}`}>
                                                                <span className="font-semibold min-w-[100px]">Your Answer:</span>
                                                                <span>
                                                                    <span className="font-bold">{mcqUserAnswers[i] || '—'}</span>
                                                                    {userAnswerOption && <span className="ml-1">- {userAnswerOption.text}</span>}
                                                                </span>
                                                            </div>

                                                            {!isCorrect && (
                                                                <div className="flex items-start gap-2 text-green-700">
                                                                    <span className="font-semibold min-w-[100px]">Correct Answer:</span>
                                                                    <span>
                                                                        <span className="font-bold">{q.correct_answer}</span>
                                                                        {correctAnswerOption && <span className="ml-1">- {correctAnswerOption.text}</span>}
                                                                    </span>
                                                                </div>
                                                            )}

                                                            {q.explanation && (
                                                                <div className="mt-3 p-3 bg-white/60 rounded-lg border border-[#E6D5CC]/50">
                                                                    <span className="font-semibold text-[#4A3B32] block mb-1">Explanation:</span>
                                                                    <div className="text-[#5a4a42] prose prose-sm max-w-none">
                                                                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{q.explanation}</ReactMarkdown>
                                                                    </div>
                                                                </div>
                                                            )}
                                                        </div>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    </div>
                                ) : (
                                    /* Active Question View */
                                    <div className="flex-1 flex flex-col animate-in fade-in slide-in-from-right-4 duration-300 px-2" key={currentQuestionIndex}>
                                        <div className="bg-white p-6 md:p-8 rounded-3xl border border-[#E6D5CC] shadow-sm mb-6 flex-1 md:flex-none">
                                            <div className="prose prose-lg max-w-none text-[#4A3B32] font-medium mb-6">
                                                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                                    {mcqTest.questions[currentQuestionIndex].question}
                                                </ReactMarkdown>
                                            </div>

                                            <div className="space-y-3">
                                                {mcqTest.questions[currentQuestionIndex].options.map((opt, idx) => {
                                                    const isSelected = mcqUserAnswers[currentQuestionIndex] === opt.option;
                                                    return (
                                                        <button
                                                            key={idx}
                                                            onClick={() => handleOptionSelect(currentQuestionIndex, opt.option)}
                                                            className={`w-full text-left p-4 rounded-xl border-2 transition-all duration-200 flex items-center gap-4 group ${isSelected
                                                                ? 'bg-[#FDF6F0] border-[#C8A288] shadow-sm'
                                                                : 'bg-white border-transparent hover:bg-gray-50 hover:border-gray-200'
                                                            }`}
                                                        >
                                                            <div className={`h-8 w-8 rounded-full border-2 flex items-center justify-center font-bold text-sm transition-colors ${isSelected
                                                                ? 'bg-[#C8A288] border-[#C8A288] text-white'
                                                                : 'bg-white border-[#E6D5CC] text-[#8a6a5c] group-hover:border-[#C8A288]'
                                                            }`}>
                                                                {opt.option}
                                                            </div>
                                                            <span className={`text-[#4A3B32] font-medium ${isSelected ? 'opacity-100' : 'opacity-80'}`}>
                                                                {opt.text}
                                                            </span>
                                                        </button>
                                                    );
                                                })}
                                            </div>
                                        </div>

                                        <div className="flex justify-between items-center mt-auto md:mt-0 pb-4 md:pb-0">
                                            <button
                                                onClick={() => setCurrentQuestionIndex(prev => Math.max(0, prev - 1))}
                                                disabled={currentQuestionIndex === 0}
                                                className="px-6 py-3 rounded-xl font-bold text-[#8a6a5c] disabled:opacity-30 hover:bg-[#FDF6F0] transition-colors"
                                            >
                                                Previous
                                            </button>

                                            {currentQuestionIndex === mcqTest.questions.length - 1 ? (
                                                <button
                                                    onClick={handleSubmitMCQ}
                                                    disabled={Object.keys(mcqUserAnswers).length !== mcqTest.questions.length}
                                                    className="px-8 py-3 bg-[#C8A288] text-white rounded-xl font-bold shadow-lg shadow-[#C8A288]/20 hover:bg-[#B08B72] transition-colors disabled:opacity-50 disabled:shadow-none"
                                                >
                                                    Submit Quiz
                                                </button>
                                            ) : (
                                                <button
                                                    onClick={() => setCurrentQuestionIndex(prev => Math.min(mcqTest.questions.length - 1, prev + 1))}
                                                    className="px-8 py-3 bg-[#4A3B32] text-white rounded-xl font-bold hover:bg-[#2e2520] transition-colors flex items-center gap-2"
                                                >
                                                    Next <ChevronDown className="h-4 w-4 -rotate-90" />
                                                </button>
                                            )}
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}
                    </>
                )}

                {/* ==================== SUBJECTIVE ONLY MODE ==================== */}
                {quizMode === 'subjective' && (
                    <>
                        {!evalTest ? (
                            <div className="mt-8 text-center animate-in fade-in slide-in-from-bottom-4">
                                <div className="inline-flex items-center justify-center p-4 bg-white rounded-2xl shadow-sm border border-[#E6D5CC] mb-6">
                                    <FileText className="h-8 w-8 text-[#C8A288]" />
                                </div>
                                <h3 className="text-2xl font-bold mb-2 text-[#4A3B32]">Subjective Evaluation</h3>
                                <p className="text-[#8a6a5c] mb-8">Write answers and get AI feedback.</p>

                                {renderPreSelectedBanner()}

                                <div className="max-w-md mx-auto space-y-4 bg-white p-6 md:p-8 rounded-3xl border border-[#E6D5CC] shadow-sm text-left">
                                    <div>
                                        <label className="block text-sm font-bold mb-2 text-[#4A3B32] uppercase tracking-wide opacity-80">Topic</label>

                                        {cameFromPath ? (
                                            <div className="px-5 py-3.5 bg-[#FDF6F0] rounded-xl text-[#4A3B32] font-medium">
                                                {evalTopic}
                                            </div>
                                        ) : availableTopics.length > 0 ? (
                                            <div className="relative">
                                                <select
                                                    value={evalTopicSelection}
                                                    onChange={(e) => {
                                                        const val = e.target.value;
                                                        setEvalTopicSelection(val);
                                                        if (val !== '__custom__') setEvalTopic(val);
                                                        else setEvalTopic('');
                                                    }}
                                                    className="w-full px-5 py-3.5 bg-[#FDF6F0] border-0 rounded-xl focus:ring-2 focus:ring-[#C8A288] text-[#4A3B32] font-medium appearance-none"
                                                >
                                                    <option value="">Select a topic...</option>
                                                    {availableTopics.map((topic, idx) => (
                                                        <option key={idx} value={topic}>{topic}</option>
                                                    ))}
                                                    <option value="__custom__">Custom Topic...</option>
                                                </select>
                                                <ChevronDown className="absolute right-4 top-1/2 -translate-y-1/2 h-4 w-4 text-[#8a6a5c] pointer-events-none" />
                                                {evalTopicSelection === '__custom__' && (
                                                    <input
                                                        type="text"
                                                        value={evalTopic}
                                                        onChange={(e) => setEvalTopic(e.target.value)}
                                                        placeholder="Enter custom topic..."
                                                        className="w-full px-5 py-3.5 bg-[#FDF6F0] border-0 rounded-xl focus:ring-2 focus:ring-[#C8A288] mt-3"
                                                        autoFocus
                                                    />
                                                )}
                                            </div>
                                        ) : (
                                            <input
                                                type="text"
                                                value={evalTopic}
                                                onChange={(e) => setEvalTopic(e.target.value)}
                                                placeholder="e.g., Photosynthesis"
                                                className="w-full px-5 py-3.5 bg-[#FDF6F0] border-0 rounded-xl focus:ring-2 focus:ring-[#C8A288]"
                                            />
                                        )}
                                    </div>

                                    <div>
                                        <label className="block text-sm font-bold mb-2 text-[#4A3B32] uppercase tracking-wide opacity-80">Questions</label>
                                        <div className="relative">
                                            <select
                                                value={evalNumQuestions}
                                                onChange={(e) => setEvalNumQuestions(e.target.value)}
                                                className="w-full px-5 py-3.5 bg-[#FDF6F0] border-0 rounded-xl focus:ring-2 focus:ring-[#C8A288] text-[#4A3B32] font-medium appearance-none"
                                            >
                                                {[1, 2, 3, 5].map(num => (
                                                    <option key={num} value={num}>{num} Questions</option>
                                                ))}
                                            </select>
                                            <ChevronDown className="absolute right-4 top-1/2 -translate-y-1/2 h-4 w-4 text-[#8a6a5c] pointer-events-none" />
                                        </div>
                                    </div>

                                    <button
                                        onClick={handleGenerateSubjectiveTest}
                                        disabled={evalLoading}
                                        className="w-full py-4 bg-[#C8A288] text-white rounded-xl hover:bg-[#B08B72] font-bold disabled:opacity-50 transition-colors mt-4 flex items-center justify-center gap-2"
                                    >
                                        {evalLoading ? <Loader2 className="h-5 w-5 animate-spin" /> : <FileText className="h-5 w-5" />}
                                        {evalLoading ? 'Generating...' : 'Start Evaluation'}
                                    </button>
                                </div>
                            </div>
                        ) : (
                            <div className="space-y-8 pb-20 px-2">
                                <div className="flex justify-between items-center">
                                    <div>
                                        <h3 className="text-2xl font-bold">{evalTest.topic || 'Subjective'} Evaluation</h3>
                                        <p className="text-sm text-[#8a6a5c]">{evalTest.questions.length} Questions</p>
                                    </div>
                                    <button
                                        onClick={handleResetSubjectiveTest}
                                        className="text-[#C8A288] hover:text-[#B08B72] font-medium flex items-center gap-1"
                                    >
                                        <LogOut className="h-4 w-4 rotate-180" /> Back
                                    </button>
                                </div>

                                {evalResult && (
                                    <div className="bg-white p-6 rounded-2xl border border-[#E6D5CC] shadow-sm text-center">
                                        <h4 className="text-lg font-bold text-[#4A3B32] mb-2">Evaluation Report</h4>
                                        <div className={`text-3xl font-bold mb-1 ${
                                            evalResult.percentage >= 80 ? 'text-green-600' : 'text-[#C8A288]'
                                        }`}>{evalResult.total_score} / {evalResult.max_score}</div>
                                        <p className="text-[#8a6a5c] mb-4">{evalResult.percentage.toFixed(0)}% Score</p>
                                        
                                        {cameFromPath && (
                                            <p className={`text-sm font-bold mb-4 ${evalResult.percentage >= 80 ? 'text-green-600' : 'text-orange-600'}`}>
                                                {evalResult.percentage >= 80 ? '✓ Topic completed!' : 'Need 80% to complete this topic'}
                                            </p>
                                        )}

                                        <div className="flex justify-center gap-4">
                                            {cameFromPath && onReturnToPath && (
                                                <button
                                                    onClick={onReturnToPath}
                                                    className="px-6 py-2 bg-[#C8A288] text-white rounded-lg hover:bg-[#B08B72] font-medium transition-colors flex items-center gap-2"
                                                >
                                                    <ArrowLeft className="h-4 w-4" />
                                                    Back to Path
                                                </button>
                                            )}
                                            <button
                                                onClick={handleResetSubjectiveTest}
                                                className="px-6 py-2 bg-[#FDF6F0] text-[#4A3B32] rounded-lg hover:bg-[#E6D5CC] font-medium transition-colors"
                                            >
                                                New Evaluation
                                            </button>
                                        </div>
                                    </div>
                                )}

                                {evalTest.questions.map((q, i) => {
                                    const result = evalResult?.evaluations?.find(e => String(e.question_id) === String(q.id));
                                    return (
                                        <div key={q.id} className="p-6 bg-[#FDF6F0] rounded-2xl border border-[#E6D5CC] shadow-sm">
                                            <div className="font-bold text-lg mb-4 flex gap-2">
                                                <span>{i + 1}.</span>
                                                <div className="prose prose-sm max-w-none">
                                                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{q.question}</ReactMarkdown>
                                                </div>
                                            </div>

                                            {!evalResult ? (
                                                <textarea
                                                    value={evalUserAnswers[q.id] || ''}
                                                    onChange={(e) => handleSubjectiveAnswerChange(q.id, e.target.value)}
                                                    rows={4}
                                                    className="w-full px-4 py-3 bg-white border border-[#E6D5CC] rounded-xl focus:ring-2 focus:ring-[#C8A288] outline-none resize-none"
                                                    placeholder="Type your answer here..."
                                                />
                                            ) : (
                                                <div className="space-y-4">
                                                    <div className="bg-white p-4 rounded-xl border border-[#E6D5CC]">
                                                        <p className="text-xs text-[#8a6a5c] uppercase font-bold mb-1">Your Answer</p>
                                                        <p className="text-[#4A3B32]">{result?.user_answer}</p>
                                                    </div>

                                                    <div className={`p-4 rounded-xl border ${result?.score >= 7 ? 'bg-green-50 border-green-200' :
                                                        result?.score >= 4 ? 'bg-yellow-50 border-yellow-200' :
                                                            'bg-red-50 border-red-200'
                                                    }`}>
                                                        <div className="flex justify-between items-start mb-2">
                                                            <p className="font-bold text-sm uppercase opacity-80">AI Feedback</p>
                                                            <span className="font-bold text-lg">{result?.score}/10</span>
                                                        </div>
                                                        <div className="mb-2 prose prose-sm max-w-none">
                                                            <ReactMarkdown remarkPlugins={[remarkGfm]}>{result?.feedback}</ReactMarkdown>
                                                        </div>
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    );
                                })}

                                {!evalResult && (
                                    <div className="pt-4 pb-8">
                                        <button
                                            onClick={handleSubmitSubjectiveTest}
                                            disabled={evalLoading || Object.keys(evalUserAnswers).length === 0}
                                            className="w-full py-4 bg-[#C8A288] text-white rounded-xl hover:bg-[#B08B72] font-bold text-lg shadow-sm disabled:opacity-50 transition-all transform active:scale-[0.99]"
                                        >
                                            {evalLoading ? 'Evaluating Answers...' : 'Submit All Answers'}
                                        </button>
                                    </div>
                                )}
                            </div>
                        )}
                    </>
                )}
            </div>
            )}

            {/* Quiz Mode Toggle - Sticky Bottom Footer */}
            {!mcqLoading && !evalLoading && !mcqTest && !evalTest && !cameFromPath && (
                <div className="flex-none p-4 bottom-0 w-full border-t border-[#E6D5CC] bg-[#FDF6F0]/95 backdrop-blur-md z-10">
                    <div className="flex justify-center">
                        <div className="bg-[#E6D5CC]/40 p-1.5 rounded-xl flex gap-1 shadow-inner">
                            <button
                                onClick={() => setQuizMode('mcq')}
                                className={`px-5 py-2.5 rounded-lg text-sm font-bold transition-all ${quizMode === 'mcq' ? 'bg-[#C8A288] text-white shadow-md transform scale-105' : 'text-[#8a6a5c] hover:bg-white/50'}`}
                            >
                                MCQ
                            </button>
                            <button
                                onClick={() => setQuizMode('subjective')}
                                className={`px-5 py-2.5 rounded-lg text-sm font-bold transition-all ${quizMode === 'subjective' ? 'bg-[#C8A288] text-white shadow-md transform scale-105' : 'text-[#8a6a5c] hover:bg-white/50'}`}
                            >
                                Subjective
                            </button>
                            <button
                                onClick={() => setQuizMode('both')}
                                className={`px-5 py-2.5 rounded-lg text-sm font-bold transition-all ${quizMode === 'both' ? 'bg-[#C8A288] text-white shadow-md transform scale-105' : 'text-[#8a6a5c] hover:bg-white/50'}`}
                            >
                                Complete
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default QuizView;
