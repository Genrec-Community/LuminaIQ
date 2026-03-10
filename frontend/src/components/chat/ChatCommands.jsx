import React, { useState, useEffect, useRef } from 'react';
import {
    BookOpen, HelpCircle, CheckSquare,
    ChevronDown, Sparkles, X, ArrowRight,
    Brain, CreditCard
} from 'lucide-react';

// Command definitions with their parameters
const COMMANDS = [
    {
        id: 'notes',
        label: 'Notes',
        description: 'Generate study notes from your documents',
        icon: BookOpen,
        color: 'text-emerald-600',
        bgColor: 'bg-emerald-50',
        borderColor: 'border-emerald-200',
        params: [
            {
                key: 'noteType',
                label: 'Note Type',
                type: 'select',
                options: ['Comprehensive Summary', 'Bullet Point Key Facts', 'Glossary of Terms', 'Exam Cheat Sheet'],
                default: 'Comprehensive Summary',
                required: true,
            },
            {
                key: 'topic',
                label: 'Topic',
                type: 'topic', // special: uses availableTopics + custom input
                default: '',
                required: false,
                placeholder: 'Leave empty for general notes',
            },
        ],
    },
    {
        id: 'qa',
        label: 'Q&A',
        description: 'Generate questions and answers',
        icon: HelpCircle,
        color: 'text-blue-600',
        bgColor: 'bg-blue-50',
        borderColor: 'border-blue-200',
        params: [
            {
                key: 'topic',
                label: 'Topic',
                type: 'topic',
                default: '',
                required: false,
                placeholder: 'Leave empty for general Q&A',
            },
            {
                key: 'numQuestions',
                label: 'Questions',
                type: 'select',
                options: ['3', '5', '8', '10'],
                default: '5',
                required: true,
            },
            {
                key: 'answerSize',
                label: 'Answer Detail',
                type: 'select',
                options: ['small', 'medium', 'large'],
                default: 'medium',
                required: true,
            },
        ],
    },
    {
        id: 'quiz',
        label: 'Quiz',
        description: 'Generate MCQ quiz questions',
        icon: CheckSquare,
        color: 'text-purple-600',
        bgColor: 'bg-purple-50',
        borderColor: 'border-purple-200',
        params: [
            {
                key: 'topic',
                label: 'Topic',
                type: 'topic',
                default: '',
                required: false,
                placeholder: 'Leave empty for general quiz',
            },
            {
                key: 'numQuestions',
                label: 'Questions',
                type: 'select',
                options: ['5', '10', '15', '20'],
                default: '5',
                required: true,
            },
            {
                key: 'difficulty',
                label: 'Difficulty',
                type: 'select',
                options: ['easy', 'medium', 'hard'],
                default: 'medium',
                required: true,
            },
        ],
    },
    {
        id: 'mindmap',
        label: 'Mindmap',
        description: 'Generate a visual mindmap for a topic',
        icon: Brain,
        color: 'text-pink-600',
        bgColor: 'bg-pink-50',
        borderColor: 'border-pink-200',
        params: [
            {
                key: 'topic',
                label: 'Topic',
                type: 'topic',
                default: '',
                required: true,
                placeholder: 'Enter a topic for the mindmap',
            },
            {
                key: 'title',
                label: 'Title',
                type: 'text',
                default: '',
                required: false,
                placeholder: 'Optional custom title',
            },
        ],
    },
    {
        id: 'flashcards',
        label: 'Flashcards',
        description: 'Generate flashcards for studying',
        icon: CreditCard,
        color: 'text-orange-600',
        bgColor: 'bg-orange-50',
        borderColor: 'border-orange-200',
        params: [
            {
                key: 'topic',
                label: 'Topic',
                type: 'topic',
                default: '',
                required: true,
                placeholder: 'Enter a topic for flashcards',
            },
            {
                key: 'numCards',
                label: 'Number of Cards',
                type: 'select',
                options: ['5', '10', '15', '20'],
                default: '10',
                required: true,
            },
        ],
    },
];

// --- Command Picker Dropdown ---
export const CommandPicker = ({ filter, onSelect, onClose, visible }) => {
    const ref = useRef(null);
    const [selectedIndex, setSelectedIndex] = useState(0);

    const filtered = COMMANDS.filter(cmd =>
        cmd.id.includes(filter.toLowerCase()) || cmd.label.toLowerCase().includes(filter.toLowerCase())
    );

    useEffect(() => {
        setSelectedIndex(0);
    }, [filter]);

    useEffect(() => {
        const handleKey = (e) => {
            if (!visible) return;
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                setSelectedIndex(i => Math.min(i + 1, filtered.length - 1));
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                setSelectedIndex(i => Math.max(i - 1, 0));
            } else if (e.key === 'Enter' && filtered.length > 0) {
                e.preventDefault();
                onSelect(filtered[selectedIndex]);
            } else if (e.key === 'Escape') {
                e.preventDefault();
                onClose();
            }
        };
        window.addEventListener('keydown', handleKey);
        return () => window.removeEventListener('keydown', handleKey);
    }, [visible, filtered, selectedIndex, onSelect, onClose]);

    if (!visible || filtered.length === 0) return null;

    return (
        <div
            ref={ref}
            className="absolute bottom-full left-0 right-0 mb-2 bg-white rounded-2xl border border-[#E6D5CC] shadow-xl overflow-hidden z-30 animate-in fade-in slide-in-from-bottom-2 duration-200"
        >
            <div className="px-4 py-2.5 border-b border-[#E6D5CC]/50 flex items-center gap-2">
                <Sparkles className="h-3.5 w-3.5 text-[#C8A288]" />
                <span className="text-xs font-bold text-[#8a6a5c] uppercase tracking-wider">AI Tools</span>
            </div>
            <div className="py-1.5 max-h-[280px] overflow-y-auto">
                {filtered.map((cmd, idx) => {
                    const Icon = cmd.icon;
                    return (
                        <button
                            key={cmd.id}
                            onClick={() => onSelect(cmd)}
                            className={`w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors ${
                                idx === selectedIndex ? 'bg-[#FDF6F0]' : 'hover:bg-gray-50'
                            }`}
                        >
                            <div className={`h-9 w-9 rounded-xl ${cmd.bgColor} flex items-center justify-center shrink-0`}>
                                <Icon className={`h-4.5 w-4.5 ${cmd.color}`} />
                            </div>
                            <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2">
                                    <span className="font-semibold text-[#4A3B32] text-sm">@{cmd.label}</span>
                                </div>
                                <p className="text-xs text-[#8a6a5c] truncate">{cmd.description}</p>
                            </div>
                            <ArrowRight className="h-3.5 w-3.5 text-[#C8A288] opacity-0 group-hover:opacity-100 shrink-0" />
                        </button>
                    );
                })}
            </div>
        </div>
    );
};

// --- Command Parameter Form ---
export const CommandParamForm = ({ command, availableTopics, onExecute, onCancel, loading }) => {
    const [params, setParams] = useState(() => {
        const initial = {};
        command.params.forEach(p => {
            initial[p.key] = p.default;
        });
        return initial;
    });
    const [customTopic, setCustomTopic] = useState('');
    const [topicMode, setTopicMode] = useState('select'); // 'select' | 'custom'

    const Icon = command.icon;

    const handleSubmit = (e) => {
        e.preventDefault();
        // Resolve topic
        const resolved = { ...params };
        const topicParam = command.params.find(p => p.type === 'topic');
        if (topicParam) {
            if (topicMode === 'custom') {
                resolved[topicParam.key] = customTopic;
            }
        }
        // Validate required topic
        if (topicParam?.required && !resolved[topicParam.key]?.trim()) {
            return; // Don't submit if required topic is missing
        }
        onExecute(command.id, resolved);
    };

    const topicParam = command.params.find(p => p.type === 'topic');
    const isTopicValid = !topicParam?.required || 
        (topicMode === 'select' && params[topicParam?.key]) ||
        (topicMode === 'custom' && customTopic.trim());

    return (
        <div className="absolute bottom-full left-0 right-0 mb-2 z-30 animate-in fade-in slide-in-from-bottom-3 duration-300">
            <form
                onSubmit={handleSubmit}
                className={`bg-white rounded-2xl border ${command.borderColor} shadow-xl overflow-hidden`}
            >
                {/* Header */}
                <div className={`px-4 py-3 ${command.bgColor} border-b ${command.borderColor} flex items-center justify-between`}>
                    <div className="flex items-center gap-2.5">
                        <div className={`h-8 w-8 rounded-lg bg-white/80 flex items-center justify-center`}>
                            <Icon className={`h-4 w-4 ${command.color}`} />
                        </div>
                        <div>
                            <span className="font-bold text-sm text-[#4A3B32]">@{command.label}</span>
                            <p className="text-xs text-[#8a6a5c]">{command.description}</p>
                        </div>
                    </div>
                    <button
                        type="button"
                        onClick={onCancel}
                        className="p-1.5 rounded-lg hover:bg-black/5 transition-colors"
                    >
                        <X className="h-4 w-4 text-[#8a6a5c]" />
                    </button>
                </div>

                {/* Params */}
                <div className="p-4 space-y-3">
                    {command.params.map((param) => {
                        if (param.type === 'topic') {
                            return (
                                <div key={param.key}>
                                    <label className="block text-xs font-bold text-[#4A3B32] uppercase tracking-wide mb-1.5 opacity-80">
                                        {param.label} {param.required && <span className="text-red-400">*</span>}
                                    </label>
                                    {availableTopics.length > 0 ? (
                                        <div className="space-y-2">
                                            <div className="flex gap-2">
                                                <button
                                                    type="button"
                                                    onClick={() => setTopicMode('select')}
                                                    className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                                                        topicMode === 'select'
                                                            ? 'bg-[#C8A288] text-white'
                                                            : 'bg-gray-100 text-[#8a6a5c] hover:bg-gray-200'
                                                    }`}
                                                >
                                                    From Documents
                                                </button>
                                                <button
                                                    type="button"
                                                    onClick={() => setTopicMode('custom')}
                                                    className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                                                        topicMode === 'custom'
                                                            ? 'bg-[#C8A288] text-white'
                                                            : 'bg-gray-100 text-[#8a6a5c] hover:bg-gray-200'
                                                    }`}
                                                >
                                                    Custom
                                                </button>
                                            </div>
                                            {topicMode === 'select' ? (
                                                <div className="relative">
                                                    <select
                                                        value={params[param.key] || ''}
                                                        onChange={(e) => setParams(p => ({ ...p, [param.key]: e.target.value }))}
                                                        className="w-full px-3.5 py-2.5 bg-[#FDF6F0] border-0 rounded-xl focus:ring-2 focus:ring-[#C8A288] text-[#4A3B32] text-sm font-medium appearance-none"
                                                    >
                                                        <option value="">{param.required ? 'Select a topic...' : 'General (all topics)'}</option>
                                                        {availableTopics.map((t, i) => (
                                                            <option key={i} value={t}>{t}</option>
                                                        ))}
                                                    </select>
                                                    <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[#8a6a5c] pointer-events-none" />
                                                </div>
                                            ) : (
                                                <input
                                                    type="text"
                                                    value={customTopic}
                                                    onChange={(e) => setCustomTopic(e.target.value)}
                                                    placeholder={param.placeholder || 'Type a custom topic...'}
                                                    className="w-full px-3.5 py-2.5 bg-[#FDF6F0] border-0 rounded-xl focus:ring-2 focus:ring-[#C8A288] text-sm text-[#4A3B32]"
                                                    autoFocus
                                                />
                                            )}
                                        </div>
                                    ) : (
                                        <input
                                            type="text"
                                            value={customTopic}
                                            onChange={(e) => { setCustomTopic(e.target.value); setTopicMode('custom'); }}
                                            placeholder={param.placeholder || 'Type a topic...'}
                                            className="w-full px-3.5 py-2.5 bg-[#FDF6F0] border-0 rounded-xl focus:ring-2 focus:ring-[#C8A288] text-sm text-[#4A3B32]"
                                        />
                                    )}
                                </div>
                            );
                        }

                        // Select param
                        if (param.type === 'select') {
                            return (
                                <div key={param.key}>
                                    <label className="block text-xs font-bold text-[#4A3B32] uppercase tracking-wide mb-1.5 opacity-80">
                                        {param.label}
                                    </label>
                                    <div className="flex flex-wrap gap-1.5">
                                        {param.options.map(opt => (
                                            <button
                                                key={opt}
                                                type="button"
                                                onClick={() => setParams(p => ({ ...p, [param.key]: opt }))}
                                                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                                                    params[param.key] === opt
                                                        ? `${command.bgColor} ${command.color} ring-1 ring-current`
                                                        : 'bg-gray-50 text-[#8a6a5c] hover:bg-gray-100'
                                                }`}
                                            >
                                                {opt.charAt(0).toUpperCase() + opt.slice(1)}
                                            </button>
                                        ))}
                                    </div>
                                </div>
                            );
                        }

                        // Text param
                        if (param.type === 'text') {
                            return (
                                <div key={param.key}>
                                    <label className="block text-xs font-bold text-[#4A3B32] uppercase tracking-wide mb-1.5 opacity-80">
                                        {param.label} {param.required && <span className="text-red-400">*</span>}
                                    </label>
                                    <input
                                        type="text"
                                        value={params[param.key] || ''}
                                        onChange={(e) => setParams(p => ({ ...p, [param.key]: e.target.value }))}
                                        placeholder={param.placeholder || ''}
                                        className="w-full px-3.5 py-2.5 bg-[#FDF6F0] border-0 rounded-xl focus:ring-2 focus:ring-[#C8A288] text-sm text-[#4A3B32]"
                                    />
                                </div>
                            );
                        }

                        return null;
                    })}
                </div>

                {/* Footer */}
                <div className="px-4 pb-4 flex items-center gap-2">
                    <button
                        type="submit"
                        disabled={loading || !isTopicValid}
                        className={`flex-1 py-2.5 ${command.color.replace('text-', 'bg-').replace('-600', '-500')} text-white rounded-xl font-bold text-sm hover:opacity-90 disabled:opacity-40 transition-all flex items-center justify-center gap-2`}
                    >
                        {loading ? (
                            <>
                                <div className="h-4 w-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                Generating...
                            </>
                        ) : (
                            <>
                                <Sparkles className="h-4 w-4" />
                                Generate
                            </>
                        )}
                    </button>
                    <button
                        type="button"
                        onClick={onCancel}
                        disabled={loading}
                        className="px-4 py-2.5 bg-gray-100 text-[#8a6a5c] rounded-xl font-medium text-sm hover:bg-gray-200 transition-colors disabled:opacity-40"
                    >
                        Cancel
                    </button>
                </div>
            </form>
        </div>
    );
};

export { COMMANDS };
export default CommandPicker;
