import React from 'react';
import {
    BookOpen, HelpCircle, CheckSquare, GitBranch, Layers,
    ExternalLink, Loader2, FileText, Sparkles
} from 'lucide-react';

const TOOL_CONFIG = {
    notes: {
        icon: BookOpen,
        label: 'Study Notes',
        color: 'text-emerald-600',
        bgColor: 'bg-emerald-50',
        borderColor: 'border-emerald-200',
        gradientFrom: 'from-emerald-50',
        gradientTo: 'to-green-50',
        accentBg: 'bg-emerald-500',
    },
    qa: {
        icon: HelpCircle,
        label: 'Q&A',
        color: 'text-blue-600',
        bgColor: 'bg-blue-50',
        borderColor: 'border-blue-200',
        gradientFrom: 'from-blue-50',
        gradientTo: 'to-cyan-50',
        accentBg: 'bg-blue-500',
    },
    quiz: {
        icon: CheckSquare,
        label: 'MCQ Quiz',
        color: 'text-purple-600',
        bgColor: 'bg-purple-50',
        borderColor: 'border-purple-200',
        gradientFrom: 'from-purple-50',
        gradientTo: 'to-violet-50',
        accentBg: 'bg-purple-500',
    },
    mindmap: {
        icon: GitBranch,
        label: 'Mindmap',
        color: 'text-indigo-600',
        bgColor: 'bg-indigo-50',
        borderColor: 'border-indigo-200',
        gradientFrom: 'from-indigo-50',
        gradientTo: 'to-blue-50',
        accentBg: 'bg-indigo-500',
    },
    flashcards: {
        icon: Layers,
        label: 'Flashcards',
        color: 'text-orange-600',
        bgColor: 'bg-orange-50',
        borderColor: 'border-orange-200',
        gradientFrom: 'from-orange-50',
        gradientTo: 'to-amber-50',
        accentBg: 'bg-orange-500',
    },
};

// --- Loading Card (shown while tool is generating) ---
export const ToolLoadingCard = ({ toolType, toolParams }) => {
    const config = TOOL_CONFIG[toolType];
    if (!config) return null;
    const Icon = config.icon;

    return (
        <div className={`max-w-[95%] md:max-w-[85%] rounded-2xl overflow-hidden border ${config.borderColor} shadow-sm animate-in fade-in slide-in-from-bottom-2 duration-300`}>
            <div className={`bg-gradient-to-r ${config.gradientFrom} ${config.gradientTo} px-5 py-4`}>
                <div className="flex items-center gap-3">
                    <div className={`h-10 w-10 ${config.bgColor} rounded-xl flex items-center justify-center`}>
                        <Icon className={`h-5 w-5 ${config.color}`} />
                    </div>
                    <div className="flex-1">
                        <div className="flex items-center gap-2">
                            <span className="font-bold text-[#4A3B32] text-sm">Generating {config.label}</span>
                            <div className="flex gap-1">
                                <div className="h-1.5 w-1.5 bg-[#C8A288] rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                                <div className="h-1.5 w-1.5 bg-[#C8A288] rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                                <div className="h-1.5 w-1.5 bg-[#C8A288] rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                            </div>
                        </div>
                        <p className="text-xs text-[#8a6a5c] mt-0.5">
                            {toolParams?.topic ? `Topic: ${toolParams.topic}` : 'General — from your documents'}
                        </p>
                    </div>
                </div>
                {/* Animated progress bar */}
                <div className="mt-3 h-1.5 bg-white/60 rounded-full overflow-hidden">
                    <div
                        className={`h-full ${config.accentBg} rounded-full animate-pulse`}
                        style={{ width: '60%', animation: 'pulse 1.5s ease-in-out infinite, grow 3s ease-in-out infinite' }}
                    />
                </div>
            </div>
        </div>
    );
};

// --- Result Card (shown after tool completes) ---
export const ToolResultCard = ({ toolType, toolParams, toolData, onOpen }) => {
    const config = TOOL_CONFIG[toolType];
    if (!config) return null;
    const Icon = config.icon;

    // Build summary stats based on tool type
    const getSummary = () => {
        switch (toolType) {
            case 'notes': {
                const len = toolData?.content?.length || 0;
                const words = toolData?.content?.split(/\s+/)?.length || 0;
                return { primary: `${words.toLocaleString()} words`, secondary: toolParams?.noteType || 'Summary' };
            }
            case 'qa': {
                const count = toolData?.questions?.length || 0;
                return { primary: `${count} questions`, secondary: toolParams?.answerSize ? `${toolParams.answerSize} answers` : '' };
            }
            case 'quiz': {
                const count = toolData?.questions?.length || 0;
                return { primary: `${count} MCQs`, secondary: toolParams?.difficulty || 'medium' };
            }
            case 'mindmap': {
                const branches = toolData?.mindmap?.children?.length || 0;
                return { primary: `${branches} branches`, secondary: 'Interactive tree' };
            }
            case 'flashcards': {
                const count = toolData?.flashcards?.length || toolData?.count || 0;
                return { primary: `${count} cards`, secondary: 'Flip to study' };
            }
            default:
                return { primary: '', secondary: '' };
        }
    };

    // Build preview snippet
    const getPreview = () => {
        switch (toolType) {
            case 'notes':
                return toolData?.content?.slice(0, 200)?.replace(/[#*_]/g, '') + '...' || '';
            case 'qa':
                return toolData?.questions?.[0]?.question || '';
            case 'quiz':
                return toolData?.questions?.[0]?.question || '';
            case 'mindmap':
                return toolData?.mindmap?.children?.map(c => c.label).join(' / ') || '';
            case 'flashcards':
                return toolData?.flashcards?.[0]?.front || '';
            default:
                return '';
        }
    };

    const summary = getSummary();
    const preview = getPreview();

    return (
        <div className={`max-w-[95%] md:max-w-[85%] rounded-2xl overflow-hidden border ${config.borderColor} shadow-sm hover:shadow-md transition-shadow animate-in fade-in slide-in-from-bottom-2 duration-300`}>
            {/* Header */}
            <div className={`bg-gradient-to-r ${config.gradientFrom} ${config.gradientTo} px-5 py-3.5 flex items-center justify-between`}>
                <div className="flex items-center gap-3">
                    <div className={`h-9 w-9 ${config.bgColor} rounded-xl flex items-center justify-center ring-1 ring-white/50`}>
                        <Icon className={`h-4.5 w-4.5 ${config.color}`} />
                    </div>
                    <div>
                        <div className="flex items-center gap-2">
                            <span className="font-bold text-[#4A3B32] text-sm">{config.label} Ready</span>
                            <Sparkles className="h-3.5 w-3.5 text-amber-500" />
                        </div>
                        <p className="text-xs text-[#8a6a5c]">
                            {toolParams?.topic || 'General'} {summary.secondary && `\u00b7 ${summary.secondary}`}
                        </p>
                    </div>
                </div>
                <div className={`px-2.5 py-1 rounded-full ${config.bgColor} ${config.color} text-xs font-bold`}>
                    {summary.primary}
                </div>
            </div>

            {/* Preview */}
            {preview && (
                <div className="px-5 py-3 bg-white border-t border-b border-[#E6D5CC]/30">
                    <p className="text-xs text-[#8a6a5c] line-clamp-2 leading-relaxed italic">
                        {toolType === 'qa' || toolType === 'quiz' ? (
                            <><span className="font-semibold not-italic text-[#4A3B32]">Q1:</span> {preview}</>
                        ) : toolType === 'flashcards' ? (
                            <><span className="font-semibold not-italic text-[#4A3B32]">Card 1:</span> {preview}</>
                        ) : toolType === 'mindmap' ? (
                            <><span className="font-semibold not-italic text-[#4A3B32]">Branches:</span> {preview}</>
                        ) : (
                            preview
                        )}
                    </p>
                </div>
            )}

            {/* Open Button */}
            <div className="px-5 py-3 bg-white flex items-center justify-between">
                <span className="text-xs text-[#8a6a5c]">
                    Generated from your documents
                </span>
                <button
                    onClick={() => onOpen(toolType, toolParams, toolData)}
                    className={`flex items-center gap-2 px-4 py-2 ${config.accentBg} text-white rounded-xl text-sm font-bold hover:opacity-90 transition-all shadow-sm`}
                >
                    <ExternalLink className="h-3.5 w-3.5" />
                    Open
                </button>
            </div>
        </div>
    );
};

// --- Error Card (shown on failure) ---
export const ToolErrorCard = ({ toolType, error, onRetry }) => {
    const config = TOOL_CONFIG[toolType] || TOOL_CONFIG.notes;
    const Icon = config.icon;

    return (
        <div className="max-w-[95%] md:max-w-[85%] rounded-2xl overflow-hidden border border-red-200 shadow-sm animate-in fade-in duration-200">
            <div className="bg-gradient-to-r from-red-50 to-orange-50 px-5 py-4">
                <div className="flex items-center gap-3">
                    <div className="h-9 w-9 bg-red-100 rounded-xl flex items-center justify-center">
                        <Icon className="h-4.5 w-4.5 text-red-500" />
                    </div>
                    <div className="flex-1">
                        <span className="font-bold text-red-700 text-sm">Failed to generate {config.label}</span>
                        <p className="text-xs text-red-500 mt-0.5">{error || 'Something went wrong. Please try again.'}</p>
                    </div>
                    {onRetry && (
                        <button
                            onClick={onRetry}
                            className="px-3 py-1.5 bg-red-500 text-white rounded-lg text-xs font-bold hover:bg-red-600 transition-colors"
                        >
                            Retry
                        </button>
                    )}
                </div>
            </div>
        </div>
    );
};

export default ToolResultCard;
