import axios from 'axios';

const API_URL = import.meta.env.VITE_MAIN_API_URL //|| 'http://localhost:8000/api/v1';

export const api = axios.create({
    baseURL: API_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

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
    try {
        const token = localStorage.getItem('token'); // Retrieve token
        const response = await fetch(`${API_URL}/chat/stream`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}` // Add Auth header
            },
            body: JSON.stringify({
                project_id: projectId,
                message,
                session_history: history,
                selected_documents: selectedDocuments
            })
        });

        // Check for HTTP errors before reading stream
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

    } catch (error) {
        console.error("Streaming error:", error);
        onComplete({ answer: "Error streaming response.", sources: [] });
    }
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

