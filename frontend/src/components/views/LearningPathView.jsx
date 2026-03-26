import React, { useState, useEffect, useCallback } from 'react';
import { 
    Target, BookOpen, ChevronRight, Loader2, RefreshCw, 
    CheckCircle, Circle, Brain, Sparkles,
    ArrowRight, Play, AlertTriangle, Trophy, XCircle,
    Plus, FileText, CheckSquare, HelpCircle, MessageSquare,
    Network, Zap, GitBranch, Layers
} from 'lucide-react';
import { 
    getLearningPath, 
    buildKnowledgeGraph, 
    getKnowledgeGraph,
    getPerformance 
} from '../../api';
import { useToast } from '../../context/ToastContext';
import { recordActivity } from '../../utils/studyActivity';
import { getRotatingLoadingMessage } from '../../utils/LoadingMessages';

const humorReasons = [
    "Weak topic detected. You skipped leg day on this one.",
    "Your brain is currently spaghetti on this topic. Let's make it al dente.",
    "Exam boss fight detected. Recommend weapon: Full Quiz.",
    "Stop watering every plant at once. Water this specific plant right now.",
    "Step 1: Chop onions. Step 2: Learn this. Step 3: Ace exam.",
    "Without this, you're just punching trees for 4 hours in Minecraft.",
    "If you don't study this, you'll just be eating flour and crying.",
    "Calculated bullshit go. We fight this chapter first.",
    "Notes = raw vegetables, ChatGPT = guy yelling recipes. Eat this first."
];

const getStableHumor = (str) => {
    let hash = 0;
    for (let i = 0; i < str.length; i++) hash = str.charCodeAt(i) + ((hash << 5) - hash);
    return humorReasons[Math.abs(hash) % humorReasons.length];
};

const LearningPathView = ({ 
    projectId, 
    availableTopics, 
    selectedDocuments, 
    setSelectedDocuments, 
    documentTopics,
    documents = [],
    completedTopics = new Set(),
    onStartQuiz,
    onTopicComplete,
    onGenerateNotes,
    onStartQA,
    onOpenTutor,
    onOpenKnowledgeGraph,
    onOpenMindmap,
    onOpenFlashcards
}) => {
    // Helper to get document name by ID
    const getDocName = (docId) => {
        const doc = documents.find(d => d.id === docId);
        return doc?.filename || `Doc: ${docId.slice(0, 8)}...`;
    };
    const toast = useToast();
    const [loading, setLoading] = useState(true);
    const [building, setBuilding] = useState(false);
    const [learningPath, setLearningPath] = useState(null);
    const [graphStats, setGraphStats] = useState(null);
    const [performance, setPerformance] = useState({});
    const [selectedDoc, setSelectedDoc] = useState('all');
    const [expandedTopic, setExpandedTopic] = useState(null);
    const [loadingMsgIdx, setLoadingMsgIdx] = useState(0);
    
    useEffect(() => {
        loadData();
    }, [projectId]);

    // Handle rotating loading messages
    useEffect(() => {
        let interval;
        if (loading || building) {
            interval = setInterval(() => {
                setLoadingMsgIdx(i => i + 1);
            }, 5000); // Rotate roughly every 5 seconds
        }
        return () => clearInterval(interval);
    }, [loading, building]);

    // Automatically trigger build if there is no path and there are available topics
    useEffect(() => {
        if (!loading && !building && availableTopics && availableTopics.length > 0) {
            if (!learningPath || !learningPath.learning_path || learningPath.learning_path.length === 0) {
                const autoGenerateKey = `lumina_path_autoun_${projectId}`;
                if (!sessionStorage.getItem(autoGenerateKey)) {
                    sessionStorage.setItem(autoGenerateKey, 'true');
                    handleBuildGraph();
                }
            }
        }
    }, [loading, building, learningPath, availableTopics, projectId]);
    
    const loadData = async () => {
        // Try to load from sessionStorage cache for instant display
        const cacheKey = `lumina_path_${projectId}`;
        const cached = sessionStorage.getItem(cacheKey);
        if (cached) {
            try {
                const { learningPath: cachedPath, graphStats: cachedStats, performance: cachedPerf } = JSON.parse(cached);
                if (cachedPath) setLearningPath(cachedPath);
                if (cachedStats) setGraphStats(cachedStats);
                if (cachedPerf) setPerformance(cachedPerf);
                setLoading(false); // Show cached data immediately
            } catch (e) {
                // ignore parse errors, will fetch fresh
            }
        }
        
        try {
            // Fetch fresh data (background refresh if cached data was shown)
            const pathData = await getLearningPath(projectId);
            setLearningPath(pathData);
            
            const graphData = await getKnowledgeGraph(projectId);
            setGraphStats(graphData.stats);
            
            const perfData = await getPerformance(projectId);
            const perfMap = {};
            (perfData.performance || []).forEach(p => {
                const total = (p.correct_count || 0) + (p.wrong_count || 0);
                perfMap[p.topic] = {
                    accuracy: total > 0 ? (p.correct_count / total * 100) : 0,
                    attempts: total,
                    correct: p.correct_count || 0,
                    wrong: p.wrong_count || 0
                };
            });
            setPerformance(perfMap);
            
            // Cache the fresh data for next visit
            sessionStorage.setItem(cacheKey, JSON.stringify({
                learningPath: pathData,
                graphStats: graphData.stats,
                performance: perfMap
            }));
        } catch (error) {
            console.error('Failed to load learning path:', error);
        } finally {
            setLoading(false);
        }
    };
    
    const handleBuildGraph = async () => {
        // Get topics based on selection
        let topicsToUse = availableTopics;
        
        if (selectedDoc !== 'all' && documentTopics && documentTopics[selectedDoc]) {
            topicsToUse = documentTopics[selectedDoc];
        }
        
        if (!topicsToUse || topicsToUse.length < 2) {
            toast.warning('Need at least 2 topics to build a learning path. Please select a document with more topics.');
            return;
        }
        
        setBuilding(true);
        try {
            await buildKnowledgeGraph(projectId, topicsToUse, true);
            // Clear cache so fresh data is loaded
            sessionStorage.removeItem(`lumina_path_${projectId}`);
            await loadData();
            recordActivity(projectId, 'path', { action: 'build_graph', topicCount: topicsToUse.length });
        } catch (error) {
            console.error('Failed to build graph:', error);
            toast.error('Failed to build learning path. Please try again.');
        } finally {
            setBuilding(false);
        }
    };
    
    // Find which documents contain a topic
    const findDocumentsForTopic = (topic) => {
        if (!documentTopics) return [];
        
        const docs = [];
        for (const [docId, topics] of Object.entries(documentTopics)) {
            if (topics && topics.includes(topic)) {
                docs.push(docId);
            }
        }
        return docs;
    };
    
    // Handle adding documents to context
    const handleAddToContext = (topic) => {
        const docsWithTopic = findDocumentsForTopic(topic);
        if (setSelectedDocuments && docsWithTopic.length > 0) {
            // Add to existing selection, not replace
            setSelectedDocuments(prev => {
                const newSet = new Set(prev);
                docsWithTopic.forEach(docId => newSet.add(docId));
                return [...newSet];
            });
        }
    };
    
    // Handle starting quiz for a topic
    const handleStartQuiz = (topicIndex, mode = 'both') => {
        const pathItems = learningPath?.learning_path || [];
        const topic = pathItems[topicIndex]?.topic;
        
        if (!topic) return;
        
        // Get documents containing this topic
        const docsWithTopic = findDocumentsForTopic(topic);
        
        // Call parent's onStartQuiz callback
        if (onStartQuiz) {
            onStartQuiz(topic, mode, docsWithTopic);
            recordActivity(projectId, 'path', { action: 'start_topic_quiz', topic });
        }
    };

    // Handle generating notes for a topic
    const handleGenerateNotes = (topicIndex) => {
        const pathItems = learningPath?.learning_path || [];
        const topic = pathItems[topicIndex]?.topic;
        if (!topic || !onGenerateNotes) return;
        const docsWithTopic = findDocumentsForTopic(topic);
        onGenerateNotes(topic, docsWithTopic);
        recordActivity(projectId, 'path', { action: 'generate_notes', topic });
    };

    // Handle starting Q&A for a topic
    const handleStartQA = (topicIndex) => {
        const pathItems = learningPath?.learning_path || [];
        const topic = pathItems[topicIndex]?.topic;
        if (!topic || !onStartQA) return;
        const docsWithTopic = findDocumentsForTopic(topic);
        onStartQA(topic, docsWithTopic);
        recordActivity(projectId, 'path', { action: 'start_qa', topic });
    };

    // Handle opening AI Tutor for a topic
    const handleOpenTutor = (topicIndex) => {
        const pathItems = learningPath?.learning_path || [];
        const topic = pathItems[topicIndex]?.topic;
        if (!topic || !onOpenTutor) return;
        onOpenTutor(topic);
        recordActivity(projectId, 'path', { action: 'open_tutor', topic });
    };

    // Handle opening Mindmap for a topic
    const handleOpenMindmap = (topicIndex) => {
        const pathItems = learningPath?.learning_path || [];
        const topic = pathItems[topicIndex]?.topic;
        if (!topic || !onOpenMindmap) return;
        const docsWithTopic = findDocumentsForTopic(topic);
        onOpenMindmap(topic, docsWithTopic);
        recordActivity(projectId, 'path', { action: 'open_mindmap', topic });
    };

    // Handle opening Flashcards for a topic
    const handleOpenFlashcards = (topicIndex) => {
        const pathItems = learningPath?.learning_path || [];
        const topic = pathItems[topicIndex]?.topic;
        if (!topic || !onOpenFlashcards) return;
        const docsWithTopic = findDocumentsForTopic(topic);
        onOpenFlashcards(topic, docsWithTopic);
        recordActivity(projectId, 'path', { action: 'open_flashcards', topic });
    };
    
    const getTopicStatus = (topic) => {
        // Check if completed
        if (completedTopics.has(topic)) {
            return { status: 'completed', label: 'Completed', color: 'green' };
        }
        
        // Check if in progress (has attempts but not completed)
        const perf = performance[topic];
        if (perf && perf.attempts > 0) {
            return { status: 'in_progress', label: 'In Progress', color: 'yellow' };
        }
        
        return { status: 'ready', label: 'Ready', color: 'blue' };
    };
    
    // Calculate overall progress
    const calculateProgress = () => {
        const pathItems = learningPath?.learning_path || [];
        if (pathItems.length === 0) return 0;
        return Math.round((completedTopics.size / pathItems.length) * 100);
    };
    
    // Check how many docs in context for a topic
    const getDocsInContext = (topic) => {
        const docsWithTopic = findDocumentsForTopic(topic);
        return docsWithTopic.filter(docId => selectedDocuments.includes(docId)).length;
    };

    if (loading || building) {
        return (
            <div className="flex flex-col items-center justify-center h-full min-h-[400px] gap-6 px-4">
                <div className="relative">
                    <div className="h-20 w-20 border-4 border-[#E6D5CC] rounded-full"></div>
                    <div className="absolute inset-0 h-20 w-20 border-4 border-[#C8A288] rounded-full border-t-transparent animate-spin"></div>
                    <Brain className="absolute inset-0 m-auto h-8 w-8 text-[#C8A288] animate-pulse" />
                </div>
                <div className="text-center max-w-[80vw] md:max-w-[60vw]">
                    <p className="text-[#C8A288] font-bold uppercase tracking-widest text-xs mb-3">
                        {building ? 'Synthesizing Path' : 'Loading Path'}
                    </p>
                    <p className="text-[#4A3B32] font-medium italic whitespace-pre-line leading-relaxed text-sm md:text-base selection:bg-[#C8A288] selection:text-white transition-opacity duration-300">
                        {getRotatingLoadingMessage(loadingMsgIdx)}
                    </p>
                </div>
            </div>
        );
    }

    return (
        <div className="h-full flex flex-col">
            <div className="flex-1 overflow-y-auto custom-scrollbar p-4 md:p-8 max-w-4xl mx-auto w-full">
                {/* Header */}
                <div className="text-center mb-8">
                    <div className="inline-flex items-center justify-center p-4 bg-white rounded-2xl shadow-sm border border-[#E6D5CC] mb-4">
                        <Target className="h-8 w-8 text-[#C8A288]" />
                    </div>
                    <h2 className="text-2xl font-bold text-[#4A3B32] mb-2">Learning Path</h2>
                    <p className="text-[#8a6a5c]">
                        Your personalized study sequence
                    </p>
                </div>

                {/* Progress Bar */}
                {learningPath?.learning_path?.length > 0 && (
                    <div className="bg-white rounded-xl border border-[#E6D5CC] p-4 mb-6">
                        <div className="flex items-center justify-between mb-2">
                            <span className="text-sm font-bold text-[#4A3B32]">Overall Progress</span>
                            <span className="text-sm font-bold text-[#C8A288]">{calculateProgress()}%</span>
                        </div>
                        <div className="h-3 bg-[#E6D5CC] rounded-full overflow-hidden">
                            <div 
                                className="h-full bg-gradient-to-r from-[#C8A288] to-green-500 rounded-full transition-all duration-500"
                                style={{ width: `${calculateProgress()}%` }}
                            />
                        </div>
                        <div className="mt-2 text-xs text-[#8a6a5c]">
                            {completedTopics.size} of {learningPath.learning_path.length} topics completed
                        </div>
                    </div>
                )}

                {/* Document Selector & Build Button */}
                <div className="bg-white rounded-xl border border-[#E6D5CC] p-4 mb-6 overflow-hidden">
                    <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
                        <div className="w-full sm:w-auto sm:max-w-[60%]">
                            <label className="block text-sm font-bold text-[#4A3B32] mb-1">
                                Generate Path For
                            </label>
                            <select
                                value={selectedDoc}
                                onChange={(e) => setSelectedDoc(e.target.value)}
                                className="w-full sm:w-auto px-4 py-2 bg-[#FDF6F0] border border-[#E6D5CC] rounded-lg focus:ring-2 focus:ring-[#C8A288] text-[#4A3B32] font-medium max-w-full truncate"
                                style={{ maxWidth: '100%' }}
                            >
                                <option value="all">All Documents ({availableTopics?.length || 0} topics)</option>
                                {/* Show ALL documents with topics for selection */}
                                {Object.entries(documentTopics || {}).map(([docId, topics]) => {
                                    const topicCount = topics?.length || 0;
                                    if (topicCount === 0) return null;
                                    const docName = getDocName(docId);
                                    // Truncate long names for dropdown
                                    const displayName = docName.length > 40 ? docName.substring(0, 37) + '...' : docName;
                                    return (
                                        <option key={docId} value={docId} title={docName}>
                                            {displayName} ({topicCount} topics)
                                        </option>
                                    );
                                })}
                            </select>
                        </div>
                        
                        <button
                            onClick={handleBuildGraph}
                            disabled={building}
                            className="px-4 py-3 bg-[#C8A288] text-white rounded-xl font-bold hover:bg-[#B08B72] transition-colors disabled:opacity-50 flex items-center gap-2 whitespace-nowrap flex-shrink-0"
                        >
                            {building ? (
                                <>
                                    <Loader2 className="h-5 w-5 animate-spin" />
                                    Synthesizing...
                                </>
                            ) : (
                                <>
                                    <Brain className="h-5 w-5" />
                                    Regenerate Path
                                </>
                            )}
                        </button>
                    </div>
                </div>

                {/* Learning Path Content */}
                {!learningPath?.learning_path?.length ? (
                    <div className="bg-[#FDF6F0] rounded-2xl border border-[#E6D5CC] p-8 text-center">
                        <Sparkles className="h-12 w-12 text-[#C8A288] mx-auto mb-4" />
                        <h3 className="text-xl font-bold text-[#4A3B32] mb-2">No Learning Path Yet</h3>
                        <p className="text-[#8a6a5c] mb-6 max-w-md mx-auto">
                            Click "Generate Path" to create an AI-powered learning sequence based on topic dependencies.
                        </p>
                        <div className="flex items-center justify-center gap-2 text-sm text-[#8a6a5c]">
                            <BookOpen className="h-4 w-4" />
                            <span>{availableTopics?.length || 0} topics available</span>
                        </div>
                    </div>
                ) : (
                    <div className="space-y-4">
                        {/* Legend */}
                        <div className="flex flex-wrap gap-4 text-xs font-medium mb-4">
                            <div className="flex items-center gap-1.5">
                                <Play className="h-3 w-3 text-blue-500" />
                                <span className="text-blue-700">Ready</span>
                            </div>
                            <div className="flex items-center gap-1.5">
                                <div className="h-3 w-3 rounded-full bg-yellow-400"></div>
                                <span className="text-yellow-700">In Progress</span>
                            </div>
                            <div className="flex items-center gap-1.5">
                                <CheckCircle className="h-3 w-3 text-green-500" />
                                <span className="text-green-700">Completed</span>
                            </div>
                        </div>

                        {/* Path Items */}
                        {learningPath.learning_path.map((item, idx) => {
                            const status = getTopicStatus(item.topic);
                            const perf = performance[item.topic];
                            const isLast = idx === learningPath.learning_path.length - 1;
                            const isExpanded = expandedTopic === idx;
                            const docsWithTopic = findDocumentsForTopic(item.topic);
                            const docsInContext = getDocsInContext(item.topic);
                            
                            return (
                                <div key={idx} className="relative">
                                    {/* Connector Line */}
                                    {!isLast && (
                                        <div className={`absolute left-6 top-16 w-0.5 h-8 ${
                                            status.status === 'completed' ? 'bg-green-300' : 'bg-[#E6D5CC]'
                                        }`}></div>
                                    )}
                                    
                                    {/* Topic Card */}
                                    <div 
                                        className={`bg-white rounded-xl border-2 transition-all ${
                                            isExpanded ? 'border-[#C8A288] shadow-lg ring-2 ring-[#C8A288]/20' :
                                            status.status === 'completed' ? 'border-green-200 bg-green-50/50' :
                                            status.status === 'in_progress' ? 'border-yellow-200 bg-yellow-50/50' :
                                            'border-[#E6D5CC] hover:border-[#C8A288]'
                                        }`}
                                    >
                                        {/* Main Card Content */}
                                        <div 
                                            className="p-4 cursor-pointer"
                                            onClick={() => setExpandedTopic(isExpanded ? null : idx)}
                                        >
                                            <div className="flex items-start gap-4">
                                                {/* Order Badge */}
                                                <div className={`h-12 w-12 rounded-full flex items-center justify-center font-bold text-lg flex-shrink-0 ${
                                                    status.status === 'completed' ? 'bg-green-500 text-white' :
                                                    status.status === 'in_progress' ? 'bg-yellow-400 text-white' :
                                                    'bg-blue-500 text-white'
                                                }`}>
                                                    {status.status === 'completed' ? (
                                                        <CheckCircle className="h-6 w-6" />
                                                    ) : (
                                                        item.order
                                                    )}
                                                </div>
                                                
                                                {/* Content */}
                                                <div className="flex-1 min-w-0">
                                                    <div className="flex items-start justify-between gap-2">
                                                        <h4 className="font-bold text-lg text-[#4A3B32]">{item.topic}</h4>
                                                        <div className="flex items-center gap-2">
                                                            {/* Context indicator */}
                                                            {docsWithTopic.length > 0 && (
                                                                <span className={`text-xs px-2 py-0.5 rounded-full ${
                                                                    docsInContext > 0 
                                                                        ? 'bg-blue-100 text-blue-700' 
                                                                        : 'bg-gray-100 text-gray-500'
                                                                }`}>
                                                                    {docsInContext}/{docsWithTopic.length} docs
                                                                </span>
                                                            )}
                                                            <span className={`text-xs font-bold px-2 py-1 rounded-full whitespace-nowrap ${
                                                                status.status === 'completed' ? 'bg-green-100 text-green-700' :
                                                                status.status === 'in_progress' ? 'bg-yellow-100 text-yellow-700' :
                                                                'bg-blue-100 text-blue-700'
                                                            }`}>
                                                                {status.label}
                                                            </span>
                                                        </div>
                                                    </div>
                                                    
                                                    {/* Performance Stats */}
                                                    {perf && perf.attempts > 0 && (
                                                        <div className="flex items-center gap-4 mt-3 text-sm">
                                                            <span className="text-[#4A3B32]">
                                                                <span className="font-bold">{Math.round(perf.accuracy)}%</span> accuracy
                                                            </span>
                                                            <span className="text-green-600">{perf.correct} correct</span>
                                                            <span className="text-red-500">{perf.wrong} wrong</span>
                                                        </div>
                                                    )}
                                                    
                                                    {/* Click to expand hint */}
                                                    {!isExpanded && status.status !== 'completed' && (
                                                        <div className="flex items-center gap-2 mt-3 text-sm text-[#C8A288] font-medium">
                                                            <Play className="h-4 w-4" />
                                                            <span>Click to see options</span>
                                                        </div>
                                                    )}
                                                    
                                                    {status.status === 'completed' && (
                                                        <div className="flex items-center gap-2 mt-3 text-sm text-green-600 font-medium">
                                                            <Trophy className="h-4 w-4" />
                                                            <span>Topic mastered!</span>
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                        </div>
                                        
                                        {/* Expanded Actions Section -- Study Hub */}
                                        {isExpanded && (() => {
                                            const isFirstUncompleted = learningPath.learning_path.findIndex(t => getTopicStatus(t.topic).status !== 'completed') === idx;
                                            
                                            return (
                                            <div className="px-4 pb-4 pt-2 border-t border-[#E6D5CC] mt-2">
                                                <div className="bg-[#FDF6F0] rounded-xl p-4 shadow-inner">
                                                    
                                                    {isFirstUncompleted ? (
                                                        <div className="bg-white rounded-xl p-5 mb-5 border-2 border-[#C8A288] shadow-md relative overflow-hidden">
                                                            <div className="absolute top-0 right-0 w-24 h-24 bg-gradient-to-br from-[#FDF6F0] to-[#E6D5CC] rounded-bl-full -z-10 opacity-50"></div>
                                                            <h5 className="font-black text-[#C8A288] text-[10px] uppercase tracking-[0.2em] mb-3 flex items-center gap-1.5">
                                                                <Target className="h-3 w-3" />
                                                                Next Step in Your Learning Path
                                                            </h5>
                                                            <h3 className="text-xl font-black text-[#4A3B32] mb-3">{item.topic}</h3>
                                                            
                                                            <div className="flex gap-6 text-sm mt-3 mb-4">
                                                                <div className="flex flex-col"><span className="text-[10px] uppercase font-bold text-[#8a6a5c]">Difficulty</span> <span className="font-bold text-[#4A3B32]">Dynamic</span></div>
                                                                <div className="flex flex-col"><span className="text-[10px] uppercase font-bold text-[#8a6a5c]">Study time</span> <span className="font-bold text-[#4A3B32]">~20 mins</span></div>
                                                            </div>
                                                            
                                                            {perf && perf.attempts > 0 && (
                                                            <div className="bg-red-50 text-red-800 p-3 rounded-lg text-sm border border-red-100 flex gap-3 items-start mt-2">
                                                                <AlertTriangle className="h-5 w-5 shrink-0 mt-0.5 text-red-500" />
                                                                <div>
                                                                    <span className="font-black block mb-0.5 text-xs uppercase tracking-wider text-red-900">Why learn this now?</span>
                                                                    <span className="font-medium text-red-700">{getStableHumor(item.topic)}</span>
                                                                </div>
                                                            </div>
                                                            )}
                                                        </div>
                                                    ) : (
                                                        <h5 className="font-bold text-[#4A3B32] mb-4 flex items-center gap-2">
                                                            <Play className="h-4 w-4 text-[#C8A288]" />
                                                            Study Hub: {item.topic}
                                                        </h5>
                                                    )}
                                                    
                                                    {/* Context Selection */}
                                                    {docsWithTopic.length > 0 && docsInContext < docsWithTopic.length && (
                                                        <div className="mb-4 p-3 bg-white rounded-lg border border-[#E6D5CC]">
                                                            <div className="flex items-center justify-between">
                                                                <div className="text-sm text-[#8a6a5c]">
                                                                    <span className="font-medium">{docsWithTopic.length - docsInContext}</span> document(s) with this topic not in context
                                                                </div>
                                                                <button
                                                                    onClick={(e) => {
                                                                        e.stopPropagation();
                                                                        handleAddToContext(item.topic);
                                                                    }}
                                                                    className="px-3 py-1.5 bg-blue-100 text-blue-700 rounded-lg text-sm font-bold hover:bg-blue-200 transition-colors flex items-center gap-1"
                                                                >
                                                                    <Plus className="h-3 w-3" />
                                                                    Add to Context
                                                                </button>
                                                            </div>
                                                        </div>
                                                    )}

                                                    {/* LEARN Section */}
                                                    <div className="mb-4">
                                                        <p className="text-[10px] font-bold text-[#8a6a5c] uppercase tracking-wider mb-2 flex items-center gap-1.5">
                                                            <BookOpen className="h-3 w-3" />
                                                            Learn
                                                        </p>
                                                        <div className="grid grid-cols-2 gap-2">
                                                            <button
                                                                onClick={(e) => { e.stopPropagation(); handleGenerateNotes(idx); }}
                                                                className="p-3 bg-white border border-[#E6D5CC] rounded-xl hover:border-emerald-400 hover:bg-emerald-50/50 transition-all flex items-center gap-3 group shadow-sm"
                                                            >
                                                                <div className="h-10 w-10 bg-emerald-100 rounded-lg flex items-center justify-center shrink-0 group-hover:scale-105 transition-transform">
                                                                    <FileText className="h-5 w-5 text-emerald-600" />
                                                                </div>
                                                                <div className="text-left">
                                                                    <div className="font-bold text-sm text-[#4A3B32]">Notes</div>
                                                                    <div className="text-[10px] text-[#8a6a5c]">Generate readables</div>
                                                                </div>
                                                            </button>

                                                            <button
                                                                onClick={(e) => { e.stopPropagation(); handleOpenTutor(idx); }}
                                                                className="p-3 bg-white border border-[#E6D5CC] rounded-xl hover:border-blue-400 hover:bg-blue-50/50 transition-all flex items-center gap-3 group shadow-sm"
                                                            >
                                                                <div className="h-10 w-10 bg-blue-100 rounded-lg flex items-center justify-center shrink-0 group-hover:scale-105 transition-transform">
                                                                    <MessageSquare className="h-5 w-5 text-blue-600" />
                                                                </div>
                                                                <div className="text-left">
                                                                    <div className="font-bold text-sm text-[#4A3B32]">AI Tutor</div>
                                                                    <div className="text-[10px] text-[#8a6a5c]">Chat & Ask</div>
                                                                </div>
                                                            </button>
                                                        </div>
                                                    </div>

                                                    {/* EXPLORE Section */}
                                                    <div className="mb-4">
                                                        <p className="text-[10px] font-bold text-[#8a6a5c] uppercase tracking-wider mb-2 flex items-center gap-1.5">
                                                            <GitBranch className="h-3 w-3" />
                                                            Explore
                                                        </p>
                                                        <div className="grid grid-cols-2 gap-2">
                                                            {onOpenMindmap && (
                                                                <button
                                                                    onClick={(e) => { e.stopPropagation(); handleOpenMindmap(idx); }}
                                                                    className="p-3 bg-white border border-[#E6D5CC] rounded-xl hover:border-indigo-400 hover:bg-indigo-50/50 transition-all flex items-center gap-3 group shadow-sm"
                                                                >
                                                                    <div className="h-10 w-10 bg-indigo-100 rounded-lg flex items-center justify-center shrink-0 group-hover:scale-105 transition-transform">
                                                                        <GitBranch className="h-5 w-5 text-indigo-600" />
                                                                    </div>
                                                                    <div className="text-left flex-1">
                                                                        <div className="font-bold text-sm text-[#4A3B32]">Mindmap</div>
                                                                        <div className="text-[10px] text-[#8a6a5c]">Visualize concepts visually</div>
                                                                    </div>
                                                                </button>
                                                            )}
                                                            
                                                            {onOpenKnowledgeGraph && (
                                                                <button
                                                                    onClick={(e) => { e.stopPropagation(); onOpenKnowledgeGraph(); }}
                                                                    className="p-3 bg-white border border-[#E6D5CC] rounded-xl hover:border-emerald-400 hover:bg-emerald-50/50 transition-all flex items-center gap-3 group shadow-sm"
                                                                >
                                                                    <div className="h-10 w-10 bg-emerald-100 rounded-lg flex items-center justify-center shrink-0 group-hover:scale-105 transition-transform">
                                                                        <Network className="h-5 w-5 text-emerald-600" />
                                                                    </div>
                                                                    <div className="text-left flex-1">
                                                                        <div className="font-bold text-sm text-[#4A3B32]">Knowledge Graph</div>
                                                                        <div className="text-[10px] text-[#8a6a5c]">Explore relation paths</div>
                                                                    </div>
                                                                </button>
                                                            )}
                                                        </div>
                                                    </div>

                                                    {/* PRACTICE Section */}
                                                    <div className="mb-4">
                                                        <p className="text-[10px] font-bold text-[#8a6a5c] uppercase tracking-wider mb-2 flex items-center gap-1.5">
                                                            <Layers className="h-3 w-3" />
                                                            Practice
                                                        </p>
                                                        <div className="grid grid-cols-2 gap-2">
                                                            <button
                                                                onClick={(e) => { e.stopPropagation(); handleStartQA(idx); }}
                                                                className="p-3 bg-white border border-[#E6D5CC] rounded-xl hover:border-amber-400 hover:bg-amber-50/50 transition-all flex items-center gap-3 group shadow-sm"
                                                            >
                                                                <div className="h-10 w-10 bg-amber-100 rounded-lg flex items-center justify-center shrink-0 group-hover:scale-105 transition-transform">
                                                                    <HelpCircle className="h-5 w-5 text-amber-600" />
                                                                </div>
                                                                <div className="text-left">
                                                                    <div className="font-bold text-sm text-[#4A3B32]">Q&A</div>
                                                                    <div className="text-[10px] text-[#8a6a5c]">Direct questions</div>
                                                                </div>
                                                            </button>

                                                            {onOpenFlashcards && (
                                                                <button
                                                                    onClick={(e) => { e.stopPropagation(); handleOpenFlashcards(idx); }}
                                                                    className="p-3 bg-white border border-[#E6D5CC] rounded-xl hover:border-orange-400 hover:bg-orange-50/50 transition-all flex items-center gap-3 group shadow-sm"
                                                                >
                                                                    <div className="h-10 w-10 bg-orange-100 rounded-lg flex items-center justify-center shrink-0 group-hover:scale-105 transition-transform">
                                                                        <Layers className="h-5 w-5 text-orange-600" />
                                                                    </div>
                                                                    <div className="text-left">
                                                                        <div className="font-bold text-sm text-[#4A3B32]">Flashcards</div>
                                                                        <div className="text-[10px] text-[#8a6a5c]">Spaced study</div>
                                                                    </div>
                                                                </button>
                                                            )}
                                                        </div>
                                                    </div>
                                                    
                                                    {/* TEST Section */}
                                                    <div className="mb-3">
                                                        <p className="text-[10px] font-bold text-[#8a6a5c] uppercase tracking-wider mb-2 flex items-center gap-1.5">
                                                            <Zap className="h-3 w-3" />
                                                            Test
                                                        </p>
                                                        <div className="grid grid-cols-3 gap-2">
                                                            <button
                                                                onClick={(e) => { e.stopPropagation(); handleStartQuiz(idx, 'mcq'); }}
                                                                className="p-3 bg-white border border-[#E6D5CC] rounded-xl hover:border-purple-400 hover:bg-purple-50/50 transition-all flex flex-col items-center justify-center group shadow-sm"
                                                            >
                                                                <CheckSquare className="h-5 w-5 text-purple-600 mb-1 group-hover:scale-110 transition-transform" />
                                                                <span className="font-bold text-[11px] text-[#4A3B32]">MCQ</span>
                                                            </button>
                                                            
                                                            <button
                                                                onClick={(e) => { e.stopPropagation(); handleStartQuiz(idx, 'subjective'); }}
                                                                className="p-3 bg-white border border-[#E6D5CC] rounded-xl hover:border-blue-400 hover:bg-blue-50/50 transition-all flex flex-col items-center justify-center group shadow-sm"
                                                            >
                                                                <FileText className="h-5 w-5 text-blue-600 mb-1 group-hover:scale-110 transition-transform" />
                                                                <span className="font-bold text-[11px] text-[#4A3B32]">Subjective</span>
                                                            </button>
                                                            
                                                            <button
                                                                onClick={(e) => { e.stopPropagation(); handleStartQuiz(idx, 'both'); }}
                                                                className="p-3 bg-gradient-to-br from-[#C8A288] to-[#A08072] text-white border-2 border-transparent rounded-xl hover:shadow-lg transition-all flex flex-col items-center justify-center group"
                                                            >
                                                                <Brain className="h-5 w-5 mb-1 group-hover:scale-110 transition-transform" />
                                                                <span className="font-bold text-[11px]">Full Quiz</span>
                                                            </button>
                                                        </div>
                                                    </div>
                                                    </div>
                                            </div>
                                            );
                                        })()}
                                    </div>
                                    
                                    {/* Arrow connector */}
                                    {!isLast && (
                                        <div className="flex justify-center py-2">
                                            <ArrowRight className={`h-5 w-5 rotate-90 ${
                                                status.status === 'completed' ? 'text-green-400' : 'text-[#C8A288]'
                                            }`} />
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                        
                        {/* All Complete Banner */}
                        {calculateProgress() === 100 && (
                            <div className="bg-gradient-to-r from-green-500 to-emerald-500 text-white rounded-2xl p-8 text-center animate-in fade-in zoom-in">
                                <Trophy className="h-16 w-16 mx-auto mb-4" />
                                <h3 className="text-2xl font-bold mb-2">Congratulations!</h3>
                                <p className="opacity-90">You've mastered all topics in this learning path!</p>
                            </div>
                        )}
                    </div>
                )}

                {/* Help Text */}
                <div className="mt-8 p-4 bg-[#FDF6F0] rounded-xl border border-[#E6D5CC] text-sm text-[#8a6a5c]">
                    <div className="flex gap-3">
                        <AlertTriangle className="h-5 w-5 text-[#C8A288] flex-shrink-0 mt-0.5" />
                        <div>
                            <p className="font-bold text-[#4A3B32] mb-1">How It Works</p>
                            <ul className="space-y-1">
                                <li>1. Click on any topic to open the Study Hub</li>
                                <li>2. Use <strong>Learn & Review</strong> tools: Notes, Q&A, AI Tutor</li>
                                <li>3. When ready, <strong>Test Your Knowledge</strong> with MCQ, Subjective, or Full Quiz</li>
                                <li>4. Track your progress as you complete each topic</li>
                                <li>5. Use "Add to Context" to select relevant documents</li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default LearningPathView;
