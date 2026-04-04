import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
    Search, X, FileText, MessageSquare, BookOpen,
    Clock, ArrowRight, Loader2, Tag, ChevronRight,
    Sparkles, Filter
} from 'lucide-react';
import { searchDocuments, getRecentSearches, saveRecentSearch as saveRecentSearchApi, clearRecentSearches as clearRecentSearchesApi } from '../api';
import { createLogger } from '../utils/logger';

const logger = createLogger('GlobalSearch');

// Simple debounce helper (no lodash dependency)
const debounce = (fn, ms) => {
    let timer;
    return (...args) => {
        clearTimeout(timer);
        timer = setTimeout(() => fn(...args), ms);
    };
};

const GlobalSearch = ({
    projectId,
    documents = [],
    documentTopics = {},
    onSelectDocument,
    onSelectTopic,
    onClose,
    isOpen
}) => {
    const [query, setQuery] = useState('');
    const [results, setResults] = useState({ documents: [], topics: [], semantic: [] });
    const [loading, setLoading] = useState(false);
    const [activeTab, setActiveTab] = useState('all');
    const [recentSearches, setRecentSearches] = useState([]);
    const inputRef = useRef(null);

    // Collect all topics from documentTopics
    const allTopics = React.useMemo(() => {
        const topicsSet = new Set();
        Object.values(documentTopics).forEach(topics => {
            topics.forEach(t => topicsSet.add(t));
        });
        return Array.from(topicsSet);
    }, [documentTopics]);

    // Load recent searches from API
    useEffect(() => {
        const load = async () => {
            try {
                const data = await getRecentSearches(projectId);
                setRecentSearches(data.searches || []);
            } catch (err) {
                logger.warn('Failed to load recent searches', err);
            }
        };
        load();
    }, [projectId]);

    // Focus input when opened
    useEffect(() => {
        if (isOpen && inputRef.current) {
            inputRef.current.focus();
        }
    }, [isOpen]);

    // Debounced search
    const performSearch = useCallback(
        debounce(async (searchQuery) => {
            if (!searchQuery.trim()) {
                setResults({ documents: [], topics: [], semantic: [] });
                return;
            }

            setLoading(true);
            const lowerQuery = searchQuery.toLowerCase();

            // Local search for documents
            const matchedDocs = documents.filter(doc =>
                doc.filename.toLowerCase().includes(lowerQuery)
            );

            // Local search for topics
            const matchedTopics = allTopics.filter(topic =>
                topic.toLowerCase().includes(lowerQuery)
            );

            // Semantic search via API
            let semanticResults = [];
            try {
                const data = await searchDocuments(projectId, searchQuery, null, 5);
                semanticResults = data.results || [];
            } catch (error) {
                logger.error('Semantic search failed', error);
            }

            setResults({
                documents: matchedDocs,
                topics: matchedTopics,
                semantic: semanticResults,
            });
            setLoading(false);
        }, 300),
        [documents, allTopics, projectId]
    );

    useEffect(() => {
        performSearch(query);
    }, [query, performSearch]);

    const saveRecentSearch = (searchQuery) => {
        if (!searchQuery.trim()) return;
        const updated = [searchQuery, ...recentSearches.filter(s => s !== searchQuery)].slice(0, 5);
        setRecentSearches(updated);
        saveRecentSearchApi(projectId, searchQuery).catch(err =>
            logger.warn('Failed to save recent search', err)
        );
    };

    const handleSelect = (type, item) => {
        saveRecentSearch(query);
        if (type === 'document' && onSelectDocument) {
            onSelectDocument(item.id);
        } else if (type === 'topic' && onSelectTopic) {
            onSelectTopic(item);
        } else if (type === 'content' && onSelectTopic) {
            // For content matches, we can trigger the AI tutor with context
            onSelectTopic(item.text?.slice(0, 100) || 'Selected content');
        }
        onClose?.();
    };

    const clearRecentSearches = () => {
        setRecentSearches([]);
        clearRecentSearchesApi(projectId).catch(err =>
            logger.warn('Failed to clear recent searches', err)
        );
    };

    const totalResults = results.documents.length + results.topics.length + results.semantic.length;

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-start justify-center pt-[10vh] backdrop-blur-sm">
            <div 
                className="w-full max-w-2xl mx-4 bg-white rounded-2xl shadow-2xl overflow-hidden animate-in slide-in-from-top-4 fade-in duration-200"
                onClick={(e) => e.stopPropagation()}
            >
                {/* Search Input */}
                <div className="p-4 border-b border-[#E6D5CC]">
                    <div className="relative flex items-center gap-3">
                        <Search className="h-6 w-6 text-[#8a6a5c]" />
                        <input
                            ref={inputRef}
                            type="text"
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            placeholder="Search documents, topics, or ask a question..."
                            className="flex-1 text-lg text-[#4A3B32] placeholder-[#8a6a5c] outline-none bg-transparent"
                        />
                        {loading && <Loader2 className="h-5 w-5 animate-spin text-[#C8A288]" />}
                        {query && (
                            <button
                                onClick={() => setQuery('')}
                                className="p-1 hover:bg-[#FDF6F0] rounded-lg transition-colors"
                            >
                                <X className="h-5 w-5 text-[#8a6a5c]" />
                            </button>
                        )}
                        <button
                            onClick={onClose}
                            className="p-2 hover:bg-[#FDF6F0] rounded-lg transition-colors text-[#8a6a5c]"
                        >
                            <span className="text-xs font-medium">ESC</span>
                        </button>
                    </div>
                </div>

                {/* Filter Tabs */}
                {query && (
                    <div className="flex gap-2 p-2 border-b border-[#E6D5CC] bg-[#FDF6F0]">
                        {[
                            { id: 'all', label: `All (${totalResults})` },
                            { id: 'documents', label: `Documents (${results.documents.length})` },
                            { id: 'topics', label: `Topics (${results.topics.length})` },
                            { id: 'content', label: `Content (${results.semantic.length})` },
                        ].map(tab => (
                            <button
                                key={tab.id}
                                onClick={() => setActiveTab(tab.id)}
                                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                                    activeTab === tab.id
                                        ? 'bg-[#C8A288] text-white'
                                        : 'text-[#8a6a5c] hover:bg-white'
                                }`}
                            >
                                {tab.label}
                            </button>
                        ))}
                    </div>
                )}

                {/* Results */}
                <div className="max-h-[60vh] overflow-y-auto">
                    {!query && recentSearches.length > 0 && (
                        <div className="p-4">
                            <div className="flex items-center justify-between mb-2">
                                <p className="text-sm font-medium text-[#8a6a5c]">Recent Searches</p>
                                <button
                                    onClick={clearRecentSearches}
                                    className="text-xs text-[#C8A288] hover:text-[#B08B72]"
                                >
                                    Clear
                                </button>
                            </div>
                            <div className="space-y-1">
                                {recentSearches.map((search, idx) => (
                                    <button
                                        key={idx}
                                        onClick={() => setQuery(search)}
                                        className="w-full flex items-center gap-3 p-2 hover:bg-[#FDF6F0] rounded-lg text-left transition-colors"
                                    >
                                        <Clock className="h-4 w-4 text-[#8a6a5c]" />
                                        <span className="text-[#4A3B32]">{search}</span>
                                    </button>
                                ))}
                            </div>
                        </div>
                    )}

                    {query && totalResults === 0 && !loading && (
                        <div className="p-8 text-center">
                            <Search className="h-12 w-12 mx-auto text-[#8a6a5c] opacity-50 mb-3" />
                            <p className="text-[#4A3B32] font-medium">No results found</p>
                            <p className="text-sm text-[#8a6a5c]">Try different keywords or check spelling</p>
                        </div>
                    )}

                    {/* Document Results */}
                    {(activeTab === 'all' || activeTab === 'documents') && results.documents.length > 0 && (
                        <div className="p-4 border-b border-[#E6D5CC]">
                            <p className="text-xs font-bold text-[#8a6a5c] uppercase tracking-wide mb-2">
                                Documents
                            </p>
                            <div className="space-y-1">
                                {results.documents.map((doc) => (
                                    <button
                                        key={doc.id}
                                        onClick={() => handleSelect('document', doc)}
                                        className="w-full flex items-center gap-3 p-3 hover:bg-[#FDF6F0] rounded-xl text-left transition-colors group"
                                    >
                                        <div className="h-10 w-10 bg-blue-100 rounded-lg flex items-center justify-center flex-shrink-0">
                                            <FileText className="h-5 w-5 text-blue-600" />
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <p className="font-medium text-[#4A3B32] truncate">{doc.filename}</p>
                                            <p className="text-sm text-[#8a6a5c]">
                                                {(doc.file_size / 1024 / 1024).toFixed(2)} MB
                                            </p>
                                        </div>
                                        <ChevronRight className="h-5 w-5 text-[#8a6a5c] opacity-0 group-hover:opacity-100 transition-opacity" />
                                    </button>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Topic Results */}
                    {(activeTab === 'all' || activeTab === 'topics') && results.topics.length > 0 && (
                        <div className="p-4 border-b border-[#E6D5CC]">
                            <p className="text-xs font-bold text-[#8a6a5c] uppercase tracking-wide mb-2">
                                Topics
                            </p>
                            <div className="flex flex-wrap gap-2">
                                {results.topics.map((topic, idx) => (
                                    <button
                                        key={idx}
                                        onClick={() => handleSelect('topic', topic)}
                                        className="flex items-center gap-2 px-3 py-2 bg-[#FDF6F0] hover:bg-[#E6D5CC] rounded-lg transition-colors"
                                    >
                                        <Tag className="h-4 w-4 text-[#C8A288]" />
                                        <span className="text-[#4A3B32]">{topic}</span>
                                    </button>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Semantic/Content Results */}
                    {(activeTab === 'all' || activeTab === 'content') && results.semantic.length > 0 && (
                        <div className="p-4">
                            <p className="text-xs font-bold text-[#8a6a5c] uppercase tracking-wide mb-2 flex items-center gap-1">
                                <Sparkles className="h-3 w-3" />
                                Content Matches
                            </p>
                            <div className="space-y-2">
                                {results.semantic.map((result, idx) => (
                                    <button
                                        key={idx}
                                        onClick={() => handleSelect('content', result)}
                                        className="w-full p-3 bg-[#FDF6F0] hover:bg-[#E6D5CC] rounded-xl text-left transition-colors"
                                    >
                                        <p className="text-sm text-[#4A3B32] line-clamp-2">
                                            {result.text || result.chunk_text}
                                        </p>
                                        <p className="text-xs text-[#8a6a5c] mt-1 flex items-center gap-1">
                                            <FileText className="h-3 w-3" />
                                            {result.document_name || 'Document'}
                                        </p>
                                    </button>
                                ))}
                            </div>
                        </div>
                    )}
                </div>

                {/* Footer */}
                <div className="p-3 border-t border-[#E6D5CC] bg-[#FDF6F0] flex items-center justify-between text-xs text-[#8a6a5c]">
                    <div className="flex items-center gap-4">
                        <span className="flex items-center gap-1">
                            <kbd className="px-1.5 py-0.5 bg-white rounded border border-[#E6D5CC] font-mono">↑</kbd>
                            <kbd className="px-1.5 py-0.5 bg-white rounded border border-[#E6D5CC] font-mono">↓</kbd>
                            Navigate
                        </span>
                        <span className="flex items-center gap-1">
                            <kbd className="px-1.5 py-0.5 bg-white rounded border border-[#E6D5CC] font-mono">↵</kbd>
                            Select
                        </span>
                    </div>
                    <span className="flex items-center gap-1">
                        <kbd className="px-1.5 py-0.5 bg-white rounded border border-[#E6D5CC] font-mono">ESC</kbd>
                        Close
                    </span>
                </div>
            </div>
        </div>
    );
};

export default GlobalSearch;
