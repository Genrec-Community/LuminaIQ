import React, { useState, useRef, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
    MessageSquare,
    FileText,
    CheckSquare,
    Upload,
    Send,
    BookOpen,
    Loader2,
    Plus,
    User,
    Settings,
    HelpCircle,
    LogOut,
    X,
    ChevronDown,
    ChevronUp,
    ChevronLeft,
    ChevronRight,
    RefreshCw,
    Trash2,
    Menu,
    Calendar,
    Brain,
    Target,
    Search,
    Timer,
    GraduationCap,
    Bookmark,
    Network,
    BarChart3,
    Trophy,
    Maximize2,
    Minimize2
} from 'lucide-react';
import {
    uploadDocument,
    getDocuments,
    getChatHistory, // Imported
    chatMessage,
    chatMessageStream, // Imported
    generateMCQ,
    submitEvaluation,
    getTopics,
    getProjectSummary,
    generateSubjectiveTest,
    submitSubjectiveTest,
    deleteDocument,
    generateNotes,
    getLearningProgress,
    saveLearningProgress
} from '../api';
import { useToast } from '../context/ToastContext';
import { useSettings } from '../context/SettingsContext';
import { useGamification } from '../context/GamificationContext';
import { recordActivity } from '../utils/studyActivity';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import UploadZone from '../components/UploadZone';

// View Components
import QuizView from '../components/views/QuizView';
import QAView from '../components/views/QAView';
import NotesView from '../components/views/NotesView';
import StudyDashboard from '../components/views/StudyDashboard';
import LearningPathView from '../components/views/LearningPathView';
import AdvancedAnalytics from '../components/views/AdvancedAnalytics';
import ExamPrepMode from '../components/views/ExamPrepMode';
import KnowledgeGraphView from '../components/views/KnowledgeGraphView';
import TopicMindmap from '../components/views/TopicMindmap';
import TopicFlashcards from '../components/views/TopicFlashcards';

// Utility Components
import PomodoroTimer from '../components/PomodoroTimer';
import AITutorChat from '../components/AITutorChat';
import BookmarksPanel from '../components/BookmarksPanel';
import GlobalSearch from '../components/GlobalSearch';
import GamificationPanel from '../components/GamificationPanel';

const ProjectView = () => {
    const { projectId } = useParams();
    const navigate = useNavigate();
    const toast = useToast();
    const { settings } = useSettings();
    const { data: gamificationData } = useGamification();
    const [showGamification, setShowGamification] = useState(false);
    const [activeTab, setActiveTab] = useState(() => {
        return sessionStorage.getItem(`lumina_tab_${projectId}`) || 'chat';
    });
    const [messages, setMessages] = useState([]);

    // Session cache keys
    const chatCacheKey = `lumina_chat_${projectId}`;

    // Persist activeTab to sessionStorage
    useEffect(() => {
        sessionStorage.setItem(`lumina_tab_${projectId}`, activeTab);
        // Dismiss mindmap/flashcard overlays when switching tabs
        setMindmapTopic(null);
        setMindmapDocs([]);
        setFlashcardTopic(null);
        setFlashcardDocs([]);
    }, [activeTab, projectId]);

    // Persist chat messages to sessionStorage
    useEffect(() => {
        if (messages.length > 0) {
            sessionStorage.setItem(chatCacheKey, JSON.stringify(messages));
        }
    }, [messages, chatCacheKey]);
    const [inputMessage, setInputMessage] = useState('');
    const [documents, setDocuments] = useState([]);
    const [selectedDocuments, setSelectedDocuments] = useState([]);
    const [deleteConfirmDoc, setDeleteConfirmDoc] = useState(null);
    const [deletingDocIds, setDeletingDocIds] = useState(new Set());
    const [loading, setLoading] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [showUploadModal, setShowUploadModal] = useState(false);
    const [isProcessingDocs, setIsProcessingDocs] = useState(true);
    const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
    const [isDocsMenuOpen, setIsDocsMenuOpen] = useState(false);
    const [isLeftCollapsed, setIsLeftCollapsed] = useState(false);
    const [isRightCollapsed, setIsRightCollapsed] = useState(false);

    // Derived: force expanded when mobile drawers open
    const leftCollapsed = isLeftCollapsed && !isMobileMenuOpen;
    const rightCollapsed = isRightCollapsed && !isDocsMenuOpen;

    // New Feature States
    const [showSearch, setShowSearch] = useState(false);
    const [showPomodoro, setShowPomodoro] = useState(false);
    const [showAITutor, setShowAITutor] = useState(false);
    const [showBookmarks, setShowBookmarks] = useState(false);
    const [zenMode, setZenMode] = useState(false);
    const [tutorTopic, setTutorTopic] = useState(null);

    // Topics State
    const [availableTopics, setAvailableTopics] = useState([]);
    const [allProjectTopics, setAllProjectTopics] = useState([]);
    const [documentTopics, setDocumentTopics] = useState({});
    
    // Learning Path Integration State
    const [preSelectedTopic, setPreSelectedTopic] = useState(null);
    const [preSelectedQuizMode, setPreSelectedQuizMode] = useState(null);
    const [cameFromPath, setCameFromPath] = useState(false);
    
    // Mindmap & Flashcards State (shown inline, only from learning path)
    const [mindmapTopic, setMindmapTopic] = useState(null);
    const [mindmapDocs, setMindmapDocs] = useState([]);
    const [flashcardTopic, setFlashcardTopic] = useState(null);
    const [flashcardDocs, setFlashcardDocs] = useState([]);
    
    // Learning Progress (persisted in Supabase)
    const [learningProgress, setLearningProgress] = useState(new Set());
    
    // Load learning progress from API
    useEffect(() => {
        const loadProgress = async () => {
            try {
                const data = await getLearningProgress(projectId);
                if (data.completed_topics && data.completed_topics.length > 0) {
                    setLearningProgress(new Set(data.completed_topics));
                }
            } catch (err) {
                console.warn('Failed to load learning progress:', err);
            }
        };
        loadProgress();
    }, [projectId]);
    
    // Quiz/Q&A Active State (hides sidebars during generation/active)
    const [isQuizActive, setIsQuizActive] = useState(false);
    const [isQAActive, setIsQAActive] = useState(false);
    
    // Combined sidebar hidden state
    const isSidebarHidden = isQuizActive || isQAActive || zenMode;

    // File Upload Ref
    const fileInputRef = useRef(null);

    // Add loading state for ProjectView
    const [projectViewLoading, setProjectViewLoading] = useState(true);

    useEffect(() => {
        let intervalId;
        let timeoutId;

        // Helper to check if any document is still processing
        const isAnyDocProcessing = (docs) => {
            if (!docs || docs.length === 0) return false;
            return docs.some(d => 
                d.upload_status === 'pending' || 
                d.upload_status === 'processing' || 
                d.upload_status === 'embedding' ||
                d.upload_status === 'queued'
            );
        };

        const initialLoad = async () => {
            setProjectViewLoading(true); // Start loading animation
            const [docData] = await Promise.all([
                fetchDocuments()
            ]);

            // Restore chat messages from session cache, or start fresh
            const cachedMessages = sessionStorage.getItem(`lumina_chat_${projectId}`);
            if (cachedMessages) {
                try {
                    const parsed = JSON.parse(cachedMessages);
                    if (Array.isArray(parsed) && parsed.length > 0) {
                        setMessages(parsed);
                    } else {
                        setMessages([{ role: 'system', content: 'Ready to chat! Ask me anything about your documents.' }]);
                    }
                } catch {
                    setMessages([{ role: 'system', content: 'Ready to chat! Ask me anything about your documents.' }]);
                }
            } else {
                setMessages([{ role: 'system', content: 'Ready to chat! Ask me anything about your documents.' }]);
            }

            if (docData && docData.documents) {
                const processing = isAnyDocProcessing(docData.documents);
                setIsProcessingDocs(processing);
            } else {
                setIsProcessingDocs(false);
            }
            setProjectViewLoading(false); // End loading animation
        };

        initialLoad(); // Call initial load once

        // Poll every 2 seconds to check document status
        intervalId = setInterval(async () => {
            const data = await fetchDocuments();
            if (data && data.documents) {
                const processing = isAnyDocProcessing(data.documents);
                setIsProcessingDocs(processing);
                
                // Don't stop polling - we need to detect new uploads too
                // Just update the state
            }
        }, 2000); // Reduced to 2 seconds for faster response

        // Timeout to stop polling after 2 minutes and assume processing is done
        timeoutId = setTimeout(() => {
            clearInterval(intervalId);
            setIsProcessingDocs(false);
        }, 120000); // 2 minutes

        return () => {
            clearInterval(intervalId);
            clearTimeout(timeoutId);
        };
    }, [projectId]);

    const fetchDocuments = async () => {
        try {
            const data = await getDocuments(projectId);
            setDocuments(data.documents || []);
            return data;
        } catch (error) {
            console.error("Failed to fetch documents", error);
            return null;
        }
    };

    useEffect(() => {
        if (activeTab === 'quiz' || activeTab === 'qa' || activeTab === 'notes' || activeTab === 'path' || activeTab === 'exam') {
            fetchTopics();
        }
    }, [activeTab, projectId]);

    const fetchTopics = async () => {
        try {
            const data = await getTopics(projectId);
            // Handle new object structure (or fallback for backward compat during dev)
            if (data.all && data.by_doc) {
                setAllProjectTopics(data.all);
                setDocumentTopics(data.by_doc);
                // The useEffect will handle setAvailableTopics
            } else if (Array.isArray(data)) {
                // Fallback if backend rollout lags
                setAvailableTopics(data);
                setAllProjectTopics(data);
            }
        } catch (error) {
            console.error("Failed to fetch topics", error);
        }
    };

    // Filter topics based on selected documents
    useEffect(() => {
        // Only filter if we actually have document-topic mappings
        // This handles the fallback case where API returns just an array (no by_doc mapping)
        const hasMappings = Object.keys(documentTopics).length > 0;

        if (selectedDocuments.length > 0 && hasMappings) {
            const filtered = new Set();
            selectedDocuments.forEach(docId => {
                const docSpecific = documentTopics[docId];
                if (docSpecific && docSpecific.length > 0) {
                    docSpecific.forEach(t => filtered.add(t));
                }
            });
            // If we have selected docs but no topics found for them yet, 
            // filtered set is empty. 
            // Logic: "Only show topics of selected". So show empty (or maybe show all if empty? No, empty is correct for strict filtering).
            setAvailableTopics(Array.from(filtered).sort());
        } else {
            // If nothing selected (Global) OR we don't have mappings, show ALL.
            setAvailableTopics(allProjectTopics);
        }
    }, [selectedDocuments, documentTopics, allProjectTopics]);

    // Default Selection: If only 1 document, select it.
    useEffect(() => {
        if (documents.length === 1 && selectedDocuments.length === 0) {
            // Need to pass array to setSelectedDocuments?
            // Wait, setSelectedDocuments is passed from context or protected route?
            // No, it's not defined in ProjectView props usually.
            // Let's check where selectedDocuments comes from.
            // It's likely state in ProjectView.
            // Lines 70-80 usually define it.
            if (typeof setSelectedDocuments === 'function') {
                setSelectedDocuments([documents[0].id]);
            }
        }
    }, [documents]);

    // Keyboard shortcuts
    useEffect(() => {
        const handleKeyDown = (e) => {
            // Ctrl+K or Cmd+K for search
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                setShowSearch(true);
            }
            // Ctrl+Shift+Z or Cmd+Shift+Z for zen mode toggle
            if ((e.ctrlKey || e.metaKey) && e.shiftKey && (e.key === 'z' || e.key === 'Z')) {
                e.preventDefault();
                setZenMode(prev => !prev);
            }
            // Escape to close modals or exit zen mode
            if (e.key === 'Escape') {
                if (zenMode) { setZenMode(false); return; }
                if (showSearch) setShowSearch(false);
                if (showPomodoro) setShowPomodoro(false);
                if (showAITutor) setShowAITutor(false);
                if (showBookmarks) setShowBookmarks(false);
                if (showGamification) setShowGamification(false);
            }
        };

        document.addEventListener('keydown', handleKeyDown);
        return () => document.removeEventListener('keydown', handleKeyDown);
    }, [showSearch, showPomodoro, showAITutor, showBookmarks, zenMode]);

    const [showSummary, setShowSummary] = useState(false);
    const [summaryContent, setSummaryContent] = useState('');
    const [summaryLoading, setSummaryLoading] = useState(false);

    const toggleSummary = async () => {
        if (!showSummary) {
            // Show the popup immediately with loading state
            setShowSummary(true);
            // Then fetch the summary
            await fetchSummary();
        } else {
            setShowSummary(false);
        }
    };

    const fetchSummary = async () => {
        setSummaryLoading(true);
        // Clear previous content to avoid confusion
        setSummaryContent('');
        try {
            const response = await getProjectSummary(projectId, selectedDocuments);
            setSummaryContent(response.answer);
        } catch (error) {
            console.error("Summary error", error);
            setSummaryContent("Could not retrieve summary. Please try again.");
        } finally {
            setSummaryLoading(false);
        }
    };

    const handleNewSession = () => {
        setMessages([{ role: 'system', content: 'Ready to chat! Ask me anything about your documents.' }]);
        setInputMessage('');
        sessionStorage.removeItem(chatCacheKey);
    };

    const handleSendMessage = async (e) => {
        e.preventDefault();
        if (!inputMessage.trim() || loading) return;

        if (selectedDocuments.length === 0) {
            toast.warning('Please select at least one document from the sidebar to start chatting.');
            return;
        }

        const userMsg = inputMessage;
        // Add user message immediately
        const newMessages = [...messages, { role: 'user', content: userMsg }];
        setMessages(newMessages);
        setInputMessage('');
        setLoading(true);

        // Create a placeholder for the assistant's response
        setMessages(prev => [...prev, { role: 'assistant', content: '', sources: [] }]);

        try {
            const history = newMessages.filter(m => m.role !== 'system').map(m => ({
                role: m.role,
                content: m.content
            }));

            await chatMessageStream(
                projectId,
                userMsg,
                history,
                selectedDocuments,
                (chunkText) => {
                    // Update the last message (assistant's placeholder) with current chunk text
                    setMessages(prev => {
                        const updated = [...prev];
                        const lastMsg = updated[updated.length - 1];
                        if (lastMsg.role === 'assistant') {
                            lastMsg.content = chunkText;
                        }
                        return updated;
                    });
                },
                (finalResult) => {
                    // Final update with sources
                    setMessages(prev => {
                        const updated = [...prev];
                        const lastMsg = updated[updated.length - 1];
                        if (lastMsg.role === 'assistant') {
                            lastMsg.content = finalResult.answer;
                            lastMsg.sources = finalResult.sources;
                        }
                        return updated;
                    });
                    
                    // Track chat activity for heatmap
                    recordActivity(projectId, 'chat');
                    setLoading(false);
                }
            );
        } catch (error) {
            console.error("Chat error", error);
            setMessages(prev => {
                const updated = [...prev];
                const lastMsg = updated[updated.length - 1];
                lastMsg.content = "Sorry, I encountered an error processing your request.";
                return updated;
            });
            setLoading(false);
        }
    };

    const handleFileUpload = async (files) => {
        if (!files || files.length === 0) return;
        setUploading(true);
        try {
            // Upload files in parallel for better performance
            await Promise.all(
                Array.from(files).map(file => uploadDocument(projectId, file))
            );
            await fetchDocuments();
            setShowUploadModal(false);
        } catch (error) {
            console.error("Upload error", error);
            toast.error('Failed to upload document(s)');
        } finally {
            setUploading(false);
        }
    };

    const requestDelete = (doc) => {
        setDeleteConfirmDoc(doc);
    };

    const confirmDelete = async () => {
        if (!deleteConfirmDoc) return;
        const docId = deleteConfirmDoc.id;

        // Add to deleting set
        setDeletingDocIds(prev => new Set(prev).add(docId));
        setDeleteConfirmDoc(null); // Close modal

        try {
            await deleteDocument(projectId, docId);
            // Success: Remove from documents list
            setDocuments(prev => prev.filter(d => d.id !== docId));
            setSelectedDocuments(prev => prev.filter(id => id !== docId));
            fetchDocuments();
        } catch (error) {
            console.error("Delete failed", error);
            toast.error('Failed to delete document');
            fetchDocuments();
            // Remove from deleting set on error so user can retry
            setDeletingDocIds(prev => {
                const next = new Set(prev);
                next.delete(docId);
                return next;
            });
        }
    };



    // Sidebar Navigation Item
    const NavItem = ({ id, icon: Icon, label }) => (
        <button
            onClick={() => {
                setActiveTab(id);
                setIsMobileMenuOpen(false);
            }}
            className={`w-full flex items-center ${leftCollapsed ? 'justify-center px-2' : 'gap-3 px-4'} py-3 rounded-lg transition-colors ${activeTab === id
                ? 'bg-[#C8A288] text-white font-medium'
                : 'text-[#4A3B32] hover:bg-[#E6D5CC]'
                }`}
            title={leftCollapsed ? label : undefined}
        >
            <Icon className="h-5 w-5 shrink-0" />
            {!leftCollapsed && <span>{label}</span>}
        </button>
    );

    if (projectViewLoading) {
        return (
            <div className="min-h-screen bg-[#FDF6F0] flex flex-col items-center justify-center">
                <div className="relative w-24 h-24">
                    <div className="absolute inset-0 border-4 border-[#E6D5CC] rounded-full"></div>
                    <div className="absolute inset-0 border-4 border-[#C8A288] rounded-full border-t-transparent animate-spin"></div>
                    <BookOpen className="absolute inset-0 m-auto h-8 w-8 text-[#C8A288] animate-pulse" />
                </div>
                <p className="mt-6 text-[#4A3B32] font-medium animate-pulse">Opening Project...</p>
            </div>
        );
    }

    return (
        <div className="h-[100dvh] flex bg-[#FDF6F0] overflow-hidden font-sans text-[#4A3B32]">

            {/* Mobile Sidebar Overlay */}
            {isMobileMenuOpen && (
                <div
                    className="fixed inset-0 bg-black/50 z-40 md:hidden"
                    onClick={() => setIsMobileMenuOpen(false)}
                />
            )}

            {/* Sidebar - Desktop & Mobile - Hidden when quiz/qa is active */}
            {!isSidebarHidden && (
            <div className={`
                fixed inset-y-0 left-0 z-50 ${leftCollapsed ? 'w-16' : 'w-72'} bg-[#FDF6F0]/95 backdrop-blur-xl border-r border-white/20 flex-col transition-all duration-300 ease-in-out md:translate-x-0 md:static md:flex md:shrink-0 shadow-2xl md:shadow-none
                ${isMobileMenuOpen ? 'translate-x-0' : '-translate-x-full'}
            `}>
                <div className={leftCollapsed ? 'p-2' : 'p-6'}>
                    <div className={`flex items-center ${leftCollapsed ? 'justify-center' : 'justify-between'} mb-8`}>
                        {!leftCollapsed && (
                            <div className="flex items-center gap-3">
                                <div className="h-10 w-10 bg-gradient-to-br from-[#C8A288] to-[#A08072] rounded-xl flex items-center justify-center text-white shadow-lg shadow-[#C8A288]/20">
                                    <BookOpen className="h-6 w-6" />
                                </div>
                                <h1 className="text-2xl font-bold text-[#4A3B32] tracking-tight">Lumina IQ</h1>
                            </div>
                        )}
                        <div className="flex items-center gap-1">
                            {/* Desktop collapse toggle */}
                            <button
                                onClick={() => setIsLeftCollapsed(!isLeftCollapsed)}
                                className="hidden md:block p-2 hover:bg-[#E6D5CC]/30 rounded-full text-[#8a6a5c] transition-colors"
                                title={isLeftCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
                            >
                                {leftCollapsed ? <ChevronRight className="h-5 w-5" /> : <ChevronLeft className="h-5 w-5" />}
                            </button>
                            {/* Close button for mobile */}
                            <button
                                onClick={() => setIsMobileMenuOpen(false)}
                                className="md:hidden p-2 hover:bg-[#E6D5CC]/30 rounded-full text-[#8a6a5c] transition-colors"
                            >
                                <X className="h-6 w-6" />
                            </button>
                        </div>
                    </div>

                    <nav className={leftCollapsed ? 'space-y-1' : 'space-y-3'}>
                        <NavItem id="chat" icon={MessageSquare} label="Chat" />
                        <NavItem id="qa" icon={HelpCircle} label="Q&A Generation" />
                        <NavItem id="quiz" icon={CheckSquare} label="Answer Quiz" />
                        <NavItem id="notes" icon={FileText} label="Notes" />
                        <NavItem id="path" icon={Target} label="Learning Path" />
                        <NavItem id="study" icon={Brain} label="Study Dashboard" />
                        <NavItem id="analytics" icon={BarChart3} label="Analytics" />
                        <NavItem id="exam" icon={GraduationCap} label="Exam Prep" />
                        <NavItem id="knowledge" icon={Network} label="Knowledge Graph" />
                        
                        {/* Settings - prominent in nav */}
                        <div className={leftCollapsed ? 'pt-2 border-t border-[#E6D5CC]/50' : 'pt-3 mt-3 border-t border-[#E6D5CC]/50'}>
                            <button
                                onClick={() => {
                                    navigate('/settings');
                                    setIsMobileMenuOpen(false);
                                }}
                                className={`w-full flex items-center ${leftCollapsed ? 'justify-center px-2' : 'gap-3 px-4'} py-3 rounded-lg transition-colors text-[#4A3B32] hover:bg-[#E6D5CC]`}
                                title={leftCollapsed ? 'Settings' : undefined}
                            >
                                <Settings className="h-5 w-5 shrink-0" />
                                {!leftCollapsed && <span>Settings</span>}
                            </button>
                        </div>
                    </nav>
                </div>

                <div className={`mt-auto ${leftCollapsed ? 'p-2' : 'p-6'} border-t border-[#E6D5CC]/50`}>
                    {!leftCollapsed ? (
                        <>
                            <button
                                onClick={() => {
                                    setShowUploadModal(true);
                                    setIsMobileMenuOpen(false);
                                }}
                                disabled={uploading}
                                className="w-full flex items-center gap-3 px-4 py-4 text-[#4A3B32] bg-white border border-[#E6D5CC] hover:bg-[#FDF6F0] hover:border-[#C8A288] rounded-xl transition-all mb-4 shadow-sm group"
                            >
                                <div className="h-8 w-8 bg-[#FDF6F0] rounded-lg flex items-center justify-center text-[#C8A288] group-hover:scale-110 transition-transform">
                                    <Plus className="h-5 w-5" />
                                </div>
                                <span className="font-semibold">New PDF</span>
                            </button>

                            <div className="flex items-center gap-3 px-4 py-3 bg-white/50 rounded-xl border border-[#E6D5CC]/30">
                                <div className="h-10 w-10 bg-gradient-to-br from-[#E6D5CC] to-[#d2bab0] rounded-full flex items-center justify-center shadow-inner">
                                    <User className="h-5 w-5 text-[#4A3B32]" />
                                </div>
                                <div className="flex-1 min-w-0">
                                    <p className="text-sm font-bold text-[#4A3B32] truncate">User</p>
                                    <p className="text-xs text-[#8a6a5c] font-medium">Free Plan</p>
                                </div>
                            </div>
                        </>
                    ) : (
                        <div className="space-y-2">
                            <button
                                onClick={() => {
                                    setShowUploadModal(true);
                                    setIsMobileMenuOpen(false);
                                }}
                                disabled={uploading}
                                className="w-full flex items-center justify-center p-3 text-[#C8A288] hover:bg-[#E6D5CC]/30 rounded-xl transition-colors"
                                title="New PDF"
                            >
                                <Plus className="h-5 w-5" />
                            </button>
                        </div>
                    )}
                </div>
            </div>
            )}

            {/* Main Content Area */}
            <div className={`flex-1 flex flex-col min-w-0 overflow-hidden backdrop-blur-sm ${
                zenMode
                    ? 'bg-white m-0 rounded-none border-0 shadow-none'
                    : 'bg-white/50 md:bg-white md:m-4 md:rounded-3xl shadow-sm border-x md:border-y border-[#E6D5CC]/50 md:border-[#E6D5CC]'
            }`}>

                {/* Header (Context) - Hidden in Zen Mode */}
                {!zenMode && (
                <div className="px-3 md:px-5 py-2.5 border-b border-[#E6D5CC]/50 bg-white/50 backdrop-blur-md sticky top-0 z-30">
                    {/* Single-row header with proper spacing */}
                    <div className="flex items-center gap-2 h-11">
                        {/* Mobile Menu Button */}
                        <button
                            onClick={() => setIsMobileMenuOpen(true)}
                            className="md:hidden p-2 -ml-1 hover:bg-[#E6D5CC]/30 rounded-lg text-[#4A3B32] transition-colors shrink-0"
                        >
                            <Menu className="h-5 w-5" />
                        </button>

                        {/* Left: Tab name + Summary */}
                        <div className="flex items-center gap-2 min-w-0 shrink-0">
                            <h2 className="text-base font-bold text-[#4A3B32] whitespace-nowrap">
                                {activeTab === 'chat' && 'Chat'}
                                {activeTab === 'qa' && 'Q&A'}
                                {activeTab === 'quiz' && 'Quiz'}
                                {activeTab === 'notes' && 'Notes'}
                                {activeTab === 'path' && 'Learning Path'}
                                {activeTab === 'study' && 'Study'}
                                {activeTab === 'analytics' && 'Analytics'}
                                {activeTab === 'exam' && 'Exam Prep'}
                                {activeTab === 'knowledge' && 'Knowledge Graph'}
                            </h2>

                            {/* Summary Dropdown - compact pill */}
                            {documents.length > 0 && (
                                <button
                                    onClick={toggleSummary}
                                    className={`hidden sm:flex items-center gap-1 text-[11px] font-semibold px-2.5 py-1 rounded-full transition-all shrink-0 ${
                                        showSummary
                                            ? 'bg-[#C8A288] text-white'
                                            : 'bg-[#FDF6F0] text-[#C8A288] border border-[#E6D5CC] hover:border-[#C8A288]/40'
                                    }`}
                                >
                                    <FileText className="h-3 w-3" />
                                    Su
                                    {showSummary ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                                </button>
                            )}
                        </div>

                        {/* Center: Active document name - fills remaining space */}
                        <div className="flex-1 min-w-0 hidden md:block">
                            <p className="text-xs text-[#8a6a5c]/70 truncate text-center px-2">
                                {documents.length > 0 ? documents[0].filename : ''}
                            </p>
                        </div>

                        {/* Spacer for mobile */}
                        <div className="flex-1 md:hidden" />

                        {/* Right: Toolbar - grouped with subtle dividers */}
                        <div className="flex items-center shrink-0">
                            {/* Core tools group */}
                            <div className="flex items-center">
                                <button
                                    onClick={() => setShowSearch(true)}
                                    className="p-2 rounded-lg text-[#8a6a5c] hover:text-[#4A3B32] hover:bg-[#E6D5CC]/30 transition-colors"
                                    title="Search (Ctrl+K)"
                                >
                                    <Search className="h-[18px] w-[18px]" />
                                </button>
                                <button
                                    onClick={() => setShowPomodoro(!showPomodoro)}
                                    className={`p-2 rounded-lg transition-colors ${showPomodoro ? 'bg-[#C8A288] text-white' : 'text-[#8a6a5c] hover:text-[#4A3B32] hover:bg-[#E6D5CC]/30'}`}
                                    title="Pomodoro Timer"
                                >
                                    <Timer className="h-[18px] w-[18px]" />
                                </button>
                                <button
                                    onClick={() => setShowBookmarks(!showBookmarks)}
                                    className={`p-2 rounded-lg transition-colors ${showBookmarks ? 'bg-[#C8A288] text-white' : 'text-[#8a6a5c] hover:text-[#4A3B32] hover:bg-[#E6D5CC]/30'}`}
                                    title="Bookmarks & Highlights"
                                >
                                    <Bookmark className="h-[18px] w-[18px]" />
                                </button>
                            </div>

                            {/* Divider */}
                            <div className="w-px h-5 bg-[#E6D5CC]/60 mx-1 hidden sm:block" />

                            {/* Secondary tools */}
                            <div className="hidden sm:flex items-center">
                                <button
                                    onClick={() => setShowAITutor(!showAITutor)}
                                    className={`p-2 rounded-lg transition-colors ${showAITutor ? 'bg-[#C8A288] text-white' : 'text-[#8a6a5c] hover:text-[#4A3B32] hover:bg-[#E6D5CC]/30'}`}
                                    title="AI Tutor"
                                >
                                    <Brain className="h-[18px] w-[18px]" />
                                </button>
                                <button
                                    onClick={() => setZenMode(true)}
                                    className="p-2 rounded-lg text-[#8a6a5c] hover:text-[#4A3B32] hover:bg-[#E6D5CC]/30 transition-colors"
                                    title="Focus Mode (Ctrl+Shift+Z)"
                                >
                                    <Maximize2 className="h-[18px] w-[18px]" />
                                </button>
                            </div>

                            {/* Divider */}
                            <div className="w-px h-5 bg-[#E6D5CC]/60 mx-0.5 hidden sm:block" />

                            {/* Gamification Button */}
                            <button
                                onClick={() => setShowGamification(!showGamification)}
                                className={`hidden sm:flex items-center gap-1.5 px-2 py-1.5 rounded-lg transition-all ${
                                    showGamification
                                        ? 'bg-[#C8A288] text-white'
                                        : 'text-[#8a6a5c] hover:text-[#4A3B32] hover:bg-[#E6D5CC]/30'
                                }`}
                                title="Progress & XP"
                            >
                                <Trophy className="h-[18px] w-[18px]" />
                                {gamificationData && (
                                    <span className="text-[11px] font-bold tabular-nums">
                                        {gamificationData.total_xp?.toLocaleString()} XP
                                    </span>
                                )}
                            </button>

                            {/* Docs Toggle - Mobile/Tablet */}
                            <button
                                onClick={() => setIsDocsMenuOpen(!isDocsMenuOpen)}
                                className={`p-2 rounded-lg transition-colors lg:hidden ${isDocsMenuOpen ? 'bg-[#C8A288] text-white' : 'text-[#8a6a5c] hover:text-[#4A3B32] hover:bg-[#E6D5CC]/30'}`}
                                title="Documents"
                            >
                                <FileText className="h-[18px] w-[18px]" />
                            </button>

                            {/* Exit */}
                            <button
                                onClick={() => navigate('/dashboard')}
                                className="p-2 rounded-lg text-[#8a6a5c]/50 hover:bg-red-50 hover:text-red-500 transition-colors ml-0.5"
                                title="Back to Dashboard"
                            >
                                <LogOut className="h-[18px] w-[18px]" />
                            </button>
                        </div>
                    </div>

                    {/* Summary Content Area - positioned below header */}
                    {showSummary && (
                        <div className="absolute top-full left-4 right-4 md:left-auto md:right-4 md:w-96 mt-1 p-5 bg-white/95 backdrop-blur-xl rounded-2xl border border-[#E6D5CC] shadow-2xl animate-in slide-in-from-top-2 z-50">
                            <div className="flex justify-between items-center mb-3">
                                <h4 className="font-bold text-sm text-[#4A3B32] uppercase tracking-wide">
                                    {selectedDocuments.length > 0 ? (selectedDocuments.length === 1 ? 'Document Summary' : 'Selection Summary') : 'Project Summary'}
                                </h4>
                                <div className="flex items-center gap-1">
                                    <button
                                        onClick={fetchSummary}
                                        disabled={summaryLoading}
                                        title="Regenerate Summary"
                                        className="p-1.5 hover:bg-[#FDF6F0] rounded-full transition-colors disabled:opacity-50"
                                    >
                                        <RefreshCw className={`h-3.5 w-3.5 ${summaryLoading ? 'animate-spin' : ''}`} />
                                    </button>
                                    <button
                                        onClick={() => setShowSummary(false)}
                                        className="p-1.5 hover:bg-[#FDF6F0] rounded-full transition-colors"
                                    >
                                        <X className="h-3.5 w-3.5" />
                                    </button>
                                </div>
                            </div>
                            {summaryLoading ? (
                                <div className="flex flex-col items-center justify-center py-12 gap-4">
                                    <div className="relative">
                                        <div className="h-16 w-16 border-4 border-[#E6D5CC] rounded-full"></div>
                                        <div className="absolute inset-0 h-16 w-16 border-4 border-[#C8A288] rounded-full border-t-transparent animate-spin"></div>
                                        <FileText className="absolute inset-0 m-auto h-6 w-6 text-[#C8A288]" />
                                    </div>
                                    <div className="text-center">
                                        <p className="text-sm font-bold text-[#4A3B32]">Generating Summary</p>
                                        <p className="text-xs text-[#8a6a5c] mt-1">Analyzing your documents...</p>
                                    </div>
                                    <div className="flex gap-1">
                                        <div className="h-2 w-2 bg-[#C8A288] rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                                        <div className="h-2 w-2 bg-[#C8A288] rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                                        <div className="h-2 w-2 bg-[#C8A288] rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                                    </div>
                                </div>
                            ) : (
                                <div className="prose prose-sm max-w-none text-sm text-[#4A3B32] max-h-[60vh] overflow-y-auto overflow-x-auto pr-2 custom-scrollbar">
                                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{summaryContent}</ReactMarkdown>
                                </div>
                            )}
                        </div>
                    )}
                </div>
                )}

                {/* Zen Mode Floating Controls */}
                {zenMode && (
                    <div className="absolute top-3 right-3 z-50 flex items-center gap-2 animate-in fade-in duration-300">
                        <div className="flex items-center gap-2 px-3 py-1.5 bg-[#4A3B32]/80 backdrop-blur-md text-white/90 rounded-full text-xs font-medium shadow-lg">
                            <div className="h-2 w-2 bg-green-400 rounded-full animate-pulse" />
                            Focus Mode
                        </div>
                        <button
                            onClick={() => setZenMode(false)}
                            className="p-2 bg-[#4A3B32]/80 backdrop-blur-md text-white/90 rounded-full hover:bg-[#4A3B32] transition-colors shadow-lg"
                            title="Exit Focus Mode (Esc)"
                        >
                            <Minimize2 className="h-4 w-4" />
                        </button>
                    </div>
                )}

                {/* Content Body */}
                <div className="flex-1 overflow-hidden relative">

                    {/* Chat View */}
                    {activeTab === 'chat' && (
                        <div className="h-full flex flex-col">
                            <div className="flex-1 overflow-y-auto overflow-x-hidden px-2 py-4 md:p-6 space-y-6">
                                {messages.map((msg, idx) => (
                                    <div key={idx} className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                                        <div className={`max-w-[95%] md:max-w-[85%] break-words rounded-2xl px-4 py-3 md:px-6 md:py-4 ${msg.role === 'user'
                                            ? 'bg-[#C8A288] text-white rounded-br-none'
                                            : 'bg-[#FDF6F0] text-[#4A3B32] rounded-bl-none'
                                            }`}>
                                            {msg.content ? (
                                                <div className={`text-sm leading-relaxed ${msg.role === 'assistant' ? 'prose prose-sm max-w-none overflow-x-auto prose-p:my-2 prose-headings:text-[#4A3B32] prose-a:text-[#C8A288]' : ''}`}>
                                                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                                        {msg.content}
                                                    </ReactMarkdown>
                                                </div>
                                            ) : (
                                                <Loader2 className="h-5 w-5 animate-spin text-[#8a6a5c]" />
                                            )}

                                            {/* Citations Rendering */}
                                            {msg.sources && msg.sources.length > 0 && (
                                                <div className="mt-4 pt-3 border-t border-black/10">
                                                    <p className="text-xs font-bold mb-2 opacity-70 flex items-center gap-1">
                                                        <BookOpen className="h-3 w-3" /> Sources:
                                                    </p>
                                                    <div className="flex flex-wrap gap-2">
                                                        {msg.sources.map((source, i) => (
                                                            <div key={i} className="text-xs bg-white/50 px-2 py-1 rounded border border-black/5 max-w-xs truncate cursor-help" title={source.chunk_text}>
                                                                <span className="font-medium">{source.doc_name}</span>
                                                            </div>
                                                        ))}
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                ))}
                                {isProcessingDocs && (
                                    <div className="flex justify-center my-4">
                                        <div className="bg-gradient-to-r from-amber-50 to-orange-50 text-amber-700 px-5 py-4 rounded-xl text-sm flex items-center gap-3 border border-amber-200 shadow-md max-w-lg">
                                            <div className="relative">
                                                <div className="h-8 w-8 border-2 border-amber-300 rounded-full"></div>
                                                <div className="absolute inset-0 h-8 w-8 border-2 border-amber-500 rounded-full border-t-transparent animate-spin"></div>
                                            </div>
                                            <div>
                                                <p className="font-bold text-amber-800">Processing Documents</p>
                                                <p className="text-xs text-amber-600 mt-0.5">
                                                    Extracting text and generating embeddings. This will complete automatically.
                                                </p>
                                            </div>
                                        </div>
                                    </div>
                                )}

                            </div>

                            <div className="p-4 border-t border-[#E6D5CC] bg-white">
                                <form onSubmit={handleSendMessage} className="flex gap-3 max-w-4xl mx-auto">
                                    <div className="flex-1 relative">
                                        <input
                                            type="text"
                                            value={inputMessage}
                                            onChange={(e) => setInputMessage(e.target.value)}
                                            placeholder="Ask a question about your PDF..."
                                            className="w-full pl-6 pr-12 py-3 bg-[#FDF6F0] border-none rounded-full focus:ring-2 focus:ring-[#C8A288] outline-none text-[#4A3B32] placeholder-[#8a6a5c]"
                                            disabled={loading}
                                        />
                                        <button
                                            type="submit"
                                            disabled={loading || !inputMessage.trim()}
                                            className="absolute right-2 top-1/2 transform -translate-y-1/2 p-2 bg-[#C8A288] text-white rounded-full hover:bg-[#B08B72] transition-colors disabled:opacity-50"
                                        >
                                            <Send className="h-4 w-4" />
                                        </button>
                                    </div>
                                </form>
                            </div>
                        </div>
                    )}

                    {activeTab === 'quiz' && (
                        <QuizView
                            projectId={projectId}
                            availableTopics={availableTopics}
                            selectedDocuments={selectedDocuments}
                            preSelectedTopic={preSelectedTopic}
                            preSelectedMode={preSelectedQuizMode}
                            cameFromPath={cameFromPath}
                            onReturnToPath={() => {
                                setActiveTab('path');
                                setPreSelectedTopic(null);
                                setPreSelectedQuizMode(null);
                                setCameFromPath(false);
                            }}
                            onQuizComplete={(topic, score, passed) => {
                                if (passed) {
                                    const newProgress = new Set(learningProgress);
                                    newProgress.add(topic);
                                    setLearningProgress(newProgress);
                                    saveLearningProgress(projectId, [...newProgress]).catch(err =>
                                        console.warn('Failed to save progress:', err)
                                    );
                                }
                                // Clear pre-selection after quiz complete
                                setPreSelectedTopic(null);
                                setPreSelectedQuizMode(null);
                            }}
                            onQuizActiveChange={setIsQuizActive}
                            onBack={() => setActiveTab('chat')}
                        />
                    )}

{/* Q&A Generation View (Study Mode) */}
                    {activeTab === 'qa' && (
                        <QAView
                            projectId={projectId}
                            availableTopics={availableTopics}
                            selectedDocuments={selectedDocuments}
                            preSelectedTopic={preSelectedTopic}
                            onQAActiveChange={setIsQAActive}
                            onBack={() => setActiveTab('chat')}
                        />
                    )}

                    {/* Notes Generation View */}
                    {activeTab === 'notes' && (
                        <NotesView
                            projectId={projectId}
                            availableTopics={availableTopics}
                            selectedDocuments={selectedDocuments}
                            preSelectedTopic={preSelectedTopic}
                        />
                    )}
                    
                    {/* Study Dashboard View */}
                    {activeTab === 'study' && (
                        <StudyDashboard
                            projectId={projectId}
                            availableTopics={allProjectTopics}
                        />
                    )}
                    
                    {/* Learning Path View */}
                    {activeTab === 'path' && (
                        <LearningPathView
                            projectId={projectId}
                            availableTopics={allProjectTopics}
                            selectedDocuments={selectedDocuments}
                            setSelectedDocuments={setSelectedDocuments}
                            documentTopics={documentTopics}
                            documents={documents}
                            completedTopics={learningProgress}
                            onStartQuiz={(topic, mode, docsToSelect) => {
                                // Set documents for context
                                if (docsToSelect && docsToSelect.length > 0) {
                                    setSelectedDocuments(docsToSelect);
                                }
                                // Set pre-selected topic and mode
                                setPreSelectedTopic(topic);
                                setPreSelectedQuizMode(mode || 'both');
                                setCameFromPath(true);
                                // Navigate to quiz tab
                                setActiveTab('quiz');
                            }}
                            onTopicComplete={(topic) => {
                                const newProgress = new Set(learningProgress);
                                newProgress.add(topic);
                                setLearningProgress(newProgress);
                                saveLearningProgress(projectId, [...newProgress]).catch(err =>
                                    console.warn('Failed to save progress:', err)
                                );
                            }}
                            onGenerateNotes={(topic, docsToSelect) => {
                                if (docsToSelect && docsToSelect.length > 0) {
                                    setSelectedDocuments(docsToSelect);
                                }
                                setPreSelectedTopic(topic);
                                setActiveTab('notes');
                            }}
                            onStartQA={(topic, docsToSelect) => {
                                if (docsToSelect && docsToSelect.length > 0) {
                                    setSelectedDocuments(docsToSelect);
                                }
                                setPreSelectedTopic(topic);
                                setActiveTab('qa');
                            }}
                            onOpenTutor={(topic) => {
                                setTutorTopic(topic);
                                setShowAITutor(true);
                            }}
                            onOpenKnowledgeGraph={() => {
                                setActiveTab('knowledge');
                            }}
                            onOpenMindmap={(topic, docsToSelect) => {
                                if (docsToSelect && docsToSelect.length > 0) {
                                    setSelectedDocuments(docsToSelect);
                                }
                                setMindmapTopic(topic);
                                setMindmapDocs(docsToSelect || []);
                            }}
                            onOpenFlashcards={(topic, docsToSelect) => {
                                if (docsToSelect && docsToSelect.length > 0) {
                                    setSelectedDocuments(docsToSelect);
                                }
                                setFlashcardTopic(topic);
                                setFlashcardDocs(docsToSelect || []);
                            }}
                        />
                    )}

                    {/* Advanced Analytics View */}
                    {activeTab === 'analytics' && (
                        <AdvancedAnalytics
                            projectId={projectId}
                            documents={documents}
                            selectedDocuments={selectedDocuments}
                            documentTopics={documentTopics}
                        />
                    )}

                    {/* Exam Prep Mode View */}
                    {activeTab === 'exam' && (
                        <ExamPrepMode
                            projectId={projectId}
                            documents={documents}
                            selectedDocuments={selectedDocuments}
                            topics={availableTopics}
                            onStartQuiz={(topic, mode) => {
                                setPreSelectedTopic(topic);
                                setPreSelectedQuizMode(mode || 'both');
                                setActiveTab('quiz');
                            }}
                        />
                    )}

                    {/* Knowledge Graph View */}
                    {activeTab === 'knowledge' && (
                        <div className="h-full p-4 overflow-auto">
                            <KnowledgeGraphView projectId={projectId} />
                        </div>
                    )}

                    {/* Mindmap Overlay (only from Learning Path) */}
                    {mindmapTopic && (
                        <div className="absolute inset-0 z-20 bg-white">
                            <TopicMindmap
                                projectId={projectId}
                                topic={mindmapTopic}
                                selectedDocuments={mindmapDocs}
                                onClose={() => {
                                    setMindmapTopic(null);
                                    setMindmapDocs([]);
                                }}
                            />
                        </div>
                    )}

                    {/* Flashcards Overlay (only from Learning Path) */}
                    {flashcardTopic && (
                        <div className="absolute inset-0 z-20 bg-white">
                            <TopicFlashcards
                                projectId={projectId}
                                topic={flashcardTopic}
                                selectedDocuments={flashcardDocs}
                                onClose={() => {
                                    setFlashcardTopic(null);
                                    setFlashcardDocs([]);
                                }}
                            />
                        </div>
                    )}
                </div>
            </div>

            {/* Right Sidebar - Documents (Responsive Drawer) - Hidden when quiz/qa is active */}
            {/* Overlay for mobile */}
            {isDocsMenuOpen && !isSidebarHidden && (
                <div
                    className="fixed inset-0 bg-black/50 z-40 lg:hidden backdrop-blur-sm"
                    onClick={() => setIsDocsMenuOpen(false)}
                />
            )}

            {!isSidebarHidden && (
            <div className={`
                fixed inset-y-0 right-0 z-50 ${rightCollapsed ? 'w-16' : 'w-80'} bg-[#FDF6F0]/95 backdrop-blur-xl border-l border-white/20 ${rightCollapsed ? 'p-2' : 'p-6'} shadow-2xl shrink-0 flex flex-col overflow-hidden transition-all duration-300 ease-in-out lg:translate-x-0 lg:static lg:flex lg:shadow-none
                ${isDocsMenuOpen ? 'translate-x-0' : 'translate-x-full'}
            `}>
                {rightCollapsed ? (
                    /* Collapsed right sidebar */
                    <div className="flex flex-col items-center h-full py-2">
                        <button
                            onClick={() => setIsRightCollapsed(false)}
                            className="p-2 hover:bg-[#E6D5CC]/30 rounded-full text-[#8a6a5c] transition-colors mb-4"
                            title="Expand panel"
                        >
                            <ChevronLeft className="h-5 w-5" />
                        </button>
                        <div className="flex-1 flex flex-col items-center justify-center gap-4">
                            <div className="relative">
                                <FileText className="h-6 w-6 text-[#C8A288]" />
                                {documents.length > 0 && (
                                    <span className="absolute -top-2 -right-2 h-5 w-5 bg-[#C8A288] text-white text-xs rounded-full flex items-center justify-center font-bold">
                                        {documents.length}
                                    </span>
                                )}
                            </div>
                            <div className="w-6 h-px bg-[#E6D5CC]/50" />
                        </div>
                        <div className="mt-auto">
                            <Calendar className="h-4 w-4 text-[#C8A288]" />
                        </div>
                    </div>
                ) : (
                    /* Expanded right sidebar */
                    <>
                <div className="flex justify-between items-center mb-6 lg:hidden shrink-0">
                    <h3 className="font-bold text-xl text-[#4A3B32]">Documents</h3>
                    <button
                        onClick={() => setIsDocsMenuOpen(false)}
                        className="p-2 hover:bg-[#E6D5CC]/30 rounded-full text-[#8a6a5c]"
                    >
                        <X className="h-6 w-6" />
                    </button>
                </div>

                {/* Desktop collapse toggle for right sidebar */}
                <div className="hidden lg:flex justify-end mb-3 shrink-0">
                    <button
                        onClick={() => setIsRightCollapsed(true)}
                        className="p-2 hover:bg-[#E6D5CC]/30 rounded-full text-[#8a6a5c] transition-colors"
                        title="Collapse documents panel"
                    >
                        <ChevronRight className="h-5 w-5" />
                    </button>
                </div>

                <div className="bg-gradient-to-br from-[#C8A288] to-[#A08072] text-white p-5 rounded-2xl mb-6 shadow-lg shadow-[#C8A288]/30 shrink-0">
                    <div className="flex items-center gap-3 mb-2">
                        <div className="h-8 w-8 bg-white/20 rounded-lg flex items-center justify-center backdrop-blur-md">
                            <FileText className="h-5 w-5" />
                        </div>
                        <h3 className="font-bold text-lg">Documents</h3>
                    </div>
                    <p className="text-sm opacity-90 pl-1">
                        {documents.length} file{documents.length !== 1 ? 's' : ''}
                        {selectedDocuments.length > 0 && ` • ${selectedDocuments.length} selected`}
                    </p>
                </div>

                {
                    documents.length > 0 ? (
                        <div className="min-h-0 space-y-3 pr-1 custom-scrollbar" style={{ maxHeight: '40vh', overflowY: 'auto' }}>
                            {documents.map((doc) => (
                                <div
                                    key={doc.id}
                                    className={`p-3 rounded-xl border transition-all duration-200 group relative ${selectedDocuments.includes(doc.id)
                                        ? 'bg-white border-[#C8A288] shadow-md shadow-[#C8A288]/10'
                                        : 'bg-white/60 border-transparent hover:bg-white hover:border-[#E6D5CC]'
                                        }`}
                                >
                                    <label className="flex items-start gap-4 cursor-pointer pr-8">
                                        <div className="relative mt-1">
                                            <input
                                                type="checkbox"
                                                checked={selectedDocuments.includes(doc.id)}
                                                onChange={(e) => {
                                                    if (e.target.checked) {
                                                        setSelectedDocuments([...selectedDocuments, doc.id]);
                                                    } else {
                                                        setSelectedDocuments(selectedDocuments.filter(id => id !== doc.id));
                                                    }
                                                }}
                                                className="peer h-5 w-5 rounded-md border-2 border-[#C8A288] text-[#C8A288] focus:ring-[#C8A288] focus:ring-offset-0 transition-all checked:bg-[#C8A288] checked:border-[#C8A288] appearance-none cursor-pointer"
                                            />
                                            <CheckSquare className="h-5 w-5 text-white absolute top-0 left-0 pointer-events-none opacity-0 peer-checked:opacity-100 transition-opacity" />
                                        </div>

                                        <div className="flex-1 min-w-0">
                                            <p className={`text-sm font-semibold truncate transition-colors ${selectedDocuments.includes(doc.id) ? 'text-[#4A3B32]' : 'text-[#8a6a5c]'}`} title={doc.filename}>
                                                {doc.filename}
                                            </p>
                                            <div className="flex items-center gap-2 mt-1.5">
                                                <span className="text-[10px] uppercase font-bold text-[#8a6a5c]/70 bg-[#E6D5CC]/30 px-2 py-0.5 rounded-full">
                                                    {(doc.file_size / 1024 / 1024).toFixed(2)} MB
                                                </span>
                                                {(doc.upload_status === 'processing' || doc.upload_status === 'pending') && (
                                                    <div className="flex items-center gap-1 text-[10px] text-blue-600 bg-blue-50 px-2 py-0.5 rounded-full">
                                                        <Loader2 className="h-3 w-3 animate-spin" />
                                                        Processing
                                                    </div>
                                                )}
                                                {doc.upload_status === 'queued' && (
                                                    <div className="flex items-center gap-1 text-[10px] text-orange-600 bg-orange-50 px-2 py-0.5 rounded-full">
                                                        <Loader2 className="h-3 w-3 animate-spin" />
                                                        {doc.error_message || 'Queued'}
                                                    </div>
                                                )}
                                                {doc.upload_status === 'embedding' && (
                                                    <div className="flex items-center gap-1 text-[10px] text-purple-600 bg-purple-50 px-2 py-0.5 rounded-full">
                                                        <Loader2 className="h-3 w-3 animate-spin" />
                                                        Embedding
                                                    </div>
                                                )}
                                                {doc.upload_status === 'completed' && (
                                                    <div className="flex items-center gap-1 text-[10px] text-green-600 bg-green-50 px-2 py-0.5 rounded-full">
                                                        <CheckSquare className="h-3 w-3" />
                                                        Ready
                                                    </div>
                                                )}
                                                {(doc.upload_status === 'error' || doc.upload_status === 'failed') && (
                                                    <div className="flex items-center gap-1 text-[10px] text-red-600 bg-red-50 px-2 py-0.5 rounded-full">
                                                        Failed
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    </label>

                                    {deletingDocIds.has(doc.id) ? (
                                        <div className="absolute top-3 right-3 p-1.5 text-[#8a6a5c]">
                                            <Loader2 className="h-4 w-4 animate-spin" />
                                        </div>
                                    ) : (
                                        <button
                                            onClick={(e) => {
                                                e.preventDefault();
                                                e.stopPropagation();
                                                requestDelete(doc);
                                            }}
                                            className="absolute top-3 right-3 p-2 text-[#8a6a5c]/60 hover:text-red-500 hover:bg-red-50 rounded-lg transition-all opacity-0 group-hover:opacity-100 focus:opacity-100"
                                            title="Delete Document"
                                        >
                                            <Trash2 className="h-4 w-4" />
                                        </button>
                                    )}
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="flex flex-col items-center justify-center text-center py-6 text-[#8a6a5c]/60">
                            <div className="h-12 w-12 bg-[#E6D5CC]/30 rounded-full flex items-center justify-center mb-3">
                                <FileText className="h-6 w-6 opacity-50" />
                            </div>
                            <p className="text-sm font-medium">No documents yet</p>
                            <p className="text-xs mt-1">Upload a PDF to get started</p>
                        </div>
                    )
                }

                <div className="flex-1" />

                <div className="mt-auto pt-3 shrink-0">
                    <div className="bg-white/60 p-3 rounded-xl border border-[#E6D5CC]/50 backdrop-blur-sm">
                        <p className="text-[10px] text-[#8a6a5c] uppercase font-bold mb-1 tracking-wider">Date Selected</p>
                        <div className="flex items-center gap-2 text-[#4A3B32]">
                            <Calendar className="h-4 w-4 text-[#C8A288]" />
                            <p className="font-bold text-sm">{new Date().toLocaleDateString()}</p>
                        </div>
                    </div>
                </div>
                    </>
                )}
            </div>
            )}

            {/* Upload Modal */}
            {
                showUploadModal && (
                    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setShowUploadModal(false)}>
                        <div className="bg-white rounded-2xl p-8 max-w-2xl w-full mx-4" onClick={(e) => e.stopPropagation()}>
                            <div className="flex justify-between items-center mb-6">
                                <h2 className="text-2xl font-bold text-[#4A3B32]">Upload Documents</h2>
                                <button
                                    onClick={() => setShowUploadModal(false)}
                                    className="text-[#8a6a5c] hover:text-[#4A3B32] p-2"
                                >
                                    <X className="h-6 w-6" />
                                </button>
                            </div>

                            <UploadZone onFilesSelected={handleFileUpload} uploading={uploading} />
                        </div>
                    </div>
                )
            }
            {/* Delete Confirmation Modal */}
            {
                deleteConfirmDoc && (
                    <div className="fixed inset-0 bg-black/50 z-[60] flex items-center justify-center p-4">
                        <div className="bg-white rounded-xl shadow-xl max-w-sm w-full p-6 animate-in fade-in zoom-in-95 duration-200">
                            <h3 className="text-xl font-bold text-[#4A3B32] mb-2">Delete Document?</h3>
                            <p className="text-[#8a6a5c] mb-6">
                                Are you sure you want to delete <span className="font-semibold text-[#4A3B32]">{deleteConfirmDoc.filename}</span>?
                                This action cannot be undone.
                            </p>
                            <div className="flex gap-3 justify-end">
                                <button
                                    onClick={() => setDeleteConfirmDoc(null)}
                                    className="px-4 py-2 rounded-lg text-[#4A3B32] hover:bg-[#FDF6F0] font-medium transition-colors"
                                >
                                    Cancel
                                </button>
                                <button
                                    onClick={confirmDelete}
                                    className="px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 font-medium transition-colors shadow-sm"
                                >
                                    Delete
                                </button>
                            </div>
                        </div>
                    </div>
                )
            }

            {/* Floating Pomodoro Timer */}
            {showPomodoro && (
                <div className="fixed bottom-4 right-4 z-50 animate-in slide-in-from-bottom-4">
                    <PomodoroTimer
                        projectId={projectId}
                        documentId={selectedDocuments.length === 1 ? selectedDocuments[0] : null}
                        onClose={() => setShowPomodoro(false)}
                    />
                </div>
            )}

            {/* AI Tutor Chat Panel - self-positioned, draggable */}
            {showAITutor && (
                <AITutorChat
                    projectId={projectId}
                    selectedDocuments={selectedDocuments}
                    topic={tutorTopic}
                    onClose={() => {
                        setShowAITutor(false);
                        setTutorTopic(null);
                    }}
                />
            )}

            {/* Bookmarks Panel */}
            {showBookmarks && (
                <div className="fixed top-20 right-4 z-50 animate-in slide-in-from-right-4 md:right-[340px]">
                    <BookmarksPanel
                        projectId={projectId}
                        documents={documents}
                        onClose={() => setShowBookmarks(false)}
                        onNavigate={(docId, topic) => {
                            if (docId) {
                                setSelectedDocuments([docId]);
                            }
                            if (topic) {
                                setTutorTopic(topic);
                                setShowAITutor(true);
                            }
                        }}
                    />
                </div>
            )}

            {/* Gamification Panel — Floating Popup */}
            {showGamification && (
                <div className="fixed top-14 right-4 z-50 animate-in slide-in-from-top-2 duration-200">
                    <GamificationPanel onClose={() => setShowGamification(false)} />
                </div>
            )}

            {/* Global Search Modal */}
            <GlobalSearch
                isOpen={showSearch}
                onClose={() => setShowSearch(false)}
                projectId={projectId}
                documents={documents}
                documentTopics={documentTopics}
                onSelectDocument={(docId) => {
                    setSelectedDocuments([docId]);
                    setShowSearch(false);
                }}
                onSelectTopic={(topic) => {
                    setTutorTopic(topic);
                    setShowAITutor(true);
                    setShowSearch(false);
                }}
            />
        </div >
    );
};

export default ProjectView;
