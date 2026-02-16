import React, { useState, useEffect } from 'react';
import {
    GraduationCap, Calendar, Clock, Target, Brain,
    BookOpen, AlertTriangle, CheckCircle, Play, Pause,
    RotateCcw, ChevronRight, Zap, Award, Timer,
    FileText, TrendingUp, X, Plus, Trash2, Settings
} from 'lucide-react';
import { generateMCQ, generateSubjectiveTest, getExams, saveExam as saveExamApi, deleteExam as deleteExamApi } from '../../api';
import { recordActivity } from '../../utils/studyActivity';

const ExamPrepMode = ({
    projectId,
    documents = [],
    topics = [],
    selectedDocuments = [],
    onStartQuiz,
    onClose
}) => {
    // Exam Configuration
    const [examName, setExamName] = useState('');
    const [examDate, setExamDate] = useState('');
    const [selectedTopics, setSelectedTopics] = useState([]);
    const [difficulty, setDifficulty] = useState('medium');
    const [examMode, setExamMode] = useState('practice'); // 'practice', 'mock', 'lastMinute'
    
    // Progress tracking
    const [savedExams, setSavedExams] = useState([]);
    const [activeExam, setActiveExam] = useState(null);
    const [loading, setLoading] = useState(false);
    const [mockTest, setMockTest] = useState(null);
    const [countdown, setCountdown] = useState(null);

    // Load saved exams from API
    useEffect(() => {
        const load = async () => {
            try {
                const data = await getExams(projectId);
                setSavedExams(data.exams || []);
            } catch (err) {
                console.error('Failed to load exams:', err);
            }
        };
        load();
    }, [projectId]);

    // Countdown timer
    useEffect(() => {
        const examDateValue = activeExam?.date || activeExam?.exam_date;
        if (examDateValue) {
            const updateCountdown = () => {
                const now = new Date();
                const examDateTime = new Date(examDateValue);
                const diff = examDateTime - now;

                if (diff > 0) {
                    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
                    const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
                    const mins = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
                    setCountdown({ days, hours, mins, total: diff });
                } else {
                    setCountdown({ days: 0, hours: 0, mins: 0, total: 0, passed: true });
                }
            };

            updateCountdown();
            const interval = setInterval(updateCountdown, 60000);
            return () => clearInterval(interval);
        }
    }, [activeExam]);

    const saveExam = async () => {
        if (!examName || !examDate) return;

        try {
            const result = await saveExamApi(projectId, examName, examDate, selectedTopics, difficulty);
            const newExam = {
                ...result,
                date: result.exam_date || examDate,
                name: result.name || examName,
            };
            setSavedExams([...savedExams, newExam]);
            setActiveExam(newExam);
            setExamName('');
            setExamDate('');
            setSelectedTopics([]);
            recordActivity(projectId, 'exam', { action: 'save_exam', examName });
        } catch (err) {
            console.error('Failed to save exam:', err);
        }
    };

    const deleteExam = async (examId) => {
        try {
            await deleteExamApi(examId);
            const updated = savedExams.filter(e => e.id !== examId);
            setSavedExams(updated);
            if (activeExam?.id === examId) {
                setActiveExam(null);
            }
        } catch (err) {
            console.error('Failed to delete exam:', err);
        }
    };

    const generateMockExam = async () => {
        if (!activeExam) return;
        setLoading(true);
        try {
            // Generate a mix of MCQ and subjective questions
            const topicsToUse = activeExam.topics.length > 0 ? activeExam.topics : topics.slice(0, 5);
            const mcqs = [];
            const subjective = [];

            // Get 2-3 MCQs per topic
            for (const topic of topicsToUse.slice(0, 5)) {
                const mcqResult = await generateMCQ(projectId, topic, 3, selectedDocuments, activeExam.difficulty);
                if (mcqResult.questions) {
                    mcqs.push(...mcqResult.questions.map(q => ({ ...q, topic })));
                }
            }

            // Get 1 subjective per key topic
            for (const topic of topicsToUse.slice(0, 3)) {
                const subjResult = await generateSubjectiveTest(projectId, topic, 1, selectedDocuments, 'medium');
                if (subjResult.questions) {
                    subjective.push(...subjResult.questions.map(q => ({ ...q, topic })));
                }
            }

            setMockTest({
                mcqs: mcqs.slice(0, 15), // Max 15 MCQs
                subjective: subjective.slice(0, 3), // Max 3 subjective
                timeLimit: (mcqs.length * 1.5 + subjective.length * 5) * 60, // Time in seconds
                generated: new Date().toISOString(),
            });
            recordActivity(projectId, 'exam', { action: 'generate_mock', mcqCount: mcqs.length, subjectiveCount: subjective.length });
        } catch (error) {
            console.error('Failed to generate mock exam:', error);
        } finally {
            setLoading(false);
        }
    };

    const getUrgencyLevel = () => {
        if (!countdown || countdown.passed) return { level: 'passed', color: 'text-gray-500', bg: 'bg-gray-100' };
        if (countdown.days <= 1) return { level: 'critical', color: 'text-red-600', bg: 'bg-red-100' };
        if (countdown.days <= 3) return { level: 'urgent', color: 'text-orange-600', bg: 'bg-orange-100' };
        if (countdown.days <= 7) return { level: 'soon', color: 'text-amber-600', bg: 'bg-amber-100' };
        return { level: 'normal', color: 'text-green-600', bg: 'bg-green-100' };
    };

    const urgency = getUrgencyLevel();

    const ModeCard = ({ id, title, description, icon: Icon, recommended }) => (
        <button
            onClick={() => setExamMode(id)}
            className={`p-4 rounded-xl border-2 text-left transition-all ${
                examMode === id
                    ? 'border-[#C8A288] bg-[#C8A288]/10'
                    : 'border-[#E6D5CC] hover:border-[#C8A288]/50'
            }`}
        >
            <div className="flex items-start gap-3">
                <div className={`h-10 w-10 rounded-lg flex items-center justify-center ${
                    examMode === id ? 'bg-[#C8A288]' : 'bg-[#FDF6F0]'
                }`}>
                    <Icon className={`h-5 w-5 ${examMode === id ? 'text-white' : 'text-[#C8A288]'}`} />
                </div>
                <div className="flex-1">
                    <div className="flex items-center gap-2">
                        <h4 className="font-bold text-[#4A3B32]">{title}</h4>
                        {recommended && (
                            <span className="text-xs px-2 py-0.5 bg-amber-100 text-amber-700 rounded-full">
                                Recommended
                            </span>
                        )}
                    </div>
                    <p className="text-sm text-[#8a6a5c] mt-1">{description}</p>
                </div>
            </div>
        </button>
    );

    return (
        <div className="h-full overflow-y-auto">
            {/* Header */}
            <div className="sticky top-0 bg-gradient-to-r from-[#C8A288] to-[#A08072] text-white p-4 z-10">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="h-12 w-12 bg-white/20 rounded-xl flex items-center justify-center backdrop-blur-sm">
                            <GraduationCap className="h-7 w-7" />
                        </div>
                        <div>
                            <h2 className="text-xl font-bold">Exam Preparation</h2>
                            <p className="text-sm opacity-90">Focused study mode for your exams</p>
                        </div>
                    </div>
                    {onClose && (
                        <button
                            onClick={onClose}
                            className="p-2 hover:bg-white/20 rounded-lg transition-colors"
                        >
                            <X className="h-6 w-6" />
                        </button>
                    )}
                </div>
            </div>

            <div className="p-4 md:p-6 space-y-6">
                {/* Active Exam Countdown */}
                {activeExam && countdown && (
                    <div className={`rounded-2xl p-6 ${urgency.bg} border-2 border-current ${urgency.color}`}>
                        <div className="flex items-center justify-between mb-4">
                            <div>
                                <h3 className="text-xl font-bold text-[#4A3B32]">{activeExam.name}</h3>
                                <p className="text-sm text-[#8a6a5c]">
                                    {new Date(activeExam.date).toLocaleDateString('en-US', {
                                        weekday: 'long',
                                        month: 'long',
                                        day: 'numeric',
                                        year: 'numeric'
                                    })}
                                </p>
                            </div>
                            <button
                                onClick={() => setActiveExam(null)}
                                className="p-2 hover:bg-white/50 rounded-lg transition-colors"
                            >
                                <X className="h-5 w-5 text-[#8a6a5c]" />
                            </button>
                        </div>

                        {countdown.passed ? (
                            <div className="text-center py-4">
                                <CheckCircle className="h-12 w-12 mx-auto mb-2 text-green-500" />
                                <p className="font-bold text-[#4A3B32]">Exam day has passed!</p>
                            </div>
                        ) : (
                            <div className="grid grid-cols-3 gap-4 text-center">
                                <div className="bg-white/80 rounded-xl p-4">
                                    <p className="text-3xl font-bold text-[#4A3B32]">{countdown.days}</p>
                                    <p className="text-sm text-[#8a6a5c]">Days</p>
                                </div>
                                <div className="bg-white/80 rounded-xl p-4">
                                    <p className="text-3xl font-bold text-[#4A3B32]">{countdown.hours}</p>
                                    <p className="text-sm text-[#8a6a5c]">Hours</p>
                                </div>
                                <div className="bg-white/80 rounded-xl p-4">
                                    <p className="text-3xl font-bold text-[#4A3B32]">{countdown.mins}</p>
                                    <p className="text-sm text-[#8a6a5c]">Minutes</p>
                                </div>
                            </div>
                        )}

                        {urgency.level === 'critical' && !countdown.passed && (
                            <div className="mt-4 p-3 bg-red-200 rounded-xl flex items-center gap-2 text-red-700">
                                <AlertTriangle className="h-5 w-5 flex-shrink-0" />
                                <p className="text-sm font-medium">
                                    Your exam is tomorrow! Focus on weak topics and key concepts.
                                </p>
                            </div>
                        )}
                    </div>
                )}

                {/* Study Mode Selection */}
                <div className="space-y-3">
                    <h3 className="font-bold text-[#4A3B32]">Choose Study Mode</h3>
                    <div className="grid gap-3 sm:grid-cols-3">
                        <ModeCard
                            id="practice"
                            title="Topic Practice"
                            description="Focus on individual topics with quizzes"
                            icon={Target}
                            recommended={countdown?.days > 3}
                        />
                        <ModeCard
                            id="mock"
                            title="Mock Exam"
                            description="Timed full-length practice test"
                            icon={Timer}
                            recommended={countdown?.days <= 3 && countdown?.days > 1}
                        />
                        <ModeCard
                            id="lastMinute"
                            title="Last-Minute Review"
                            description="Quick summary of key concepts"
                            icon={Zap}
                            recommended={countdown?.days <= 1}
                        />
                    </div>
                </div>

                {/* Mode-specific content */}
                {examMode === 'practice' && (
                    <div className="bg-white rounded-2xl border border-[#E6D5CC] p-4">
                        <h4 className="font-bold text-[#4A3B32] mb-3">Select Topics to Practice</h4>
                        <div className="max-h-48 overflow-y-auto space-y-2">
                            {topics.slice(0, 15).map((topic, idx) => (
                                <label
                                    key={idx}
                                    className="flex items-center gap-3 p-2 hover:bg-[#FDF6F0] rounded-lg cursor-pointer"
                                >
                                    <input
                                        type="checkbox"
                                        checked={selectedTopics.includes(topic)}
                                        onChange={(e) => {
                                            if (e.target.checked) {
                                                setSelectedTopics([...selectedTopics, topic]);
                                            } else {
                                                setSelectedTopics(selectedTopics.filter(t => t !== topic));
                                            }
                                        }}
                                        className="h-4 w-4 text-[#C8A288] rounded focus:ring-[#C8A288]"
                                    />
                                    <span className="text-[#4A3B32]">{topic}</span>
                                </label>
                            ))}
                        </div>
                        <button
                            onClick={() => onStartQuiz && onStartQuiz(selectedTopics[0], 'both')}
                            disabled={selectedTopics.length === 0}
                            className="w-full mt-4 py-3 bg-[#C8A288] text-white rounded-xl font-bold hover:bg-[#B08B72] transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
                        >
                            <Play className="h-5 w-5" />
                            Start Practice Quiz
                        </button>
                    </div>
                )}

                {examMode === 'mock' && (
                    <div className="bg-white rounded-2xl border border-[#E6D5CC] p-4">
                        <h4 className="font-bold text-[#4A3B32] mb-3">Generate Mock Exam</h4>
                        <p className="text-sm text-[#8a6a5c] mb-4">
                            A timed exam with 15 MCQs and 3 subjective questions covering your selected topics.
                        </p>

                        <div className="grid grid-cols-3 gap-3 mb-4">
                            {['easy', 'medium', 'hard'].map((diff) => (
                                <button
                                    key={diff}
                                    onClick={() => setDifficulty(diff)}
                                    className={`py-2 px-4 rounded-lg font-medium capitalize transition-colors ${
                                        difficulty === diff
                                            ? 'bg-[#C8A288] text-white'
                                            : 'bg-[#FDF6F0] text-[#4A3B32] hover:bg-[#E6D5CC]'
                                    }`}
                                >
                                    {diff}
                                </button>
                            ))}
                        </div>

                        <button
                            onClick={generateMockExam}
                            disabled={loading}
                            className="w-full py-3 bg-gradient-to-r from-[#C8A288] to-[#A08072] text-white rounded-xl font-bold hover:shadow-lg transition-all disabled:opacity-50 flex items-center justify-center gap-2"
                        >
                            {loading ? (
                                <>
                                    <div className="h-5 w-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                                    Generating...
                                </>
                            ) : (
                                <>
                                    <FileText className="h-5 w-5" />
                                    Generate Mock Exam
                                </>
                            )}
                        </button>
                    </div>
                )}

                {examMode === 'lastMinute' && (
                    <div className="bg-white rounded-2xl border border-[#E6D5CC] p-4">
                        <h4 className="font-bold text-[#4A3B32] mb-3">Last-Minute Review</h4>
                        <div className="space-y-3">
                            <button className="w-full p-4 bg-[#FDF6F0] rounded-xl text-left hover:bg-[#E6D5CC] transition-colors flex items-center gap-3">
                                <div className="h-10 w-10 bg-amber-100 rounded-lg flex items-center justify-center">
                                    <Zap className="h-5 w-5 text-amber-600" />
                                </div>
                                <div className="flex-1">
                                    <p className="font-bold text-[#4A3B32]">Key Concepts Summary</p>
                                    <p className="text-sm text-[#8a6a5c]">Quick overview of main ideas</p>
                                </div>
                                <ChevronRight className="h-5 w-5 text-[#8a6a5c]" />
                            </button>
                            <button className="w-full p-4 bg-[#FDF6F0] rounded-xl text-left hover:bg-[#E6D5CC] transition-colors flex items-center gap-3">
                                <div className="h-10 w-10 bg-red-100 rounded-lg flex items-center justify-center">
                                    <AlertTriangle className="h-5 w-5 text-red-600" />
                                </div>
                                <div className="flex-1">
                                    <p className="font-bold text-[#4A3B32]">Weak Topics Drill</p>
                                    <p className="text-sm text-[#8a6a5c]">Focus on areas that need work</p>
                                </div>
                                <ChevronRight className="h-5 w-5 text-[#8a6a5c]" />
                            </button>
                            <button className="w-full p-4 bg-[#FDF6F0] rounded-xl text-left hover:bg-[#E6D5CC] transition-colors flex items-center gap-3">
                                <div className="h-10 w-10 bg-blue-100 rounded-lg flex items-center justify-center">
                                    <Brain className="h-5 w-5 text-blue-600" />
                                </div>
                                <div className="flex-1">
                                    <p className="font-bold text-[#4A3B32]">Flashcard Review</p>
                                    <p className="text-sm text-[#8a6a5c]">Quick memory reinforcement</p>
                                </div>
                                <ChevronRight className="h-5 w-5 text-[#8a6a5c]" />
                            </button>
                        </div>
                    </div>
                )}

                {/* Create New Exam */}
                {!activeExam && (
                    <div className="bg-white rounded-2xl border border-[#E6D5CC] p-4">
                        <h4 className="font-bold text-[#4A3B32] mb-3 flex items-center gap-2">
                            <Plus className="h-5 w-5 text-[#C8A288]" />
                            Schedule New Exam
                        </h4>
                        <div className="space-y-3">
                            <input
                                type="text"
                                value={examName}
                                onChange={(e) => setExamName(e.target.value)}
                                placeholder="Exam name (e.g., Midterm, Final)"
                                className="w-full px-4 py-3 bg-[#FDF6F0] border-none rounded-xl focus:ring-2 focus:ring-[#C8A288] text-[#4A3B32]"
                            />
                            <input
                                type="datetime-local"
                                value={examDate}
                                onChange={(e) => setExamDate(e.target.value)}
                                className="w-full px-4 py-3 bg-[#FDF6F0] border-none rounded-xl focus:ring-2 focus:ring-[#C8A288] text-[#4A3B32]"
                            />
                            <button
                                onClick={saveExam}
                                disabled={!examName || !examDate}
                                className="w-full py-3 bg-[#C8A288] text-white rounded-xl font-bold hover:bg-[#B08B72] transition-colors disabled:opacity-50"
                            >
                                Save Exam
                            </button>
                        </div>
                    </div>
                )}

                {/* Saved Exams */}
                {savedExams.length > 0 && (
                    <div className="space-y-3">
                        <h4 className="font-bold text-[#4A3B32]">Your Exams</h4>
                        {savedExams.map((exam) => (
                            <div
                                key={exam.id}
                                className={`bg-white rounded-xl border-2 p-4 transition-all cursor-pointer ${
                                    activeExam?.id === exam.id
                                        ? 'border-[#C8A288]'
                                        : 'border-[#E6D5CC] hover:border-[#C8A288]/50'
                                }`}
                                onClick={() => setActiveExam(exam)}
                            >
                                <div className="flex items-center justify-between">
                                    <div>
                                        <h5 className="font-bold text-[#4A3B32]">{exam.name}</h5>
                                        <p className="text-sm text-[#8a6a5c]">
                                            {new Date(exam.date).toLocaleDateString()}
                                        </p>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                deleteExam(exam.id);
                                            }}
                                            className="p-2 hover:bg-red-50 rounded-lg text-[#8a6a5c] hover:text-red-500 transition-colors"
                                        >
                                            <Trash2 className="h-4 w-4" />
                                        </button>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
};

export default ExamPrepMode;
