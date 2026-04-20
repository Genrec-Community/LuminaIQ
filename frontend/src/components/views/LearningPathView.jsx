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
import { useSettings } from '../../context/SettingsContext';
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
    const { settings } = useSettings();
    const isDark = settings?.darkMode ?? false;

    // Dark-mode colour tokens
    const card  = isDark ? '#252018'  : '#FFFFFF';
    const cardBorder = isDark ? '#3d3028' : '#E6D5CC';
    const cardBg2 = isDark ? '#1e1a16' : '#FDF6F0';
    const bodyText = isDark ? '#e8d8c0' : '#4A3B32';
    const mutedText = isDark ? '#b09878' : '#8a6a5c';

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
        <div className="h-full flex flex-col" style={{ color: bodyText }}>
            <div className="flex-1 overflow-y-auto custom-scrollbar p-4 md:p-8 max-w-4xl mx-auto w-full">
                {/* Header */}
                <div className="text-center mb-8">
                    <div className="inline-flex items-center justify-center p-4 rounded-2xl shadow-sm border mb-4"
                        style={{ background: card, borderColor: cardBorder }}>
                        <Target className="h-8 w-8 text-[#C8A288]" />
                    </div>
                    <h2 className="text-2xl font-bold mb-2" style={{ color: bodyText }}>Learning Path</h2>
                    <p style={{ color: mutedText }}>Your personalized study sequence</p>
                </div>

                {/* Progress Bar */}
                {learningPath?.learning_path?.length > 0 && (
                    <div className="rounded-xl border p-5 mb-6" style={{ background: card, borderColor: cardBorder }}>
                        <div className="flex items-center justify-between mb-3">
                            <span className="text-sm font-bold" style={{ color: bodyText }}>Overall Progress</span>
                            <span className="text-sm font-black tabular-nums" style={{ color: '#C8A288', textShadow: isDark ? '0 0 12px rgba(200,162,136,0.6)' : 'none' }}>
                                {calculateProgress()}%
                            </span>
                        </div>
                        {/* Track */}
                        <div className="h-4 rounded-full overflow-hidden" style={{ background: isDark ? '#2e2318' : '#E6D5CC' }}>
                            <div
                                className="h-full rounded-full transition-all duration-700 ease-out"
                                style={{
                                    width: `${calculateProgress()}%`,
                                    background: calculateProgress() === 0
                                        ? 'transparent'
                                        : isDark
                                            ? 'linear-gradient(90deg, #a06820 0%, #C8A288 60%, #e8c878 100%)'
                                            : 'linear-gradient(90deg, #C8A288 0%, #a8d060 100%)',
                                    boxShadow: isDark && calculateProgress() > 0
                                        ? '0 0 12px rgba(200,162,136,0.55), 0 0 4px rgba(200,162,136,0.35)'
                                        : 'none'
                                }}
                            />
                        </div>
                        <div className="mt-2.5 flex items-center gap-1.5">
                            <span className="text-xs font-semibold" style={{ color: isDark ? '#C8A288' : '#8a6a5c' }}>
                                {completedTopics.size}
                            </span>
                            <span className="text-xs" style={{ color: mutedText }}>of</span>
                            <span className="text-xs font-semibold" style={{ color: isDark ? '#C8A288' : '#8a6a5c' }}>
                                {learningPath.learning_path.length}
                            </span>
                            <span className="text-xs" style={{ color: mutedText }}>topics completed</span>
                        </div>
                    </div>
                )}

                {/* Document Selector & Build Button */}
                <div className="rounded-xl border p-4 mb-6 overflow-hidden" style={{ background: card, borderColor: cardBorder }}>
                    <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
                        <div className="w-full sm:w-auto sm:max-w-[60%]">
                            <label className="block text-sm font-bold mb-1" style={{ color: bodyText }}>Generate Path For</label>
                            <select
                                value={selectedDoc}
                                onChange={(e) => setSelectedDoc(e.target.value)}
                                className="w-full sm:w-auto px-4 py-2 border rounded-lg focus:ring-2 focus:ring-[#C8A288] font-medium max-w-full truncate"
                                style={{ background: cardBg2, borderColor: cardBorder, color: bodyText, maxWidth: '100%' }}
                            >
                                <option value="all">All Documents ({availableTopics?.length || 0} topics)</option>
                                {Object.entries(documentTopics || {}).map(([docId, topics]) => {
                                    const topicCount = topics?.length || 0;
                                    if (topicCount === 0) return null;
                                    const docName = getDocName(docId);
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
                            className="px-5 py-3 rounded-xl font-bold disabled:opacity-50 flex items-center gap-2 whitespace-nowrap flex-shrink-0 transition-all duration-200"
                            style={isDark ? {
                                background: 'linear-gradient(135deg, #C8A288 0%, #a8824a 100%)',
                                color: '#fff',
                                boxShadow: '0 4px 14px rgba(200,162,136,0.35), 0 0 0 1px rgba(200,162,136,0.25)'
                            } : { background: '#C8A288', color: '#fff' }}
                        >
                            {building ? (
                                <><Loader2 className="h-5 w-5 animate-spin" />Synthesizing...</>
                            ) : (
                                <><Brain className="h-5 w-5" />Regenerate Path</>
                            )}
                        </button>
                    </div>
                </div>

                {/* Learning Path Content */}
                {!learningPath?.learning_path?.length ? (
                    <div className="rounded-2xl border p-8 text-center"
                        style={{ background: cardBg2, borderColor: cardBorder }}>
                        <Sparkles className="h-12 w-12 text-[#C8A288] mx-auto mb-4" />
                        <h3 className="text-xl font-bold mb-2" style={{ color: bodyText }}>No Learning Path Yet</h3>
                        <p className="mb-6 max-w-md mx-auto" style={{ color: mutedText }}>
                            Click "Generate Path" to create an AI-powered learning sequence based on topic dependencies.
                        </p>
                        <div className="flex items-center justify-center gap-2 text-sm" style={{ color: mutedText }}>
                            <BookOpen className="h-4 w-4" />
                            <span>{availableTopics?.length || 0} topics available</span>
                        </div>
                    </div>
                ) : (
                    <div className="space-y-4">
                        {/* Legend */}
                        <div className="flex flex-wrap gap-4 text-xs font-medium mb-4">
                            <div className="flex items-center gap-1.5">
                                <Play className="h-3 w-3 text-[#C8A288]" />
                                <span style={{ color: mutedText }}>Ready</span>
                            </div>
                            <div className="flex items-center gap-1.5">
                                <div className="h-3 w-3 rounded-full bg-[#d4974a]"></div>
                                <span style={{ color: isDark ? '#c8922a' : '#7a5e30' }}>In Progress</span>
                            </div>
                            <div className="flex items-center gap-1.5">
                                <CheckCircle className="h-3 w-3 text-[#5a8a5a]" />
                                <span style={{ color: isDark ? '#5aaa5a' : '#3d6b3d' }}>Completed</span>
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
                                            status.status === 'completed'
                                                ? isDark ? 'bg-green-700' : 'bg-green-300'
                                                : isDark ? 'bg-[#4a3020]' : 'bg-[#E6D5CC]'
                                        }`}></div>
                                    )}
                                    
                                    {/* Topic Card */}
                                    <div
                                        className="rounded-xl border-2 transition-all"
                                        style={isExpanded ? {
                                            borderColor: '#C8A288',
                                            background: isDark ? '#2a1e12' : '#fff',
                                            boxShadow: isDark ? '0 0 0 2px rgba(200,162,136,0.20), 0 8px 24px rgba(0,0,0,0.35)' : '0 4px 16px rgba(200,162,136,0.15)'
                                        } : status.status === 'completed' ? {
                                            borderColor: isDark ? '#2a5a3a' : '#bbf7d0',
                                            background: isDark ? '#182418' : 'rgba(240,253,244,0.5)'
                                        } : status.status === 'in_progress' ? {
                                            borderColor: isDark ? '#7a4a10' : '#fde68a',
                                            background: isDark ? '#241808' : 'rgba(255,251,235,0.5)'
                                        } : {
                                            borderColor: isDark ? '#3d3028' : '#E6D5CC',
                                            background: isDark ? '#252018' : '#fff'
                                        }}
                                    >
                                        {/* Main Card Content */}
                                        <div 
                                            className="p-4 cursor-pointer"
                                            onClick={() => setExpandedTopic(isExpanded ? null : idx)}
                                        >
                                            <div className="flex items-start gap-4">
                                                {/* Order Badge — outlined premium style */}
                                                <div
                                                    className="h-12 w-12 rounded-full flex items-center justify-center font-black text-base flex-shrink-0"
                                                    style={status.status === 'completed'
                                                        ? { background: isDark ? '#2a5a3a' : 'rgba(61,122,74,0.12)', color: isDark ? '#6adc8a' : '#2e6b3e', border: `2px solid ${isDark ? '#3a7a4a' : '#3d7a4a'}` }
                                                        : status.status === 'in_progress'
                                                            ? { background: isDark ? '#3a2008' : 'rgba(200,131,42,0.10)', color: isDark ? '#e8a040' : '#8a5210', border: `2px solid ${isDark ? '#c8832a' : '#c8832a'}` }
                                                            : { background: isDark ? '#2e1f10' : 'rgba(200,162,136,0.12)', color: isDark ? '#d4aa82' : '#7a5030', border: `2px solid ${isDark ? '#5a3820' : '#C8A288'}` }
                                                    }
                                                >
                                                    {status.status === 'completed' ? (
                                                        <CheckCircle className="h-6 w-6" />
                                                    ) : (
                                                        item.order
                                                    )}
                                                </div>
                                                
                                                {/* Content */}
                                                <div className="flex-1 min-w-0">
                                                    <div className="flex items-start justify-between gap-2">
                                                        <h4 className="font-bold text-lg" style={{ color: bodyText }}>{item.topic}</h4>
                                                        <div className="flex items-center gap-2">
                                                            {/* Context indicator — warm gray pill, not blue */}
                                                            {docsWithTopic.length > 0 && (
                                                                <span className={`text-xs px-2 py-0.5 rounded-full`}
                                                                    style={docsInContext > 0
                                                                        ? { background: isDark ? '#3a2a1a' : '#e8ddd5', color: isDark ? '#c8a060' : '#6b5044' }
                                                                        : { background: isDark ? '#2e2820' : '#ece8e5', color: isDark ? '#a09080' : '#8a7870' }
                                                                    }>
                                                                    {docsInContext}/{docsWithTopic.length} docs
                                                                </span>
                                                            )}
                                                            {/* Status badge — warm palette only */}
                                                            <span className={`text-xs font-bold px-2 py-1 rounded-full whitespace-nowrap ${
                                                                status.status === 'completed' ? 'bg-[#d4edda] text-[#2e6b3e]' :
                                                                status.status === 'in_progress' ? 'bg-[#fde8c8] text-[#7a4f1a]' :
                                                                'bg-[#ede3da] text-[#6b4c38]'
                                                            }`}>
                                                                {status.label}
                                                            </span>
                                                        </div>
                                                    </div>
                                                    
                                                    {/* Performance Stats */}
                                                    {perf && perf.attempts > 0 && (
                                                        <div className="flex items-center gap-4 mt-3 text-sm">
                                                            <span style={{ color: bodyText }}>
                                                                <span className="font-bold">{Math.round(perf.accuracy)}%</span> accuracy
                                                            </span>
                                                            <span style={{ color: isDark ? '#5aaa6a' : '#16a34a' }}>{perf.correct} correct</span>
                                                            <span style={{ color: isDark ? '#e87060' : '#dc2626' }}>{perf.wrong} wrong</span>
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
                                                            
                                                            <div className="bg-[#fef3e2] text-[#7a4a1a] p-3 rounded-xl text-sm border-l-4 border-[#c49a6c] flex gap-3 items-start mt-2">
                                                                <Sparkles className="h-5 w-5 shrink-0 mt-0.5 text-[#c49a6c]" />
                                                                <div>
                                                                    <span className="font-black block mb-0.5 text-xs uppercase tracking-wider text-[#5a3010]">Why learn this now?</span>
                                                                    <span className="font-medium text-[#7a4a1a]">{getStableHumor(item.topic)}</span>
                                                                </div>
                                                            </div>
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
                                                                    className="px-3 py-1.5 bg-[#f0e6d8] text-[#7a4a1a] rounded-lg text-sm font-bold hover:bg-[#e6d5c0] transition-colors flex items-center gap-1"
                                                                >
                                                                    <Plus className="h-3 w-3" />
                                                                    Add to Context
                                                                </button>
                                                            </div>
                                                        </div>
                                                    )}

                                                    {/* LEARN — warm tan family */}
                                                    <div className="mb-4">
                                                        <p className="text-[10px] font-bold text-[#8a6a5c] uppercase tracking-wider mb-2 flex items-center gap-1.5">
                                                            <BookOpen className="h-3 w-3" />
                                                            Learn
                                                        </p>
                                                        <div className="grid grid-cols-2 gap-2">
                                                            <button
                                                                onClick={(e) => { e.stopPropagation(); handleGenerateNotes(idx); }}
                                                                className="p-3 bg-white border border-[#E6D5CC] rounded-xl hover:border-[#C8A288] hover:bg-[#FDF6F0] transition-all flex items-center gap-3 group shadow-sm"
                                                            >
                                                                <div className="h-10 w-10 bg-[#f5ede3] rounded-lg flex items-center justify-center shrink-0 group-hover:scale-105 transition-transform">
                                                                    <FileText className="h-5 w-5 text-[#9b7055]" />
                                                                </div>
                                                                <div className="text-left">
                                                                    <div className="font-bold text-sm text-[#4A3B32]">Notes</div>
                                                                    <div className="text-[10px] text-[#8a6a5c]">Generate readables</div>
                                                                </div>
                                                            </button>

                                                            <button
                                                                onClick={(e) => { e.stopPropagation(); handleOpenTutor(idx); }}
                                                                className="p-3 bg-white border border-[#E6D5CC] rounded-xl hover:border-[#C8A288] hover:bg-[#FDF6F0] transition-all flex items-center gap-3 group shadow-sm"
                                                            >
                                                                <div className="h-10 w-10 bg-[#f5ede3] rounded-lg flex items-center justify-center shrink-0 group-hover:scale-105 transition-transform">
                                                                    <MessageSquare className="h-5 w-5 text-[#9b7055]" />
                                                                </div>
                                                                <div className="text-left">
                                                                    <div className="font-bold text-sm text-[#4A3B32]">AI Tutor</div>
                                                                    <div className="text-[10px] text-[#8a6a5c]">Chat &amp; Ask</div>
                                                                </div>
                                                            </button>
                                                        </div>
                                                    </div>

                                                    {/* EXPLORE — muted warm gray-brown family */}
                                                    <div className="mb-4">
                                                        <p className="text-[10px] font-bold text-[#8a6a5c] uppercase tracking-wider mb-2 flex items-center gap-1.5">
                                                            <GitBranch className="h-3 w-3" />
                                                            Explore
                                                        </p>
                                                        <div className="grid grid-cols-2 gap-2">
                                                            {onOpenMindmap && (
                                                                <button
                                                                    onClick={(e) => { e.stopPropagation(); handleOpenMindmap(idx); }}
                                                                    className="p-3 bg-white border border-[#E6D5CC] rounded-xl hover:border-[#b8a090] hover:bg-[#f7f0e8] transition-all flex items-center gap-3 group shadow-sm"
                                                                >
                                                                    <div className="h-10 w-10 bg-[#ede5dc] rounded-lg flex items-center justify-center shrink-0 group-hover:scale-105 transition-transform">
                                                                        <GitBranch className="h-5 w-5 text-[#7a6050]" />
                                                                    </div>
                                                                    <div className="text-left flex-1">
                                                                        <div className="font-bold text-sm text-[#4A3B32]">Mindmap</div>
                                                                        <div className="text-[10px] text-[#8a6a5c]">Visualize concepts</div>
                                                                    </div>
                                                                </button>
                                                            )}
                                                            
                                                            {onOpenKnowledgeGraph && (
                                                                <button
                                                                    onClick={(e) => { e.stopPropagation(); onOpenKnowledgeGraph(); }}
                                                                    className="p-3 bg-white border border-[#E6D5CC] rounded-xl hover:border-[#b8a090] hover:bg-[#f7f0e8] transition-all flex items-center gap-3 group shadow-sm"
                                                                >
                                                                    <div className="h-10 w-10 bg-[#ede5dc] rounded-lg flex items-center justify-center shrink-0 group-hover:scale-105 transition-transform">
                                                                        <Network className="h-5 w-5 text-[#7a6050]" />
                                                                    </div>
                                                                    <div className="text-left flex-1">
                                                                        <div className="font-bold text-sm text-[#4A3B32]">Knowledge Graph</div>
                                                                        <div className="text-[10px] text-[#8a6a5c]">Explore relation paths</div>
                                                                    </div>
                                                                </button>
                                                            )}
                                                        </div>
                                                    </div>

                                                    {/* PRACTICE — golden amber family */}
                                                    <div className="mb-4">
                                                        <p className="text-[10px] font-bold text-[#8a6a5c] uppercase tracking-wider mb-2 flex items-center gap-1.5">
                                                            <Layers className="h-3 w-3" />
                                                            Practice
                                                        </p>
                                                        <div className="grid grid-cols-2 gap-2">
                                                            <button
                                                                onClick={(e) => { e.stopPropagation(); handleStartQA(idx); }}
                                                                className="p-3 bg-white border border-[#E6D5CC] rounded-xl hover:border-[#c49a6c] hover:bg-[#fdf4e8] transition-all flex items-center gap-3 group shadow-sm"
                                                            >
                                                                <div className="h-10 w-10 bg-[#faebd6] rounded-lg flex items-center justify-center shrink-0 group-hover:scale-105 transition-transform">
                                                                    <HelpCircle className="h-5 w-5 text-[#a06820]" />
                                                                </div>
                                                                <div className="text-left">
                                                                    <div className="font-bold text-sm text-[#4A3B32]">Q&amp;A</div>
                                                                    <div className="text-[10px] text-[#8a6a5c]">Direct questions</div>
                                                                </div>
                                                            </button>

                                                            {onOpenFlashcards && (
                                                                <button
                                                                    onClick={(e) => { e.stopPropagation(); handleOpenFlashcards(idx); }}
                                                                    className="p-3 bg-white border border-[#E6D5CC] rounded-xl hover:border-[#c49a6c] hover:bg-[#fdf4e8] transition-all flex items-center gap-3 group shadow-sm"
                                                                >
                                                                    <div className="h-10 w-10 bg-[#faebd6] rounded-lg flex items-center justify-center shrink-0 group-hover:scale-105 transition-transform">
                                                                        <Layers className="h-5 w-5 text-[#a06820]" />
                                                                    </div>
                                                                    <div className="text-left">
                                                                        <div className="font-bold text-sm text-[#4A3B32]">Flashcards</div>
                                                                        <div className="text-[10px] text-[#8a6a5c]">Spaced study</div>
                                                                    </div>
                                                                </button>
                                                            )}
                                                        </div>
                                                    </div>
                                                    
                                                    {/* TEST — deeper warm tan family */}
                                                    <div className="mb-3">
                                                        <p className="text-[10px] font-bold text-[#8a6a5c] uppercase tracking-wider mb-2 flex items-center gap-1.5">
                                                            <Zap className="h-3 w-3" />
                                                            Test
                                                        </p>
                                                        <div className="grid grid-cols-3 gap-2">
                                                            <button
                                                                onClick={(e) => { e.stopPropagation(); handleStartQuiz(idx, 'mcq'); }}
                                                                className="p-3 bg-white border border-[#E6D5CC] rounded-xl hover:border-[#C8A288] hover:bg-[#FDF6F0] transition-all flex flex-col items-center justify-center group shadow-sm"
                                                            >
                                                                <CheckSquare className="h-5 w-5 text-[#9b7055] mb-1 group-hover:scale-110 transition-transform" />
                                                                <span className="font-bold text-[11px] text-[#4A3B32]">MCQ</span>
                                                            </button>
                                                            
                                                            <button
                                                                onClick={(e) => { e.stopPropagation(); handleStartQuiz(idx, 'subjective'); }}
                                                                className="p-3 bg-white border border-[#E6D5CC] rounded-xl hover:border-[#C8A288] hover:bg-[#FDF6F0] transition-all flex flex-col items-center justify-center group shadow-sm"
                                                            >
                                                                <FileText className="h-5 w-5 text-[#9b7055] mb-1 group-hover:scale-110 transition-transform" />
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
