import React, { useState, useRef, useEffect, lazy, Suspense } from 'react';
import Logo from '../components/brand/Logo';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
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
    Minimize2,
    Layers,
    Zap,
    PanelRight,
    Check,
    Eye,
    EyeOff,
    WifiOff,
    Moon,
    FlaskConical
} from 'lucide-react';
import {
    uploadDocument,
    getDocuments,
    getDocumentUrl,
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
    retryDocument,
    generateNotes,
    getLearningProgress,
    saveLearningProgress,
    generateMindmap,
    generateFlashcardsWithAI,
    subscribeDocumentProgress,
} from '../api';
import { useToast } from '../context/ToastContext';
import { Joyride, STATUS } from 'react-joyride';
import { TOUR_OPTIONS } from '../utils/tourConfig';
import { useAuth } from '../context/AuthContext';
import { useSettings } from '../context/SettingsContext';
import { useGamification } from '../context/GamificationContext';
import { recordActivity } from '../utils/studyActivity';
import { supabase } from '../supabaseClient';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import UploadZone from '../components/UploadZone';
import ProcessingProgress from '../components/ProcessingProgress';
import SidebarNav from '../components/SidebarNav';
import { pendingUploads, forgetPendingUpload } from '../utils/resumableUpload';
import { MAX_UPLOAD_MB } from '../utils/pricing';
import { getRotatingLoadingMessage, getRandomLoadingMessage } from '../utils/LoadingMessages';

// View Components
const QuizView = lazy(() => import('../components/views/QuizView'));
const QAView = lazy(() => import('../components/views/QAView'));
const NotesView = lazy(() => import('../components/views/NotesView'));
const StudyDashboard = lazy(() => import('../components/views/StudyDashboard'));
const LearningPathView = lazy(() => import('../components/views/LearningPathView'));
const AdvancedAnalytics = lazy(() => import('../components/views/AdvancedAnalytics'));
const KnowledgeGraphView = lazy(() => import('../components/views/KnowledgeGraphView'));
const TopicMindmap = lazy(() => import('../components/views/TopicMindmap'));
const TopicFlashcards = lazy(() => import('../components/views/TopicFlashcards'));
const FlashcardsView = lazy(() => import('../components/views/FlashcardsView'));
const MindmapView = lazy(() => import('../components/views/MindmapView'));
const PowerHourView = lazy(() => import('../components/views/PowerHourView'));
const ExamTonightView = lazy(() => import('../components/views/ExamTonightView'));
const VisualLabView = lazy(() => import('../components/views/VisualLabView'));
const LessonView = lazy(() => import('../components/LessonView'));
import useFocusTimer from '../hooks/useFocusTimer';
import { LAST_PROJECT_KEY } from '../utils/dailyProgress';
import { aiName } from '../utils/persona';
import usePlan from '../hooks/usePlan';
import { emitLimit, emitPlanChanged } from '../utils/plan';
import { isNativeApp, isAppShell } from '../utils/platform';

// Inside the phone app: no sidebar or tour; a back button and tool chips instead
const APP_SHELL = isAppShell();
const APP_TOOLS = [
    ['power', 'Power Hour'], ['cram', 'Exam Tonight'], ['chat', 'Ask'], ['quiz', 'Quiz'], ['flashcards', 'Flashcards'],
    ['notes', 'Notes'], ['mindmap', 'Mind map'], ['path', 'Path'], ['qa', 'Q&A'], ['lab', 'Visual Lab'], ['knowledge', 'Graph'],
];


// One chat message's Markdown. Memoized so that while an answer streams in,
// only that message re-renders, not the whole conversation.
const ChatMarkdown = React.memo(({ content, role, sources, onOpenSource }) => (
    <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
            a: ({ node, ...props }) => {
                // Inline citation links (e.g. href="1")
                if (props.href && !isNaN(props.href) && sources) {
                    const source = sources[parseInt(props.href) - 1];
                    if (source) {
                        return (
                            <button
                                onClick={(e) => { e.preventDefault(); onOpenSource(source); }}
                                className="inline-flex items-center justify-center gap-0.5 min-w-[32px] h-[20px] px-1.5 mx-0.5 text-[10px] font-bold text-white bg-[#1E5C42]/90 hover:bg-[#163628] rounded shadow-sm transition-all cursor-pointer align-text-top"
                                title={`Source ${props.href}: ${source.doc_name}`}
                            >
                                <FileText className="h-2.5 w-2.5 opacity-80 shrink-0" />
                                <span>{props.href}</span>
                            </button>
                        );
                    }
                }
                if (props.href && props.href.startsWith('http') && !props.href.includes(window.location.origin)) {
                    return <a {...props} target="_blank" rel="noopener noreferrer" className="text-[#1E5C42] hover:underline" />;
                }
                return (
                    <button
                        onClick={(e) => { e.preventDefault(); onOpenSource({ doc_name: String(props.children) }); }}
                        className="text-[#1E5C42] hover:underline hover:text-[#6B5F55] cursor-pointer bg-transparent border-none p-0 inline font-medium"
                        title={`Open document: ${props.children}`}
                    >
                        {props.children}
                    </button>
                );
            },
        }}
    >
        {role === 'assistant' ? content.replace(/(?:&lt;|<|\[)?source\s+(\d+)(?:&gt;|>|\])?/gi, '[$1]($1)') : content}
    </ReactMarkdown>
));

// Utility Components
const PomodoroTimer = lazy(() => import('../components/PomodoroTimer'));
const AITutorChat = lazy(() => import('../components/AITutorChat'));
const BookmarksPanel = lazy(() => import('../components/BookmarksPanel'));
const GlobalSearch = lazy(() => import('../components/GlobalSearch'));
const GamificationPanel = lazy(() => import('../components/GamificationPanel'));
import { ProjectViewSkeleton } from '../components/Skeleton';
const AddDocumentModal = lazy(() => import('../components/AddDocumentModal'));


// Chat Agentic Components
import { CommandPicker, CommandParamForm } from '../components/chat/ChatCommands';
import { ToolLoadingCard, ToolResultCard, ToolErrorCard } from '../components/chat/ToolResultCard';
const DocumentReader = lazy(() => import('../components/chat/DocumentReader'));
import ErrorBoundary from '../components/ErrorBoundary';


// ── Chat time log helpers ───────────────────────────────────────────
const formatChatTime = (iso) => {
    const d = new Date(iso);
    return isNaN(d) ? '' : d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
};
const chatDayLabel = (iso) => {
    const d = new Date(iso);
    if (isNaN(d)) return '';
    const today = new Date();
    const yesterday = new Date();
    yesterday.setDate(today.getDate() - 1);
    if (d.toDateString() === today.toDateString()) return 'Today';
    if (d.toDateString() === yesterday.toDateString()) return 'Yesterday';
    return d.toLocaleDateString([], { weekday: 'short', day: 'numeric', month: 'short', year: d.getFullYear() === today.getFullYear() ? undefined : 'numeric' });
};
const welcomeMessage = (settings) => ({
    role: 'system',
    content: `Hi! I'm ${aiName(settings)} ${settings.aiAvatar || '✨'} Ask me anything about your documents — or try "explain like I'm 12", "quiz me", or "give me a memory trick".`,
});

const ViewLoader = () => (
    <div className="h-full flex items-center justify-center">
        <div className="h-10 w-10 rounded-2xl bg-[#1E5C42]/70 animate-pulse" />
    </div>
);

const ProjectView = () => {
    const { projectId } = useParams();
    const navigate = useNavigate();
    const toast = useToast();
    const { user } = useAuth();
    const { settings } = useSettings();
    const isDark = settings?.darkMode ?? false;
    const { data: gamificationData } = useGamification();
    const [showGamification, setShowGamification] = useState(false);
    const [searchParams] = useSearchParams();
    const askParam = searchParams.get('ask');
    const [activeTab, setActiveTab] = useState(() => {
        const tool = searchParams.get('tool');
        if (tool && tool !== 'general') return tool;
        const saved = sessionStorage.getItem(`lumina_tab_${projectId}`);
        // 'general' was a menu toggle, not a real view
        // First visit opens on the Learning Path: one clear next step, plus the memory curve
        return saved && saved !== 'general' ? saved : 'path';
    });
    const [labTopic, setLabTopic] = useState('');
    // Six-step lesson opened from the adaptive plan; planVersion refreshes the plan after it
    const [lessonTopic, setLessonTopic] = useState(null);
    const [planVersion, setPlanVersion] = useState(0);
    // Deep mode: Topper answers from the stronger model (monthly allowance)
    const { plan: myPlan } = usePlan();
    const [deepMode, setDeepMode] = useState(false);
    // No limit (limit null, e.g. while plan limits are switched off) means Deep is open to everyone
    const deepUnlimited = !!myPlan?.usage?.deep && myPlan.usage.deep.limit == null;
    const deepLeft = deepUnlimited ? Infinity : myPlan?.usage?.deep?.limit ? Math.max(0, myPlan.usage.deep.limit - myPlan.usage.deep.used) : 0;
    const toggleDeep = () => {
        if (deepMode) { setDeepMode(false); return; }
        if (!deepUnlimited && !myPlan?.usage?.deep?.limit) {
            emitLimit({
                code: 'limit_reached', plan: myPlan?.plan || 'free', feature: 'deep', limit: 0, used: 0,
                message: 'Deep answers use our most capable model for tricky questions. They come with Topper.',
            });
            return;
        }
        setDeepMode(true);
    };
    // Stable handle for memoized chat messages; always calls the latest handler
    const openSourceRef = useRef(null);
    const openSourceStable = useRef((source) => openSourceRef.current?.(source)).current;
    useFocusTimer(user?.id);
    useEffect(() => {
        try { localStorage.setItem(LAST_PROJECT_KEY, projectId); } catch { /* ignore */ }
    }, [projectId]);
    const [messages, setMessages] = useState([]);
    const messagesEndRef = useRef(null);

    // Time log: stamp every newly added message with the time it appeared
    const stampedCountRef = useRef(0);
    useEffect(() => {
        const from = stampedCountRef.current;
        if (messages.length < from) {
            stampedCountRef.current = messages.length; // chat was cleared
            return;
        }
        stampedCountRef.current = messages.length;
        if (messages.slice(from).some(m => !m.timestamp)) {
            const now = new Date().toISOString();
            setMessages(prev => prev.map((m, i) => (i >= from && !m.timestamp ? { ...m, timestamp: now } : m)));
        }
    }, [messages]);

    const [{ run, steps }, setTourState] = useState({
        run: false,
        steps: [
            {
                content: <h2>Welcome to your project workspace!</h2>,
                locale: { skip: 'Skip tutorial' },
                placement: 'center',
                target: 'body',
            },
            {
                content: 'Power Hour: bite-sized lessons with instant quizzes. The fastest way through your whole book.',
                placement: 'right',
                target: '#tour-nav-power',
                title: 'Power Hour ⚡',
            },
            {
                content: 'This is your Learning Path, which guides you through topics.',
                placement: 'right',
                target: '#tour-nav-path',
                title: 'Learning Path',
            },
            {
                content: 'Explore connections between topics using the Knowledge Graph.',
                placement: 'right',
                target: '#tour-nav-knowledge',
                title: 'Knowledge Graph',
            },
            {
                content: 'Study Tools: Notes, Quizzes, Flashcards, Mindmaps and Q&A for any topic.',
                placement: 'right',
                target: '#tour-nav-general',
                title: 'Study Tools',
            }
        ],
    });

    // Tutorial scrolling fix: we will pass disableScrolling to Joyride component later
    // but we can also set it in tour options if needed.

    // useEffect for tutorial has been moved below state declarations

    const handleJoyrideCallback = (data) => {
        const { status } = data;
        if ([STATUS.FINISHED, STATUS.SKIPPED].includes(status) && user?.id) {
            localStorage.setItem(`hasSeenProjectTutorial_${user.id}`, 'true');
            setTourState(prev => ({ ...prev, run: false }));
        }
    };

    // Chat scrolling: follow new messages only while the reader is at the
    // bottom; scroll the chat container itself (scrollIntoView also scrolled
    // parent layouts and fought the reader on every streamed chunk).
    const chatScrollRef = useRef(null);
    const stickToBottomRef = useRef(true);
    const [showJumpToLatest, setShowJumpToLatest] = useState(false);

    const scrollToBottom = (smooth = false) => {
        const el = chatScrollRef.current;
        if (!el) return;
        el.scrollTo({ top: el.scrollHeight, behavior: smooth ? 'smooth' : 'auto' });
        stickToBottomRef.current = true;
        setShowJumpToLatest(false);
    };

    const handleChatScroll = () => {
        const el = chatScrollRef.current;
        if (!el) return;
        const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
        stickToBottomRef.current = atBottom;
        setShowJumpToLatest(!atBottom);
    };

    useEffect(() => {
        if (activeTab === 'chat' && stickToBottomRef.current) {
            // Wait for the DOM to paint the new content, then follow it
            requestAnimationFrame(() => scrollToBottom(false));
        }
    }, [messages, activeTab]);

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
    const [loadingMsgIdx, setLoadingMsgIdx] = useState(0);
    const [deleteConfirmDoc, setDeleteConfirmDoc] = useState(null);
    const [deletingDocIds, setDeletingDocIds] = useState(new Set());
    const [loading, setLoading] = useState(false);
    const [isProcessingDocs, setIsProcessingDocs] = useState(true);
    // Per-document SSE stage: { [docId]: 'extracting'|'chunking'|'embedding'|'topics'|'graph'|'completed'|'failed' }
    const [docStages, setDocStages] = useState({}); // docId -> { stage, progress, message } from the progress stream
    const [uploadsInFlight, setUploadsInFlight] = useState([]); // [{ key, name, size, pct }]
    const [justReady, setJustReady] = useState(() => new Set()); // docs that finished a moment ago
    const [pausedUploads, setPausedUploads] = useState([]); // uploads interrupted by a refresh
    // A book still "processing" with no live updates and no server heartbeat for 20 min
    // was interrupted (e.g. the server restarted); say so instead of showing a frozen bar
    const isStalled = (doc) => !docStages[doc.id] && !!doc.updated_at
        && Date.now() - new Date(doc.updated_at).getTime() > 20 * 60 * 1000;
    const resumeInputRef = useRef(null);
    const uploadsInFlightRef = useRef([]);
    uploadsInFlightRef.current = uploadsInFlight;
    const uploadFilesRef = useRef({}); // upload key -> File, so a stalled upload can be retried
    const [, setNowTick] = useState(0);
    useEffect(() => { // re-render every 15 s while uploading, so a stall shows up
        if (!uploadsInFlight.length) return undefined;
        const t = setInterval(() => setNowTick(n => n + 1), 15000);
        return () => clearInterval(t);
    }, [uploadsInFlight.length]);

    useEffect(() => { setPausedUploads(pendingUploads(projectId)); }, [projectId]);

    // Leaving mid-upload pauses it: say so before the tab closes
    useEffect(() => {
        if (!uploadsInFlight.some(u => u.pct < 100)) return undefined;
        const warn = (e) => { e.preventDefault(); e.returnValue = ''; };
        window.addEventListener('beforeunload', warn);
        return () => window.removeEventListener('beforeunload', warn);
    }, [uploadsInFlight]);
    const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
    const [isLeftCollapsed, setIsLeftCollapsed] = useState(false);
    const [showRightSidebarUpload, setShowRightSidebarUpload] = useState(false);
    const [isMobileDocsOpen, setIsMobileDocsOpen] = useState(false);
    const [isRightCollapsed, setIsRightCollapsed] = useState(false);
    // Documents panel width (desktop): drag its left edge; remembered per browser
    const DOCS_MIN = 280, DOCS_MAX = 560, DOCS_DEFAULT = 320;
    const [docsWidth, setDocsWidth] = useState(() => {
        try {
            const w = Number(localStorage.getItem('lumina_docs_width'));
            return w >= DOCS_MIN && w <= DOCS_MAX ? w : DOCS_DEFAULT;
        } catch { return DOCS_DEFAULT; }
    });
    const [resizingDocs, setResizingDocs] = useState(false);
    const startDocsResize = (e) => {
        e.preventDefault();
        setResizingDocs(true);
        const onMove = (ev) => setDocsWidth(Math.min(DOCS_MAX, Math.max(DOCS_MIN, window.innerWidth - ev.clientX)));
        const onUp = () => {
            setResizingDocs(false);
            window.removeEventListener('pointermove', onMove);
            window.removeEventListener('pointerup', onUp);
            setDocsWidth(w => { try { localStorage.setItem('lumina_docs_width', String(w)); } catch { /* ignore */ } return w; });
        };
        window.addEventListener('pointermove', onMove);
        window.addEventListener('pointerup', onUp);
    };

    // Derived: force expanded when mobile drawers open
    const leftCollapsed = isLeftCollapsed && !isMobileMenuOpen;

    // New Feature States
    const [showSearch, setShowSearch] = useState(false);
    const [showPomodoro, setShowPomodoro] = useState(false);
    const [showAITutor, setShowAITutor] = useState(false);
    const [showBookmarks, setShowBookmarks] = useState(false);
    const [showAddDocModal, setShowAddDocModal] = useState(false);
    const [zenMode, setZenMode] = useState(false);
    const [tutorTopic, setTutorTopic] = useState(null);
    const [showProfileMenu, setShowProfileMenu] = useState(false);

    // Topics State
    const [availableTopics, setAvailableTopics] = useState([]);
    const [allProjectTopics, setAllProjectTopics] = useState([]);
    const [topicMeta, setTopicMeta] = useState({}); // topic -> { order, level, chapter, prerequisites }
    const [documentTopics, setDocumentTopics] = useState({});

    // Learning Path Integration State
    const [preSelectedTopic, setPreSelectedTopic] = useState(null);
    const [preSelectedQuizMode, setPreSelectedQuizMode] = useState(null);
    const [cameFromPath, setCameFromPath] = useState(false);

    // Pre-generated data from chat @ commands (passed to views via "Open" button)
    const [preGeneratedNotes, setPreGeneratedNotes] = useState(null);
    const [preGeneratedQA, setPreGeneratedQA] = useState(null);
    const [preGeneratedQuiz, setPreGeneratedQuiz] = useState(null);

    // Auto-generate flags — set by LearningPath when user clicks "Generate Notes" / "Start Q&A"
    const [notesAutoGenerate, setNotesAutoGenerate] = useState(false);
    const [qaAutoGenerate, setQAAutoGenerate] = useState(false);

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

    // PDF Viewer State
    const [activePDF, setActivePDF] = useState(null);

    // Quiz/Q&A Active State (hides sidebars during generation/active)
    const [isQuizActive, setIsQuizActive] = useState(false);
    const [isQAActive, setIsQAActive] = useState(false);

    // Combined sidebar hidden state
    const isSidebarHidden = isQuizActive || isQAActive || zenMode;

    // File Upload Ref
    const fileInputRef = useRef(null);

    // @ Command System State
    const [showCommandPicker, setShowCommandPicker] = useState(false);
    const [commandFilter, setCommandFilter] = useState('');
    const [activeCommand, setActiveCommand] = useState(null); // command object when param form is shown
    const [toolLoading, setToolLoading] = useState(false);

    // Add loading state for ProjectView
    const [projectViewLoading, setProjectViewLoading] = useState(true);
    const [fetchError, setFetchError] = useState(false);
    const [isSlowLoad, setIsSlowLoad] = useState(false);

    // Ref to ensure fetchTopics is only called once per mount, not on every tab change
    const topicsFetchedRef = useRef(false);

    // Tutorial visibility effect (moved from top to fix TDZ ReferenceError)
    useEffect(() => {
        if (!projectViewLoading && !fetchError && user?.id && settings.onboardingComplete) {
            const hasSeenProjectTutorial = localStorage.getItem(`hasSeenProjectTutorial_${user?.id}`);
            if (!hasSeenProjectTutorial) {
                // Marked as seen only when finished or skipped (see handleJoyrideCallback)
                setTimeout(() => setTourState(prev => ({ ...prev, run: true })), 500);
            }
        }
    }, [projectViewLoading, fetchError, user?.id, settings.onboardingComplete]);

    useEffect(() => {
        let intervalId;
        
        const rotationInterval = setInterval(() => {
            setLoadingMsgIdx(i => i + 1);
        }, 3000);

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

        // Helper to check if any document has failed
        const isAnyDocFailed = (docs) => {
            if (!docs || docs.length === 0) return false;
            return docs.some(d => d.upload_status === 'failed');
        };

        const initialLoad = async () => {
            // Show 'waking up' banner if load takes more than 3s
            const slowTimer = setTimeout(() => {
                setIsSlowLoad(true);
            }, 3000);

            let docData = null;
            try {
                // No local race-timeout — rely on the axios 60s timeout so Azure
                // cold starts (30-50s) don't prematurely trigger the error screen.
                docData = await fetchDocuments();
            } catch (err) {
                console.warn('Initial document load failed:', err.message);
                setFetchError(true);
                setProjectViewLoading(false);
                clearInterval(rotationInterval);
                clearTimeout(slowTimer);
                return;
            } finally {
                clearTimeout(slowTimer);
                setIsSlowLoad(false);
            }

            // Restore chat messages from session cache, or start fresh
            // Restore chat: this tab's cache first, then saved server history
            // (with real timestamps), otherwise a fresh welcome.
            let restored = null;
            try {
                const parsed = JSON.parse(sessionStorage.getItem(`lumina_chat_${projectId}`) || 'null');
                if (Array.isArray(parsed) && parsed.length > 0) restored = parsed;
            } catch { /* ignore */ }
            if (!restored) {
                try {
                    const history = await getChatHistory(projectId);
                    if (Array.isArray(history) && history.length > 0) {
                        restored = [
                            welcomeMessage(settings),
                            ...history.map(m => ({ role: m.role, content: m.content, timestamp: m.created_at || undefined })),
                        ];
                    }
                } catch (histErr) {
                    console.warn('Failed to load chat history:', histErr);
                }
            }
            const initialMessages = restored || [welcomeMessage(settings)];
            stampedCountRef.current = initialMessages.length; // don't re-stamp restored messages
            setMessages(initialMessages);

            const docs = docData?.documents || [];
            const processingDocs = docs.filter(d =>
                d.upload_status === 'pending' ||
                d.upload_status === 'processing' ||
                d.upload_status === 'embedding' ||
                d.upload_status === 'queued'
            );
            const docsProcessing = processingDocs.length > 0;
            setIsProcessingDocs(docsProcessing);
            setProjectViewLoading(false);

            if (!docsProcessing) {
                fetchTopics();
                topicsFetchedRef.current = true;
                return;
            }

            // Open one SSE connection per processing document.
            // Each stream delivers live stage events: extracting → chunking → embedding → topics → graph → completed/failed.
            // Topics are fetched exactly once when the FIRST doc completes.
            const sseCleanups = [];

            processingDocs.forEach((doc) => {
                const cleanup = subscribeDocumentProgress(
                    doc.id,
                    async (event) => {
                        const { stage } = event;
                        if (stage === 'keepalive') return;

                        // Live stage + percentage for the progress bar
                        setDocStages(prev => ({ ...prev, [doc.id]: { stage, progress: event.progress, message: event.message } }));

                        if (stage === 'completed') {
                            // Hold the "Ready" state on screen for a moment before the bar goes away
                            setJustReady(prev => new Set(prev).add(doc.id));
                            setTimeout(() => setJustReady(prev => { const n = new Set(prev); n.delete(doc.id); return n; }), 2600);
                        }

                        if (stage === 'completed' || stage === 'failed') {
                            // Refresh this document's status from DB to get error_message etc.
                            const refreshed = await fetchDocuments();
                            const remaining = (refreshed?.documents || []).filter(d =>
                                d.upload_status === 'pending' ||
                                d.upload_status === 'processing' ||
                                d.upload_status === 'embedding' ||
                                d.upload_status === 'queued'
                            );
                            if (remaining.length === 0) {
                                setIsProcessingDocs(false);
                                if (!topicsFetchedRef.current) {
                                    fetchTopics();
                                    topicsFetchedRef.current = true;
                                }
                            }
                        }
                    },
                    (err) => {
                        // SSE failed (network drop etc.) — fall back to one-time poll
                        console.warn(`SSE connection lost for doc ${doc.id}, falling back to poll`);
                        setTimeout(() => fetchDocuments(), 5000);
                    }
                );
                sseCleanups.push(cleanup);
            });

            // Store cleanups so the outer return() can close all SSE connections on unmount
            intervalId = { close: () => sseCleanups.forEach(fn => fn()) };
        };

        initialLoad();

        return () => {
            if (intervalId?.close) intervalId.close();
            else clearInterval(intervalId);
            clearInterval(rotationInterval);
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

    const fetchTopics = async () => {
        try {
            const data = await getTopics(projectId);
            if (data.all && data.by_doc) {
                // Keep the server's learning order (prerequisites first) — the
                // same order the Learning Path uses. Never re-sort here.
                const uniqueAll = [...new Set(data.all)];
                setAllProjectTopics(uniqueAll);
                setAvailableTopics(uniqueAll);
                setDocumentTopics(data.by_doc);
                setTopicMeta(data.meta || {});
            } else if (Array.isArray(data)) {
                const unique = [...new Set(data)];
                setAvailableTopics(unique);
                setAllProjectTopics(unique);
            }
        } catch (error) {
            console.error('Failed to fetch topics', error);
        }
    };

    // fetchTopics on tab change — only if topics haven't been loaded yet
    useEffect(() => {
        if (!isProcessingDocs && !topicsFetchedRef.current) {
            if (activeTab === 'power' || activeTab === 'cram' || activeTab === 'lab' || activeTab === 'chat' || activeTab === 'quiz' || activeTab === 'qa' || activeTab === 'notes' || activeTab === 'path') {
                fetchTopics();
                topicsFetchedRef.current = true;
            }
        }
    }, [activeTab, projectId, isProcessingDocs]);

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
            // Preserve learning order while filtering to the selected documents
            setAvailableTopics(allProjectTopics.filter(t => filtered.has(t)));
        } else {
            // If nothing selected (Global) OR we don't have mappings, show ALL.
            setAvailableTopics(allProjectTopics);
        }
    }, [selectedDocuments, documentTopics, allProjectTopics]);

    // Default selection: start with every ready document selected, so study
    // tools work straight away (once; a later "Deselect all" is respected)
    const autoSelected = useRef(false);
    useEffect(() => {
        if (autoSelected.current || selectedDocuments.length) return;
        const ready = documents.filter(d => d.upload_status === 'completed');
        if (ready.length) {
            autoSelected.current = true;
            setSelectedDocuments(ready.map(d => d.id));
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
                if (showProfileMenu) setShowProfileMenu(false);
            }
        };

        document.addEventListener('keydown', handleKeyDown);
        return () => document.removeEventListener('keydown', handleKeyDown);
    }, [showSearch, showPomodoro, showAITutor, showBookmarks, zenMode]);

    // Close profile menu when clicking outside
    useEffect(() => {
        const handleClickOutside = (e) => {
            if (showProfileMenu && !e.target.closest('.profile-dropdown')) {
                setShowProfileMenu(false);
            }
        };

        if (showProfileMenu) {
            document.addEventListener('click', handleClickOutside);
            return () => document.removeEventListener('click', handleClickOutside);
        }
    }, [showProfileMenu]);

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
        setMessages([welcomeMessage(settings)]);
        setInputMessage('');
        setActiveCommand(null);
        setShowCommandPicker(false);
        sessionStorage.removeItem(chatCacheKey);
    };

    // --- @ Command: Input change handler ---
    const handleInputChange = (e) => {
        const val = e.target.value;
        setInputMessage(val);

        // Detect @ at start of input or after space
        const atMatch = val.match(/(?:^|\s)@(\w*)$/);
        if (atMatch) {
            setCommandFilter(atMatch[1]);
            setShowCommandPicker(true);
        } else {
            setShowCommandPicker(false);
            setCommandFilter('');
        }
    };

    // --- @ Command: Select a command from picker ---
    const handleCommandSelect = (command) => {
        setShowCommandPicker(false);
        setCommandFilter('');
        setInputMessage('');
        setActiveCommand(command);
    };

    // --- @ Command: Execute a tool command ---
    const handleToolExecute = async (toolType, params) => {
        if (selectedDocuments.length === 0) {
            toast.warning('Please select at least one document from the sidebar first.');
            return;
        }

        setActiveCommand(null);
        setToolLoading(true);

        // Build a user-facing label for what was requested
        const labels = {
            notes: `@Notes — ${params.noteType || 'Summary'}${params.topic ? ` about "${params.topic}"` : ''}`,
            qa: `@Q&A${params.topic ? ` about "${params.topic}"` : ''} — ${params.numQuestions || 5} questions (${params.answerSize || 'medium'})`,
            quiz: `@Quiz${params.topic ? ` about "${params.topic}"` : ''} — ${params.numQuestions || 5} MCQs (${params.difficulty || 'medium'})`,
            mindmap: `@Mindmap — "${params.topic}"`,
            flashcards: `@Flashcards — "${params.topic}" (${params.numCards || 8} cards)`,
        };

        // Add user command message
        setMessages(prev => [...prev,
        { role: 'user', content: labels[toolType] || `@${toolType}`, type: 'tool_command' },
        { role: 'assistant', type: 'tool_loading', toolType, toolParams: params }
        ]);

        try {
            let result;
            switch (toolType) {
                case 'notes':
                    result = await generateNotes(projectId, params.noteType, params.topic || '', selectedDocuments);
                    break;
                case 'qa':
                    result = await generateSubjectiveTest(projectId, params.topic || '', parseInt(params.numQuestions) || 5, selectedDocuments, params.answerSize || 'medium');
                    break;
                case 'quiz':
                    result = await generateMCQ(projectId, params.topic || '', parseInt(params.numQuestions) || 5, selectedDocuments, params.difficulty || 'medium');
                    break;
                case 'mindmap':
                    result = await generateMindmap(
                        projectId,
                        params.title || `${params.topic} - Mindmap`,
                        params.topic,
                        selectedDocuments
                    );
                    break;
                case 'flashcards':
                    result = await generateFlashcardsWithAI(
                        projectId,
                        params.topic,
                        parseInt(params.numCards) || 10,
                        selectedDocuments
                    );
                    break;
                default:
                    throw new Error(`Unknown tool: ${toolType}`);
            }

            // Replace loading card with result card
            setMessages(prev => {
                const updated = [...prev];
                const loadingIdx = updated.findLastIndex(m => m.type === 'tool_loading' && m.toolType === toolType);
                if (loadingIdx !== -1) {
                    updated[loadingIdx] = {
                        role: 'assistant',
                        type: 'tool_result',
                        toolType,
                        toolParams: params,
                        toolData: result,
                    };
                }
                return updated;
            });

            recordActivity(projectId, toolType === 'notes' ? 'notes' : toolType === 'qa' ? 'qa' : 'chat');
        } catch (error) {
            console.error(`Tool ${toolType} error:`, error);
            // Replace loading card with error card
            setMessages(prev => {
                const updated = [...prev];
                const loadingIdx = updated.findLastIndex(m => m.type === 'tool_loading' && m.toolType === toolType);
                if (loadingIdx !== -1) {
                    updated[loadingIdx] = {
                        role: 'assistant',
                        type: 'tool_error',
                        toolType,
                        toolParams: params,
                        error: error?.response?.data?.detail || error.message || 'Generation failed',
                    };
                }
                return updated;
            });
        } finally {
            setToolLoading(false);
        }
    };

    // --- @ Command: Open result in its dedicated view ---
    const handleToolOpen = (toolType, toolParams, toolData) => {
        const topic = toolParams?.topic || '';
        switch (toolType) {
            case 'notes':
                if (topic) setPreSelectedTopic(topic);
                // Pass pre-generated notes content + noteType so the view displays it directly
                setPreGeneratedNotes({
                    content: toolData?.content || '',
                    noteType: toolParams?.noteType || 'Comprehensive Summary',
                    topic: topic,
                });
                setActiveTab('notes');
                break;
            case 'qa':
                if (topic) setPreSelectedTopic(topic);
                // Pass pre-generated Q&A data so the view displays it directly
                setPreGeneratedQA(toolData);
                setActiveTab('qa');
                break;
            case 'quiz':
                if (topic) setPreSelectedTopic(topic);
                // Pass pre-generated quiz data so the view displays it directly
                setPreGeneratedQuiz(toolData);
                setActiveTab('quiz');
                break;
            case 'mindmap':
                setActiveTab('mindmap');
                toast.success('Mindmap generated! Opening Mindmaps view...');
                break;
            case 'flashcards':
                setActiveTab('flashcards');
                toast.success('Flashcards generated! Opening Flashcards view...');
                break;
        }
    };

    // ?ask=… (from the app's feed): ask it as soon as the book's files are selected
    const askRef = useRef(askParam);
    useEffect(() => {
        if (askRef.current && selectedDocuments.length > 0 && !loading) {
            setInputMessage(askRef.current);
        }
    }, [selectedDocuments.length, loading]);
    useEffect(() => {
        if (askRef.current && inputMessage === askRef.current) {
            askRef.current = null;
            handleSendMessage({ preventDefault() {} });
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [inputMessage]);

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
        stickToBottomRef.current = true; // sending always jumps to the latest message
        setMessages(newMessages);
        setInputMessage('');
        setLoading(true);

        // Create a placeholder for the assistant's response
        setMessages(prev => [...prev, { role: 'assistant', content: '', sources: [] }]);

        try {
            const history = newMessages
                .filter(m => m.role !== 'system' && (!m.type || m.type === 'tool_command'))
                .map(m => ({
                    role: m.role,
                    content: m.content || ''
                }));

            // Inject student profile as a system context prefix (only if any profile data exists)
            const { studentName, learningGoal, selfLevel, tutorStyle } = settings;
            const contextParts = [];
            if (studentName) contextParts.push(`The student's name is ${studentName}.`);
            if (learningGoal) contextParts.push(`Their learning goal is: ${learningGoal}.`);
            if (selfLevel) contextParts.push(`Self-assessed level: ${selfLevel}.`);
            if (tutorStyle && tutorStyle !== 'balanced') contextParts.push(`Preferred tutor style: ${tutorStyle}.`);
            if (contextParts.length > 0) {
                history.unshift({ role: 'system', content: contextParts.join(' ') });
            }

            await chatMessageStream(
                projectId,
                userMsg,
                history,
                selectedDocuments,
                (chunkText) => {
                    // Replace only the assistant placeholder; earlier messages keep
                    // their identity so they don't re-render on every token
                    setMessages(prev => {
                        const last = prev[prev.length - 1];
                        if (!last || last.role !== 'assistant') return prev;
                        return [...prev.slice(0, -1), { ...last, content: chunkText }];
                    });
                },
                (finalResult) => {
                    if (deepMode) emitPlanChanged(); // refresh the Deep counter
                    // Final update with sources
                    setMessages(prev => {
                        const last = prev[prev.length - 1];
                        if (!last || last.role !== 'assistant') return prev;
                        return [...prev.slice(0, -1), {
                            ...last,
                            content: finalResult.answer,
                            sources: finalResult.sources,
                            completedAt: new Date().toISOString(),
                        }];
                    });

                    // Track chat activity for heatmap
                    recordActivity(projectId, 'chat');
                    setLoading(false);
                },
                { deep: deepMode }
            );
        } catch (error) {
            console.error("Chat error", error);
            setMessages(prev => [
                ...prev.slice(0, -1),
                { ...prev[prev.length - 1], content: "Sorry, I encountered an error processing your request." },
            ]);
            setLoading(false);
        }
    };

    const handleFileUpload = async (files, bookOptions = {}) => {
        if (!files || files.length === 0) return;
        const tooBig = Array.from(files).find(f => f.size > MAX_UPLOAD_MB * 1024 * 1024);
        if (tooBig) {
            toast.error(`"${tooBig.name}" is ${(tooBig.size / 1024 / 1024).toFixed(0)} MB. The limit is ${MAX_UPLOAD_MB} MB per file.`);
            return;
        }
        // Skip books already uploading or already in this project (double taps, re-picks)
        const inFlight = new Set(uploadsInFlightRef.current.map(u => `${u.name}|${u.size}`));
        const inProject = new Set(documents.filter(d => d.upload_status !== 'failed').map(d => `${d.filename}|${d.file_size}`));
        const fresh = Array.from(files).filter(f => !inFlight.has(`${f.name}|${f.size}`) && !inProject.has(`${f.name}|${f.size}`));
        const skipped = files.length - fresh.length;
        if (skipped) toast.info(skipped === 1 && files.length === 1 ? `"${files[0].name}" is already in this project.` : `${skipped} book${skipped > 1 ? 's are' : ' is'} already in this project, skipped.`);
        setShowUploadModal(false);
        if (!fresh.length) return;
        files = fresh;
        // Show each upload's progress in the document list straight away
        const entries = Array.from(files).map((file, i) => ({ key: `${Date.now()}-${i}`, name: file.name, size: file.size, pct: 0, file, startedAt: Date.now() }));
        uploadFilesRef.current = { ...uploadFilesRef.current, ...Object.fromEntries(entries.map(e => [e.key, e.file])) };
        // Re-picking a paused file resumes it, so it no longer shows as paused
        setPausedUploads(prev => prev.filter(p => !entries.some(e => e.name === p.name && e.size === p.size)));
        setUploadsInFlight(prev => [...prev, ...entries.map(({ file, ...e }) => e)]);
        setShowUploadModal(false);
        const setPct = (key, pct) => setUploadsInFlight(prev => prev.map(u => (u.key === key ? { ...u, pct: Math.max(u.pct, pct) } : u)));
        try {
            // Upload files in parallel for better performance
            const results = await Promise.allSettled(
                entries.map(({ key, file }) => uploadDocument(projectId, file, (pct) => setPct(key, pct), bookOptions))
            );
            results.forEach((r, i) => {
                if (r.status !== 'rejected') return;
                const error = r.reason;
                console.error("Upload error", error);
                const detail = error?.response?.data?.detail;
                const why = typeof detail === 'string' ? detail
                    : error?.response?.status === 402 ? "your plan's book limit is reached"
                    : error?.code === 'ECONNABORTED' ? 'the server took too long to answer'
                    : !error?.response ? "couldn't reach the server" : `server error ${error.response.status}`;
                toast.error(`${entries[i].name}: ${why}`);
            });
            await fetchDocuments();
        } finally {
            const done = new Set(entries.map(e => e.key));
            setUploadsInFlight(prev => prev.filter(u => !done.has(u.key)));
            setPausedUploads(pendingUploads(projectId));
        }
    };

    const [retryingIds, setRetryingIds] = useState(() => new Set());
    const retryDoc = async (doc) => {
        if (retryingIds.has(doc.id)) return;
        setRetryingIds(prev => new Set(prev).add(doc.id));
        try {
            await retryDocument(projectId, doc.id);
            setDocuments(prev => prev.map(d => (d.id === doc.id ? { ...d, upload_status: 'pending', error_message: null } : d)));
            fetchDocuments();
        } catch (error) {
            const detail = error?.response?.data?.detail;
            toast.error(typeof detail === 'string' ? detail : `Couldn't retry "${doc.filename}". Try again in a moment.`);
        } finally {
            setRetryingIds(prev => { const next = new Set(prev); next.delete(doc.id); return next; });
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
    // Called as a plain function, not <NavItem/>: defined inside this component,
    // it would be a new component type every render and remount the buttons,
    // which made the guided-tour tooltips jump around.
    const markTopicMastered = (topic) => {
        setLearningProgress(prev => {
            if (prev.has(topic)) return prev;
            const next = new Set(prev);
            next.add(topic);
            saveLearningProgress(projectId, [...next]).catch(err =>
                console.warn('Failed to save progress:', err)
            );
            return next;
        });
    };

    const openVisualLab = (topic) => {
        setLabTopic(topic);
        setActiveTab('lab');
    };

    // Open a document in the reader; with a citation, jump to and highlight its passage
    const handleOpenSource = (source) => {
        const doc = documents.find(d => d.id === source.doc_id || d.filename === source.doc_name);
        const documentId = source.doc_id || doc?.id;
        if (!documentId) {
            toast.error("Couldn't find that book in this project.");
            return;
        }
        setActivePDF({
            documentId,
            title: doc ? doc.filename : (source.doc_name || 'Document'),
            passage: source.chunk_text || '',
        });
    };
    openSourceRef.current = handleOpenSource;

    if (projectViewLoading && documents.length === 0) {
        return (
            <div className="relative">
                <ProjectViewSkeleton />
                {isSlowLoad && (
                    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 flex items-center gap-3 bg-[#163628] text-white px-5 py-3 rounded-2xl shadow-xl text-sm">
                        <WifiOff className="h-4 w-4 shrink-0 text-[#1E5C42]" />
                        <span>Taking longer than expected… backend may be waking up</span>
                    </div>
                )}
            </div>
        );
    }

    // Error fallback — initial load timed out and no docs
    if (fetchError) {
        return (
            <div className="min-h-screen bg-[#FDF6F0] flex items-center justify-center p-4">
                <div className="text-center max-w-sm">
                    <div className="h-16 w-16 bg-[#FDF6F0] border-2 border-[#E6D5CC] rounded-2xl flex items-center justify-center mx-auto mb-4">
                        <WifiOff className="h-8 w-8 text-[#1E5C42]" />
                    </div>
                    <h2 className="text-xl font-bold text-[#163628] mb-2">Couldn't load project</h2>
                    <p className="text-[#5E5046] text-sm mb-6">
                        Your world has been paused, kindly wait for it to spin again...
                    </p>
                    <button
                        onClick={() => {
                            setFetchError(false);
                            setProjectViewLoading(true);
                            // Trigger remount by navigating to same route (or just re-run)
                            window.location.reload();
                        }}
                        className="inline-flex items-center gap-2 px-6 py-3 bg-[#1E5C42] text-white rounded-xl font-medium hover:bg-[#163628] transition-colors shadow-lg shadow-[#1E5C42]/20"
                    >
                        <RefreshCw className="h-4 w-4" />
                        Retry
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="h-[100dvh] flex overflow-hidden font-sans transition-colors duration-300"
            style={{ ...(APP_SHELL ? { paddingBottom: 'var(--sab)' } : {}), ...(isDark ? {
                background: 'radial-gradient(ellipse at 20% 0%, color-mix(in srgb, var(--dm-accent) 10%, var(--dm-bg)) 0%, var(--dm-bg) 45%, var(--dm-bg) 100%)',
                color: '#e8e2dc'
            } : { background: 'var(--th-bg, #FDF6F0)', color: 'var(--th-text, #163628)' }) }}>

            <Joyride
                onEvent={handleJoyrideCallback}
                continuous
                run={run && !APP_SHELL}
                steps={steps}
                options={TOUR_OPTIONS}
            />

            {/* In-app reader: whole book, jumping to a cited passage when opened from a reference */}
            {activePDF && (
                <ErrorBoundary>
                    <Suspense fallback={null}>
                        <DocumentReader
                            projectId={projectId}
                            documentId={activePDF.documentId}
                            title={activePDF.title}
                            passage={activePDF.passage}
                            onClose={() => setActivePDF(null)}
                        />
                    </Suspense>
                </ErrorBoundary>
            )}

            {/* Mobile Sidebar Overlay */}
            {isMobileMenuOpen && (
                <div
                    className="fixed inset-0 bg-black/50 z-40 md:hidden"
                    onClick={() => setIsMobileMenuOpen(false)}
                />
            )}

            {/* Sidebar - Desktop & Mobile - Hidden when quiz/qa is active */}
            {!isSidebarHidden && !APP_SHELL && (
                <div className={`
                fixed inset-y-0 left-0 z-50 ${leftCollapsed ? 'w-20' : 'w-80'} backdrop-blur-xl border-r flex flex-col transition-all duration-300 ease-in-out md:translate-x-0 md:static md:shrink-0 shadow-2xl md:shadow-none
                ${isMobileMenuOpen ? 'translate-x-0' : '-translate-x-full'}`}
                style={isDark ? {
                    background: 'linear-gradient(180deg, var(--dm-sidebar) 0%, var(--dm-bg) 100%)',
                    borderColor: 'rgba(90,60,30,0.35)'
                } : { background: 'color-mix(in srgb, var(--th-alt, #FDF6F0) 95%, transparent)', borderColor: 'rgba(255,255,255,0.20)'
                }}>
                    <div className={`flex-1 flex flex-col min-h-0 ${leftCollapsed ? 'p-3' : 'px-4 pt-5 pb-3'}`}>
                        <div className={`flex items-center ${leftCollapsed ? 'justify-center' : 'justify-between px-1.5'} mb-6`}>
                            {!leftCollapsed && (
                                <Link to="/dashboard" aria-label="Back to your books" className="rounded-xl"><Logo /></Link>
                            )}
                            <div className="flex items-center gap-1">
                                {/* Desktop collapse toggle */}
                                <button
                                    onClick={() => setIsLeftCollapsed(!isLeftCollapsed)}
                                    className="hidden md:block p-2 hover:bg-[#E6D5CC]/30 rounded-full text-[#5E5046] transition-colors"
                                    title={isLeftCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
                                >
                                    {leftCollapsed ? <ChevronRight className="h-5 w-5" /> : <ChevronLeft className="h-5 w-5" />}
                                </button>
                                {/* Close button for mobile */}
                                <button
                                    onClick={() => setIsMobileMenuOpen(false)}
                                    className="md:hidden p-2 hover:bg-[#E6D5CC]/30 rounded-full text-[#5E5046] transition-colors"
                                >
                                    <X className="h-6 w-6" />
                                </button>
                            </div>
                        </div>

                        <SidebarNav
                            activeTab={activeTab}
                            onSelect={(id) => { setActiveTab(id); setIsMobileMenuOpen(false); }}
                            collapsed={leftCollapsed}
                            isDark={isDark}
                            aiLabel={aiName(settings)}
                        />

                        {/* Profile Section - Fixed at Bottom of Sidebar */}
                        <div className={`shrink-0 ${leftCollapsed ? 'p-3' : 'p-4'} border-t backdrop-blur-sm`}
                            style={isDark ? { borderColor: 'var(--dm-border)', background: 'linear-gradient(to top, var(--dm-sidebar) 0%, color-mix(in srgb, var(--dm-sidebar) 85%, transparent) 100%)' } : { borderColor: 'var(--th-border, rgba(230,213,204,0.5))', background: 'color-mix(in srgb, var(--th-alt, #FDF6F0) 95%, transparent)' }}>
                            <div className={`w-full flex items-center ${leftCollapsed ? 'justify-center' : 'gap-1'}`}>
                                <button
                                    onClick={() => setShowProfileMenu(!showProfileMenu)}
                                    className={`profile-dropdown flex-1 flex items-center ${leftCollapsed ? 'justify-center p-3' : 'gap-3 px-3 py-3'} rounded-xl transition-all group ${isDark ? 'hover:bg-[#20382B]/80' : 'hover:bg-[#E6D5CC] hover:shadow-sm'}`}
                                    title={leftCollapsed ? 'Profile' : undefined}
                                >
                                    <div className="h-10 w-10 bg-gradient-to-br from-[#1E5C42] to-[#163628] rounded-full flex items-center justify-center text-white shadow-md group-hover:shadow-lg transition-shadow shrink-0">
                                        <span className="text-lg leading-none">{settings?.userAvatar || '🦊'}</span>
                                    </div>
                                    {!leftCollapsed && (
                                        <div className="flex-1 text-left min-w-0">
                                            <p className={`text-sm font-bold truncate ${isDark ? 'text-[#E9EFD6]' : 'text-[#163628]'}`}>
                                                {settings?.nickname || settings?.studentName || 'Profile'}
                                            </p>
                                            <p className={`text-xs ${isDark ? 'text-[#8FA093]' : 'text-[#5E5046]'}`}>Menu</p>
                                        </div>
                                    )}
                                </button>
                                {!leftCollapsed && (
                                    <button 
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            navigate('/settings');
                                        }}
                                        className={`shrink-0 p-3 rounded-xl transition-all group ${isDark ? 'hover:bg-[#20382B]/80' : 'hover:bg-[#E6D5CC] hover:shadow-sm'}`}
                                        title="Settings"
                                    >
                                        <Settings className="h-5 w-5 text-[#5E5046] group-hover:text-[#1E5C42] transition-colors" />
                                    </button>
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Main Content Area */}
            <div className={`lumina-workspace flex-1 flex flex-col min-w-0 overflow-hidden backdrop-blur-sm transition-colors duration-300`}
                style={zenMode
                    ? { background: isDark ? 'var(--dm-bg)' : 'var(--th-surface, #fff)' }
                    : isDark
                        ? { background: 'color-mix(in srgb, var(--dm-surface) 85%, transparent)', margin: '1rem', borderRadius: '1.5rem', border: '1px solid var(--dm-border-strong)', boxShadow: '0 0 0 1px var(--dm-border), inset 0 1px 0 color-mix(in srgb, var(--dm-accent) 6%, transparent)' }
                        : { background: 'color-mix(in srgb, var(--th-surface, #ffffff) 50%, transparent)' }
                }
            >

                {/* Header (Context) - Hidden in Zen Mode */}
                {!zenMode && (
                    <div className="px-3 md:px-5 py-2.5 border-b backdrop-blur-md sticky top-0 z-30"
                        style={APP_SHELL ? { paddingTop: 'calc(var(--sat) + 0.5rem)', ...(isDark ? { borderColor: 'var(--dm-border-strong)', background: 'var(--dm-sidebar)' } : { borderColor: 'var(--th-border, rgba(230,213,204,0.5))', background: 'var(--th-surface, #ffffff)' }) } : isDark ? { borderColor: 'var(--dm-border-strong)', background: 'color-mix(in srgb, var(--dm-sidebar) 80%, transparent)' } : { borderColor: 'var(--th-border, rgba(230,213,204,0.5))', background: 'color-mix(in srgb, var(--th-surface, #ffffff) 50%, transparent)' }}>
                        {/* Single-row header with proper spacing */}
                        <div className="flex items-center gap-2 h-11">
                            {/* Mobile Menu Button (the phone app has a back button instead) */}
                            {APP_SHELL ? (
                                <button
                                    onClick={() => (window.history.length > 1 ? navigate(-1) : navigate(`/app/book/${projectId}`))}
                                    className="p-2 -ml-1.5 rounded-full text-[#163628] active:bg-[#E6D5CC]/40 shrink-0"
                                    aria-label="Back"
                                >
                                    <ChevronLeft className="h-6 w-6" />
                                </button>
                            ) : (
                                <button
                                    onClick={() => setIsMobileMenuOpen(true)}
                                    className="md:hidden p-2 -ml-1 hover:bg-[#E6D5CC]/30 rounded-lg text-[#163628] transition-colors shrink-0"
                                >
                                    <Menu className="h-5 w-5" />
                                </button>
                            )}

                            {/* Left: Tab name + Summary */}
                            <div className="flex items-center gap-2 min-w-0 shrink-0">
                                <h2 className={`text-base font-bold whitespace-nowrap ${isDark ? 'text-[#E9EFD6]' : 'text-[#163628]'}`}>
                                    {activeTab === 'cram' && 'Exam Tonight'}
                                    {activeTab === 'lab' && 'Visual Lab'}
                                    {activeTab === 'power' && 'Power Hour'}
                                    {activeTab === 'chat' && `Chat with ${aiName(settings)}`}
                                    {activeTab === 'qa' && 'Q&A'}
                                    {activeTab === 'quiz' && 'Quiz'}
                                    {activeTab === 'notes' && 'Notes'}
                                    {activeTab === 'flashcards' && 'Flashcards'}
                                    {activeTab === 'mindmap' && 'Mindmap'}
                                    {activeTab === 'path' && 'Learning Path'}
                                    {activeTab === 'study' && 'Study'}
                                    {activeTab === 'analytics' && 'Analytics'}
                                    {activeTab === 'knowledge' && 'Knowledge Graph'}
                                </h2>

                                {/* Summary Dropdown - compact pill */}
                                {documents.length > 0 && (
                                    <button
                                        onClick={toggleSummary}
                                        className={`hidden sm:flex items-center gap-1 text-[11px] font-semibold px-2.5 py-1 rounded-full transition-all shrink-0 ${showSummary
                                            ? 'bg-[#1E5C42] text-white'
                                            : 'bg-[#FDF6F0] text-[#1E5C42] border border-[#E6D5CC] hover:border-[#1E5C42]/40'
                                            }`}
                                    >
                                        <FileText className="h-3 w-3" />
                                        Summary
                                        {showSummary ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                                    </button>
                                )}
                            </div>

                            {/* Spacer for mobile */}
                            <div className="flex-1" />

                            {/* Right: Toolbar - grouped with subtle dividers */}
                            <div className="flex items-center shrink-0">
                                {/* Core tools group */}
                                <div className="flex items-center">
                                    <button
                                        onClick={() => setShowSearch(true)}
                                        className="p-2.5 rounded-lg text-[#5E5046] hover:text-[#163628] hover:bg-[#E6D5CC]/30 transition-colors"
                                        title="Search (Ctrl+K)"
                                    >
                                        <Search className="h-5 w-5" />
                                    </button>
                                    <button
                                        onClick={() => setShowAITutor(!showAITutor)}
                                        className={`p-2.5 rounded-lg transition-colors ${showAITutor ? 'bg-[#1E5C42] text-white' : 'text-[#5E5046] hover:text-[#163628] hover:bg-[#E6D5CC]/30'}`}
                                        title="AI Tutor"
                                    >
                                        <Brain className="h-5 w-5" />
                                    </button>
                                    <button
                                        onClick={() => setShowPomodoro(!showPomodoro)}
                                        className={`p-2.5 rounded-lg transition-colors ${showPomodoro ? 'bg-[#1E5C42] text-white' : 'text-[#5E5046] hover:text-[#163628] hover:bg-[#E6D5CC]/30'}`}
                                        title="Pomodoro Timer"
                                    >
                                        <Timer className="h-5 w-5" />
                                    </button>
                                    <button
                                        onClick={() => setShowBookmarks(!showBookmarks)}
                                        className={`p-2.5 rounded-lg transition-colors ${showBookmarks ? 'bg-[#1E5C42] text-white' : 'text-[#5E5046] hover:text-[#163628] hover:bg-[#E6D5CC]/30'}`}
                                        title="Bookmarks & Highlights"
                                    >
                                        <Bookmark className="h-5 w-5" />
                                    </button>
                                </div>

                                {/* Divider */}
                                <div className="w-px h-6 bg-[#E6D5CC]/60 mx-1 hidden sm:block" />

                                {/* Secondary tools */}
                                <div className="hidden sm:flex items-center">
                                    <button
                                        onClick={() => setZenMode(true)}
                                        className="p-2.5 rounded-lg text-[#5E5046] hover:text-[#163628] hover:bg-[#E6D5CC]/30 transition-colors"
                                        title="Focus Mode (Ctrl+Shift+Z)"
                                    >
                                        <Maximize2 className="h-5 w-5" />
                                    </button>
                                    <button
                                        onClick={() => setIsRightCollapsed(!isRightCollapsed)}
                                        className={`p-2.5 rounded-lg transition-colors ${!isRightCollapsed ? 'bg-[#1E5C42]/10 text-[#1E5C42]' : 'text-[#5E5046] hover:text-[#163628] hover:bg-[#E6D5CC]/30'}`}
                                        title={isRightCollapsed ? 'Show Documents Panel' : 'Hide Documents Panel'}
                                    >
                                        <PanelRight className="h-5 w-5" />
                                    </button>
                                </div>

                                {/* Divider */}
                                <div className="w-px h-6 bg-[#E6D5CC]/60 mx-0.5 hidden sm:block" />

                                {/* Gamification Button */}
                                <button
                                    onClick={() => setShowGamification(!showGamification)}
                                    className={`hidden sm:flex items-center gap-1.5 px-3 py-2 rounded-lg transition-all ${showGamification
                                        ? 'bg-[#1E5C42] text-white'
                                        : 'text-[#5E5046] hover:text-[#163628] hover:bg-[#E6D5CC]/30'
                                        }`}
                                    title="Progress & XP"
                                >
                                    <Trophy className="h-5 w-5" />
                                    {gamificationData && (
                                        <span className="text-xs font-bold tabular-nums">
                                            {gamificationData.total_xp?.toLocaleString()} XP
                                        </span>
                                    )}
                                </button>

                                {/* Documents Sidebar Toggle (Mobile) */}
                                <button
                                    onClick={() => setIsMobileDocsOpen(!isMobileDocsOpen)}
                                    className={`md:hidden p-2.5 rounded-lg transition-colors ${isMobileDocsOpen ? 'bg-[#1E5C42] text-white' : 'text-[#5E5046] hover:text-[#163628] hover:bg-[#E6D5CC]/30'}`}
                                    title="Documents"
                                >
                                    <PanelRight className="h-5 w-5" />
                                </button>

                                {/* Exit */}
                                {!APP_SHELL && <button
                                    onClick={() => navigate('/dashboard')}
                                    className="p-2.5 rounded-lg text-[#5E5046]/50 hover:bg-red-50 hover:text-red-500 transition-colors ml-0.5"
                                    title="Back to Dashboard"
                                >
                                    <LogOut className="h-5 w-5" />
                                </button>}
                            </div>
                        </div>
                        {APP_SHELL && (
                            <div className="-mx-3 flex gap-2 overflow-x-auto px-3 pb-1 pt-1.5" style={{ scrollbarWidth: 'none' }}>
                                {APP_TOOLS.map(([id, label]) => (
                                    <button key={id} onClick={() => setActiveTab(id)}
                                        className={`shrink-0 rounded-full px-3.5 py-1.5 text-[13px] font-semibold transition-colors ${activeTab === id ? 'bg-[#1E5C42] text-white' : isDark ? 'bg-[#20382B] text-[#B7C2B4]' : 'bg-[#F3E8DF] text-[#396D53]'}`}>
                                        {id === 'chat' ? `Ask ${aiName(settings)}` : label}
                                    </button>
                                ))}
                            </div>
                        )}

                        {/* Summary Content Area - positioned below header */}
                        {showSummary && (
                            <div className="absolute top-full left-4 right-4 md:left-auto md:right-4 md:w-96 mt-1 p-5 bg-white/95 backdrop-blur-xl rounded-2xl border border-[#E6D5CC] shadow-2xl animate-in slide-in-from-top-2 z-50">
                                <div className="flex justify-between items-center mb-3">
                                    <h4 className="font-bold text-sm text-[#163628] uppercase tracking-wide">
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
                                            <div className="absolute inset-0 h-16 w-16 border-4 border-[#1E5C42] rounded-full border-t-transparent animate-spin"></div>
                                            <FileText className="absolute inset-0 m-auto h-6 w-6 text-[#1E5C42]" />
                                        </div>
                                        <div className="text-center">
                                            <p className="text-sm font-bold text-[#163628]">Generating Summary</p>
                                            <p className="text-xs text-[#5E5046] mt-1">Analyzing your documents...</p>
                                        </div>
                                        <div className="flex gap-1">
                                            <div className="h-2 w-2 bg-[#1E5C42] rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                                            <div className="h-2 w-2 bg-[#1E5C42] rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                                            <div className="h-2 w-2 bg-[#1E5C42] rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                                        </div>
                                    </div>
                                ) : (
                                    <div className="prose prose-sm max-w-none text-sm text-[#163628] max-h-[60vh] overflow-y-auto overflow-x-auto pr-2 custom-scrollbar">
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
                        <div className="flex items-center gap-2 px-3 py-1.5 bg-[#163628]/80 backdrop-blur-md text-white/90 rounded-full text-xs font-medium shadow-lg">
                            <div className="h-2 w-2 bg-green-400 rounded-full animate-pulse" />
                            Focus Mode
                        </div>
                        <button
                            onClick={() => setZenMode(false)}
                            className="p-2 bg-[#163628]/80 backdrop-blur-md text-white/90 rounded-full hover:bg-[#163628] transition-colors shadow-lg"
                            title="Exit Focus Mode (Esc)"
                        >
                            <Minimize2 className="h-4 w-4" />
                        </button>
                    </div>
                )}

                {/* Content Body */}
                <div className="flex-1 overflow-hidden relative">
                <Suspense fallback={<ViewLoader />}>

                    {/* Chat View */}
                    {activeTab === 'chat' && (
                        <div className="h-full flex flex-col relative">
                            <div className="relative flex-1 min-h-0 flex flex-col">
                            <div
                                ref={chatScrollRef}
                                onScroll={handleChatScroll}
                                className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden overscroll-contain px-2 py-4 md:p-6 space-y-6"
                            >
                                {messages.map((msg, idx) => (
                                    <React.Fragment key={idx}>
                                    {/* Day separator whenever the date changes */}
                                    {msg.timestamp && (() => {
                                        const prevStamp = messages.slice(0, idx).reverse().find(m => m.timestamp)?.timestamp;
                                        const label = chatDayLabel(msg.timestamp);
                                        return (!prevStamp || chatDayLabel(prevStamp) !== label) ? (
                                            <div className="flex items-center gap-3 my-2 text-[11px] font-semibold uppercase tracking-wide text-[#5E5046]">
                                                <span className="h-px flex-1 bg-[#E6D5CC]" />
                                                {label}
                                                <span className="h-px flex-1 bg-[#E6D5CC]" />
                                            </div>
                                        ) : null;
                                    })()}
                                    <div className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                                        {/* Tool Loading Card */}
                                        {msg.type === 'tool_loading' && (
                                            <ToolLoadingCard toolType={msg.toolType} toolParams={msg.toolParams} />
                                        )}

                                        {/* Tool Result Card */}
                                        {msg.type === 'tool_result' && (
                                            <ToolResultCard
                                                toolType={msg.toolType}
                                                toolParams={msg.toolParams}
                                                toolData={msg.toolData}
                                                onOpen={handleToolOpen}
                                            />
                                        )}

                                        {/* Tool Error Card */}
                                        {msg.type === 'tool_error' && (
                                            <ToolErrorCard
                                                toolType={msg.toolType}
                                                error={msg.error}
                                                onRetry={() => handleToolExecute(msg.toolType, msg.toolParams)}
                                            />
                                        )}

                                        {/* Companion label on assistant replies */}
                                        {msg.role === 'assistant' && (!msg.type || msg.type === 'tool_command') && (
                                            <div className="flex items-center gap-1.5 mb-1 ml-1 text-xs font-semibold text-[#1E5C42]">
                                                <span className="text-base leading-none">{settings.aiAvatar || '✨'}</span>
                                                {aiName(settings)}
                                            </div>
                                        )}

                                        {/* Regular message (no type or tool_command) */}
                                        {(!msg.type || msg.type === 'tool_command') && (
                                            <div className={`max-w-[95%] md:max-w-[85%] break-words rounded-2xl px-4 py-3 md:px-6 md:py-4 ${msg.role === 'user'
                                                ? 'bg-[#1E5C42] text-white rounded-br-none'
                                                : 'bg-[#FDF6F0] text-[#163628] rounded-bl-none'
                                                }`}>
                                                {msg.content ? (
                                                    <div className={`chat-text leading-relaxed ${msg.role === 'assistant' ? 'prose prose-sm max-w-none overflow-x-auto prose-p:my-2 prose-headings:text-[#163628] prose-a:text-[#1E5C42]' : ''}`}>
                                                        <ChatMarkdown content={msg.content} role={msg.role} sources={msg.sources} onOpenSource={openSourceStable} />
                                                    </div>
                                                ) : (
                                                    <Loader2 className="h-5 w-5 animate-spin text-[#5E5046]" />
                                                )}

                                                {/* Citations are now rendered inline within ReactMarkdown */}
                                            </div>
                                        )}

                                        {/* Time log */}
                                        {msg.timestamp && msg.role !== 'system' && (
                                            <div
                                                className={`mt-1 px-1 text-[11px] text-[#5E5046] ${msg.role === 'user' ? 'text-right' : ''}`}
                                                title={new Date(msg.timestamp).toLocaleString()}
                                            >
                                                {formatChatTime(msg.timestamp)}
                                                {msg.role === 'assistant' && msg.completedAt && !String(msg.content || '').startsWith('Error:') && (
                                                    <> · answered in {Math.max(0.1, (new Date(msg.completedAt) - new Date(msg.timestamp)) / 1000).toFixed(1)}s</>
                                                )}
                                            </div>
                                        )}
                                    </div>
                                    </React.Fragment>
                                ))}
                                <div ref={messagesEndRef} />
                                {(() => {
                                    // The book being prepared, with live progress
                                    const doc = documents.find(d => selectedDocuments.includes(d.id) && ['pending', 'processing', 'embedding', 'queued'].includes(d.upload_status) && !isStalled(d));
                                    if (!isProcessingDocs || !doc) return null;
                                    const live = docStages[doc.id];
                                    return (
                                        <div className="flex justify-center my-4 animate-in fade-in slide-in-from-bottom-2">
                                            <div className="max-w-lg w-full">
                                                <ProcessingProgress
                                                    variant="full"
                                                    title={doc.filename}
                                                    stage={live?.stage || doc.upload_status}
                                                    stagePct={live?.progress}
                                                    message={live?.message}
                                                />
                                            </div>
                                        </div>
                                    );
                                })()}

                                {/* Failed doc banner — shown when any doc fails */}
                                {!isProcessingDocs && documents.some(d => d.upload_status === 'failed' || d.upload_status === 'error') && (
                                    <div className="flex justify-center my-4 animate-in fade-in slide-in-from-bottom-2">
                                        <div className="bg-red-50 text-red-700 px-5 py-4 rounded-xl text-sm flex items-start gap-3 border border-red-200 shadow-md max-w-lg w-full">
                                            <div className="shrink-0 mt-0.5 h-8 w-8 bg-red-100 rounded-full flex items-center justify-center">
                                                <X className="h-4 w-4 text-red-500" />
                                            </div>
                                            <div className="flex-1">
                                                <p className="font-bold text-red-800 tracking-wide text-xs uppercase mb-1.5">Document Processing Failed</p>
                                                <p className="text-[11px] leading-relaxed text-red-700/90">
                                                    {documents.filter(d => d.upload_status === 'failed' || d.upload_status === 'error').length === 1
                                                        ? `"${documents.find(d => d.upload_status === 'failed' || d.upload_status === 'error')?.filename}" couldn't be processed. Tap Retry next to it in the sidebar. If it fails again, the file may be encrypted or damaged: delete it and try a different copy.`
                                                        : `${documents.filter(d => d.upload_status === 'failed' || d.upload_status === 'error').length} documents couldn't be processed. Tap Retry next to each one in the sidebar. If one fails again, the file may be encrypted or damaged.`
                                                    }
                                                </p>
                                            </div>
                                        </div>
                                    </div>
                                )}

                            </div>
                            {showJumpToLatest && (
                                <button
                                    onClick={() => scrollToBottom(true)}
                                    className="absolute bottom-3 left-1/2 -translate-x-1/2 z-10 flex items-center gap-1.5 rounded-full bg-[#1E5C42] px-4 py-2 text-xs font-semibold text-white shadow-lg shadow-[#1E5C42]/30 hover:bg-[#163628]"
                                >
                                    <ChevronDown className="h-4 w-4" /> Latest
                                </button>
                            )}
                            </div>

                            <div className="p-4 border-t border-[#E6D5CC] bg-white">
                                <div className="max-w-4xl mx-auto relative">
                                    {/* Command Picker Dropdown */}
                                    <CommandPicker
                                        filter={commandFilter}
                                        onSelect={handleCommandSelect}
                                        onClose={() => { setShowCommandPicker(false); setCommandFilter(''); }}
                                        visible={showCommandPicker && !activeCommand}
                                    />

                                    {/* Command Parameter Form */}
                                    {activeCommand && (
                                        <CommandParamForm
                                            command={activeCommand}
                                            availableTopics={availableTopics}
                                            onExecute={handleToolExecute}
                                            onCancel={() => setActiveCommand(null)}
                                            loading={toolLoading}
                                        />
                                    )}

                                    <form onSubmit={handleSendMessage} className="flex gap-2 md:gap-3 items-center">
                                        {(!isNativeApp() || deepLeft > 0) && <button
                                            type="button"
                                            onClick={toggleDeep}
                                            aria-pressed={deepMode}
                                            title={deepMode ? (deepUnlimited ? 'Deep mode on' : `Deep mode on · ${deepLeft} left this month`) : 'Deep mode: our most capable model for tricky questions'}
                                            className={`shrink-0 flex items-center gap-1 rounded-full px-3 py-2.5 text-xs font-semibold transition-colors ${deepMode
                                                ? 'bg-[#163628] text-white shadow-md'
                                                : 'bg-[#FDF6F0] text-[#5E5046] hover:text-[#163628]'}`}
                                        >
                                            <Brain className="h-4 w-4" />
                                            <span className="hidden sm:inline">Deep{deepMode && !deepUnlimited ? ` · ${deepLeft}` : ''}</span>
                                        </button>}
                                        <div className="flex-1 relative">
                                            <input
                                                type="text"
                                                value={inputMessage}
                                                onChange={handleInputChange}
                                                placeholder="Ask a question or type @ for AI tools..."
                                                className="w-full pl-4 md:pl-6 pr-12 py-3 bg-[#FDF6F0] border-none rounded-full focus:ring-2 focus:ring-[#1E5C42] outline-none text-[#163628] placeholder-[#5E5046] text-sm md:text-base"
                                                disabled={loading || toolLoading}
                                            />
                                            <button
                                                type="submit"
                                                disabled={loading || toolLoading || !inputMessage.trim()}
                                                className="absolute right-2 top-1/2 transform -translate-y-1/2 p-2 bg-[#1E5C42] text-white rounded-full hover:bg-[#163628] transition-colors disabled:opacity-50"
                                            >
                                                <Send className="h-4 w-4" />
                                            </button>
                                        </div>
                                    </form>
                                </div>
                            </div>
                        </div>
                    )}

                    {activeTab === 'cram' && (
                        <ExamTonightView
                            projectId={projectId}
                            selectedDocuments={selectedDocuments}
                            onTopicMastered={markTopicMastered}
                            onVisualize={openVisualLab}
                        />
                    )}

                    {activeTab === 'lab' && (
                        <VisualLabView
                            projectId={projectId}
                            availableTopics={availableTopics.length ? availableTopics : allProjectTopics}
                            selectedDocuments={selectedDocuments}
                            initialTopic={labTopic}
                            onConsumeInitialTopic={() => setLabTopic('')}
                        />
                    )}

                    {activeTab === 'power' && (
                        <PowerHourView
                            projectId={projectId}
                            availableTopics={availableTopics.length ? availableTopics : allProjectTopics}
                            selectedDocuments={selectedDocuments}
                            completedTopics={learningProgress}
                            topicMeta={topicMeta}
                            onTopicMastered={markTopicMastered}
                            onVisualize={openVisualLab}
                            onOpenChat={(prompt) => {
                                setInputMessage(prompt);
                                setActiveTab('chat');
                            }}
                        />
                    )}

                    {activeTab === 'quiz' && (
                        <QuizView
                            projectId={projectId}
                            availableTopics={availableTopics}
                            selectedDocuments={selectedDocuments}
                            preSelectedTopic={preSelectedTopic}
                            preSelectedMode={preSelectedQuizMode}
                            preGeneratedData={preGeneratedQuiz}
                            onConsumePreGenerated={() => setPreGeneratedQuiz(null)}
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
                            onBack={() => {
                                setActiveTab('chat');
                                setIsQuizActive(false);
                            }}
                        />
                    )}

                    {/* Q&A Generation View (Study Mode) */}
                    {activeTab === 'qa' && (
                        <QAView
                            projectId={projectId}
                            availableTopics={availableTopics}
                            selectedDocuments={selectedDocuments}
                            preSelectedTopic={preSelectedTopic}
                            preGeneratedData={preGeneratedQA}
                            onConsumePreGenerated={() => setPreGeneratedQA(null)}
                            onQAActiveChange={setIsQAActive}
                            autoGenerate={qaAutoGenerate}
                            onBack={() => {
                                setActiveTab('chat');
                                setIsQAActive(false);
                            }}
                        />
                    )}

                    {/* Notes Generation View */}
                    {activeTab === 'notes' && (
                        <NotesView
                            projectId={projectId}
                            availableTopics={allProjectTopics}
                            selectedDocuments={selectedDocuments}
                            preSelectedTopic={preSelectedTopic}
                            preGeneratedData={preGeneratedNotes}
                            onConsumePreGenerated={() => setPreGeneratedNotes(null)}
                            autoGenerate={notesAutoGenerate}
                            onAutoGenerateConsumed={() => setNotesAutoGenerate(false)}
                        />
                    )}

                    {/* Flashcards View */}
                    {activeTab === 'flashcards' && (
                        <FlashcardsView
                            projectId={projectId}
                            availableTopics={availableTopics}
                            selectedDocuments={selectedDocuments}
                        />
                    )}

                    {/* Mindmap View */}
                    {activeTab === 'mindmap' && (
                        <MindmapView
                            projectId={projectId}
                            availableTopics={availableTopics}
                            selectedDocuments={selectedDocuments}
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
                            onTopicsChange={fetchTopics}
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
                                setNotesAutoGenerate(true);
                                setActiveTab('notes');
                            }}
                            onStartQA={(topic, docsToSelect) => {
                                if (docsToSelect && docsToSelect.length > 0) {
                                    setSelectedDocuments(docsToSelect);
                                }
                                setPreSelectedTopic(topic);
                                setQAAutoGenerate(true);
                                setActiveTab('qa');
                            }}
                            onOpenTutor={(topic) => {
                                setTutorTopic(topic);
                                setShowAITutor(true);
                            }}
                            onStartLesson={(topic) => setLessonTopic(topic)}
                            planVersion={planVersion}
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

                    {/* Knowledge Graph View */}
                    {activeTab === 'knowledge' && (
                        <KnowledgeGraphView projectId={projectId} zenMode={zenMode} />
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
                </Suspense>
                </div>
            </div>

            {/* ===== RIGHT SIDEBAR — Document Management ===== */}
            {!isSidebarHidden && (
                <>
                    {/* Mobile Overlay */}
                    {isMobileDocsOpen && (
                        <div
                            className="fixed inset-0 bg-black/50 z-40 md:hidden"
                            onClick={() => setIsMobileDocsOpen(false)}
                        />
                    )}
                    <div
                        style={{ '--docs-w': `${docsWidth}px` }}
                        className={`
                    fixed inset-y-0 right-0 z-50 w-80 bg-[#FDF6F0]/98 backdrop-blur-xl border-l border-[#E6D5CC]/60 flex flex-col ${resizingDocs ? 'transition-none select-none' : 'transition-all duration-300 ease-in-out'}
                    md:translate-x-0 md:relative md:shrink-0
                    ${isRightCollapsed ? 'md:w-0 md:border-0 md:overflow-hidden md:p-0' : 'md:w-[var(--docs-w)]'}
                    ${isMobileDocsOpen ? 'translate-x-0' : 'translate-x-full'}
                    shadow-2xl md:shadow-none
                `}>
                        {/* Drag the left edge to resize (desktop); double-click resets */}
                        {!isRightCollapsed && (
                            <div
                                role="separator"
                                aria-orientation="vertical"
                                aria-label="Resize documents panel"
                                title="Drag to resize · double-click to reset"
                                onPointerDown={startDocsResize}
                                onDoubleClick={() => { setDocsWidth(DOCS_DEFAULT); try { localStorage.setItem('lumina_docs_width', String(DOCS_DEFAULT)); } catch { /* ignore */ } }}
                                className="group/resize absolute inset-y-0 -left-1.5 z-10 hidden w-3 cursor-col-resize md:block"
                            >
                                <span className={`absolute inset-y-0 left-1/2 w-0.5 -translate-x-1/2 rounded-full transition-colors ${resizingDocs ? 'bg-[#1E5C42]' : 'bg-transparent group-hover/resize:bg-[#1E5C42]/60'}`} />
                            </div>
                        )}
                        {/* Right Sidebar Header */}
                        <div className="shrink-0 px-5 py-4 border-b border-[#E6D5CC]/50 bg-gradient-to-br from-[#FDF6F0] to-white/80">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2.5">
                                    <div className="h-8 w-8 bg-gradient-to-br from-[#1E5C42] to-[#163628] rounded-lg flex items-center justify-center text-white shadow-sm">
                                        <FileText className="h-4 w-4" />
                                    </div>
                                    <div>
                                        <h3 className="text-sm font-bold text-[#163628] leading-tight">Documents</h3>
                                        <p className="text-[10px] text-[#5E5046]">
                                            {selectedDocuments.length > 0
                                                ? `${selectedDocuments.length} of ${documents.length} selected`
                                                : `${documents.length} document${documents.length !== 1 ? 's' : ''}`
                                            }
                                        </p>
                                    </div>
                                </div>
                                <div className="flex items-center gap-1">
                                    {/* Collapse toggle (desktop) */}
                                    <button
                                        onClick={() => setIsRightCollapsed(!isRightCollapsed)}
                                        className="hidden md:block p-1.5 hover:bg-[#E6D5CC]/40 rounded-lg text-[#5E5046] transition-colors"
                                        title={isRightCollapsed ? 'Expand' : 'Collapse'}
                                    >
                                        <ChevronRight className="h-4 w-4" />
                                    </button>
                                    {/* Close (mobile) */}
                                    <button
                                        onClick={() => setIsMobileDocsOpen(false)}
                                        className="md:hidden p-1.5 hover:bg-[#E6D5CC]/40 rounded-lg text-[#5E5046] transition-colors"
                                    >
                                        <X className="h-4 w-4" />
                                    </button>
                                </div>
                            </div>
                        </div>

                        {/* Upload Section */}
                        <div className="shrink-0 px-4 pt-3 pb-2">
                            <button
                                onClick={() => setShowAddDocModal(true)}
                                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold bg-gradient-to-r from-[#1E5C42] to-[#163628] text-white shadow-md hover:shadow-lg hover:scale-[1.01] transition-all"
                            >
                                <Plus className="h-4 w-4" />
                                Add Document
                            </button>
                        </div>

                        {/* Select All / Deselect All Controls */}
                        {documents.length > 0 && (
                            <div className="shrink-0 px-4 py-2 flex items-center gap-2 border-b border-[#E6D5CC]/30">
                                <button
                                    onClick={() => {
                                        const readyDocs = documents.filter(d => d.upload_status === 'completed' || d.upload_status === 'ready');
                                        setSelectedDocuments(readyDocs.map(d => d.id));
                                    }}
                                    className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-[#1E5C42]/10 text-[#1E5C42] hover:bg-[#1E5C42]/20 transition-colors"
                                >
                                    <Eye className="h-3 w-3" />
                                    Select All
                                </button>
                                <button
                                    onClick={() => setSelectedDocuments([])}
                                    className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-[#FDF6F0] text-[#5E5046] hover:bg-[#E6D5CC]/50 transition-colors"
                                >
                                    <EyeOff className="h-3 w-3" />
                                    Deselect All
                                </button>
                            </div>
                        )}

                        {/* Document List */}
                        <div className="flex-1 overflow-y-auto custom-scrollbar px-3 py-2 space-y-1.5">
                            {/* Processing Banner (Only show if > 1 document processing) */}
                            {documents.filter(d => d.upload_status === 'pending' || d.upload_status === 'processing' || d.upload_status === 'embedding' || d.upload_status === 'queued').length > 1 && (
                                <div className="flex items-center gap-2.5 p-3 mb-2 bg-gradient-to-r from-amber-50 to-orange-50 rounded-xl border border-amber-200/80">
                                    <div className="relative shrink-0">
                                        <div className="h-6 w-6 border-2 border-amber-300 rounded-full"></div>
                                        <div className="absolute inset-0 h-6 w-6 border-2 border-amber-500 rounded-full border-t-transparent animate-spin"></div>
                                    </div>
                                    <div>
                                        <p className="text-xs font-bold text-amber-800">
                                            Processing {documents.filter(d => d.upload_status === 'pending' || d.upload_status === 'processing' || d.upload_status === 'embedding' || d.upload_status === 'queued').length} Documents
                                        </p>
                                        <p className="text-[10px] text-amber-600">{getRotatingLoadingMessage(loadingMsgIdx)}</p>
                                    </div>
                                </div>
                            )}

                            {pausedUploads.length > 0 && (
                                <input
                                    ref={resumeInputRef}
                                    type="file"
                                    accept=".pdf,.docx,.txt"
                                    className="hidden"
                                    onChange={(e) => { if (e.target.files?.length) handleFileUpload(e.target.files); e.target.value = ''; }}
                                />
                            )}
                            {pausedUploads.filter(p => !uploadsInFlight.some(u => u.name === p.name && u.size === p.size)).map((p) => (
                                <div key={p.key} className="p-3 rounded-xl bg-[#FDF6F0] border border-dashed border-[#d2bab0]">
                                    <p className="text-sm font-medium truncate leading-tight text-[#2B3F35]">{p.name}</p>
                                    <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-[#F1E6DD]">
                                        <div className="h-full rounded-full bg-[#d9c2b2]" style={{ width: `${Math.max(3, p.pct)}%` }} />
                                    </div>
                                    <p className="mt-1 text-[10px] text-[#5E5046]">Paused at {p.pct}%. Choose the same file and it carries on from there.</p>
                                    <div className="mt-2 flex gap-2">
                                        <button
                                            onClick={() => resumeInputRef.current?.click()}
                                            className="rounded-lg bg-[#1E5C42] px-2.5 py-1 text-[11px] font-semibold text-white hover:bg-[#163628]"
                                        >
                                            Resume upload
                                        </button>
                                        <button
                                            onClick={() => { forgetPendingUpload(p.key); setPausedUploads(pendingUploads(projectId)); }}
                                            className="rounded-lg px-2.5 py-1 text-[11px] font-semibold text-[#5E5046] hover:bg-[#E6D5CC]/50"
                                        >
                                            Discard
                                        </button>
                                    </div>
                                </div>
                            ))}
                            {uploadsInFlight.map((u) => (
                                <div key={u.key} className="p-3 rounded-xl bg-white/70 border border-[#E6D5CC]/70">
                                    <p className="text-sm font-medium truncate leading-tight text-[#2B3F35]">{u.name}</p>
                                    {u.pct === 0 && Date.now() - (u.startedAt || Date.now()) > 45000 && (
                                        <div className="mt-1.5 flex items-center gap-2 text-[10px] text-amber-700">
                                            <span className="flex-1">The upload hasn't started. Check your connection, or refresh the page and try again.</span>
                                            <button
                                                onClick={() => {
                                                    const file = uploadFilesRef.current[u.key];
                                                    setUploadsInFlight(prev => prev.filter(x => x.key !== u.key));
                                                    if (file) handleFileUpload([file]);
                                                }}
                                                className="shrink-0 rounded-md bg-[#1E5C42] px-2 py-0.5 font-semibold text-white hover:bg-[#163628]"
                                            >
                                                Retry
                                            </button>
                                        </div>
                                    )}
                                    <ProcessingProgress
                                        stage={u.pct >= 100 ? 'pending' : 'uploading'}
                                        stagePct={u.pct >= 100 ? 50 : u.pct}
                                        message={`${(u.size * u.pct / 100 / 1048576).toFixed(1)} of ${(u.size / 1048576).toFixed(1)} MB`}
                                    />
                                </div>
                            ))}

                            {documents.length > 0 || uploadsInFlight.length > 0 || pausedUploads.length > 0 ? (
                                documents.map((doc) => {
                                    const isSelected = selectedDocuments.includes(doc.id);
                                    const isDeleting = deletingDocIds.has(doc.id);
                                    const isWorking = doc.upload_status === 'pending' || doc.upload_status === 'processing' || doc.upload_status === 'embedding' || doc.upload_status === 'queued';
                                    const isStalledDoc = isWorking && isStalled(doc);
                                    const isProcessing = isWorking && !isStalledDoc;
                                    const isReady = doc.upload_status === 'completed' || doc.upload_status === 'ready';
                                    const isFailed = doc.upload_status === 'failed' || doc.upload_status === 'error';

                                    return (
                                        <div
                                            key={doc.id}
                                            className={`group relative flex items-start gap-2.5 p-3 rounded-xl cursor-pointer transition-all duration-200 ${isDeleting
                                                ? 'opacity-40 pointer-events-none scale-95'
                                                : isFailed
                                                    ? 'bg-red-50/60 border border-red-200/70 opacity-80'
                                                    : isSelected
                                                        ? 'bg-[#1E5C42]/15 border border-[#1E5C42]/40 shadow-sm'
                                                        : 'bg-white/60 border border-transparent hover:bg-[#FDF6F0] hover:border-[#E6D5CC]/60'
                                                }`}
                                            onClick={() => {
                                                if (isDeleting || !isReady) return;
                                                // Toggle multi-select
                                                setSelectedDocuments(prev =>
                                                    prev.includes(doc.id)
                                                        ? prev.filter(id => id !== doc.id)
                                                        : [...prev, doc.id]
                                                );
                                            }}
                                        >
                                            {/* Checkbox */}
                                            <div className={`shrink-0 mt-0.5 h-5 w-5 rounded-md border-2 flex items-center justify-center transition-all ${isSelected
                                                ? 'bg-[#1E5C42] border-[#1E5C42] text-white shadow-sm'
                                                : isReady
                                                    ? 'border-[#d2bab0] group-hover:border-[#1E5C42]'
                                                    : 'border-[#E6D5CC] opacity-50'
                                                }`}>
                                                {isSelected && <Check className="h-3 w-3" />}
                                            </div>

                                            {/* Document Info */}
                                            <div className="flex-1 min-w-0">
                                                <p 
                                                    onClick={(e) => {
                                                        if (!isReady) return;
                                                        e.stopPropagation();
                                                        handleOpenSource({ doc_id: doc.id, doc_name: doc.filename });
                                                    }}
                                                    className={`text-sm font-medium truncate leading-tight hover:underline cursor-pointer ${isSelected ? 'text-[#163628]' : 'text-[#2B3F35]'
                                                    }`}
                                                    title="Read this book"
                                                >
                                                    {doc.filename}
                                                </p>
                                                {(isProcessing || (isReady && justReady.has(doc.id))) && (
                                                    <ProcessingProgress
                                                        stage={isReady ? 'completed' : (docStages[doc.id]?.stage || doc.upload_status)}
                                                        stagePct={isReady ? 100 : docStages[doc.id]?.progress}
                                                        message={docStages[doc.id]?.message}
                                                    />
                                                )}
                                                {isStalledDoc && (
                                                    <p className="mt-1 text-[10px] leading-snug text-amber-700">
                                                        This upload stopped (the server restarted while reading it). Delete it and upload it again.
                                                    </p>
                                                )}
                                                <div className="flex items-center gap-2 mt-1">
                                                    {isReady && !justReady.has(doc.id) && (
                                                        <span className="flex items-center gap-1 text-[10px] text-emerald-600 font-medium">
                                                            <div className="h-1.5 w-1.5 bg-emerald-500 rounded-full" />
                                                            Ready
                                                        </span>
                                                    )}
                                                    {isFailed && (
                                                        <span
                                                            className="flex items-center gap-1 text-[10px] text-red-500 font-medium cursor-help"
                                                            title={doc.error_message || 'This PDF could not be processed. Try a different file.'}
                                                        >
                                                            <div className="h-1.5 w-1.5 bg-red-500 rounded-full shrink-0" />
                                                            Can’t be processed
                                                        </span>
                                                    )}
                                                    {isFailed && (
                                                        <button
                                                            onClick={(e) => { e.stopPropagation(); retryDoc(doc); }}
                                                            disabled={retryingIds.has(doc.id)}
                                                            className="rounded-md bg-[#1E5C42] px-2 py-0.5 text-[10px] font-semibold text-white hover:bg-[#163628] disabled:opacity-60"
                                                        >
                                                            {retryingIds.has(doc.id) ? 'Retrying…' : 'Retry'}
                                                        </button>
                                                    )}
                                                </div>
                                            </div>

                                            {/* Actions */}
                                            <div className="flex items-center md:opacity-0 md:group-hover:opacity-100 transition-all shrink-0">
                                                {isReady && (
                                                    <button
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            handleOpenSource({ doc_id: doc.id, doc_name: doc.filename });
                                                        }}
                                                        className="flex items-center gap-1 px-2 py-1.5 rounded-lg hover:bg-[#E6D5CC]/50 text-[#5E5046] text-[11px] font-semibold transition-all"
                                                        title="Read this book"
                                                    >
                                                        <BookOpen className="h-3.5 w-3.5" /> Read
                                                    </button>
                                                )}
                                                <button
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        requestDelete(doc);
                                                    }}
                                                    className="p-1.5 rounded-lg hover:bg-red-50 hover:text-red-500 text-[#5E5046] transition-all"
                                                    title="Delete document"
                                                >
                                                    <Trash2 className="h-3.5 w-3.5" />
                                                </button>
                                            </div>
                                        </div>
                                    );
                                })
                            ) : (
                                <div className="flex flex-col items-center justify-center py-12 text-center">
                                    <div className="h-16 w-16 bg-[#E6D5CC]/30 rounded-2xl flex items-center justify-center mb-4">
                                        <Upload className="h-7 w-7 text-[#1E5C42]/60" />
                                    </div>
                                    <p className="text-sm font-medium text-[#5E5046]">No documents yet</p>
                                    <p className="text-xs text-[#5E5046]/60 mt-1">Upload PDF, TXT, or DOCX files</p>
                                    <button
                                        onClick={() => setShowAddDocModal(true)}
                                        className="mt-4 px-4 py-2 bg-[#1E5C42] text-white text-xs font-semibold rounded-lg hover:bg-[#163628] transition-colors shadow-sm"
                                    >
                                        Upload First Document
                                    </button>
                                </div>
                            )}
                        </div>
                    </div>
                </>
            )}


            {/* Delete Confirmation Modal */}
            {
                deleteConfirmDoc && (
                    <div className="fixed inset-0 bg-black/50 z-[60] flex items-center justify-center p-4">
                        <div className="bg-white rounded-xl shadow-xl max-w-sm w-full p-6 animate-in fade-in zoom-in-95 duration-200">
                            <h3 className="text-xl font-bold text-[#163628] mb-2">Delete Document?</h3>
                            <p className="text-[#5E5046] mb-6">
                                Are you sure you want to delete <span className="font-semibold text-[#163628]">{deleteConfirmDoc.filename}</span>?
                                This action cannot be undone.
                            </p>
                            <div className="flex gap-3 justify-end">
                                <button
                                    onClick={() => setDeleteConfirmDoc(null)}
                                    className="px-4 py-2 rounded-lg text-[#163628] hover:bg-[#FDF6F0] font-medium transition-colors"
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

            <Suspense fallback={null}>
            {/* Floating Pomodoro Timer */}
            {showPomodoro && (
                <div className="fixed bottom-4 right-4 left-4 md:left-auto md:w-auto z-50 animate-in slide-in-from-bottom-4">
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
                <div className="fixed top-20 right-4 left-4 md:left-auto md:right-4 md:w-96 z-50 animate-in slide-in-from-right-4">
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
                <div className="fixed top-14 right-4 left-4 md:left-auto md:w-96 z-50 animate-in slide-in-from-top-2 duration-200">
                    <GamificationPanel onClose={() => setShowGamification(false)} />
                </div>
            )}

            </Suspense>

            {/* Profile Dropdown - Floating Popup */}
            {showProfileMenu && (
                <>
                    {/* Mobile: Full-screen overlay */}
                    <div
                        className="fixed inset-0 bg-black/50 z-[60] md:hidden"
                        onClick={() => setShowProfileMenu(false)}
                    />

                    {/* Profile Menu */}
                    <div className={`profile-dropdown fixed z-[70] animate-in duration-200 slide-in-from-bottom-4 md:slide-in-from-left-2 left-0 right-0 bottom-0 md:left-auto md:right-auto md:bottom-6 ${leftCollapsed ? 'md:left-24' : 'md:left-[340px]'}`}>
                        <div className="bg-white rounded-t-3xl md:rounded-xl shadow-xl border-t md:border border-[#E6D5CC] overflow-hidden min-w-[200px] max-w-full md:max-w-sm">
                            <div className="bg-gradient-to-r from-[#1E5C42] to-[#163628] p-4 md:p-4 text-white">
                                <div className="flex items-center justify-between md:justify-start gap-3">
                                    <div className="flex items-center gap-3">
                                        <div className="h-12 w-12 md:h-10 md:w-10 bg-white/20 rounded-full flex items-center justify-center backdrop-blur-md">
                                            <span className="text-lg leading-none">{settings?.userAvatar || '🦊'}</span>
                                        </div>
                                        <div>
                                            <p className="font-bold text-base md:text-sm">{settings?.nickname || settings?.studentName || 'User'}</p>
                                            <p className="text-xs opacity-80">Free Plan</p>
                                        </div>
                                    </div>
                                    {/* Close button for mobile */}
                                    <button
                                        onClick={() => setShowProfileMenu(false)}
                                        className="md:hidden p-2 hover:bg-white/20 rounded-full transition-colors"
                                    >
                                        <X className="h-5 w-5" />
                                    </button>
                                </div>
                            </div>
                            <div className="py-2">
                                <button
                                    onClick={() => {
                                        setActiveTab('study');
                                        setShowProfileMenu(false);
                                    }}
                                    className="w-full flex items-center gap-3 px-4 py-4 md:py-3 text-[#163628] hover:bg-[#FDF6F0] transition-colors active:bg-[#E6D5CC]"
                                >
                                    <Brain className="h-6 w-6 md:h-5 md:w-5 text-[#1E5C42]" />
                                    <span className="font-medium text-base md:text-sm">Study Dashboard</span>
                                </button>
                                <button
                                    onClick={() => {
                                        setActiveTab('analytics');
                                        setShowProfileMenu(false);
                                    }}
                                    className="w-full flex items-center gap-3 px-4 py-4 md:py-3 text-[#163628] hover:bg-[#FDF6F0] transition-colors active:bg-[#E6D5CC]"
                                >
                                    <BarChart3 className="h-6 w-6 md:h-5 md:w-5 text-[#1E5C42]" />
                                    <span className="font-medium text-base md:text-sm">Analytics</span>
                                </button>
                                <div className="border-t border-[#E6D5CC]/50 my-1" />
                                <button
                                    onClick={() => {
                                        navigate('/settings');
                                        setShowProfileMenu(false);
                                    }}
                                    className="w-full flex items-center gap-3 px-4 py-4 md:py-3 text-[#163628] hover:bg-[#FDF6F0] transition-colors active:bg-[#E6D5CC]"
                                >
                                    <Settings className="h-6 w-6 md:h-5 md:w-5 text-[#1E5C42]" />
                                    <span className="font-medium text-base md:text-sm">Settings</span>
                                </button>
                                {/* Safe area padding for mobile */}
                                <div className="h-4 md:hidden" />
                            </div>
                        </div>
                    </div>
                </>
            )}

            <Suspense fallback={null}>
            {/* Global Search Modal — mounted only when opened so its code loads on demand */}
            {showSearch && <GlobalSearch
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
            />}

            {lessonTopic && (
                <LessonView
                    key={lessonTopic}
                    projectId={projectId}
                    topic={lessonTopic}
                    selectedDocuments={selectedDocuments}
                    onClose={() => { setLessonTopic(null); setPlanVersion((v) => v + 1); }}
                    onNextTopic={(next) => { setLessonTopic(next); setPlanVersion((v) => v + 1); }}
                />
            )}

            {/* Add Document Modal — unified source picker (Book Store + Upload) */}
            {showAddDocModal && (
                <AddDocumentModal
                    projectId={projectId}
                    uploading={false /* progress shows in the document list; more books can be added meanwhile */}
                    onUpload={(files, bookOptions) => {
                        // Close straight away: progress shows in the document list
                        setShowAddDocModal(false);
                        handleFileUpload(files, bookOptions);
                    }}
                    onImported={(doc) => {
                        fetchDocuments();
                    }}
                    onClose={() => setShowAddDocModal(false)}
                />
            )}
            </Suspense>
        </div >

    );
};

export default ProjectView;
