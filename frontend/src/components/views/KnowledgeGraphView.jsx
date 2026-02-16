import { useState, useEffect, useRef, useCallback } from 'react';
import cytoscape from 'cytoscape';
import { 
    Book, 
    Network, 
    Lightbulb, 
    Clock, 
    TrendingUp, 
    ChevronRight,
    X,
    RefreshCw,
    Hand,
    ZoomIn,
    ZoomOut,
    Maximize2,
    Loader2,
    Sparkles,
    Target,
    BarChart3
} from 'lucide-react';
import { 
    getKnowledgeGraphVisualization, 
    getKnowledgeGraph,
    getTopics,
    getTopicSummary, 
    recordGraphInteraction,
    getLearningSuggestions,
    startLearningSession,
    endLearningSession
} from '../../api';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { recordActivity } from '../../utils/studyActivity';

const KnowledgeGraphView = ({ projectId }) => {
    // Graph State
    const [graphData, setGraphData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    
    // Selected Topic & Summary
    const [selectedTopic, setSelectedTopic] = useState(null);
    const [topicSummary, setTopicSummary] = useState(null);
    const [summaryLoading, setSummaryLoading] = useState(false);
    
    // Suggestions & Analytics
    const [suggestions, setSuggestions] = useState(null);
    const [analytics, setAnalytics] = useState(null);
    
    // Session Tracking
    const [sessionId, setSessionId] = useState(null);
    const [sessionStartTime, setSessionStartTime] = useState(null);
    const [topicsVisited, setTopicsVisited] = useState(new Set());
    const [topicStartTime, setTopicStartTime] = useState(null);
    
    // Cytoscape Ref
    const cyRef = useRef(null);
    const containerRef = useRef(null);
    
    // Pan mode
    const [isPanMode, setIsPanMode] = useState(false);

    // Refs to avoid stale closures in Cytoscape event handlers & cleanup
    const selectedTopicRef = useRef(null);
    const topicStartTimeRef = useRef(null);
    const sessionIdRef = useRef(null);
    const sessionStartTimeRef = useRef(null);
    const topicsVisitedRef = useRef(new Set());
    const isPanModeRef = useRef(false);

    // Sync refs with state
    useEffect(() => { selectedTopicRef.current = selectedTopic; }, [selectedTopic]);
    useEffect(() => { topicStartTimeRef.current = topicStartTime; }, [topicStartTime]);
    useEffect(() => { sessionIdRef.current = sessionId; }, [sessionId]);
    useEffect(() => { sessionStartTimeRef.current = sessionStartTime; }, [sessionStartTime]);
    useEffect(() => { topicsVisitedRef.current = topicsVisited; }, [topicsVisited]);
    useEffect(() => { isPanModeRef.current = isPanMode; }, [isPanMode]);

    // Initialize Cytoscape
    const initCytoscape = useCallback((data) => {
        if (!containerRef.current || !data) return;
        
        // Safety check: container must have dimensions
        const rect = containerRef.current.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) {
            console.warn('KnowledgeGraph: container has zero dimensions, retrying...');
            setTimeout(() => initCytoscape(data), 100);
            return;
        }
        
        // Destroy existing instance
        if (cyRef.current) {
            cyRef.current.destroy();
        }
        
        // Prepare elements
        const elements = [];
        
        // Count connections per node for size scaling
        const degreeMap = {};
        data.nodes.forEach(node => { degreeMap[node.id] = 0; });
        data.edges.forEach(edge => {
            degreeMap[edge.source] = (degreeMap[edge.source] || 0) + 1;
            degreeMap[edge.target] = (degreeMap[edge.target] || 0) + 1;
        });
        
        // Add nodes
        data.nodes.forEach(node => {
            elements.push({
                data: {
                    id: node.id,
                    label: node.label,
                    type: node.type,
                    document: node.document || null,
                    degree: degreeMap[node.id] || 0
                }
            });
        });
        
        // Add edges (use index for unique IDs to avoid collisions with hyphenated names)
        data.edges.forEach((edge, idx) => {
            elements.push({
                data: {
                    id: `edge_${idx}`,
                    source: edge.source,
                    target: edge.target,
                    type: edge.type,
                    weight: edge.weight
                }
            });
        });
        
        // Create Cytoscape instance
        cyRef.current = cytoscape({
            container: containerRef.current,
            elements,
            style: [
                // Book nodes (documents) — large, prominent anchor nodes
                {
                    selector: 'node[type="book"]',
                    style: {
                        'background-color': '#A08072',
                        'background-opacity': 0.95,
                        'border-color': '#7B5B4E',
                        'border-width': 3,
                        'label': 'data(label)',
                        'text-valign': 'bottom',
                        'text-halign': 'center',
                        'text-margin-y': 10,
                        'font-size': '11px',
                        'font-weight': 'bold',
                        'color': '#4A3B32',
                        'text-outline-color': '#FDF6F0',
                        'text-outline-width': 2,
                        'width': 55,
                        'height': 55,
                        'shape': 'round-rectangle',
                        'text-wrap': 'wrap',
                        'text-max-width': '120px',
                        'z-index': 10
                    }
                },
                // Topic nodes — sized by degree (connectivity)
                {
                    selector: 'node[type="topic"]',
                    style: {
                        'background-color': '#FDF6F0',
                        'background-opacity': 0.95,
                        'border-color': '#D4BFB4',
                        'border-width': 2,
                        'label': 'data(label)',
                        'text-valign': 'center',
                        'text-halign': 'center',
                        'font-size': '10px',
                        'color': '#4A3B32',
                        'width': 'label',
                        'height': 'label',
                        'padding': '14px',
                        'shape': 'round-rectangle',
                        'text-wrap': 'wrap',
                        'text-max-width': '130px',
                        'z-index': 5
                    }
                },
                // High-connectivity topic nodes (4+ connections)
                {
                    selector: 'node[type="topic"][degree >= 4]',
                    style: {
                        'background-color': '#F0E4DA',
                        'border-color': '#C8A288',
                        'border-width': 2.5,
                        'font-size': '11px',
                        'font-weight': 'bold',
                        'padding': '16px',
                        'text-max-width': '150px'
                    }
                },
                // Selected node
                {
                    selector: 'node:selected',
                    style: {
                        'background-color': '#C8A288',
                        'border-color': '#7B5B4E',
                        'border-width': 3,
                        'color': '#FFFFFF',
                        'text-outline-color': '#7B5B4E',
                        'text-outline-width': 1,
                        'z-index': 20
                    }
                },
                // Hovered node
                {
                    selector: 'node.hover',
                    style: {
                        'background-color': '#E6D5CC',
                        'border-color': '#C8A288',
                        'border-width': 2.5,
                        'z-index': 15
                    }
                },
                // Neighbor highlight when a node is selected
                {
                    selector: 'node.neighbor',
                    style: {
                        'background-color': '#F0E4DA',
                        'border-color': '#C8A288',
                        'border-width': 2.5,
                        'z-index': 12
                    }
                },
                // Dimmed nodes (when a selection is active)
                {
                    selector: 'node.dimmed',
                    style: {
                        'opacity': 0.3
                    }
                },
                // Edges - contains (book to topic) — subtle connectors
                {
                    selector: 'edge[type="contains"]',
                    style: {
                        'line-color': '#D4BFB4',
                        'width': 1.5,
                        'curve-style': 'bezier',
                        'opacity': 0.4,
                        'line-style': 'dotted'
                    }
                },
                // Edges - prerequisite — prominent with arrows
                {
                    selector: 'edge[type="prerequisite"]',
                    style: {
                        'line-color': '#A08072',
                        'width': 2.5,
                        'target-arrow-shape': 'triangle',
                        'target-arrow-color': '#A08072',
                        'arrow-scale': 1.2,
                        'curve-style': 'bezier',
                        'opacity': 0.75
                    }
                },
                // Edges - related — dashed connectors
                {
                    selector: 'edge[type="related"]',
                    style: {
                        'line-color': '#E6D5CC',
                        'width': 1.5,
                        'line-style': 'dashed',
                        'curve-style': 'bezier',
                        'opacity': 0.45
                    }
                },
                // Highlighted edges (connected to selected node)
                {
                    selector: 'edge.highlighted',
                    style: {
                        'opacity': 1,
                        'width': 3,
                        'z-index': 15
                    }
                },
                // Dimmed edges
                {
                    selector: 'edge.dimmed',
                    style: {
                        'opacity': 0.1
                    }
                }
            ],
            layout: {
                name: 'cose',
                animate: true,
                animationDuration: 800,
                nodeRepulsion: function() { return 12000; },
                idealEdgeLength: function() { return 150; },
                edgeElasticity: function() { return 80; },
                nestingFactor: 1.2,
                gravity: 0.15,
                numIter: 1500,
                coolingFactor: 0.95,
                minTemp: 1.0,
                nodeDimensionsIncludeLabels: true,
                padding: 60
            },
            minZoom: 0.2,
            maxZoom: 4,
            wheelSensitivity: 0.15,
            boxSelectionEnabled: false,
            selectionType: 'single'
        });
        
        // Event handlers
        cyRef.current.on('tap', 'node[type="topic"]', async (evt) => {
            const node = evt.target;
            const topicLabel = node.data('label');
            
            // Record click interaction (non-blocking)
            if (topicStartTimeRef.current && selectedTopicRef.current) {
                const duration = Date.now() - topicStartTimeRef.current;
                recordGraphInteraction(projectId, selectedTopicRef.current, 'click', duration).catch(() => {});
            }
            
            // Highlight neighborhood: dim everything, then highlight selected + neighbors
            cyRef.current.elements().removeClass('neighbor highlighted dimmed');
            cyRef.current.elements().addClass('dimmed');
            
            const neighborhood = node.neighborhood().add(node);
            neighborhood.nodes().removeClass('dimmed').addClass('neighbor');
            neighborhood.edges().removeClass('dimmed').addClass('highlighted');
            node.removeClass('neighbor dimmed'); // selected state handles this node
            
            setSelectedTopic(topicLabel);
            setTopicStartTime(Date.now());
            setTopicsVisited(prev => new Set([...prev, topicLabel]));
            
            // Record activity for unified tracking
            recordActivity(projectId, 'knowledge_graph', { action: 'explore_topic', topic: topicLabel });
            
            // Fetch summary
            await fetchTopicSummary(topicLabel);
            
            // Fetch suggestions (non-blocking)
            fetchSuggestions(topicLabel);
        });
        
        // Click on book nodes to highlight their topics
        cyRef.current.on('tap', 'node[type="book"]', (evt) => {
            const node = evt.target;
            cyRef.current.elements().removeClass('neighbor highlighted dimmed');
            cyRef.current.elements().addClass('dimmed');
            
            const neighborhood = node.neighborhood().add(node);
            neighborhood.nodes().removeClass('dimmed').addClass('neighbor');
            neighborhood.edges().removeClass('dimmed').addClass('highlighted');
            node.removeClass('neighbor dimmed');
        });
        
        // Click on background to clear highlight
        cyRef.current.on('tap', (evt) => {
            if (evt.target === cyRef.current) {
                cyRef.current.elements().removeClass('neighbor highlighted dimmed');
            }
        });
        
        cyRef.current.on('mouseover', 'node', (evt) => {
            evt.target.addClass('hover');
            containerRef.current.style.cursor = 'pointer';
        });
        
        cyRef.current.on('mouseout', 'node', (evt) => {
            evt.target.removeClass('hover');
            containerRef.current.style.cursor = isPanModeRef.current ? 'grab' : 'default';
        });
        
        // Fit graph to container AFTER layout completes (not immediately,
        // since the cose layout animates over 500ms and the container may
        // not have dimensions yet if it just appeared in the DOM)
        cyRef.current.on('layoutstop', () => {
            cyRef.current.fit(undefined, 50);
        });
        
    }, [projectId]);

    // Fetch graph data
    const fetchGraphData = async () => {
        try {
            setLoading(true);
            setError(null);
            
            let data = null;
            try {
                data = await getKnowledgeGraphVisualization(projectId);
            } catch (vizErr) {
                console.warn('Knowledge graph visualization endpoint failed, falling back:', vizErr);
                // Fallback: use the learning API endpoint
                try {
                    const kgData = await getKnowledgeGraph(projectId);
                    const topicsData = await getTopics(projectId);
                    
                    const allTopics = topicsData?.all || (Array.isArray(topicsData) ? topicsData : []);
                    const byDoc = topicsData?.by_doc || {};
                    
                    // Build graph data from topics
                    const nodes = [];
                    const edges = [];
                    
                    // Add topic nodes
                    const addedTopics = new Set();
                    if (kgData?.graph?.nodes?.length > 0) {
                        kgData.graph.nodes.forEach(n => {
                            nodes.push({ id: n.id, label: n.label, type: 'topic', document: n.document });
                            addedTopics.add(n.id);
                        });
                    }
                    
                    // Add any missing topics from documents
                    allTopics.forEach(t => {
                        if (!addedTopics.has(t)) {
                            nodes.push({ id: t, label: t, type: 'topic', document: 'Unknown' });
                        }
                    });
                    
                    // Add edges from graph
                    if (kgData?.graph?.edges) {
                        kgData.graph.edges.forEach(e => {
                            edges.push({
                                source: e.source || e.from_topic,
                                target: e.target || e.to_topic,
                                type: e.type || e.relation_type || 'related',
                                weight: e.weight || 0.5
                            });
                        });
                    }
                    
                    data = { project_name: 'Knowledge Graph', nodes, edges, stats: kgData?.stats || {} };
                } catch (fallbackErr) {
                    console.error('Fallback also failed:', fallbackErr);
                    throw vizErr;
                }
            }
            
            setGraphData(data);
            setLoading(false); // MUST be in same sync block as setGraphData — see useEffect below
            
            // Initialize session (fire-and-forget — do NOT await, it would
            // separate setGraphData and setLoading into different React batches,
            // causing the Cytoscape useEffect to fire while the container is
            // still hidden behind the loading spinner)
            startLearningSession(projectId).then(session => {
                setSessionId(session.session_id);
                setSessionStartTime(Date.now());
                recordActivity(projectId, 'knowledge_graph', { action: 'start_session' });
            }).catch(sessionErr => {
                console.warn('Session tracking unavailable:', sessionErr.message);
                setSessionStartTime(Date.now());
            });
            
        } catch (err) {
            console.error('Error fetching graph:', err);
            setError(err.message || 'Failed to load knowledge graph');
            setLoading(false);
        }
    };

    // Fetch topic summary
    const fetchTopicSummary = async (topic, forceRegenerate = false) => {
        try {
            setSummaryLoading(true);
            const data = await getTopicSummary(projectId, topic, forceRegenerate);
            setTopicSummary(data);
        } catch (err) {
            console.error('Error fetching summary:', err);
            setTopicSummary({
                topic,
                summary: 'Failed to load summary. Please try again.',
                sources: [],
                cached: false
            });
        } finally {
            setSummaryLoading(false);
        }
    };

    // Fetch suggestions (non-blocking)
    const fetchSuggestions = async (currentTopic = null) => {
        try {
            const data = await getLearningSuggestions(projectId, currentTopic, 3);
            setSuggestions(data);
            setAnalytics(data.analytics);
        } catch (err) {
            console.warn('Suggestions unavailable:', err.message);
        }
    };

    // Close topic panel
    const closeTopic = async () => {
        if (topicStartTime && selectedTopic) {
            const duration = Date.now() - topicStartTime;
            try {
                await recordGraphInteraction(projectId, selectedTopic, 'summary_view', duration);
            } catch (e) { /* analytics optional */ }
        }
        // Clear graph highlighting
        if (cyRef.current) {
            cyRef.current.elements().removeClass('neighbor highlighted dimmed');
            cyRef.current.elements().unselect();
        }
        setSelectedTopic(null);
        setTopicSummary(null);
        setTopicStartTime(null);
    };

    // Zoom controls
    const zoomIn = () => cyRef.current?.zoom(cyRef.current.zoom() * 1.2);
    const zoomOut = () => cyRef.current?.zoom(cyRef.current.zoom() / 1.2);
    const fitGraph = () => cyRef.current?.fit(undefined, 50);

    // Toggle pan mode
    const togglePanMode = () => {
        setIsPanMode(!isPanMode);
        if (cyRef.current) {
            cyRef.current.userPanningEnabled(!isPanMode);
            containerRef.current.style.cursor = !isPanMode ? 'grab' : 'default';
        }
    };

    // Initialize on mount
    useEffect(() => {
        fetchGraphData();
        
        // Resize observer to tell Cytoscape when container changes size
        const resizeObserver = new ResizeObserver(() => {
            if (cyRef.current) {
                cyRef.current.resize();
                cyRef.current.fit(undefined, 50);
            }
        });
        if (containerRef.current) {
            resizeObserver.observe(containerRef.current);
        }
        
        // Cleanup on unmount
        return () => {
            resizeObserver.disconnect();
            if (sessionIdRef.current && sessionStartTimeRef.current) {
                const totalTime = Date.now() - sessionStartTimeRef.current;
                endLearningSession(sessionIdRef.current, Array.from(topicsVisitedRef.current), totalTime);
            }
            if (cyRef.current) {
                cyRef.current.destroy();
            }
        };
    }, [projectId]);

    // Initialize Cytoscape when data changes
    // Use double-rAF to ensure the container div has been painted with
    // proper dimensions before Cytoscape tries to render into it.
    // When loading changes from true→false and graphData is set in the
    // same render batch, the container appears in the DOM but may have
    // 0x0 dimensions until the browser paints.
    useEffect(() => {
        if (graphData) {
            let innerRaf = null;
            const outerRaf = requestAnimationFrame(() => {
                innerRaf = requestAnimationFrame(() => {
                    initCytoscape(graphData);
                });
            });
            return () => {
                cancelAnimationFrame(outerRaf);
                if (innerRaf !== null) cancelAnimationFrame(innerRaf);
            };
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [graphData]);

    // Navigate to suggested topic
    const navigateToTopic = async (topic) => {
        setSelectedTopic(topic);
        setTopicsVisited(prev => new Set([...prev, topic]));
        await fetchTopicSummary(topic);
        
        // Highlight node in graph
        if (cyRef.current) {
            const node = cyRef.current.getElementById(topic);
            if (node.length) {
                // Highlight neighborhood
                cyRef.current.elements().removeClass('neighbor highlighted dimmed');
                cyRef.current.elements().addClass('dimmed');
                const neighborhood = node.neighborhood().add(node);
                neighborhood.nodes().removeClass('dimmed').addClass('neighbor');
                neighborhood.edges().removeClass('dimmed').addClass('highlighted');
                node.removeClass('neighbor dimmed');
                
                cyRef.current.animate({
                    center: { eles: node },
                    zoom: 1.5
                }, { duration: 300 });
                node.select();
            }
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center h-[600px] bg-[#FDF6F0] rounded-2xl">
                <div className="text-center">
                    <Loader2 className="w-12 h-12 text-[#C8A288] animate-spin mx-auto mb-4" />
                    <p className="text-[#8a6a5c]">Loading knowledge graph...</p>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex items-center justify-center h-[600px] bg-[#FDF6F0] rounded-2xl">
                <div className="text-center">
                    <Network className="w-12 h-12 text-red-400 mx-auto mb-4" />
                    <p className="text-red-500 mb-4">{error}</p>
                    <button
                        onClick={fetchGraphData}
                        className="px-4 py-2 bg-[#C8A288] text-white rounded-lg hover:bg-[#A08072] transition-colors"
                    >
                        Try Again
                    </button>
                </div>
            </div>
        );
    }

    // No topics found
    if (!graphData?.nodes?.length) {
        return (
            <div className="flex items-center justify-center h-[600px] bg-[#FDF6F0] rounded-2xl">
                <div className="text-center">
                    <Network className="w-12 h-12 text-[#E6D5CC] mx-auto mb-4" />
                    <p className="text-[#4A3B32] font-semibold mb-2">No Topics Found</p>
                    <p className="text-sm text-[#8a6a5c] mb-4">Upload documents to generate topics and build the knowledge graph.</p>
                    <button
                        onClick={fetchGraphData}
                        className="px-4 py-2 bg-[#C8A288] text-white rounded-lg hover:bg-[#A08072] transition-colors"
                    >
                        Refresh
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="flex h-[calc(100vh-200px)] min-h-[600px] gap-4">
            {/* Main Graph Container */}
            <div className="flex-1 relative bg-[#FDF6F0] rounded-2xl border border-[#E6D5CC] overflow-hidden">
                {/* Header */}
                <div className="absolute top-0 left-0 right-0 z-10 bg-gradient-to-b from-[#FDF6F0] to-transparent p-4">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <Network className="w-5 h-5 text-[#C8A288]" />
                            <h2 className="font-semibold text-[#4A3B32]">
                                {graphData?.project_name || 'Knowledge Graph'}
                            </h2>
                            <span className="text-xs text-[#8a6a5c] bg-white/80 px-2 py-1 rounded-full">
                                {graphData?.nodes?.filter(n => n.type === 'topic').length || 0} topics
                            </span>
                            <span className="text-xs text-[#8a6a5c] bg-white/80 px-2 py-1 rounded-full">
                                {graphData?.nodes?.filter(n => n.type === 'book').length || 0} docs
                            </span>
                            <span className="text-xs text-[#8a6a5c] bg-white/80 px-2 py-1 rounded-full">
                                {graphData?.edges?.length || 0} links
                            </span>
                        </div>
                        
                        {/* Controls */}
                        <div className="flex items-center gap-2">
                            <button
                                onClick={togglePanMode}
                                className={`p-2 rounded-lg transition-colors ${
                                    isPanMode 
                                        ? 'bg-[#C8A288] text-white' 
                                        : 'bg-white text-[#4A3B32] hover:bg-[#E6D5CC]'
                                }`}
                                title="Toggle pan mode (drag to move)"
                            >
                                <Hand className="w-4 h-4" />
                            </button>
                            <button
                                onClick={zoomIn}
                                className="p-2 bg-white rounded-lg hover:bg-[#E6D5CC] transition-colors"
                                title="Zoom in"
                            >
                                <ZoomIn className="w-4 h-4 text-[#4A3B32]" />
                            </button>
                            <button
                                onClick={zoomOut}
                                className="p-2 bg-white rounded-lg hover:bg-[#E6D5CC] transition-colors"
                                title="Zoom out"
                            >
                                <ZoomOut className="w-4 h-4 text-[#4A3B32]" />
                            </button>
                            <button
                                onClick={fitGraph}
                                className="p-2 bg-white rounded-lg hover:bg-[#E6D5CC] transition-colors"
                                title="Fit to view"
                            >
                                <Maximize2 className="w-4 h-4 text-[#4A3B32]" />
                            </button>
                            <button
                                onClick={fetchGraphData}
                                className="p-2 bg-white rounded-lg hover:bg-[#E6D5CC] transition-colors"
                                title="Refresh graph"
                            >
                                <RefreshCw className="w-4 h-4 text-[#4A3B32]" />
                            </button>
                        </div>
                    </div>
                </div>
                
                {/* Cytoscape Container */}
                <div 
                    ref={containerRef} 
                    className="w-full h-full"
                    style={{ cursor: isPanMode ? 'grab' : 'default', minHeight: '400px' }}
                />
                
                {/* Legend */}
                <div className="absolute bottom-4 left-4 bg-white/90 backdrop-blur-sm rounded-lg p-3 shadow-sm">
                    <p className="text-xs font-medium text-[#4A3B32] mb-2">Legend</p>
                    <div className="flex flex-col gap-1.5 text-xs text-[#8a6a5c]">
                        <div className="flex items-center gap-2">
                            <div className="w-4 h-4 bg-[#A08072] rounded border border-[#7B5B4E]" />
                            <span>Document</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <div className="w-4 h-4 bg-[#FDF6F0] border-2 border-[#D4BFB4] rounded" />
                            <span>Topic</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <div className="w-4 h-4 bg-[#F0E4DA] border-2 border-[#C8A288] rounded" />
                            <span>Key Topic (4+ links)</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <div className="w-8 h-0 border-t-2 border-dotted border-[#D4BFB4]" />
                            <span>Contains</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <div className="w-8 h-0.5 bg-[#A08072]" />
                            <span>Prerequisite</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <div className="w-8 h-0 border-t border-dashed border-[#E6D5CC]" />
                            <span>Related</span>
                        </div>
                    </div>
                </div>
                
                {/* Analytics Mini Card */}
                {analytics && (
                    <div className="absolute bottom-4 right-4 bg-white/90 backdrop-blur-sm rounded-lg p-3 shadow-sm">
                        <div className="flex items-center gap-2 mb-2">
                            <BarChart3 className="w-4 h-4 text-[#C8A288]" />
                            <span className="text-xs font-medium text-[#4A3B32]">Progress</span>
                        </div>
                        <div className="text-xs text-[#8a6a5c]">
                            <p>{analytics.coverage_percent}% coverage</p>
                            <p>{analytics.total_topics_visited}/{analytics.total_topics_available} topics</p>
                        </div>
                    </div>
                )}
            </div>
            
            {/* Right Panel - Topic Summary & Suggestions */}
            <div className={`w-96 flex flex-col gap-4 transition-all duration-300 ${selectedTopic ? 'opacity-100' : 'opacity-50'}`}>
                {/* Topic Summary Panel */}
                <div className="flex-1 bg-white rounded-2xl border border-[#E6D5CC] overflow-hidden flex flex-col">
                    {selectedTopic ? (
                        <>
                            {/* Topic Header */}
                            <div className="p-4 border-b border-[#E6D5CC] bg-gradient-to-r from-[#C8A288]/10 to-transparent">
                                <div className="flex items-start justify-between">
                                    <div className="flex-1">
                                        <h3 className="font-semibold text-[#4A3B32] text-lg">
                                            {selectedTopic}
                                        </h3>
                                        {topicSummary?.cached && (
                                            <span className="text-xs text-[#8a6a5c] flex items-center gap-1 mt-1">
                                                <Clock className="w-3 h-3" /> Cached
                                            </span>
                                        )}
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <button
                                            onClick={() => fetchTopicSummary(selectedTopic, true)}
                                            className="p-1.5 hover:bg-[#E6D5CC] rounded-lg transition-colors"
                                            title="Regenerate summary"
                                            disabled={summaryLoading}
                                        >
                                            <RefreshCw className={`w-4 h-4 text-[#8a6a5c] ${summaryLoading ? 'animate-spin' : ''}`} />
                                        </button>
                                        <button
                                            onClick={closeTopic}
                                            className="p-1.5 hover:bg-[#E6D5CC] rounded-lg transition-colors"
                                        >
                                            <X className="w-4 h-4 text-[#8a6a5c]" />
                                        </button>
                                    </div>
                                </div>
                            </div>
                            
                            {/* Summary Content */}
                            <div className="flex-1 overflow-y-auto p-4">
                                {summaryLoading ? (
                                    <div className="flex items-center justify-center h-full">
                                        <div className="text-center">
                                            <Loader2 className="w-8 h-8 text-[#C8A288] animate-spin mx-auto mb-2" />
                                            <p className="text-sm text-[#8a6a5c]">Generating summary...</p>
                                        </div>
                                    </div>
                                ) : topicSummary ? (
                                    <div className="prose prose-sm max-w-none">
                                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                            {topicSummary.summary}
                                        </ReactMarkdown>
                                        
                                        {/* Sources */}
                                        {topicSummary.sources?.length > 0 && (
                                            <div className="mt-4 pt-4 border-t border-[#E6D5CC]">
                                                <p className="text-xs font-medium text-[#8a6a5c] mb-2">Sources</p>
                                                <div className="flex flex-wrap gap-2">
                                                    {topicSummary.sources.map((source, idx) => (
                                                        <span 
                                                            key={idx}
                                                            className="text-xs bg-[#FDF6F0] text-[#4A3B32] px-2 py-1 rounded-full"
                                                        >
                                                            {source.doc_name}
                                                        </span>
                                                    ))}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                ) : (
                                    <p className="text-[#8a6a5c] text-center">Click a topic to see its summary</p>
                                )}
                            </div>
                        </>
                    ) : (
                        <div className="flex-1 flex items-center justify-center p-8">
                            <div className="text-center">
                                <Target className="w-12 h-12 text-[#E6D5CC] mx-auto mb-4" />
                                <p className="text-[#8a6a5c]">Click on a topic node to see its summary</p>
                                <p className="text-xs text-[#8a6a5c]/60 mt-2">
                                    Summaries are generated from your documents using AI
                                </p>
                            </div>
                        </div>
                    )}
                </div>
                
                {/* Suggestions Panel */}
                <div className="bg-white rounded-2xl border border-[#E6D5CC] p-4">
                    <div className="flex items-center gap-2 mb-3">
                        <Sparkles className="w-4 h-4 text-[#C8A288]" />
                        <h3 className="font-medium text-[#4A3B32]">Suggested Next</h3>
                    </div>
                    
                    {suggestions?.suggestions?.length > 0 ? (
                        <div className="space-y-2">
                            {suggestions.suggestions.map((topic, idx) => (
                                <button
                                    key={idx}
                                    onClick={() => navigateToTopic(topic)}
                                    className="w-full text-left p-3 bg-[#FDF6F0] rounded-xl hover:bg-[#E6D5CC] transition-colors group"
                                >
                                    <div className="flex items-center justify-between">
                                        <span className="text-sm text-[#4A3B32] font-medium">{topic}</span>
                                        <ChevronRight className="w-4 h-4 text-[#8a6a5c] group-hover:translate-x-1 transition-transform" />
                                    </div>
                                    {suggestions.reasons?.[idx] && (
                                        <p className="text-xs text-[#8a6a5c] mt-1">
                                            {suggestions.reasons[idx]}
                                        </p>
                                    )}
                                </button>
                            ))}
                        </div>
                    ) : (
                        <p className="text-sm text-[#8a6a5c] text-center py-4">
                            Explore topics to get personalized suggestions
                        </p>
                    )}
                </div>
            </div>
        </div>
    );
};

export default KnowledgeGraphView;
