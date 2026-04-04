import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Zap, Plus, Trash2, Eye, Loader2, Download, X, ZoomIn, ZoomOut, Maximize2, RefreshCw } from 'lucide-react';
import { useToast } from '../../context/ToastContext';
import { getMindmaps, generateMindmap as generateMindmapAPI, deleteMindmap as deleteMindmapAPI } from '../../api';
import { createLogger } from '../../utils/logger';

const logger = createLogger('MindmapView');

// ======================== Mindmap Tree Renderer ========================

const BRANCH_COLORS = [
    { bg: '#E8F5E9', border: '#66BB6A', text: '#2E7D32' },
    { bg: '#E3F2FD', border: '#42A5F5', text: '#1565C0' },
    { bg: '#FFF3E0', border: '#FFA726', text: '#E65100' },
    { bg: '#F3E5F5', border: '#AB47BC', text: '#6A1B9A' },
    { bg: '#E0F7FA', border: '#26C6DA', text: '#00695C' },
    { bg: '#FBE9E7', border: '#EF5350', text: '#B71C1C' },
    { bg: '#FFFDE7', border: '#FFEE58', text: '#F57F17' },
    { bg: '#E8EAF6', border: '#5C6BC0', text: '#283593' },
];

const MindmapRenderer = ({ data }) => {
    const containerRef = useRef(null);
    const [zoom, setZoom] = useState(1);
    const [pan, setPan] = useState({ x: 0, y: 0 });
    const [isDragging, setIsDragging] = useState(false);
    const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
    const [expandedNodes, setExpandedNodes] = useState(new Set());

    // Build tree structure from flat nodes/edges
    const tree = React.useMemo(() => {
        if (!data?.nodes?.length) return null;
        
        const nodesMap = {};
        data.nodes.forEach(n => {
            nodesMap[n.id] = { ...n, children: [] };
        });
        
        // Build parent-child relationships from edges
        const childIds = new Set();
        (data.edges || []).forEach(e => {
            const parent = nodesMap[e.from];
            const child = nodesMap[e.to];
            if (parent && child) {
                parent.children.push(child);
                childIds.add(e.to);
            }
        });
        
        // Also check parent field on nodes as fallback
        data.nodes.forEach(n => {
            if (n.parent && nodesMap[n.parent] && !childIds.has(n.id)) {
                nodesMap[n.parent].children.push(nodesMap[n.id]);
                childIds.add(n.id);
            }
        });
        
        // Find root (level 0, or first node without parent)
        const root = data.nodes.find(n => n.level === 0) 
            || data.nodes.find(n => !childIds.has(n.id))
            || data.nodes[0];
        
        return nodesMap[root.id];
    }, [data]);

    // Initialize all nodes as expanded
    useEffect(() => {
        if (data?.nodes) {
            setExpandedNodes(new Set(data.nodes.map(n => n.id)));
        }
    }, [data]);

    const toggleNode = (nodeId) => {
        setExpandedNodes(prev => {
            const next = new Set(prev);
            if (next.has(nodeId)) {
                next.delete(nodeId);
            } else {
                next.add(nodeId);
            }
            return next;
        });
    };

    // Pan/zoom handlers
    const handleMouseDown = (e) => {
        if (e.target.closest('.mindmap-node')) return;
        setIsDragging(true);
        setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
    };

    const handleMouseMove = useCallback((e) => {
        if (!isDragging) return;
        setPan({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y });
    }, [isDragging, dragStart]);

    const handleMouseUp = () => setIsDragging(false);

    useEffect(() => {
        if (isDragging) {
            window.addEventListener('mousemove', handleMouseMove);
            window.addEventListener('mouseup', handleMouseUp);
            return () => {
                window.removeEventListener('mousemove', handleMouseMove);
                window.removeEventListener('mouseup', handleMouseUp);
            };
        }
    }, [isDragging, handleMouseMove]);

    const handleWheel = (e) => {
        e.preventDefault();
        const delta = e.deltaY > 0 ? -0.1 : 0.1;
        setZoom(prev => Math.max(0.3, Math.min(2, prev + delta)));
    };

    const resetView = () => {
        setZoom(1);
        setPan({ x: 0, y: 0 });
    };

    // Recursive node renderer
    const renderNode = (node, depth = 0, branchIndex = 0) => {
        if (!node) return null;
        const isRoot = depth === 0;
        const isExpanded = expandedNodes.has(node.id);
        const hasChildren = node.children && node.children.length > 0;
        const color = BRANCH_COLORS[branchIndex % BRANCH_COLORS.length];

        return (
            <div key={node.id} className="flex flex-col items-center">
                {/* Node */}
                <div
                    className="mindmap-node relative cursor-pointer select-none transition-all duration-200 hover:scale-105"
                    onClick={() => hasChildren && toggleNode(node.id)}
                >
                    <div
                        className={`px-4 py-2.5 rounded-xl border-2 shadow-sm transition-all duration-200 max-w-[200px] text-center ${
                            isRoot
                                ? 'bg-gradient-to-br from-[#C8A288] to-[#A08072] border-[#8B7060] text-white font-bold text-base px-6 py-3.5 shadow-lg shadow-[#C8A288]/30'
                                : depth === 1
                                    ? `font-semibold text-sm`
                                    : 'bg-white text-xs font-medium'
                        }`}
                        style={!isRoot ? {
                            backgroundColor: depth === 1 ? color.bg : '#fff',
                            borderColor: depth === 1 ? color.border : color.border + '60',
                            color: depth === 1 ? color.text : '#4A3B32',
                        } : {}}
                    >
                        {node.label}
                        {hasChildren && (
                            <span className={`ml-1.5 text-xs opacity-60 ${isRoot ? 'text-white/70' : ''}`}>
                                {isExpanded ? '−' : `+${node.children.length}`}
                            </span>
                        )}
                    </div>
                </div>

                {/* Children */}
                {hasChildren && isExpanded && (
                    <div className="relative mt-3">
                        {/* Vertical connector */}
                        <div
                            className="absolute left-1/2 -top-3 w-0.5 h-3"
                            style={{ backgroundColor: isRoot ? '#C8A288' : color.border }}
                        />
                        
                        <div className="flex gap-4 items-start relative">
                            {/* Horizontal connector line */}
                            {node.children.length > 1 && (
                                <div
                                    className="absolute top-0 h-0.5 left-[calc(50%/(var(--count)))] right-[calc(50%/(var(--count)))]"
                                    style={{
                                        backgroundColor: isRoot ? '#C8A288' : color.border,
                                        left: `${100 / (node.children.length * 2)}%`,
                                        right: `${100 / (node.children.length * 2)}%`,
                                    }}
                                />
                            )}
                            
                            {node.children.map((child, idx) => (
                                <div key={child.id} className="flex flex-col items-center relative">
                                    {/* Vertical connector to child */}
                                    <div
                                        className="w-0.5 h-3 mb-1"
                                        style={{ backgroundColor: isRoot ? BRANCH_COLORS[idx % BRANCH_COLORS.length].border : color.border }}
                                    />
                                    {renderNode(child, depth + 1, isRoot ? idx : branchIndex)}
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </div>
        );
    };

    if (!tree) {
        return (
            <div className="flex items-center justify-center h-full text-[#8a6a5c]">
                <p>No mindmap data available</p>
            </div>
        );
    }

    return (
        <div className="relative h-full w-full overflow-hidden">
            {/* Zoom Controls */}
            <div className="absolute top-3 right-3 z-10 flex flex-col gap-1 bg-white rounded-xl border border-[#E6D5CC] shadow-md p-1">
                <button onClick={() => setZoom(z => Math.min(2, z + 0.2))} className="p-2 hover:bg-[#FDF6F0] rounded-lg transition-colors" title="Zoom In">
                    <ZoomIn className="h-4 w-4 text-[#4A3B32]" />
                </button>
                <button onClick={() => setZoom(z => Math.max(0.3, z - 0.2))} className="p-2 hover:bg-[#FDF6F0] rounded-lg transition-colors" title="Zoom Out">
                    <ZoomOut className="h-4 w-4 text-[#4A3B32]" />
                </button>
                <div className="w-full h-px bg-[#E6D5CC]" />
                <button onClick={resetView} className="p-2 hover:bg-[#FDF6F0] rounded-lg transition-colors" title="Reset View">
                    <Maximize2 className="h-4 w-4 text-[#4A3B32]" />
                </button>
            </div>

            {/* Zoom indicator */}
            <div className="absolute bottom-3 right-3 z-10 px-2.5 py-1 bg-white/80 backdrop-blur-sm rounded-full text-xs text-[#8a6a5c] border border-[#E6D5CC]">
                {Math.round(zoom * 100)}%
            </div>

            {/* Canvas */}
            <div
                ref={containerRef}
                className="h-full w-full cursor-grab active:cursor-grabbing"
                onMouseDown={handleMouseDown}
                onWheel={handleWheel}
            >
                <div
                    className="inline-flex min-w-full min-h-full items-start justify-center pt-8 pb-16 px-8 transition-transform"
                    style={{
                        transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
                        transformOrigin: 'center top',
                    }}
                >
                    {renderNode(tree)}
                </div>
            </div>
        </div>
    );
};

// ======================== Main MindmapView Component ========================

const MindmapView = ({ projectId, availableTopics, selectedDocuments }) => {
    const toast = useToast();
    const [mindmaps, setMindmaps] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showCreateModal, setShowCreateModal] = useState(false);
    const [selectedMindmap, setSelectedMindmap] = useState(null);
    const [generating, setGenerating] = useState(false);
    
    // Create form state
    const [formData, setFormData] = useState({
        title: '',
        topic: '',
        customTopic: ''
    });

    useEffect(() => {
        fetchMindmaps();
    }, [projectId]);

    const fetchMindmaps = async () => {
        setLoading(true);
        try {
            const data = await getMindmaps(projectId);
            setMindmaps(data);
        } catch (error) {
            logger.error('Failed to fetch mindmaps', { error: error.message });
            toast.error('Failed to load mindmaps');
        } finally {
            setLoading(false);
        }
    };

    const handleGenerateMindmap = async () => {
        const topic = formData.topic === 'custom' ? formData.customTopic : formData.topic;
        
        if (!formData.title.trim()) {
            toast.warning('Please enter a title');
            return;
        }
        
        if (!topic.trim()) {
            toast.warning('Please select or enter a topic');
            return;
        }

        if (selectedDocuments.length === 0) {
            toast.warning('Please select at least one document');
            return;
        }

        setGenerating(true);
        try {
            const result = await generateMindmapAPI(projectId, formData.title, topic, selectedDocuments);
            toast.success('Mindmap generated!');
            setShowCreateModal(false);
            setFormData({ title: '', topic: '', customTopic: '' });
            await fetchMindmaps();
            // Auto-open the newly generated mindmap
            if (result) {
                setSelectedMindmap(result);
            }
        } catch (error) {
            logger.error('Failed to generate mindmap', { error: error.message });
            toast.error('Failed to generate mindmap');
        } finally {
            setGenerating(false);
        }
    };

    const viewMindmap = (mindmap) => {
        setSelectedMindmap(mindmap);
    };

    const deleteMindmap = async (id, e) => {
        if (e) e.stopPropagation();
        try {
            await deleteMindmapAPI(id);
            toast.success('Mindmap deleted');
            if (selectedMindmap?.id === id) {
                setSelectedMindmap(null);
            }
            fetchMindmaps();
        } catch (error) {
            logger.error('Failed to delete mindmap', { error: error.message });
            toast.error('Failed to delete mindmap');
        }
    };

    if (loading) {
        return (
            <div className="h-full flex items-center justify-center">
                <Loader2 className="h-8 w-8 text-[#C8A288] animate-spin" />
            </div>
        );
    }

    // View Mode - Interactive Mindmap Visualization
    if (selectedMindmap) {
        return (
            <div className="h-full flex flex-col">
                <div className="flex items-center justify-between px-4 md:px-6 py-3 border-b border-[#E6D5CC]/50 bg-white/50 shrink-0">
                    <div className="min-w-0">
                        <h2 className="text-lg font-bold text-[#4A3B32] truncate">{selectedMindmap.title}</h2>
                        <p className="text-xs text-[#8a6a5c]">
                            {selectedMindmap.topic} · {selectedMindmap.data?.nodes?.length || 0} nodes
                        </p>
                    </div>
                    <div className="flex gap-2 shrink-0">
                        <button
                            onClick={() => setSelectedMindmap(null)}
                            className="px-4 py-2 text-sm text-[#8a6a5c] hover:bg-[#FDF6F0] rounded-lg transition-colors"
                        >
                            Back to List
                        </button>
                    </div>
                </div>

                {/* Mindmap Interactive Display */}
                <div className="flex-1 overflow-hidden bg-gradient-to-br from-[#FDFAF7] to-[#F5EDE6]">
                    <MindmapRenderer data={selectedMindmap.data} />
                </div>
            </div>
        );
    }

    // List View
    return (
        <div className="h-full overflow-y-auto custom-scrollbar p-4 md:p-8">
            <div className="max-w-6xl mx-auto">
                <div className="flex items-center justify-between mb-8">
                    <div>
                        <h2 className="text-2xl font-bold text-[#4A3B32]">Mindmaps</h2>
                        <p className="text-[#8a6a5c]">Generate visual mindmaps from your documents</p>
                    </div>
                    <button
                        onClick={() => setShowCreateModal(true)}
                        className="flex items-center gap-2 px-4 py-2 bg-[#C8A288] text-white rounded-lg hover:bg-[#B08B72] transition-colors"
                    >
                        <Plus className="h-5 w-5" />
                        Generate Mindmap
                    </button>
                </div>

                {mindmaps.length === 0 ? (
                    <div className="text-center py-16">
                        <Zap className="h-16 w-16 text-[#E6D5CC] mx-auto mb-4" />
                        <h3 className="text-xl font-bold text-[#4A3B32] mb-2">No Mindmaps Yet</h3>
                        <p className="text-[#8a6a5c] mb-6">Generate your first mindmap to visualize concepts</p>
                        <button
                            onClick={() => setShowCreateModal(true)}
                            className="px-6 py-3 bg-[#C8A288] text-white rounded-lg hover:bg-[#B08B72] transition-colors"
                        >
                            Generate Your First Mindmap
                        </button>
                    </div>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                        {mindmaps.map((mindmap) => (
                            <div
                                key={mindmap.id}
                                onClick={() => viewMindmap(mindmap)}
                                className="bg-white rounded-xl border border-[#E6D5CC] p-6 hover:shadow-lg transition-all cursor-pointer group"
                            >
                                <div className="flex items-start justify-between mb-3">
                                    <div className="flex-1 min-w-0">
                                        <h3 className="font-bold text-[#4A3B32] mb-1 truncate">{mindmap.title}</h3>
                                        <p className="text-sm text-[#8a6a5c] truncate">{mindmap.topic}</p>
                                    </div>
                                    <button
                                        onClick={(e) => deleteMindmap(mindmap.id, e)}
                                        className="text-red-400 hover:text-red-600 p-1 opacity-0 group-hover:opacity-100 transition-opacity"
                                    >
                                        <Trash2 className="h-4 w-4" />
                                    </button>
                                </div>
                                
                                {/* Mini preview of node count */}
                                <div className="flex items-center gap-3 mb-4">
                                    <div className="flex items-center gap-1.5 text-xs text-[#8a6a5c] bg-[#FDF6F0] px-2.5 py-1 rounded-full">
                                        <Zap className="h-3 w-3" />
                                        {mindmap.data?.nodes?.length || mindmap.node_count || 0} nodes
                                    </div>
                                    <p className="text-xs text-[#8a6a5c]">
                                        {new Date(mindmap.created_at).toLocaleDateString()}
                                    </p>
                                </div>
                                
                                <button
                                    onClick={(e) => { e.stopPropagation(); viewMindmap(mindmap); }}
                                    className="w-full py-2 bg-[#C8A288] text-white rounded-lg hover:bg-[#B08B72] transition-colors flex items-center justify-center gap-2 text-sm"
                                >
                                    <Eye className="h-4 w-4" />
                                    View Mindmap
                                </button>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* Create Modal */}
            {showCreateModal && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
                    <div className="bg-white rounded-2xl p-6 max-w-md w-full">
                        <div className="flex items-center justify-between mb-6">
                            <h3 className="text-xl font-bold text-[#4A3B32]">Generate Mindmap</h3>
                            <button
                                onClick={() => setShowCreateModal(false)}
                                className="p-2 hover:bg-[#FDF6F0] rounded-lg transition-colors"
                            >
                                <X className="h-5 w-5" />
                            </button>
                        </div>

                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-[#4A3B32] mb-2">Title</label>
                                <input
                                    type="text"
                                    value={formData.title}
                                    onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                                    placeholder="e.g., Cell Biology Overview"
                                    className="w-full px-4 py-2 border border-[#E6D5CC] rounded-lg focus:ring-2 focus:ring-[#C8A288] outline-none"
                                />
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-[#4A3B32] mb-2">Topic</label>
                                <select
                                    value={formData.topic}
                                    onChange={(e) => setFormData({ ...formData, topic: e.target.value })}
                                    className="w-full px-4 py-2 border border-[#E6D5CC] rounded-lg focus:ring-2 focus:ring-[#C8A288] outline-none"
                                >
                                    <option value="">Select a topic</option>
                                    {availableTopics.map((topic, idx) => (
                                        <option key={idx} value={topic}>{topic}</option>
                                    ))}
                                    <option value="custom">Custom Topic...</option>
                                </select>
                            </div>

                            {formData.topic === 'custom' && (
                                <div>
                                    <label className="block text-sm font-medium text-[#4A3B32] mb-2">Custom Topic</label>
                                    <input
                                        type="text"
                                        value={formData.customTopic}
                                        onChange={(e) => setFormData({ ...formData, customTopic: e.target.value })}
                                        placeholder="Enter custom topic"
                                        className="w-full px-4 py-2 border border-[#E6D5CC] rounded-lg focus:ring-2 focus:ring-[#C8A288] outline-none"
                                    />
                                </div>
                            )}

                            {selectedDocuments.length === 0 && (
                                <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
                                    <p className="text-sm text-amber-700">
                                        Please select at least one document from the sidebar
                                    </p>
                                </div>
                            )}
                        </div>

                        <div className="flex gap-3 mt-6">
                            <button
                                onClick={() => setShowCreateModal(false)}
                                disabled={generating}
                                className="flex-1 py-2 border border-[#E6D5CC] rounded-lg hover:bg-[#FDF6F0] transition-colors disabled:opacity-50"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleGenerateMindmap}
                                disabled={generating}
                                className="flex-1 py-2 bg-[#C8A288] text-white rounded-lg hover:bg-[#B08B72] transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
                            >
                                {generating ? (
                                    <>
                                        <Loader2 className="h-4 w-4 animate-spin" />
                                        Generating...
                                    </>
                                ) : (
                                    'Generate'
                                )}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default MindmapView;
