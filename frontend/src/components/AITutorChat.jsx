import React, { useState, useRef, useEffect } from 'react';
import {
    Brain, Send, Loader2, Lightbulb, HelpCircle,
    BookOpen, Sparkles, RefreshCw, ThumbsUp, ThumbsDown,
    MessageSquare, GraduationCap, Baby, Microscope, X
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { recordActivity } from '../utils/studyActivity';
import { useSettings } from '../context/SettingsContext';

const AITutorChat = ({
    projectId,
    documentId = null,
    documentName = 'Your Documents',
    topic = null,
    onClose,
    selectedDocuments = []
}) => {
    const { settings } = useSettings();

    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const [tutorStyle, setTutorStyle] = useState(settings.tutorStyle || 'balanced');
    const [showStylePicker, setShowStylePicker] = useState(false);
    const messagesEndRef = useRef(null);
    const inputRef = useRef(null);

    const tutorStyles = {
        simple: {
            icon: Baby,
            name: 'Simple',
            description: 'Explain like I\'m 5',
            color: 'bg-green-500',
            prompt: 'Explain this concept in the simplest possible way, as if explaining to a young child. Use analogies, simple words, and avoid jargon.',
        },
        balanced: {
            icon: GraduationCap,
            name: 'Balanced',
            description: 'Clear with examples',
            color: 'bg-blue-500',
            prompt: 'Explain this concept clearly with practical examples. Use a balanced approach that is accessible but thorough.',
        },
        detailed: {
            icon: Microscope,
            name: 'Detailed',
            description: 'In-depth analysis',
            color: 'bg-purple-500',
            prompt: 'Provide a comprehensive, detailed explanation with technical depth. Include nuances, edge cases, and advanced concepts.',
        },
        socratic: {
            icon: Lightbulb,
            name: 'Socratic',
            description: 'Learn through questions',
            color: 'bg-amber-500',
            prompt: 'Use the Socratic method. Instead of giving direct answers, guide understanding through thoughtful questions that help discover the answer.',
        },
    };

    const quickPrompts = [
        { icon: HelpCircle, text: 'Explain this concept', prompt: 'Can you explain this concept in detail?' },
        { icon: Lightbulb, text: 'Give me an example', prompt: 'Can you give me a practical example of this?' },
        { icon: BookOpen, text: 'Summarize key points', prompt: 'What are the key points I should remember?' },
        { icon: Brain, text: 'Test my understanding', prompt: 'Can you ask me some questions to test my understanding?' },
    ];

    useEffect(() => {
        // Initial greeting
        const style = tutorStyles[tutorStyle];
        setMessages([{
            role: 'assistant',
            content: `Hello! I'm your AI tutor in **${style.name}** mode. ${
                topic ? `I see you're studying **${topic}**.` : `I'm here to help you learn from **${documentName}**.`
            }\n\nHow can I help you understand the material better?`,
        }]);
    }, []);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    const handleSend = async (customPrompt = null) => {
        const messageText = customPrompt || input.trim();
        if (!messageText || loading) return;

        const userMessage = { role: 'user', content: messageText };
        setMessages(prev => [...prev, userMessage]);
        setInput('');
        setLoading(true);

        try {
            const token = localStorage.getItem('token');
            const style = tutorStyles[tutorStyle];
            
            // Build context-aware prompt
            const systemPrompt = `You are an expert AI tutor. ${style.prompt}
            
${topic ? `The student is currently studying the topic: "${topic}".` : ''}
${documentName ? `They are learning from: "${documentName}".` : ''}

Guidelines:
- Be encouraging and supportive
- Break down complex concepts
- Use markdown formatting for clarity
- If the student seems confused, try explaining differently
- Provide examples from the document context when possible`;

            const response = await fetch(`${import.meta.env.VITE_MAIN_API_URL}/chat/stream`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({
                    project_id: projectId,
                    message: `[Tutor Mode: ${style.name}]\n\n${messageText}`,
                    session_history: messages.slice(-10).map(m => ({ role: m.role, content: m.content })),
                    selected_documents: selectedDocuments.length > 0 ? selectedDocuments : (documentId ? [documentId] : []),
                    system_prompt: systemPrompt
                })
            });

            if (!response.ok) throw new Error('Failed to get response');

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let fullText = '';

            // Add placeholder for assistant response
            setMessages(prev => [...prev, { role: 'assistant', content: '' }]);

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                fullText += chunk;

                // Remove sources marker for display
                const displayText = fullText.split('__SOURCES__:')[0];

                setMessages(prev => {
                    const updated = [...prev];
                    updated[updated.length - 1] = { role: 'assistant', content: displayText };
                    return updated;
                });
            }
            
            // Track chat activity for heatmap
            recordActivity(projectId, 'chat');
        } catch (error) {
            console.error('Tutor error:', error);
            setMessages(prev => [...prev, {
                role: 'assistant',
                content: 'I apologize, but I encountered an error. Please try again.',
            }]);
        } finally {
            setLoading(false);
            inputRef.current?.focus();
        }
    };

    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    const changeStyle = (newStyle) => {
        setTutorStyle(newStyle);
        setShowStylePicker(false);
        const style = tutorStyles[newStyle];
        setMessages(prev => [...prev, {
            role: 'assistant',
            content: `Switching to **${style.name}** mode. ${style.description}. How can I help you?`,
        }]);
    };

    const CurrentStyleIcon = tutorStyles[tutorStyle].icon;

    return (
        <div className="h-full flex flex-col bg-white rounded-2xl border border-[#E6D5CC] overflow-hidden">
            {/* Header */}
            <div className="p-4 border-b border-[#E6D5CC] bg-gradient-to-r from-[#C8A288] to-[#A08072] text-white">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="h-10 w-10 bg-white/20 rounded-xl flex items-center justify-center backdrop-blur-sm">
                            <Brain className="h-6 w-6" />
                        </div>
                        <div>
                            <h3 className="font-bold flex items-center gap-2">
                                AI Tutor
                                <span className={`text-xs px-2 py-0.5 rounded-full ${tutorStyles[tutorStyle].color} text-white`}>
                                    {tutorStyles[tutorStyle].name}
                                </span>
                            </h3>
                            <p className="text-sm opacity-90 truncate max-w-[200px]">
                                {topic || documentName}
                            </p>
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                        <button
                            onClick={() => setShowStylePicker(!showStylePicker)}
                            className="p-2 hover:bg-white/20 rounded-lg transition-colors"
                            title="Change teaching style"
                        >
                            <CurrentStyleIcon className="h-5 w-5" />
                        </button>
                        {onClose && (
                            <button
                                onClick={onClose}
                                className="p-2 hover:bg-white/20 rounded-lg transition-colors"
                            >
                                <X className="h-5 w-5" />
                            </button>
                        )}
                    </div>
                </div>

                {/* Style Picker */}
                {showStylePicker && (
                    <div className="mt-3 grid grid-cols-2 gap-2">
                        {Object.entries(tutorStyles).map(([key, style]) => {
                            const Icon = style.icon;
                            return (
                                <button
                                    key={key}
                                    onClick={() => changeStyle(key)}
                                    className={`p-3 rounded-xl text-left transition-all ${
                                        tutorStyle === key
                                            ? 'bg-white text-[#4A3B32]'
                                            : 'bg-white/20 hover:bg-white/30'
                                    }`}
                                >
                                    <div className="flex items-center gap-2 mb-1">
                                        <Icon className="h-4 w-4" />
                                        <span className="font-bold text-sm">{style.name}</span>
                                    </div>
                                    <p className="text-xs opacity-80">{style.description}</p>
                                </button>
                            );
                        })}
                    </div>
                )}
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {messages.map((msg, idx) => (
                    <div
                        key={idx}
                        className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                        <div
                            className={`max-w-[85%] rounded-2xl px-4 py-3 ${
                                msg.role === 'user'
                                    ? 'bg-[#C8A288] text-white rounded-br-none'
                                    : 'bg-[#FDF6F0] text-[#4A3B32] rounded-bl-none'
                            }`}
                        >
                            {msg.content ? (
                                <div className={`text-sm prose prose-sm max-w-none ${
                                    msg.role === 'user' ? 'prose-invert' : ''
                                }`}>
                                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                        {msg.content}
                                    </ReactMarkdown>
                                </div>
                            ) : (
                                <Loader2 className="h-5 w-5 animate-spin" />
                            )}
                        </div>
                    </div>
                ))}
                <div ref={messagesEndRef} />
            </div>

            {/* Quick Prompts */}
            {messages.length <= 2 && (
                <div className="px-4 pb-2">
                    <p className="text-xs text-[#8a6a5c] mb-2">Quick questions:</p>
                    <div className="flex flex-wrap gap-2">
                        {quickPrompts.map((prompt, idx) => {
                            const Icon = prompt.icon;
                            return (
                                <button
                                    key={idx}
                                    onClick={() => handleSend(prompt.prompt)}
                                    disabled={loading}
                                    className="flex items-center gap-1.5 px-3 py-1.5 bg-[#FDF6F0] text-[#4A3B32] rounded-full text-xs font-medium hover:bg-[#E6D5CC] transition-colors disabled:opacity-50"
                                >
                                    <Icon className="h-3 w-3" />
                                    {prompt.text}
                                </button>
                            );
                        })}
                    </div>
                </div>
            )}

            {/* Input */}
            <div className="p-4 border-t border-[#E6D5CC] bg-white">
                <div className="flex gap-3">
                    <div className="flex-1 relative">
                        <textarea
                            ref={inputRef}
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyDown={handleKeyDown}
                            placeholder="Ask me anything about the material..."
                            rows={1}
                            className="w-full px-4 py-3 bg-[#FDF6F0] border-none rounded-xl focus:ring-2 focus:ring-[#C8A288] outline-none text-[#4A3B32] placeholder-[#8a6a5c] resize-none"
                            disabled={loading}
                        />
                    </div>
                    <button
                        onClick={() => handleSend()}
                        disabled={loading || !input.trim()}
                        className="px-4 py-3 bg-[#C8A288] text-white rounded-xl hover:bg-[#B08B72] transition-colors disabled:opacity-50 flex items-center gap-2"
                    >
                        {loading ? (
                            <Loader2 className="h-5 w-5 animate-spin" />
                        ) : (
                            <Send className="h-5 w-5" />
                        )}
                    </button>
                </div>
                <p className="text-xs text-[#8a6a5c] mt-2 text-center">
                    Tip: Press Enter to send, Shift+Enter for new line
                </p>
            </div>
        </div>
    );
};

export default AITutorChat;
