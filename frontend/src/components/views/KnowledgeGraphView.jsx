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
import { useSettings } from '../../context/SettingsContext';

// ─── Palette definitions ──────────────────────────────────────────────────────
const LIGHT = {
    canvas: '#FFF5ED',
    toolbarBg: 'rgba(0,0,0,0.6)',   // gradient overlay
    orbFill: '#FFFFFF',
    orbGradient: '#FFFFFF #FFF8DC #FFD700',
    orbBorder: '#D4A373',
    orbLabel: '#4A3728',
    edgeContains: '#BC9A71',
    edgePrereq: '#BC9A71',
    edgeRelated: '#BC9A71',
    legendBg: 'rgba(62,47,40,0.95)',
    legendBorder: 'rgba(188,154,113,0.30)',
    glowColor: 'rgba(200,162,136,0.18)',
};

const DARK = {
    canvas: '#221810',
    toolbarBg: '#2e1f12',           // solid, per spec
    orbFill: '#3a2c1e',
    orbGradient: '#3a2c1e #4a3520 #5a4028',
    orbBorder: '#7a5c3a',
    orbLabel: '#a08060',
    edgeContains: '#7a5030',
    edgePrereq: '#7a5030',
    edgeRelated: '#7a5030',
    legendBg: '#2e1f12',
    legendBorder: '#5a3a20',
    glowColor: 'rgba(122,80,48,0.22)',
};

const KnowledgeGraphView = ({ projectId, zenMode }) => {
    const { settings } = useSettings();
    const isDark = settings?.darkMode ?? false;
    const P = isDark ? DARK : LIGHT;

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

    // Hover State for Glassmorphism Panel
    const [hoveredNodeData, setHoveredNodeData] = useState(null);

    // Session Tracking
    const [sessionId, setSessionId] = useState(null);
    const [sessionStartTime, setSessionStartTime] = useState(null);
    const [topicsVisited, setTopicsVisited] = useState(new Set());
    const [topicStartTime, setTopicStartTime] = useState(null);

    // Refs
    const cyRef = useRef(null);
    const containerRef = useRef(null);  // Cytoscape mount target
    const wrapRef = useRef(null);  // outer wrapper (for glow canvas sizing)
    const glowCanvasRef = useRef(null); // ambient glow overlay
    const glowRafRef = useRef(null);
    const mouseRef = useRef({ x: -9999, y: -9999 });
    const glowRef = useRef({ x: -9999, y: -9999 }); // lerped position

    // Pan mode
    const [isPanMode, setIsPanMode] = useState(false);

    // Refs to avoid stale closures
    const selectedTopicRef = useRef(null);
    const topicStartTimeRef = useRef(null);
    const sessionIdRef = useRef(null);
    const sessionStartTimeRef = useRef(null);
    const topicsVisitedRef = useRef(new Set());
    const isPanModeRef = useRef(false);

    useEffect(() => { selectedTopicRef.current = selectedTopic; }, [selectedTopic]);
    useEffect(() => { topicStartTimeRef.current = topicStartTime; }, [topicStartTime]);
    useEffect(() => { sessionIdRef.current = sessionId; }, [sessionId]);
    useEffect(() => { sessionStartTimeRef.current = sessionStartTime; }, [sessionStartTime]);
    useEffect(() => { topicsVisitedRef.current = topicsVisited; }, [topicsVisited]);
    useEffect(() => { isPanModeRef.current = isPanMode; }, [isPanMode]);

    // ── Ambient glow canvas (cursor-reactive) ─────────────────────────────────
    const startGlowLoop = useCallback(() => {
        const canvas = glowCanvasRef.current;
        if (!canvas) return;

        const resize = () => {
            const wrap = wrapRef.current;
            if (!wrap) return;
            canvas.width = wrap.clientWidth;
            canvas.height = wrap.clientHeight;
        };
        resize();

        const ro = new ResizeObserver(resize);
        if (wrapRef.current) ro.observe(wrapRef.current);

        const tick = () => {
            const ctx = canvas.getContext('2d');
            if (!ctx) { glowRafRef.current = requestAnimationFrame(tick); return; }

            // Lerp glow towards mouse (spring feel)
            glowRef.current.x += (mouseRef.current.x - glowRef.current.x) * 0.06;
            glowRef.current.y += (mouseRef.current.y - glowRef.current.y) * 0.06;

            ctx.clearRect(0, 0, canvas.width, canvas.height);

            if (mouseRef.current.x > 0) {
                const radius = Math.max(canvas.width, canvas.height) * 0.45;
                const grd = ctx.createRadialGradient(
                    glowRef.current.x, glowRef.current.y, 0,
                    glowRef.current.x, glowRef.current.y, radius
                );
                grd.addColorStop(0, isDark ? 'rgba(122,80,48,0.20)' : 'rgba(200,162,136,0.15)');
                grd.addColorStop(0.4, isDark ? 'rgba(90,58,32,0.08)' : 'rgba(200,162,136,0.06)');
                grd.addColorStop(1, 'rgba(0,0,0,0)');
                ctx.fillStyle = grd;
                ctx.fillRect(0, 0, canvas.width, canvas.height);
            }

            glowRafRef.current = requestAnimationFrame(tick);
        };

        glowRafRef.current = requestAnimationFrame(tick);
        return () => {
            cancelAnimationFrame(glowRafRef.current);
            ro.disconnect();
        };
    }, [isDark]);

    // Mouse tracking on the wrapper
    const handleMouseMove = useCallback((e) => {
        const wrap = wrapRef.current;
        if (!wrap) return;
        const rect = wrap.getBoundingClientRect();
        mouseRef.current = { x: e.clientX - rect.left, y: e.clientY - rect.top };
    }, []);

    const handleMouseLeave = useCallback(() => {
        mouseRef.current = { x: -9999, y: -9999 };
    }, []);

    // Start/restart glow loop when dark mode changes or data loads
    useEffect(() => {
        if (!graphData || loading) return;
        const cleanup = startGlowLoop();
        return cleanup;
    }, [graphData, loading, startGlowLoop]);

    // ── Cytoscape palette (re-styles existing instance when dark mode changes) ─
    const buildCyStyle = useCallback((p) => [
        // Book nodes — Central Red Giant Sun (unchanged)
        {
            selector: 'node[type="book"]',
            style: {
                'background-color': '#FFFFFF',
                'background-fill': 'radial-gradient',
                'background-gradient-stop-colors': '#FFFFFF #FFA500 #8B0000',
                'background-gradient-stop-positions': '0% 40% 100%',
                'border-width': 0,
                'label': 'data(label)',
                'text-valign': 'bottom',
                'text-halign': 'center',
                'text-margin-y': 12,
                'font-size': '12px',
                'font-weight': 'bold',
                'color': p.orbLabel,
                'text-outline-width': 0,
                'width': 80,
                'height': 80,
                'shape': 'ellipse',
                'shadow-blur': 40,
                'shadow-color': '#FF0000',
                'shadow-opacity': 0.9,
                'shadow-offset-x': 0,
                'shadow-offset-y': 0,
                'text-wrap': 'wrap',
                'text-max-width': '150px',
                'z-index': 10
            }
        },
        // Topic nodes — Warm Orbs
        {
            selector: 'node[type="topic"]',
            style: {
                'background-color': p.orbFill,
                'background-fill': 'radial-gradient',
                'background-gradient-stop-colors': p.orbGradient,
                'background-gradient-stop-positions': '0% 50% 100%',
                'shape': 'ellipse',
                'width': 24,
                'height': 24,
                'border-width': 1.5,
                'border-color': p.orbBorder,
                'label': 'data(label)',
                'text-valign': 'bottom',
                'text-halign': 'center',
                'text-margin-y': 8,
                'font-size': '10px',
                'font-family': 'sans-serif',
                'color': p.orbLabel,
                'text-outline-width': 0,
                'text-wrap': 'wrap',
                'text-max-width': '130px',
                'z-index': 5
            }
        },
        // High-connectivity nodes (4+) — Larger Orb
        {
            selector: 'node[type="topic"][degree >= 4]',
            style: {
                'width': 34,
                'height': 34,
                'font-size': '11px',
                'font-weight': 'bold',
                'text-max-width': '150px'
            }
        },
        // Selected
        {
            selector: 'node:selected',
            style: {
                'background-color': '#C8A288',
                'border-color': '#7B5B4E',
                'border-width': 3,
                'color': p.orbLabel,
                'text-outline-width': 0,
                'z-index': 20
            }
        },
        // Hovered
        {
            selector: 'node.hover',
            style: {
                'background-color': isDark ? '#4a3828' : '#E6D5CC',
                'border-color': isDark ? '#9a7050' : '#C8A288',
                'border-width': 2.5,
                'z-index': 15
            }
        },
        // Neighbor highlight
        {
            selector: 'node.neighbor',
            style: {
                'background-color': isDark ? '#3e3020' : '#F0E4DA',
                'border-color': isDark ? '#8a6040' : '#C8A288',
                'border-width': 2.5,
                'z-index': 12
            }
        },
        // Dimmed
        {
            selector: 'node.dimmed',
            style: { 'opacity': 0.25 }
        },
        // Contains edges
        {
            selector: 'edge[type="contains"]',
            style: {
                'line-color': p.edgeContains,
                'width': 1.5,
                'curve-style': 'bezier',
                'opacity': 0.5,
                'line-style': 'solid'
            }
        },
        // Prerequisite edges
        {
            selector: 'edge[type="prerequisite"]',
            style: {
                'line-color': p.edgePrereq,
                'width': 2.5,
                'target-arrow-shape': 'triangle',
                'target-arrow-color': p.edgePrereq,
                'arrow-scale': 1.2,
                'curve-style': 'bezier',
                'opacity': 0.75
            }
        },
        // Related edges
        {
            selector: 'edge[type="related"]',
            style: {
                'line-color': p.edgeRelated,
                'width': 1.5,
                'line-style': 'dashed',
                'curve-style': 'bezier',
                'opacity': 0.3
            }
        },
        // Highlighted edges
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
            style: { 'opacity': 0.08 }
        }
    ], [isDark]);

    // Re-style when dark mode flips (without reiniting the whole graph)
    useEffect(() => {
        if (cyRef.current) {
            cyRef.current.style(buildCyStyle(P));
            // Also update canvas bg
            if (containerRef.current) {
                containerRef.current.style.background = P.canvas;
            }
        }
    }, [isDark]); // eslint-disable-line react-hooks/exhaustive-deps

    // ── Cytoscape init ────────────────────────────────────────────────────────
    const initCytoscape = useCallback((data) => {
        if (!containerRef.current || !data) return;

        const rect = containerRef.current.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) {
            setTimeout(() => initCytoscape(data), 100);
            return;
        }

        if (cyRef.current) cyRef.current.destroy();

        // Degree map for size scaling
        const elements = [];
        const degreeMap = {};
        data.nodes.forEach(node => { degreeMap[node.id] = 0; });
        data.edges.forEach(edge => {
            degreeMap[edge.source] = (degreeMap[edge.source] || 0) + 1;
            degreeMap[edge.target] = (degreeMap[edge.target] || 0) + 1;
        });

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

        const p = isDark ? DARK : LIGHT;

        cyRef.current = cytoscape({
            container: containerRef.current,
            elements,
            style: buildCyStyle(p),
            layout: {
                name: 'cose',
                animate: true,
                animationDuration: 800,
                nodeRepulsion: () => 12000,
                idealEdgeLength: () => 150,
                edgeElasticity: () => 80,
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
            wheelSensitivity: 0.21,
            boxSelectionEnabled: false,
            selectionType: 'single'
        });

        // Set canvas bg via DOM (Cytoscape doesn't expose it)
        containerRef.current.style.background = p.canvas;

        // ── Event handlers ────────────────────────────────────────────────────

        cyRef.current.on('tap', 'node[type="topic"]', async (evt) => {
            const node = evt.target;
            const topicLabel = node.data('label');

            if (topicStartTimeRef.current && selectedTopicRef.current) {
                const duration = Date.now() - topicStartTimeRef.current;
                recordGraphInteraction(projectId, selectedTopicRef.current, 'click', duration).catch(() => { });
            }

            cyRef.current.elements().removeClass('neighbor highlighted dimmed');
            cyRef.current.elements().addClass('dimmed');

            const neighborhood = node.neighborhood().add(node);
            neighborhood.nodes().removeClass('dimmed').addClass('neighbor');
            neighborhood.edges().removeClass('dimmed').addClass('highlighted');
            node.removeClass('neighbor dimmed');

            setSelectedTopic(topicLabel);
            setTopicStartTime(Date.now());
            setTopicsVisited(prev => new Set([...prev, topicLabel]));

            recordActivity(projectId, 'knowledge_graph', { action: 'explore_topic', topic: topicLabel });
            await fetchTopicSummary(topicLabel);
            fetchSuggestions(topicLabel);
        });

        cyRef.current.on('tap', 'node[type="book"]', (evt) => {
            const node = evt.target;
            cyRef.current.elements().removeClass('neighbor highlighted dimmed');
            cyRef.current.elements().addClass('dimmed');
            const neighborhood = node.neighborhood().add(node);
            neighborhood.nodes().removeClass('dimmed').addClass('neighbor');
            neighborhood.edges().removeClass('dimmed').addClass('highlighted');
            node.removeClass('neighbor dimmed');
        });

        cyRef.current.on('tap', (evt) => {
            if (evt.target === cyRef.current) {
                cyRef.current.elements().removeClass('neighbor highlighted dimmed');
            }
        });

        cyRef.current.on('mouseover', 'node', (evt) => {
            const node = evt.target;
            node.addClass('hover');
            containerRef.current.style.cursor = 'pointer';
            setHoveredNodeData(node.data());

            if (node.data('type') === 'book') {
                node.stop();
                node.animate({
                    style: {
                        'width': 95, 'height': 95,
                        'shadow-blur': 80,
                        'shadow-color': '#FFA500',
                        'background-gradient-stop-colors': '#FFFFFF #FFD700 #FF0000'
                    },
                    duration: 300,
                    easing: 'ease-out'
                });
            } else {
                node.stop();
                node.animate({
                    style: {
                        'width': node.data('degree') >= 4 ? 38 : 28,
                        'height': node.data('degree') >= 4 ? 38 : 28
                    },
                    duration: 150,
                    easing: 'ease-out'
                });
            }
        });

        const pulseSun = (node, scaleUp = true) => {
            if (node.removed() || node.hasClass('hover')) return;
            node.animate({
                style: {
                    'width': scaleUp ? 85 : 80,
                    'height': scaleUp ? 85 : 80,
                    'shadow-blur': scaleUp ? 60 : 40,
                },
                duration: 2000,
                easing: 'ease-in-out-sine',
                complete: () => pulseSun(node, !scaleUp)
            });
        };

        cyRef.current.on('mouseout', 'node', (evt) => {
            const node = evt.target;
            node.removeClass('hover');
            containerRef.current.style.cursor = isPanModeRef.current ? 'grab' : 'default';
            setHoveredNodeData(null);

            if (node.data('type') === 'book') {
                node.stop();
                node.style({
                    'shadow-color': '#FF0000',
                    'background-gradient-stop-colors': '#FFFFFF #FFA500 #8B0000'
                });
                pulseSun(node);
            } else {
                node.stop();
                node.animate({
                    style: {
                        'width': node.data('degree') >= 4 ? 34 : 24,
                        'height': node.data('degree') >= 4 ? 34 : 24
                    },
                    duration: 300,
                    easing: 'ease-in-out'
                });
            }
        });

        cyRef.current.on('layoutstop', () => {
            cyRef.current.fit(undefined, 50);
            cyRef.current.nodes('[type="book"]').forEach(n => pulseSun(n));
        });

    }, [projectId, isDark, buildCyStyle]);

    // ── Data fetching ─────────────────────────────────────────────────────────
    const fetchGraphData = async () => {
        try {
            setLoading(true);
            setError(null);

            let data = null;
            try {
                data = await getKnowledgeGraphVisualization(projectId);
            } catch (vizErr) {
                console.warn('KG viz endpoint failed, falling back:', vizErr);
                try {
                    const kgData = await getKnowledgeGraph(projectId);
                    const topicsData = await getTopics(projectId);
                    const allTopics = topicsData?.all || (Array.isArray(topicsData) ? topicsData : []);
                    const nodes = [];
                    const edges = [];
                    const addedTopics = new Set();

                    if (kgData?.graph?.nodes?.length > 0) {
                        kgData.graph.nodes.forEach(n => {
                            nodes.push({ id: n.id, label: n.label, type: 'topic', document: n.document });
                            addedTopics.add(n.id);
                        });
                    }
                    allTopics.forEach(t => {
                        if (!addedTopics.has(t)) nodes.push({ id: t, label: t, type: 'topic', document: 'Unknown' });
                    });
                    if (kgData?.graph?.edges) {
                        kgData.graph.edges.forEach(e => edges.push({
                            source: e.source || e.from_topic,
                            target: e.target || e.to_topic,
                            type: e.type || e.relation_type || 'related',
                            weight: e.weight || 0.5
                        }));
                    }
                    data = { project_name: 'Knowledge Graph', nodes, edges, stats: kgData?.stats || {} };
                } catch (fallbackErr) {
                    console.error('Fallback also failed:', fallbackErr);
                    throw vizErr;
                }
            }

            setGraphData(data);
            setLoading(false);

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

    const fetchTopicSummary = async (topic, forceRegenerate = false) => {
        try {
            setSummaryLoading(true);
            const data = await getTopicSummary(projectId, topic, forceRegenerate);
            setTopicSummary(data);
        } catch (err) {
            console.error('Error fetching summary:', err);
            setTopicSummary({ topic, summary: 'Failed to load summary. Please try again.', sources: [], cached: false });
        } finally {
            setSummaryLoading(false);
        }
    };

    const fetchSuggestions = async (currentTopic = null) => {
        try {
            const data = await getLearningSuggestions(projectId, currentTopic, 3);
            setSuggestions(data);
            setAnalytics(data.analytics);
        } catch (err) {
            console.warn('Suggestions unavailable:', err.message);
        }
    };

    const closeTopic = async () => {
        if (topicStartTime && selectedTopic) {
            const duration = Date.now() - topicStartTime;
            try { await recordGraphInteraction(projectId, selectedTopic, 'summary_view', duration); } catch (e) { }
        }
        if (cyRef.current) {
            cyRef.current.elements().removeClass('neighbor highlighted dimmed');
            cyRef.current.elements().unselect();
        }
        setSelectedTopic(null);
        setTopicSummary(null);
        setTopicStartTime(null);
    };

    const zoomIn = () => cyRef.current?.zoom(cyRef.current.zoom() * 1.68);
    const zoomOut = () => cyRef.current?.zoom(cyRef.current.zoom() / 1.68);
    const fitGraph = () => cyRef.current?.fit(undefined, 50);

    const togglePanMode = () => {
        setIsPanMode(!isPanMode);
        if (cyRef.current) {
            cyRef.current.userPanningEnabled(!isPanMode);
            containerRef.current.style.cursor = !isPanMode ? 'grab' : 'default';
        }
    };

    // ── Lifecycle ─────────────────────────────────────────────────────────────
    useEffect(() => {
        fetchGraphData();

        const resizeObserver = new ResizeObserver(() => {
            if (cyRef.current) {
                cyRef.current.resize();
                cyRef.current.fit(undefined, 50);
            }
        });
        if (containerRef.current) resizeObserver.observe(containerRef.current);

        return () => {
            resizeObserver.disconnect();
            cancelAnimationFrame(glowRafRef.current);
            if (sessionIdRef.current && sessionStartTimeRef.current) {
                const totalTime = Date.now() - sessionStartTimeRef.current;
                endLearningSession(sessionIdRef.current, Array.from(topicsVisitedRef.current), totalTime);
            }
            if (cyRef.current) cyRef.current.destroy();
        };
    }, [projectId]);

    useEffect(() => {
        if (graphData) {
            let innerRaf = null;
            const outerRaf = requestAnimationFrame(() => {
                innerRaf = requestAnimationFrame(() => initCytoscape(graphData));
            });
            return () => {
                cancelAnimationFrame(outerRaf);
                if (innerRaf !== null) cancelAnimationFrame(innerRaf);
            };
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [graphData]);

    const navigateToTopic = async (topic) => {
        setSelectedTopic(topic);
        setTopicsVisited(prev => new Set([...prev, topic]));
        await fetchTopicSummary(topic);

        if (cyRef.current) {
            const node = cyRef.current.getElementById(topic);
            if (node.length) {
                cyRef.current.elements().removeClass('neighbor highlighted dimmed');
                cyRef.current.elements().addClass('dimmed');
                const neighborhood = node.neighborhood().add(node);
                neighborhood.nodes().removeClass('dimmed').addClass('neighbor');
                neighborhood.edges().removeClass('dimmed').addClass('highlighted');
                node.removeClass('neighbor dimmed');
                cyRef.current.animate({ center: { eles: node }, zoom: 1.5 }, { duration: 300 });
                node.select();
            }
        }
    };

    // ── Loading / error / empty states ────────────────────────────────────────
    const stateContainerCls = `flex items-center justify-center h-[600px] rounded-2xl border transition-colors duration-300 ${isDark ? 'bg-[#221810] border-[#5a3a20]' : 'bg-[#FFF5ED] border-white/10'
        }`;

    if (loading) return (
        <div className={stateContainerCls}>
            <div className="text-center">
                <Loader2 className="w-12 h-12 text-[#FFD700] animate-spin mx-auto mb-4" />
                <p className={isDark ? 'text-[#a08060]' : 'text-[#A0A0A0]'}>Igniting knowledge core…</p>
            </div>
        </div>
    );

    if (error) return (
        <div className={stateContainerCls}>
            <div className="text-center">
                <Network className="w-12 h-12 text-red-500 mx-auto mb-4" />
                <p className="text-red-400 mb-4">{error}</p>
                <button
                    onClick={fetchGraphData}
                    className="px-4 py-2 bg-[#FFD700] text-[#0A0A0C] font-semibold rounded-lg hover:bg-yellow-500 transition-colors"
                >
                    Try Again
                </button>
            </div>
        </div>
    );

    if (!graphData?.nodes?.length) return (
        <div className={stateContainerCls}>
            <div className="text-center">
                <Network className={`w-12 h-12 mx-auto mb-4 ${isDark ? 'text-[#5a3a20]' : 'text-[#3A3A3A]'}`} />
                <p className={`font-semibold mb-2 ${isDark ? 'text-[#a08060]' : 'text-white'}`}>No Cosmic Entities Found</p>
                <p className={`text-sm mb-4 ${isDark ? 'text-[#7a5c3a]' : 'text-[#A0A0A0]'}`}>Upload documents to ignite the central sun.</p>
                <button onClick={fetchGraphData} className="px-4 py-2 bg-[#FFD700] text-[#0A0A0C] font-semibold rounded-lg hover:bg-yellow-500 transition-colors">
                    Refresh Cosmos
                </button>
            </div>
        </div>
    );

    // ── Main render ───────────────────────────────────────────────────────────
    return (
        <div
            ref={wrapRef}
            className="flex h-full min-h-[600px] relative p-0 overflow-hidden md:rounded-2xl border-y md:border shadow-inner transition-colors duration-300"
            style={{ borderColor: isDark ? '#5a3a20' : '#EED9CA' }}
            onMouseMove={handleMouseMove}
            onMouseLeave={handleMouseLeave}
        >
            {/* ── Ambient cursor glow canvas (pointer-events:none, sits above Cy canvas) */}
            <canvas
                ref={glowCanvasRef}
                className="absolute inset-0 z-[5] pointer-events-none"
                style={{ mixBlendMode: isDark ? 'screen' : 'multiply' }}
            />

            {/* ── Main Graph Container ─────────────────────────────────────── */}
            <div
                className="flex-1 w-full relative min-h-[500px] transition-colors duration-300"
                style={{ background: P.canvas }}
            >
                {/* Header */}
                {!zenMode && (
                    <div
                        className="absolute left-0 right-0 z-10 p-3 md:p-4 pointer-events-none transition-all duration-300 top-0"
                        style={{
                            background: isDark
                                ? `linear-gradient(to bottom, ${P.toolbarBg}ee, transparent)`
                                : 'linear-gradient(to bottom, rgba(0,0,0,0.60), transparent)'
                        }}
                    >
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pointer-events-auto">
                            <div className="flex items-center gap-2 flex-wrap">
                                <Network className="w-5 h-5 text-[#FFD700] shrink-0 drop-shadow-[0_0_8px_rgba(255,215,0,0.8)]" />
                                <h2 className="font-semibold text-white tracking-wide text-sm md:text-base">
                                    {graphData?.project_name || 'Knowledge Cosmos'}
                                </h2>
                                <div className="flex items-center gap-1.5 flex-wrap">
                                    {[
                                        `${graphData?.nodes?.filter(n => n.type === 'topic').length || 0} Orbs`,
                                        `${graphData?.nodes?.filter(n => n.type === 'book').length || 0} Suns`,
                                        `${graphData?.edges?.length || 0} Links`,
                                    ].map(label => (
                                        <span key={label} className="text-xs text-white/80 bg-white/10 backdrop-blur-md px-2 py-1 rounded-full border border-white/10">
                                            {label}
                                        </span>
                                    ))}
                                </div>
                            </div>
                        </div>
                    </div>
                )}

                {/* Floating Controls */}
                <div className={`absolute z-30 pointer-events-auto transition-all duration-500 flex ${selectedTopic
                        ? 'flex-col top-1/4 md:top-1/2 -translate-y-1/2 right-4 md:right-[416px]'
                        : `flex-row ${zenMode ? 'top-[52px]' : 'top-4'} right-4`
                    } gap-1.5 md:gap-2`}>
                    {[
                        { icon: <Hand className="w-4 h-4" />, action: togglePanMode, title: 'Toggle pan mode', active: isPanMode },
                        { icon: <ZoomIn className="w-4 h-4" />, action: zoomIn, title: 'Zoom in' },
                        { icon: <ZoomOut className="w-4 h-4" />, action: zoomOut, title: 'Zoom out' },
                        { icon: <Target className="w-4 h-4" />, action: fitGraph, title: 'Fit to view' },
                        { icon: <RefreshCw className="w-4 h-4" />, action: fetchGraphData, title: 'Refresh' },
                    ].map(({ icon, action, title, active }) => (
                        <button
                            key={title}
                            onClick={action}
                            title={title}
                            className={`p-2 rounded-lg transition-colors border shadow-lg backdrop-blur-md ${active
                                    ? 'bg-[#FFD700]/20 border-[#FFD700]/50 text-[#FFD700]'
                                    : isDark
                                        ? 'bg-[#3a2c1e]/80 border-[#7a5c3a]/40 text-[#a08060] hover:bg-[#4a3828] hover:text-[#c09060]'
                                        : 'bg-black/40 border-white/10 text-white/70 hover:bg-white/10 hover:text-white'
                                }`}
                        >{icon}</button>
                    ))}
                </div>

                {/* Cytoscape Container */}
                <div
                    ref={containerRef}
                    className="w-full h-full"
                    style={{ cursor: isPanMode ? 'grab' : 'default', minHeight: '400px' }}
                />

                {/* Glassmorphism Hover Info Panel */}
                <div className={`absolute bottom-4 left-4 z-20 transition-all duration-500 ease-out transform ${hoveredNodeData ? 'translate-y-0 opacity-100 scale-100' : 'translate-y-4 opacity-0 scale-95 pointer-events-none'
                    }`}>
                    {hoveredNodeData && (
                        <div
                            className="w-64 sm:w-72 backdrop-blur-xl shadow-xl rounded-2xl p-4 border"
                            style={{
                                background: isDark ? 'rgba(46,31,18,0.95)' : 'rgba(62,47,40,0.95)',
                                borderColor: isDark ? '#5a3a20' : 'rgba(188,154,113,0.30)'
                            }}
                        >
                            <div className="flex flex-col gap-1.5">
                                <span className={`text-[10px] uppercase tracking-widest font-bold ${hoveredNodeData.type === 'book' ? 'text-[#FF4500]' : 'text-[#FFD700]'
                                    }`}>
                                    {hoveredNodeData.type === 'book' ? 'Core Sun' : 'Cosmic Orb'}
                                </span>
                                <h4 className="font-bold text-white text-lg leading-tight drop-shadow-md">
                                    {hoveredNodeData.label}
                                </h4>
                                <div className="flex items-center gap-2 text-xs text-white/60 mt-1">
                                    <Network className="w-3.5 h-3.5" />
                                    <span>{hoveredNodeData.degree || 0} Connection{(hoveredNodeData.degree || 0) !== 1 ? 's' : ''}</span>
                                </div>
                                {hoveredNodeData.type === 'book' && (
                                    <p className="text-white/50 text-[10px] leading-relaxed mt-2 italic border-t border-white/10 pt-2">
                                        Gravitational anchor representing a source document.
                                    </p>
                                )}
                            </div>
                        </div>
                    )}
                </div>

                {/* Legend — Constellations */}
                <div
                    className={`absolute top-24 right-4 backdrop-blur-md rounded-xl p-3 shadow-lg transition-opacity duration-300 ${hoveredNodeData ? 'opacity-20' : 'opacity-100'}`}
                    style={{
                        background: P.legendBg,
                        borderWidth: 1,
                        borderStyle: 'solid',
                        borderColor: P.legendBorder
                    }}
                >
                    <p className="text-[10px] uppercase tracking-wider font-bold text-white/60 mb-2">Constellations</p>
                    <div className="flex flex-col gap-2 text-xs" style={{ color: isDark ? '#a08060' : 'rgba(255,255,255,0.8)' }}>
                        <div className="flex items-center gap-2">
                            <div className="w-4 h-4 bg-[radial-gradient(ellipse_at_center,_#FFFFFF,_#FFA500,_#8B0000)] rounded-full shadow-[0_0_8px_rgba(255,0,0,0.8)] shrink-0" />
                            <span>Core Sun (Doc)</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <div
                                className="w-3 h-3 rounded-full shrink-0"
                                style={{
                                    background: isDark
                                        ? 'radial-gradient(ellipse at center, #4a3520, #3a2c1e)'
                                        : 'radial-gradient(ellipse at center, #FFF8DC, #FFD700, #DAA520)',
                                    border: `1.5px solid ${isDark ? '#7a5c3a' : '#D4A373'}`,
                                    boxShadow: isDark
                                        ? '0 0 6px rgba(122,80,48,0.6)'
                                        : '0 0 6px rgba(255,215,0,0.8)'
                                }}
                            />
                            <span>Orb (Topic)</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <div
                                className="w-4 h-4 rounded-full shrink-0"
                                style={{
                                    background: isDark
                                        ? 'radial-gradient(ellipse at center, #5a4028, #3a2c1e)'
                                        : 'radial-gradient(ellipse at center, #FFF8DC, #FFD700, #DAA520)',
                                    border: `2px solid ${isDark ? '#9a7050' : '#D4A373'}`,
                                    boxShadow: isDark
                                        ? '0 0 10px rgba(154,112,80,0.8)'
                                        : '0 0 12px rgba(255,215,0,1)'
                                }}
                            />
                            <span>Key Orb</span>
                        </div>
                    </div>
                </div>

                {/* Analytics Mini Card */}
                {analytics && (
                    <div
                        className="absolute bottom-4 right-4 backdrop-blur-md rounded-xl p-3 shadow-lg"
                        style={{
                            background: isDark ? '#2e1f12' : 'rgba(62,47,40,0.95)',
                            border: `1px solid ${isDark ? '#5a3a20' : 'rgba(188,154,113,0.30)'}`
                        }}
                    >
                        <div className="flex items-center gap-2 mb-2">
                            <BarChart3 className="w-4 h-4 text-[#FFD700]" />
                            <span className="text-xs font-semibold text-white tracking-wide">Progress</span>
                        </div>
                        <div className="text-[11px] text-white/70 space-y-0.5">
                            <p>{analytics.coverage_percent}% explored</p>
                            <p>{analytics.total_topics_visited}/{analytics.total_topics_available} discoveries</p>
                        </div>
                    </div>
                )}
            </div>

            {/* ── Right Panel — Topic Summary ──────────────────────────────── */}
            <div className={`
                fixed md:absolute inset-x-0 bottom-0 z-50 md:inset-y-0 md:right-0 md:left-auto md:w-[400px] md:z-40
                transition-transform duration-500 ease-[cubic-bezier(0.23,1,0.32,1)]
                ${selectedTopic ? 'translate-y-0 md:translate-x-0' : 'translate-y-full md:translate-y-0 md:translate-x-[110%]'}
                h-[60vh] md:h-full
            `}>
                {selectedTopic && (
                    <div className="absolute -top-10 left-0 right-0 h-10 lg:hidden" onClick={closeTopic} />
                )}

                <div className={`h-full backdrop-blur-2xl md:backdrop-blur-3xl rounded-t-3xl md:rounded-none md:border-l overflow-hidden flex flex-col ${zenMode ? 'pt-12' : ''} ${isDark
                        ? 'bg-[#1e140c]/90 border-[#5a3a20] md:shadow-[-20px_0_40px_rgba(10,6,2,0.9)]'
                        : 'bg-black/60 border-white/10 md:shadow-[-20px_0_40px_rgba(0,0,0,0.8)]'
                    }`}>
                    {selectedTopic ? (
                        <>
                            {/* Drag handle */}
                            <div className="w-full flex justify-center py-2 lg:hidden" onClick={closeTopic}
                                style={{ background: isDark ? 'rgba(46,31,18,0.5)' : 'rgba(200,162,136,0.08)' }}>
                                <div className="w-12 h-1.5 bg-[#E6D5CC] rounded-full" />
                            </div>

                            {/* Topic Header */}
                            <div className="p-4 border-b border-white/10 bg-white/5">
                                <div className="flex items-start justify-between">
                                    <div className="flex-1 min-w-0">
                                        <h3 className="font-semibold text-white text-base md:text-lg truncate drop-shadow-md">
                                            {selectedTopic}
                                        </h3>
                                        {topicSummary?.cached && (
                                            <span className="text-xs text-white/50 flex items-center gap-1 mt-1">
                                                <Clock className="w-3 h-3" /> Cached
                                            </span>
                                        )}
                                    </div>
                                    <div className="flex items-center gap-2 ml-2">
                                        <button
                                            onClick={() => fetchTopicSummary(selectedTopic, true)}
                                            className="p-1.5 hover:bg-white/10 rounded-lg transition-colors"
                                            title="Regenerate summary"
                                            disabled={summaryLoading}
                                        >
                                            <RefreshCw className={`w-4 h-4 text-white/70 ${summaryLoading ? 'animate-spin' : ''}`} />
                                        </button>
                                        <button onClick={closeTopic} className="p-1.5 hover:bg-white/10 rounded-lg transition-colors">
                                            <X className="w-4 h-4 text-white/70" />
                                        </button>
                                    </div>
                                </div>
                            </div>

                            {/* Summary Content */}
                            <div className="flex-1 overflow-y-auto p-4">
                                {summaryLoading ? (
                                    <div className="flex items-center justify-center h-full">
                                        <div className="text-center mt-10">
                                            <Loader2 className="w-8 h-8 text-[#FFD700] animate-spin mx-auto mb-3" />
                                            <p className="text-sm text-white/60">Deciphering stellar emissions…</p>
                                        </div>
                                    </div>
                                ) : topicSummary ? (
                                    <div className="prose prose-sm prose-invert max-w-none overflow-x-auto text-white/80">
                                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                            {topicSummary.summary}
                                        </ReactMarkdown>
                                        {topicSummary.sources?.length > 0 && (
                                            <div className="mt-6 pt-4 border-t border-white/10">
                                                <p className="text-[10px] uppercase tracking-wider font-bold text-[#FFD700] mb-3">Origin Systems</p>
                                                <div className="flex flex-wrap gap-2">
                                                    {topicSummary.sources.map((source, idx) => (
                                                        <span
                                                            key={idx}
                                                            className="text-[11px] bg-white/5 border border-white/10 text-white/80 px-2.5 py-1 rounded-full"
                                                        >
                                                            {source.doc_name}
                                                        </span>
                                                    ))}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                ) : (
                                    <p className="text-white/40 text-center mt-10 text-sm">Target an orb to scan its data</p>
                                )}
                            </div>
                        </>
                    ) : (
                        <div className="flex-1 flex items-center justify-center p-8">
                            <div className="text-center px-4">
                                <Target className="w-12 h-12 text-white/20 mx-auto mb-4" />
                                <p className="text-white/60 text-sm md:text-base">Target an orb to extract knowledge</p>
                                <p className="text-xs text-white/30 mt-2">
                                    Summaries are decoded from your documents in real-time
                                </p>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default KnowledgeGraphView;
