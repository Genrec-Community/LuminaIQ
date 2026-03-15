import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
    GitBranch, X, RefreshCw, ZoomIn, ZoomOut,
    ChevronRight, ChevronDown, Circle, ArrowLeft
} from 'lucide-react';
import { generateMindmapLegacy as generateMindmap } from '../../api';

const NODE_COLORS = [
    { bg: 'bg-blue-100', border: 'border-blue-300', text: 'text-blue-800', line: '#93c5fd' },
    { bg: 'bg-emerald-100', border: 'border-emerald-300', text: 'text-emerald-800', line: '#6ee7b7' },
    { bg: 'bg-purple-100', border: 'border-purple-300', text: 'text-purple-800', line: '#c4b5fd' },
    { bg: 'bg-amber-100', border: 'border-amber-300', text: 'text-amber-800', line: '#fcd34d' },
    { bg: 'bg-rose-100', border: 'border-rose-300', text: 'text-rose-800', line: '#fda4af' },
    { bg: 'bg-cyan-100', border: 'border-cyan-300', text: 'text-cyan-800', line: '#67e8f9' },
];

// Recursive mindmap node component
const MindmapNode = ({ node, depth = 0, colorIndex = 0, isLast = false }) => {
    const [expanded, setExpanded] = useState(depth < 2);
    const hasChildren = node.children && node.children.length > 0;
    const color = NODE_COLORS[colorIndex % NODE_COLORS.length];

    if (depth === 0) {
        // Root node
        return (
            <div className="flex flex-col items-center">
                <div className="px-6 py-3 bg-gradient-to-br from-[#C8A288] to-[#A08072] text-white rounded-2xl shadow-lg font-bold text-lg text-center max-w-xs border-2 border-white/20">
                    {node.label}
                </div>
                {hasChildren && (
                    <div className="mt-4 flex flex-col items-center w-full">
                        {/* Vertical connector from root */}
                        <div className="w-0.5 h-6 bg-[#C8A288]" />
                        {/* Horizontal branch bar */}
                        <div className="relative w-full flex justify-center">
                            {node.children.length > 1 && (
                                <div
                                    className="absolute top-0 h-0.5 bg-[#E6D5CC]"
                                    style={{
                                        left: `${100 / (node.children.length * 2)}%`,
                                        right: `${100 / (node.children.length * 2)}%`,
                                    }}
                                />
                            )}
                        </div>
                        {/* Branch children */}
                        <div className="grid gap-4 w-full" style={{
                            gridTemplateColumns: `repeat(${Math.min(node.children.length, 3)}, 1fr)`,
                        }}>
                            {node.children.map((child, idx) => (
                                <div key={idx} className="flex flex-col items-center">
                                    <div className="w-0.5 h-4 bg-[#E6D5CC]" />
                                    <MindmapNode
                                        node={child}
                                        depth={1}
                                        colorIndex={idx}
                                        isLast={idx === node.children.length - 1}
                                    />
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </div>
        );
    }

    // Branch and leaf nodes
    return (
        <div className="flex flex-col items-center w-full">
            <button
                onClick={() => hasChildren && setExpanded(!expanded)}
                className={`w-full px-4 py-2.5 ${color.bg} ${color.border} border-2 rounded-xl font-semibold text-sm ${color.text} text-center transition-all hover:shadow-md ${hasChildren ? 'cursor-pointer' : 'cursor-default'} relative group`}
            >
                <div className="flex items-center justify-center gap-1.5">
                    {hasChildren && (
                        expanded ?
                            <ChevronDown className="h-3.5 w-3.5 flex-shrink-0" /> :
                            <ChevronRight className="h-3.5 w-3.5 flex-shrink-0" />
                    )}
                    {!hasChildren && <Circle className="h-2 w-2 flex-shrink-0 fill-current opacity-50" />}
                    <span className="leading-tight">{node.label}</span>
                </div>
            </button>

            {hasChildren && expanded && (
                <div className="mt-2 w-full flex flex-col items-center">
                    <div className="w-0.5 h-3" style={{ backgroundColor: color.line }} />
                    <div className="space-y-2 w-full pl-3">
                        {node.children.map((child, idx) => (
                            <div key={idx} className="flex items-start gap-2">
                                <div className="flex flex-col items-center mt-3 flex-shrink-0">
                                    <div className="w-3 h-0.5" style={{ backgroundColor: color.line }} />
                                </div>
                                <div className="flex-1 min-w-0">
                                    <MindmapNode
                                        node={child}
                                        depth={depth + 1}
                                        colorIndex={colorIndex}
                                        isLast={idx === node.children.length - 1}
                                    />
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
};


const TopicMindmap = ({ projectId, topic, selectedDocuments = [], onClose }) => {
    const [loading, setLoading] = useState(true);
    const [mindmapData, setMindmapData] = useState(null);
    const [error, setError] = useState(null);
    const [scale, setScale] = useState(1);
    const containerRef = useRef(null);

    const loadMindmap = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const data = await generateMindmap(projectId, topic, selectedDocuments);
            if (data.success && data.mindmap) {
                setMindmapData(data.mindmap);
            } else {
                setError('Failed to generate mindmap');
            }
        } catch (err) {
            console.error('Mindmap generation failed:', err);
            setError(err.response?.data?.detail || 'Failed to generate mindmap. Please try again.');
        } finally {
            setLoading(false);
        }
    }, [projectId, topic, selectedDocuments]);

    useEffect(() => {
        loadMindmap();
    }, [loadMindmap]);

    const handleZoomIn = () => setScale(s => Math.min(s + 0.15, 2));
    const handleZoomOut = () => setScale(s => Math.max(s - 0.15, 0.5));

    return (
        <div className="h-full flex flex-col bg-white">
            {/* Header */}
            <div className="px-4 md:px-6 py-4 border-b border-[#E6D5CC] bg-white flex items-center justify-between flex-shrink-0">
                <div className="flex items-center gap-3 min-w-0">
                    <button
                        onClick={onClose}
                        className="p-2 hover:bg-[#FDF6F0] rounded-lg transition-colors text-[#8a6a5c] flex-shrink-0"
                        title="Back to Learning Path"
                    >
                        <ArrowLeft className="h-5 w-5" />
                    </button>
                    <div className="h-10 w-10 bg-gradient-to-br from-indigo-500 to-purple-500 rounded-xl flex items-center justify-center text-white flex-shrink-0">
                        <GitBranch className="h-5 w-5" />
                    </div>
                    <div className="min-w-0">
                        <h3 className="font-bold text-[#4A3B32] text-lg truncate">Mindmap</h3>
                        <p className="text-xs text-[#8a6a5c] truncate">{topic}</p>
                    </div>
                </div>

                <div className="flex items-center gap-1 flex-shrink-0">
                    <button
                        onClick={handleZoomOut}
                        className="p-2 hover:bg-[#FDF6F0] rounded-lg transition-colors text-[#8a6a5c]"
                        title="Zoom out"
                    >
                        <ZoomOut className="h-4 w-4" />
                    </button>
                    <span className="text-xs font-medium text-[#8a6a5c] w-10 text-center">
                        {Math.round(scale * 100)}%
                    </span>
                    <button
                        onClick={handleZoomIn}
                        className="p-2 hover:bg-[#FDF6F0] rounded-lg transition-colors text-[#8a6a5c]"
                        title="Zoom in"
                    >
                        <ZoomIn className="h-4 w-4" />
                    </button>
                    <div className="w-px h-5 bg-[#E6D5CC] mx-1" />
                    <button
                        onClick={loadMindmap}
                        disabled={loading}
                        className="p-2 hover:bg-[#FDF6F0] rounded-lg transition-colors text-[#8a6a5c] disabled:opacity-50"
                        title="Regenerate"
                    >
                        <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                    </button>
                </div>
            </div>

            {/* Content */}
            <div
                ref={containerRef}
                className="flex-1 overflow-auto p-6 md:p-10 bg-[#FDF6F0]/50"
            >
                {loading ? (
                    <div className="flex flex-col items-center justify-center h-full gap-4">
                        <div className="relative">
                            <div className="h-16 w-16 border-4 border-[#E6D5CC] rounded-full" />
                            <div className="absolute inset-0 h-16 w-16 border-4 border-indigo-400 rounded-full border-t-transparent animate-spin" />
                            <GitBranch className="absolute inset-0 m-auto h-6 w-6 text-indigo-500" />
                        </div>
                        <div className="text-center">
                            <p className="text-[#4A3B32] font-bold">Generating Mindmap</p>
                            <p className="text-xs text-[#8a6a5c] mt-1">Analyzing "{topic}" from your documents...</p>
                        </div>
                    </div>
                ) : error ? (
                    <div className="flex flex-col items-center justify-center h-full gap-4">
                        <div className="h-16 w-16 bg-red-100 rounded-full flex items-center justify-center">
                            <X className="h-8 w-8 text-red-500" />
                        </div>
                        <p className="text-[#4A3B32] font-bold">Generation Failed</p>
                        <p className="text-sm text-[#8a6a5c] text-center max-w-md">{error}</p>
                        <button
                            onClick={loadMindmap}
                            className="px-4 py-2 bg-[#C8A288] text-white rounded-lg font-medium hover:bg-[#B08B72] transition-colors flex items-center gap-2"
                        >
                            <RefreshCw className="h-4 w-4" />
                            Try Again
                        </button>
                    </div>
                ) : mindmapData ? (
                    <div
                        className="flex justify-center min-h-full"
                        style={{
                            transform: `scale(${scale})`,
                            transformOrigin: 'top center',
                            transition: 'transform 0.2s ease',
                        }}
                    >
                        <div className="inline-block min-w-[300px] max-w-4xl w-full">
                            <MindmapNode node={mindmapData} />
                        </div>
                    </div>
                ) : null}
            </div>
        </div>
    );
};

export default TopicMindmap;
