import axios from 'axios';

const API_URL = import.meta.env.VITE_MAIN_API_URL //|| 'http://localhost:8000/api/v1';

export const api = axios.create({
    baseURL: API_URL,
    headers: {
        'Content-Type': 'application/json',
    },
    timeout: 60000, // 60 second timeout for better reliability
});

// Retry interceptor for 503 and transient errors
api.interceptors.response.use(
    (response) => response,
    async (error) => {
        const config = error.config;
        
        // Don't retry if no config or already retried 3 times
        if (!config || config._retryCount >= 3) {
            return Promise.reject(error);
        }
        
        // Check if error is retryable (503, 429, network errors)
        const status = error.response?.status;
        const isRetryable = status === 503 || status === 429 || status === 502 || !error.response;
        
        if (isRetryable) {
            config._retryCount = (config._retryCount || 0) + 1;
            const delay = Math.min(1000 * Math.pow(2, config._retryCount - 1), 10000);
            console.log(`Retrying request (attempt ${config._retryCount}/3) in ${delay}ms...`);
            
            await new Promise(resolve => setTimeout(resolve, delay));
            return api(config);
        }
        
        return Promise.reject(error);
    }
);

export const login = async (email, password) => {
    const response = await api.post('/auth/login', { email, password });
    return response.data;
};

export const signup = async (email, password, fullName) => {
    const response = await api.post('/auth/signup', { email, password, full_name: fullName });
    return response.data;
};

export const loginWithGoogle = async (accessToken) => {
    const response = await api.post('/auth/google', { access_token: accessToken });
    return response.data;
};

export const createProject = async (name) => {
    const response = await api.post('/projects/', { name });
    return response.data;
};

export const deleteProject = async (projectId) => {
    await api.delete(`/projects/${projectId}`);
};

export const getProjects = async () => {
    const response = await api.get('/projects/');
    return response.data;
};

export const uploadDocument = async (projectId, file, onProgress) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('project_id', projectId);

    const response = await axios.post(`${API_URL}/documents/upload`, formData, {
        headers: {
            'Content-Type': 'multipart/form-data',
            // Forward auth token if it exists (axios interceptor might handle this, but good to be explicit if not using the instance)
            ...api.defaults.headers.common
        },
        onUploadProgress: (progressEvent) => {
            if (onProgress) {
                const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
                onProgress(percentCompleted);
            }
        }
    });
    return response.data;
};

export const getDocuments = async (projectId) => {
    const response = await api.get(`/documents/${projectId}`, { params: { _: Date.now() } });
    return response.data;
};

export const getChatHistory = async (projectId) => {
    const response = await api.get(`/chat/history/${projectId}`);
    return response.data;
};

export const chatMessage = async (projectId, message, history = []) => {
    const response = await api.post('/chat/message', {
        project_id: projectId,
        message,
        session_history: history
    });
    return response.data;
};

export const chatMessageStream = async (projectId, message, history = [], selectedDocuments = [], onChunk, onComplete) => {
    const maxRetries = 3;
    let lastError = null;
    
    for (let attempt = 0; attempt < maxRetries; attempt++) {
        try {
            const token = localStorage.getItem('token');
            const response = await fetch(`${API_URL}/chat/stream`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({
                    project_id: projectId,
                    message,
                    session_history: history,
                    selected_documents: selectedDocuments
                })
            });

            // Check for retryable HTTP errors
            if (response.status === 503 || response.status === 429 || response.status === 502) {
                const delay = Math.min(1500 * Math.pow(2, attempt), 10000);
                console.log(`Service unavailable (${response.status}), retrying in ${delay}ms (attempt ${attempt + 1}/${maxRetries})...`);
                await new Promise(resolve => setTimeout(resolve, delay));
                continue;
            }

            // Check for other HTTP errors
            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(errorText || `HTTP error ${response.status}`);
            }

            // Check for null body
            if (!response.body) {
                throw new Error('Response body is empty');
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let fullText = '';
            let sources = [];

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                fullText += chunk;

                // Check for sources delimiter in accumulated text
                if (fullText.includes('__SOURCES__:')) {
                    const parts = fullText.split('__SOURCES__:');
                    const textPart = parts[0];
                    const sourcesJson = parts[1];

                    try {
                        // Clean and parse sources
                        const cleanSourcesJson = sourcesJson.trim();
                        sources = JSON.parse(cleanSourcesJson);
                        console.log('Sources parsed successfully:', sources);

                        // Update with clean text
                        onChunk(textPart);
                        fullText = textPart; // Reset to just text without marker
                    } catch (e) {
                        console.warn('JSON parse incomplete, continuing...', e.message);
                        // Continue reading, JSON might be split across chunks
                    }
                } else {
                    // Normal streaming without sources marker
                    onChunk(fullText);
                }
            }

            // Stream complete - use parsed sources
            console.log('Stream finished. Sources:', sources);
            onComplete({ answer: fullText, sources: sources });
            return; // Success, exit retry loop

        } catch (error) {
            lastError = error;
            const errorStr = error.message?.toLowerCase() || '';
            const isRetryable = errorStr.includes('503') || errorStr.includes('service unavailable') || 
                               errorStr.includes('network') || errorStr.includes('fetch');
            
            if (isRetryable && attempt < maxRetries - 1) {
                const delay = Math.min(1500 * Math.pow(2, attempt), 10000);
                console.log(`Retryable error: ${error.message}. Retrying in ${delay}ms (attempt ${attempt + 1}/${maxRetries})...`);
                await new Promise(resolve => setTimeout(resolve, delay));
                continue;
            }
            
            console.error("Streaming error:", error);
            onComplete({ answer: `Error: ${error.message}. Please try again.`, sources: [] });
            return;
        }
    }
    
    // All retries exhausted
    console.error("All retries exhausted:", lastError);
    onComplete({ answer: "Service temporarily unavailable. Please try again in a moment.", sources: [] });
};

export const getProjectSummary = async (projectId, selectedDocuments = []) => {
    const response = await api.post('/chat/summary', {
        project_id: projectId,
        selected_documents: selectedDocuments
    });
    return response.data;
};

// generateQA removed


export const generateMCQ = async (projectId, topic, numQuestions, selectedDocuments = [], difficulty = 'medium') => {
    const response = await api.post('/mcq/generate', {
        project_id: projectId,
        topic: topic,
        num_questions: parseInt(numQuestions),
        selected_documents: selectedDocuments,
        difficulty: difficulty
    });
    return response.data;
};

export const getTopics = async (projectId) => {
    const response = await api.get(`/mcq/topics/${projectId}`);
    return response.data;
};

export const submitEvaluation = async (projectId, question, userAnswer) => {
    const response = await api.post('/evaluation/submit', {
        project_id: projectId,
        question,
        user_answer: userAnswer
    });
    return response.data;
};

export const generateSubjectiveTest = async (projectId, topic, numQuestions, selectedDocuments = [], answerSize = 'medium') => {
    const response = await api.post('/evaluation/generate-test', {
        project_id: projectId,
        topic: topic,
        num_questions: parseInt(numQuestions),
        selected_documents: selectedDocuments,
        answer_size: answerSize
    });
    return response.data;
};

export const submitSubjectiveTest = async (testId, answers) => {
    const response = await api.post('/evaluation/submit-test', {
        test_id: testId,
        answers: answers
    });
    return response.data;
};

export const deleteDocument = async (projectId, documentId) => {
    const response = await api.delete(`/documents/${documentId}`, {
        params: { project_id: projectId }
    });
    return response.data;
};

export const generateNotes = async (projectId, noteType, topic, selectedDocuments = []) => {
    const response = await api.post('/notes/generate', {
        project_id: projectId,
        note_type: noteType,
        topic: topic,
        selected_documents: selectedDocuments
    });
    return response.data;
};


// ============== Learning API (Adaptive Learning System) ==============

// Performance Tracking
export const recordPerformance = async (projectId, topic, correct, wrong) => {
    const response = await api.post('/learning/performance/record', {
        project_id: projectId,
        topic,
        correct,
        wrong
    });
    return response.data;
};

export const getPerformance = async (projectId, topic = null) => {
    const params = topic ? { topic } : {};
    const response = await api.get(`/learning/performance/${projectId}`, { params });
    return response.data;
};

// Weakness Detection
export const getWeakTopics = async (projectId, topK = 5, threshold = 0.3) => {
    const response = await api.get(`/learning/weak-topics/${projectId}`, {
        params: { top_k: topK, threshold }
    });
    return response.data;
};

// Spaced Repetition
export const createReviewCard = async (projectId, topic, question, answer) => {
    const response = await api.post('/learning/review-cards', {
        project_id: projectId,
        topic,
        question,
        answer
    });
    return response.data;
};

export const createCardsFromQuiz = async (projectId, topic, questions, wrongOnly = true) => {
    const response = await api.post('/learning/review-cards/from-quiz', {
        project_id: projectId,
        topic,
        questions,
        wrong_only: wrongOnly
    });
    return response.data;
};

export const getDueCards = async (projectId = null, limit = 20) => {
    const params = { limit };
    if (projectId) params.project_id = projectId;
    const response = await api.get('/learning/review-cards/due', { params });
    return response.data;
};

export const recordReview = async (cardId, quality) => {
    const response = await api.post(`/learning/review-cards/${cardId}/review`, {
        quality
    });
    return response.data;
};

export const deleteReviewCard = async (cardId) => {
    const response = await api.delete(`/learning/review-cards/${cardId}`);
    return response.data;
};

export const getReviewStats = async (projectId = null) => {
    const params = projectId ? { project_id: projectId } : {};
    const response = await api.get('/learning/review-stats', { params });
    return response.data;
};

// Learning Dashboard
export const getLearningDashboard = async (projectId) => {
    const response = await api.get(`/learning/dashboard/${projectId}`);
    return response.data;
};

export const getAllLearningStats = async () => {
    const response = await api.get('/learning/stats/all');
    return response.data;
};

// Knowledge Graph
export const buildKnowledgeGraph = async (projectId, topics, forceRebuild = false) => {
    const response = await api.post(`/learning/knowledge-graph/${projectId}/build`, {
        topics,
        force_rebuild: forceRebuild
    });
    return response.data;
};

export const getKnowledgeGraph = async (projectId) => {
    const response = await api.get(`/learning/knowledge-graph/${projectId}`);
    return response.data;
};

export const getRelatedTopics = async (projectId, topic, maxDistance = 2) => {
    const response = await api.get(
        `/learning/knowledge-graph/${projectId}/related/${encodeURIComponent(topic)}`,
        { params: { max_distance: maxDistance } }
    );
    return response.data;
};

export const getLearningPath = async (projectId, targetTopics = null) => {
    const params = targetTopics ? { target_topics: targetTopics.join(',') } : {};
    const response = await api.get(`/learning/knowledge-graph/${projectId}/learning-path`, { params });
    return response.data;
};

export const getTopicPrerequisites = async (projectId, topic) => {
    const response = await api.get(
        `/learning/knowledge-graph/${projectId}/prerequisites/${encodeURIComponent(topic)}`
    );
    return response.data;
};

export const getSuggestedTopic = async (projectId) => {
    const response = await api.get(`/learning/suggested-topic/${projectId}`);
    return response.data;
};

// ============== Search API ==============

export const searchDocuments = async (projectId, query, documentIds = null, limit = 10) => {
    const response = await api.post(`/documents/${projectId}/search`, {
        query,
        document_ids: documentIds,
        limit
    });
    return response.data;
};

// ============== Knowledge Graph API ==============

// Get full knowledge graph for visualization
export const getKnowledgeGraphVisualization = async (projectId) => {
    const response = await api.get(`/knowledge-graph/graph/${projectId}`);
    return response.data;
};

// Get topic summary using RAG
export const getTopicSummary = async (projectId, topic, forceRegenerate = false) => {
    const response = await api.post('/knowledge-graph/topic-summary', {
        project_id: projectId,
        topic,
        force_regenerate: forceRegenerate
    });
    return response.data;
};

// Record user interaction with graph
export const recordGraphInteraction = async (projectId, topic, eventType, durationMs = 0, metadata = null) => {
    const response = await api.post('/knowledge-graph/analytics/record', {
        project_id: projectId,
        topic,
        event_type: eventType,
        duration_ms: durationMs,
        metadata
    });
    return response.data;
};

// Record batch interactions
export const recordBatchInteractions = async (projectId, interactions) => {
    const response = await api.post('/knowledge-graph/analytics/record-batch', {
        project_id: projectId,
        interactions
    });
    return response.data;
};

// Get user analytics
export const getGraphAnalytics = async (projectId, days = 7) => {
    const response = await api.get(`/knowledge-graph/analytics/${projectId}`, {
        params: { days }
    });
    return response.data;
};

// Get learning suggestions
export const getLearningSuggestions = async (projectId, currentTopic = null, limit = 3) => {
    const response = await api.post('/knowledge-graph/suggestions', {
        project_id: projectId,
        current_topic: currentTopic,
        limit
    });
    return response.data;
};

// Start learning session
export const startLearningSession = async (projectId) => {
    const response = await api.post('/knowledge-graph/session/start', {
        project_id: projectId
    });
    return response.data;
};

// End learning session
export const endLearningSession = async (sessionId, topicsVisited, totalTimeMs) => {
    const response = await api.post('/knowledge-graph/session/end', {
        session_id: sessionId,
        topics_visited: topicsVisited,
        total_time_ms: totalTimeMs
    });
    return response.data;
};

// ============== User Data API (replaces localStorage) ==============

// --- Settings ---
export const getUserSettings = async () => {
    const response = await api.get('/user-data/settings');
    return response.data;
};

export const saveUserSettings = async (settings) => {
    const response = await api.put('/user-data/settings', { settings });
    return response.data;
};

// --- Bookmarks ---
export const getBookmarks = async (projectId) => {
    const response = await api.get(`/user-data/bookmarks/${projectId}`);
    return response.data;
};

export const addBookmark = async (projectId, title, note = '', documentId = null, type = 'general', highlightText = null, color = null) => {
    const body = {
        project_id: projectId,
        title,
        note,
        document_id: documentId,
        type,
    };
    if (highlightText) body.highlight_text = highlightText;
    if (color) body.color = color;
    const response = await api.post('/user-data/bookmarks', body);
    return response.data;
};

export const updateBookmark = async (bookmarkId, updates) => {
    const response = await api.patch(`/user-data/bookmarks/${bookmarkId}`, updates);
    return response.data;
};

export const deleteBookmark = async (bookmarkId) => {
    const response = await api.delete(`/user-data/bookmarks/${bookmarkId}`);
    return response.data;
};

// --- Study Activity ---
export const getStudyActivity = async (projectId, days = 90) => {
    const response = await api.get(`/user-data/activity/${projectId}`, { params: { days } });
    return response.data;
};

export const recordStudyActivity = async (projectId, activityType, meta = null) => {
    const response = await api.post('/user-data/activity', {
        project_id: projectId,
        activity_type: activityType,
        meta,
    });
    return response.data;
};

// --- Exams ---
export const getExams = async (projectId) => {
    const response = await api.get(`/user-data/exams/${projectId}`);
    return response.data;
};

export const saveExam = async (projectId, name, examDate, topics = [], difficulty = 'medium') => {
    const response = await api.post('/user-data/exams', {
        project_id: projectId,
        name,
        exam_date: examDate,
        topics,
        difficulty,
    });
    return response.data;
};

export const deleteExam = async (examId) => {
    const response = await api.delete(`/user-data/exams/${examId}`);
    return response.data;
};

// --- Learning Progress ---
export const getLearningProgress = async (projectId) => {
    const response = await api.get(`/user-data/progress/${projectId}`);
    return response.data;
};

export const saveLearningProgress = async (projectId, completedTopics) => {
    const response = await api.put('/user-data/progress', {
        project_id: projectId,
        completed_topics: completedTopics,
    });
    return response.data;
};

// --- Pomodoro ---
export const getPomodoro = async (projectId = null, documentId = null) => {
    const params = {};
    if (projectId) params.project_id = projectId;
    if (documentId) params.document_id = documentId;
    const response = await api.get('/user-data/pomodoro', { params });
    return response.data;
};

export const savePomodoro = async (sessions, focusTimeMinutes, projectId = null, documentId = null) => {
    const response = await api.put('/user-data/pomodoro', {
        project_id: projectId,
        document_id: documentId,
        sessions,
        focus_time_minutes: focusTimeMinutes,
    });
    return response.data;
};

// --- Recent Searches ---
export const getRecentSearches = async (projectId) => {
    const response = await api.get(`/user-data/searches/${projectId}`);
    return response.data;
};

export const saveRecentSearch = async (projectId, query) => {
    const response = await api.post('/user-data/searches', {
        project_id: projectId,
        query,
    });
    return response.data;
};

export const clearRecentSearches = async (projectId) => {
    const response = await api.delete(`/user-data/searches/${projectId}`);
    return response.data;
};

// --- Streaks ---
export const getStreak = async (projectId) => {
    const response = await api.get(`/user-data/streaks/${projectId}`);
    return response.data;
};

export const updateStreak = async (projectId) => {
    const response = await api.post(`/user-data/streaks/${projectId}`);
    return response.data;
};

// --- Gamification ---
export const getGamification = async () => {
    const response = await api.get('/user-data/gamification');
    return response.data;
};

export const awardXP = async (activityType, meta = null) => {
    const response = await api.post('/user-data/gamification/award-xp', {
        activity_type: activityType,
        meta,
    });
    return response.data;
};

