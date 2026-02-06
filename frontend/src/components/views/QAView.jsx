import React, { useState, useEffect } from 'react';
import { HelpCircle, ChevronRight, ChevronDown, Loader2, FileText, AlignLeft, AlignCenter, AlignJustify } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { generateSubjectiveTest } from '../../api';
import { useToast } from '../../context/ToastContext';

const QAView = ({ projectId, availableTopics, selectedDocuments, onQAActiveChange = null }) => {
    const toast = useToast();
    // Q&A State
    const [qaTopic, setQaTopic] = useState('');
    const [qaTopicSelection, setQaTopicSelection] = useState('');
    const [qaNumQuestions, setQaNumQuestions] = useState(5);
    const [answerSize, setAnswerSize] = useState('medium'); // 'small' | 'medium' | 'large'
    const [qaTest, setQaTest] = useState(null);
    const [qaLoading, setQaLoading] = useState(false);
    const [qaRevealed, setQaRevealed] = useState({});

    // Notify parent when Q&A is active (loading or has questions)
    useEffect(() => {
        if (onQAActiveChange) {
            const isActive = qaLoading || qaTest !== null;
            onQAActiveChange(isActive);
        }
    }, [qaLoading, qaTest, onQAActiveChange]);

    // Answer size config
    const answerSizeConfig = {
        small: { maxQuestions: 15, label: 'Short', description: 'Brief 1-2 sentence answers', icon: AlignLeft },
        medium: { maxQuestions: 10, label: 'Medium', description: 'Moderate paragraph answers', icon: AlignCenter },
        large: { maxQuestions: 5, label: 'Detailed', description: 'In-depth comprehensive answers', icon: AlignJustify }
    };

    // Get available question counts based on answer size
    const getQuestionOptions = () => {
        const max = answerSizeConfig[answerSize].maxQuestions;
        const options = [];
        for (let i = 1; i <= max; i++) {
            if (i <= 5 || i === 10 || i === 15) {
                options.push(i);
            }
        }
        // Ensure max is included
        if (!options.includes(max)) {
            options.push(max);
        }
        return options.sort((a, b) => a - b);
    };

    // Adjust question count if it exceeds new max when answer size changes
    const handleAnswerSizeChange = (size) => {
        setAnswerSize(size);
        const maxQ = answerSizeConfig[size].maxQuestions;
        if (qaNumQuestions > maxQ) {
            setQaNumQuestions(maxQ);
        }
    };

    const handleGenerateQA = async () => {
        setQaLoading(true);
        setQaTest(null);
        setQaRevealed({});

        try {
            // Pass answer size to backend
            const data = await generateSubjectiveTest(projectId, qaTopic, qaNumQuestions, selectedDocuments, answerSize);
            setQaTest(data);
        } catch (error) {
            console.error("QA gen error", error);
            toast.error('Failed to generate Q&A');
        } finally {
            setQaLoading(false);
        }
    };

    const toggleAnswer = (idx) => {
        setQaRevealed(prev => ({ ...prev, [idx]: !prev[idx] }));
    };

    const revealAll = () => {
        const allRevealed = {};
        qaTest.questions.forEach((_, idx) => {
            allRevealed[idx] = true;
        });
        setQaRevealed(allRevealed);
    };

    const hideAll = () => {
        setQaRevealed({});
    };

    return (
        <div className="h-full overflow-y-auto p-4 md:p-8 max-w-3xl mx-auto custom-scrollbar relative">
            {/* Full-screen Loading State */}
            {qaLoading && (
                <div className="h-full flex flex-col items-center justify-center animate-in fade-in duration-300">
                    <div className="relative mb-6">
                        <div className="h-20 w-20 border-4 border-[#E6D5CC] rounded-full"></div>
                        <div className="absolute inset-0 h-20 w-20 border-4 border-[#C8A288] rounded-full border-t-transparent animate-spin"></div>
                        <HelpCircle className="absolute inset-0 m-auto h-8 w-8 text-[#C8A288]" />
                    </div>
                    <h3 className="text-xl font-bold text-[#4A3B32] mb-2">Generating Q&A</h3>
                    <p className="text-[#8a6a5c] text-center max-w-xs">
                        Creating {qaNumQuestions} {answerSizeConfig[answerSize].label.toLowerCase()} questions about <span className="font-semibold">{qaTopic || 'your documents'}</span>...
                    </p>
                    <div className="flex gap-1.5 mt-6">
                        <div className="h-2 w-2 bg-[#C8A288] rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                        <div className="h-2 w-2 bg-[#C8A288] rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                        <div className="h-2 w-2 bg-[#C8A288] rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                    </div>
                </div>
            )}

            {/* Initial Form - Only show when not loading and no test */}
            {!qaLoading && !qaTest && (
                <div className="text-center py-12 animate-in fade-in slide-in-from-bottom-4">
                    <div className="h-20 w-20 bg-[#FDF6F0] rounded-full flex items-center justify-center mx-auto mb-6">
                        <HelpCircle className="h-10 w-10 text-[#C8A288]" />
                    </div>
                    <h3 className="text-2xl font-bold mb-2 text-[#4A3B32]">Q&A Generation</h3>
                    <p className="text-[#8a6a5c] mb-8">Generate study questions and reveal answers one by one.</p>

                    <div className="max-w-md mx-auto space-y-5 bg-white p-6 md:p-8 rounded-3xl border border-[#E6D5CC] shadow-sm text-left">
                        {/* Topic Selection */}
                        <div>
                            <label className="block text-sm font-bold mb-2 text-[#4A3B32] uppercase tracking-wide opacity-80">Topic</label>

                            {availableTopics.length > 0 ? (
                                <div className="relative">
                                    <select
                                        value={qaTopicSelection}
                                        onChange={(e) => {
                                            const val = e.target.value;
                                            setQaTopicSelection(val);
                                            if (val !== '__custom__') setQaTopic(val);
                                            else setQaTopic('');
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
                                    {qaTopicSelection === '__custom__' && (
                                        <input
                                            type="text"
                                            value={qaTopic}
                                            onChange={(e) => setQaTopic(e.target.value)}
                                            placeholder="Enter custom topic..."
                                            className="w-full px-5 py-3.5 bg-[#FDF6F0] border-0 rounded-xl focus:ring-2 focus:ring-[#C8A288] mt-3 animate-in fade-in"
                                            autoFocus
                                        />
                                    )}
                                </div>
                            ) : (
                                <input
                                    type="text"
                                    value={qaTopic}
                                    onChange={(e) => setQaTopic(e.target.value)}
                                    placeholder="Enter custom topic..."
                                    className="w-full px-5 py-3.5 bg-[#FDF6F0] border-0 rounded-xl focus:ring-2 focus:ring-[#C8A288]"
                                />
                            )}
                        </div>

                        {/* Answer Size Selection */}
                        <div>
                            <label className="block text-sm font-bold mb-2 text-[#4A3B32] uppercase tracking-wide opacity-80">Answer Size</label>
                            <div className="grid grid-cols-3 gap-2">
                                {Object.entries(answerSizeConfig).map(([size, config]) => {
                                    const Icon = config.icon;
                                    const isSelected = answerSize === size;
                                    return (
                                        <button
                                            key={size}
                                            type="button"
                                            onClick={() => handleAnswerSizeChange(size)}
                                            className={`p-3 rounded-xl border-2 transition-all flex flex-col items-center gap-1 ${
                                                isSelected
                                                    ? 'border-[#C8A288] bg-[#FDF6F0] text-[#4A3B32]'
                                                    : 'border-transparent bg-gray-50 text-[#8a6a5c] hover:bg-gray-100'
                                            }`}
                                        >
                                            <Icon className={`h-5 w-5 ${isSelected ? 'text-[#C8A288]' : ''}`} />
                                            <span className="font-bold text-sm">{config.label}</span>
                                            <span className="text-xs opacity-70">Max {config.maxQuestions}</span>
                                        </button>
                                    );
                                })}
                            </div>
                            <p className="text-xs text-[#8a6a5c] mt-2 text-center">
                                {answerSizeConfig[answerSize].description}
                            </p>
                        </div>

                        {/* Number of Questions */}
                        <div>
                            <label className="block text-sm font-bold mb-2 text-[#4A3B32] uppercase tracking-wide opacity-80">
                                Number of Questions
                                <span className="text-xs font-normal ml-2 opacity-60">
                                    (max {answerSizeConfig[answerSize].maxQuestions} for {answerSizeConfig[answerSize].label.toLowerCase()} answers)
                                </span>
                            </label>
                            <div className="relative">
                                <select
                                    value={qaNumQuestions}
                                    onChange={(e) => setQaNumQuestions(parseInt(e.target.value))}
                                    className="w-full px-5 py-3.5 bg-[#FDF6F0] border-0 rounded-xl focus:ring-2 focus:ring-[#C8A288] text-[#4A3B32] font-medium appearance-none"
                                >
                                    {getQuestionOptions().map(num => (
                                        <option key={num} value={num}>{num} Questions</option>
                                    ))}
                                </select>
                                <ChevronDown className="absolute right-4 top-1/2 -translate-y-1/2 h-4 w-4 text-[#8a6a5c] pointer-events-none" />
                            </div>
                        </div>

                        <button
                            onClick={handleGenerateQA}
                            disabled={qaLoading}
                            className="w-full py-4 bg-[#C8A288] text-white rounded-xl hover:bg-[#B08B72] font-bold shadow-lg shadow-[#C8A288]/20 disabled:opacity-50 transition-colors mt-4 flex items-center justify-center gap-2"
                        >
                            {qaLoading ? <Loader2 className="h-5 w-5 animate-spin" /> : <HelpCircle className="h-5 w-5" />}
                            {qaLoading ? 'Generating...' : 'Generate Questions'}
                        </button>
                    </div>
                </div>
            )}

            {/* Results - Show when test is loaded */}
            {!qaLoading && qaTest && (
                <div className="space-y-6 pb-12 animate-in fade-in slide-in-from-bottom-8 duration-500">
                    <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
                        <div>
                            <h3 className="text-2xl font-bold text-[#4A3B32]">{qaTest.topic || 'General'} Q&A</h3>
                            <p className="text-sm text-[#8a6a5c]">
                                {qaTest.questions?.length} {answerSizeConfig[answerSize].label.toLowerCase()} questions
                            </p>
                        </div>
                        <div className="flex gap-2">
                            <button
                                onClick={revealAll}
                                className="px-3 py-1.5 text-sm border border-[#E6D5CC] rounded-lg hover:bg-[#FDF6F0] text-[#8a6a5c] font-medium transition-colors"
                            >
                                Reveal All
                            </button>
                            <button
                                onClick={hideAll}
                                className="px-3 py-1.5 text-sm border border-[#E6D5CC] rounded-lg hover:bg-[#FDF6F0] text-[#8a6a5c] font-medium transition-colors"
                            >
                                Hide All
                            </button>
                            <button
                                onClick={() => setQaTest(null)}
                                className="px-4 py-1.5 text-sm bg-[#C8A288] text-white rounded-lg hover:bg-[#B08B72] font-medium transition-colors"
                            >
                                New Q&A
                            </button>
                        </div>
                    </div>

                    {qaTest.questions && qaTest.questions.map((pair, idx) => (
                        <div key={idx} className="bg-white rounded-2xl border border-[#E6D5CC] shadow-sm overflow-hidden transition-all duration-300 hover:shadow-md">
                            <button
                                onClick={() => toggleAnswer(idx)}
                                className="w-full p-6 text-left flex justify-between items-center gap-4 hover:bg-gray-50 transition-colors group"
                            >
                                <div className="flex gap-4">
                                    <span className="flex-shrink-0 h-8 w-8 bg-[#FDF6F0] text-[#C8A288] rounded-full flex items-center justify-center font-bold text-sm">
                                        Q{idx + 1}
                                    </span>
                                    <h4 className="font-bold text-lg text-[#4A3B32] group-hover:text-[#C8A288] transition-colors">
                                        {pair.question}
                                    </h4>
                                </div>
                                <div className={`transform transition-transform duration-300 ${qaRevealed[idx] ? 'rotate-90' : ''}`}>
                                    <ChevronRight className="h-5 w-5 text-[#8a6a5c]" />
                                </div>
                            </button>

                            {qaRevealed[idx] && (
                                <div className="px-6 pb-6 pt-0 animate-in fade-in slide-in-from-top-2">
                                    <div className="pl-12">
                                        <div className="p-4 bg-[#FDF6F0] rounded-xl text-[#4A3B32] leading-relaxed border border-[#E6D5CC]">
                                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                                {pair.answer}
                                            </ReactMarkdown>
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};

export default QAView;
