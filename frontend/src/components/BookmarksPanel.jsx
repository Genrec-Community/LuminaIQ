import React, { useState, useEffect } from 'react';
import {
    Bookmark, BookmarkPlus, Search, X,
    FileText, Clock, Trash2, Edit2, Check,
    Star, Highlighter, Quote, Copy, Palette
} from 'lucide-react';
import { getBookmarks, addBookmark as addBookmarkApi, updateBookmark as updateBookmarkApi, deleteBookmark as deleteBookmarkApi } from '../api';

const HIGHLIGHT_COLORS = [
    { name: 'Yellow', value: 'yellow', bg: 'bg-yellow-100', border: 'border-yellow-300', text: 'text-yellow-800', accent: 'bg-yellow-400' },
    { name: 'Green', value: 'green', bg: 'bg-green-100', border: 'border-green-300', text: 'text-green-800', accent: 'bg-green-400' },
    { name: 'Blue', value: 'blue', bg: 'bg-blue-100', border: 'border-blue-300', text: 'text-blue-800', accent: 'bg-blue-400' },
    { name: 'Pink', value: 'pink', bg: 'bg-pink-100', border: 'border-pink-300', text: 'text-pink-800', accent: 'bg-pink-400' },
    { name: 'Purple', value: 'purple', bg: 'bg-purple-100', border: 'border-purple-300', text: 'text-purple-800', accent: 'bg-purple-400' },
];

const getColorClasses = (colorValue) => {
    return HIGHLIGHT_COLORS.find(c => c.value === colorValue) || HIGHLIGHT_COLORS[0];
};

const BookmarksPanel = ({
    projectId,
    documents = [],
    onNavigateToTopic,
    onClose
}) => {
    const [bookmarks, setBookmarks] = useState([]);
    const [searchQuery, setSearchQuery] = useState('');
    const [filterDoc, setFilterDoc] = useState('all');
    const [editingId, setEditingId] = useState(null);
    const [editNote, setEditNote] = useState('');
    const [activeTab, setActiveTab] = useState('all'); // 'all' | 'bookmarks' | 'highlights'
    const [showAddForm, setShowAddForm] = useState(false);
    const [addMode, setAddMode] = useState('bookmark'); // 'bookmark' | 'highlight'
    const [newBookmark, setNewBookmark] = useState({ title: '', note: '', documentId: '', type: 'topic' });
    const [newHighlight, setNewHighlight] = useState({ title: '', highlightText: '', note: '', documentId: '', color: 'yellow' });
    const [copiedId, setCopiedId] = useState(null);

    // Load bookmarks from API
    useEffect(() => {
        const load = async () => {
            try {
                const data = await getBookmarks(projectId);
                setBookmarks(data.bookmarks || []);
            } catch (err) {
                console.error('Failed to load bookmarks:', err);
            }
        };
        load();
    }, [projectId]);

    // Counts for tabs
    const bookmarkCount = bookmarks.filter(b => b.type !== 'highlight').length;
    const highlightCount = bookmarks.filter(b => b.type === 'highlight').length;

    const addBookmark = async () => {
        if (!newBookmark.title) return;

        try {
            const result = await addBookmarkApi(
                projectId,
                newBookmark.title,
                newBookmark.note,
                newBookmark.documentId || null,
                newBookmark.type
            );
            const docName = newBookmark.documentId
                ? documents.find(d => d.id === newBookmark.documentId)?.filename
                : null;
            const bookmark = { ...result, documentName: docName, starred: false };
            setBookmarks([bookmark, ...bookmarks]);
            setNewBookmark({ title: '', note: '', documentId: '', type: 'topic' });
            setShowAddForm(false);
        } catch (err) {
            console.error('Failed to add bookmark:', err);
        }
    };

    const addHighlight = async () => {
        if (!newHighlight.highlightText) return;

        try {
            const result = await addBookmarkApi(
                projectId,
                newHighlight.title || 'Highlight',
                newHighlight.note,
                newHighlight.documentId || null,
                'highlight',
                newHighlight.highlightText,
                newHighlight.color
            );
            const docName = newHighlight.documentId
                ? documents.find(d => d.id === newHighlight.documentId)?.filename
                : null;
            const bookmark = { ...result, documentName: docName, starred: false };
            setBookmarks([bookmark, ...bookmarks]);
            setNewHighlight({ title: '', highlightText: '', note: '', documentId: '', color: 'yellow' });
            setShowAddForm(false);
        } catch (err) {
            console.error('Failed to add highlight:', err);
        }
    };

    const deleteBookmark = async (id) => {
        try {
            await deleteBookmarkApi(id);
            setBookmarks(bookmarks.filter(b => b.id !== id));
        } catch (err) {
            console.error('Failed to delete bookmark:', err);
        }
    };

    const toggleStar = (id) => {
        setBookmarks(bookmarks.map(b =>
            b.id === id ? { ...b, starred: !b.starred } : b
        ));
    };

    const updateNote = async (id) => {
        try {
            await updateBookmarkApi(id, { note: editNote });
            setBookmarks(bookmarks.map(b =>
                b.id === id ? { ...b, note: editNote } : b
            ));
            setEditingId(null);
            setEditNote('');
        } catch (err) {
            console.error('Failed to update bookmark:', err);
        }
    };

    const copyToClipboard = (text, id) => {
        navigator.clipboard.writeText(text).then(() => {
            setCopiedId(id);
            setTimeout(() => setCopiedId(null), 2000);
        });
    };

    // Filter and search
    const filteredBookmarks = bookmarks
        .filter(b => {
            if (activeTab === 'bookmarks') return b.type !== 'highlight';
            if (activeTab === 'highlights') return b.type === 'highlight';
            return true;
        })
        .filter(b => filterDoc === 'all' || b.document_id === filterDoc || b.documentId === filterDoc)
        .filter(b =>
            b.title?.toLowerCase().includes(searchQuery.toLowerCase()) ||
            b.note?.toLowerCase().includes(searchQuery.toLowerCase()) ||
            b.highlight_text?.toLowerCase().includes(searchQuery.toLowerCase())
        )
        .sort((a, b) => {
            if (a.starred && !b.starred) return -1;
            if (!a.starred && b.starred) return 1;
            return new Date(b.createdAt || b.created_at) - new Date(a.createdAt || a.created_at);
        });

    const getDocName = (docId) => {
        const doc = documents.find(d => d.id === docId);
        return doc?.filename || 'Unknown';
    };

    // Render a highlight card
    const renderHighlightCard = (bookmark) => {
        const colorClasses = getColorClasses(bookmark.color);
        return (
            <div
                key={bookmark.id}
                className={`p-3 rounded-xl ${colorClasses.bg} border ${colorClasses.border} transition-all group hover:shadow-sm`}
            >
                <div className="flex items-start gap-2">
                    {/* Color bar */}
                    <div className={`w-1 self-stretch rounded-full ${colorClasses.accent} shrink-0`} />
                    <div className="flex-1 min-w-0">
                        {/* Header */}
                        <div className="flex items-center justify-between mb-1.5">
                            <div className="flex items-center gap-1.5">
                                <Quote className={`h-3.5 w-3.5 ${colorClasses.text}`} />
                                <span className={`text-xs font-bold uppercase tracking-wide ${colorClasses.text} opacity-70`}>
                                    {bookmark.title && bookmark.title !== 'Highlight' ? bookmark.title : 'Quote'}
                                </span>
                            </div>
                            <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                <button
                                    onClick={() => copyToClipboard(bookmark.highlight_text, bookmark.id)}
                                    className="p-1 hover:bg-white/60 rounded"
                                    title="Copy quote"
                                >
                                    {copiedId === bookmark.id ? (
                                        <Check className="h-3.5 w-3.5 text-green-600" />
                                    ) : (
                                        <Copy className={`h-3.5 w-3.5 ${colorClasses.text}`} />
                                    )}
                                </button>
                                <button
                                    onClick={() => {
                                        setEditingId(bookmark.id);
                                        setEditNote(bookmark.note || '');
                                    }}
                                    className="p-1 hover:bg-white/60 rounded"
                                >
                                    <Edit2 className={`h-3.5 w-3.5 ${colorClasses.text}`} />
                                </button>
                                <button
                                    onClick={() => deleteBookmark(bookmark.id)}
                                    className="p-1 hover:bg-white/60 rounded"
                                >
                                    <Trash2 className="h-3.5 w-3.5 text-red-500" />
                                </button>
                            </div>
                        </div>

                        {/* Quote text */}
                        <blockquote className={`text-sm ${colorClasses.text} font-medium italic leading-relaxed pl-2 border-l-0`}>
                            &ldquo;{bookmark.highlight_text}&rdquo;
                        </blockquote>

                        {/* Note (editable) */}
                        {editingId === bookmark.id ? (
                            <div className="mt-2 flex gap-2">
                                <input
                                    type="text"
                                    value={editNote}
                                    onChange={(e) => setEditNote(e.target.value)}
                                    placeholder="Add a note..."
                                    className="flex-1 px-2 py-1 text-sm bg-white rounded border border-[#E6D5CC] focus:ring-1 focus:ring-[#C8A288]"
                                    autoFocus
                                />
                                <button
                                    onClick={() => updateNote(bookmark.id)}
                                    className="p-1 bg-[#C8A288] text-white rounded"
                                >
                                    <Check className="h-4 w-4" />
                                </button>
                            </div>
                        ) : bookmark.note ? (
                            <p className={`text-xs ${colorClasses.text} opacity-70 mt-1.5`}>
                                {bookmark.note}
                            </p>
                        ) : null}

                        {/* Meta */}
                        <div className="flex items-center gap-2 mt-2 text-xs opacity-60">
                            {(bookmark.document_id || bookmark.documentName) && (
                                <span className="flex items-center gap-1 bg-white/50 px-2 py-0.5 rounded-full">
                                    <FileText className="h-3 w-3" />
                                    {(bookmark.documentName || getDocName(bookmark.document_id))?.substring(0, 20)}
                                </span>
                            )}
                            <span className="flex items-center gap-1">
                                <Clock className="h-3 w-3" />
                                {new Date(bookmark.createdAt || bookmark.created_at).toLocaleDateString()}
                            </span>
                        </div>
                    </div>
                </div>
            </div>
        );
    };

    // Render a regular bookmark card
    const renderBookmarkCard = (bookmark) => {
        return (
            <div
                key={bookmark.id}
                className="p-3 bg-[#FDF6F0] rounded-xl hover:bg-[#E6D5CC]/50 transition-colors group"
            >
                <div className="flex items-start gap-3">
                    <button
                        onClick={() => toggleStar(bookmark.id)}
                        className="mt-0.5 flex-shrink-0"
                    >
                        <Star className={`h-5 w-5 transition-colors ${
                            bookmark.starred
                                ? 'text-amber-500 fill-amber-500'
                                : 'text-[#8a6a5c] hover:text-amber-500'
                        }`} />
                    </button>
                    <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between">
                            <h4 className="font-medium text-[#4A3B32] truncate">
                                {bookmark.title}
                            </h4>
                            <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                <button
                                    onClick={() => {
                                        setEditingId(bookmark.id);
                                        setEditNote(bookmark.note || '');
                                    }}
                                    className="p-1 hover:bg-white rounded"
                                >
                                    <Edit2 className="h-3.5 w-3.5 text-[#8a6a5c]" />
                                </button>
                                <button
                                    onClick={() => deleteBookmark(bookmark.id)}
                                    className="p-1 hover:bg-white rounded"
                                >
                                    <Trash2 className="h-3.5 w-3.5 text-red-500" />
                                </button>
                            </div>
                        </div>

                        {editingId === bookmark.id ? (
                            <div className="mt-2 flex gap-2">
                                <input
                                    type="text"
                                    value={editNote}
                                    onChange={(e) => setEditNote(e.target.value)}
                                    placeholder="Add a note..."
                                    className="flex-1 px-2 py-1 text-sm bg-white rounded border border-[#E6D5CC] focus:ring-1 focus:ring-[#C8A288]"
                                    autoFocus
                                />
                                <button
                                    onClick={() => updateNote(bookmark.id)}
                                    className="p-1 bg-[#C8A288] text-white rounded"
                                >
                                    <Check className="h-4 w-4" />
                                </button>
                            </div>
                        ) : bookmark.note ? (
                            <p className="text-sm text-[#8a6a5c] mt-1 line-clamp-2">
                                {bookmark.note}
                            </p>
                        ) : null}

                        <div className="flex items-center gap-2 mt-2 text-xs text-[#8a6a5c]">
                            {(bookmark.document_id || bookmark.documentName) && (
                                <span className="flex items-center gap-1 bg-white px-2 py-0.5 rounded-full">
                                    <FileText className="h-3 w-3" />
                                    {(bookmark.documentName || getDocName(bookmark.document_id))?.substring(0, 20)}
                                </span>
                            )}
                            <span className="flex items-center gap-1">
                                <Clock className="h-3 w-3" />
                                {new Date(bookmark.createdAt || bookmark.created_at).toLocaleDateString()}
                            </span>
                        </div>
                    </div>
                </div>
            </div>
        );
    };

    const emptyMessages = {
        all: { title: 'No items yet', desc: 'Save bookmarks or highlight quotes for quick access' },
        bookmarks: { title: 'No bookmarks yet', desc: 'Save important topics and concepts' },
        highlights: { title: 'No highlights yet', desc: 'Save your favorite quotes and passages' },
    };

    return (
        <div className="h-full flex flex-col bg-white rounded-2xl border border-[#E6D5CC] overflow-hidden">
            {/* Header */}
            <div className="p-4 border-b border-[#E6D5CC] bg-gradient-to-r from-amber-500 to-orange-500 text-white">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <Bookmark className="h-6 w-6" />
                        <div>
                            <h3 className="font-bold">Bookmarks & Highlights</h3>
                            <p className="text-sm opacity-90">{bookmarks.length} saved items</p>
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                        <button
                            onClick={() => { setShowAddForm(!showAddForm); setAddMode('bookmark'); }}
                            className="p-2 hover:bg-white/20 rounded-lg transition-colors"
                            title="Add Bookmark"
                        >
                            <BookmarkPlus className="h-5 w-5" />
                        </button>
                        <button
                            onClick={() => { setShowAddForm(!showAddForm); setAddMode('highlight'); }}
                            className="p-2 hover:bg-white/20 rounded-lg transition-colors"
                            title="Add Highlight"
                        >
                            <Highlighter className="h-5 w-5" />
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
            </div>

            {/* Tabs */}
            <div className="flex border-b border-[#E6D5CC] bg-[#FDF6F0]">
                {[
                    { key: 'all', label: 'All', count: bookmarks.length },
                    { key: 'bookmarks', label: 'Bookmarks', count: bookmarkCount },
                    { key: 'highlights', label: 'Highlights', count: highlightCount },
                ].map(tab => (
                    <button
                        key={tab.key}
                        onClick={() => setActiveTab(tab.key)}
                        className={`flex-1 py-2.5 text-xs font-bold uppercase tracking-wide transition-all relative ${
                            activeTab === tab.key
                                ? 'text-[#C8A288]'
                                : 'text-[#8a6a5c] hover:text-[#4A3B32]'
                        }`}
                    >
                        {tab.label}
                        {tab.count > 0 && (
                            <span className={`ml-1 px-1.5 py-0.5 rounded-full text-[10px] ${
                                activeTab === tab.key
                                    ? 'bg-[#C8A288] text-white'
                                    : 'bg-[#E6D5CC] text-[#8a6a5c]'
                            }`}>
                                {tab.count}
                            </span>
                        )}
                        {activeTab === tab.key && (
                            <div className="absolute bottom-0 left-2 right-2 h-0.5 bg-[#C8A288] rounded-full" />
                        )}
                    </button>
                ))}
            </div>

            {/* Add Form - Bookmark */}
            {showAddForm && addMode === 'bookmark' && (
                <div className="p-4 bg-amber-50 border-b border-amber-200 animate-in fade-in slide-in-from-top-2 duration-200">
                    <div className="space-y-3">
                        <div className="flex items-center gap-2 mb-2">
                            <BookmarkPlus className="h-4 w-4 text-amber-600" />
                            <span className="text-sm font-bold text-amber-800">New Bookmark</span>
                        </div>
                        <input
                            type="text"
                            value={newBookmark.title}
                            onChange={(e) => setNewBookmark({ ...newBookmark, title: e.target.value })}
                            placeholder="Topic or concept name"
                            className="w-full px-3 py-2 bg-white border border-amber-200 rounded-lg focus:ring-2 focus:ring-amber-500 text-[#4A3B32]"
                        />
                        <textarea
                            value={newBookmark.note}
                            onChange={(e) => setNewBookmark({ ...newBookmark, note: e.target.value })}
                            placeholder="Add a note (optional)"
                            rows={2}
                            className="w-full px-3 py-2 bg-white border border-amber-200 rounded-lg focus:ring-2 focus:ring-amber-500 text-[#4A3B32] resize-none"
                        />
                        <select
                            value={newBookmark.documentId}
                            onChange={(e) => setNewBookmark({ ...newBookmark, documentId: e.target.value })}
                            className="w-full px-3 py-2 bg-white border border-amber-200 rounded-lg focus:ring-2 focus:ring-amber-500 text-[#4A3B32]"
                        >
                            <option value="">No specific document</option>
                            {documents.map(doc => (
                                <option key={doc.id} value={doc.id}>{doc.filename}</option>
                            ))}
                        </select>
                        <div className="flex gap-2">
                            <button
                                onClick={addBookmark}
                                disabled={!newBookmark.title}
                                className="flex-1 py-2 bg-amber-500 text-white rounded-lg font-medium hover:bg-amber-600 transition-colors disabled:opacity-50"
                            >
                                Add Bookmark
                            </button>
                            <button
                                onClick={() => setShowAddForm(false)}
                                className="px-4 py-2 bg-white border border-amber-200 rounded-lg text-[#4A3B32] hover:bg-amber-50 transition-colors"
                            >
                                Cancel
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Add Form - Highlight / Quote */}
            {showAddForm && addMode === 'highlight' && (
                <div className="p-4 bg-purple-50 border-b border-purple-200 animate-in fade-in slide-in-from-top-2 duration-200">
                    <div className="space-y-3">
                        <div className="flex items-center gap-2 mb-2">
                            <Highlighter className="h-4 w-4 text-purple-600" />
                            <span className="text-sm font-bold text-purple-800">Save a Quote / Highlight</span>
                        </div>
                        <textarea
                            value={newHighlight.highlightText}
                            onChange={(e) => setNewHighlight({ ...newHighlight, highlightText: e.target.value })}
                            placeholder="Paste or type the quote / passage here..."
                            rows={3}
                            className="w-full px-3 py-2 bg-white border border-purple-200 rounded-lg focus:ring-2 focus:ring-purple-500 text-[#4A3B32] resize-none italic"
                            autoFocus
                        />
                        <input
                            type="text"
                            value={newHighlight.title}
                            onChange={(e) => setNewHighlight({ ...newHighlight, title: e.target.value })}
                            placeholder="Label (optional, e.g. 'Key Definition')"
                            className="w-full px-3 py-2 bg-white border border-purple-200 rounded-lg focus:ring-2 focus:ring-purple-500 text-[#4A3B32]"
                        />
                        <input
                            type="text"
                            value={newHighlight.note}
                            onChange={(e) => setNewHighlight({ ...newHighlight, note: e.target.value })}
                            placeholder="Your thoughts / note (optional)"
                            className="w-full px-3 py-2 bg-white border border-purple-200 rounded-lg focus:ring-2 focus:ring-purple-500 text-[#4A3B32]"
                        />

                        {/* Color Picker */}
                        <div>
                            <span className="text-xs font-bold text-purple-700 uppercase tracking-wide flex items-center gap-1 mb-2">
                                <Palette className="h-3 w-3" /> Color
                            </span>
                            <div className="flex gap-2">
                                {HIGHLIGHT_COLORS.map(c => (
                                    <button
                                        key={c.value}
                                        onClick={() => setNewHighlight({ ...newHighlight, color: c.value })}
                                        className={`h-7 w-7 rounded-full ${c.accent} border-2 transition-all ${
                                            newHighlight.color === c.value
                                                ? 'border-[#4A3B32] scale-110 shadow-md'
                                                : 'border-transparent hover:scale-105'
                                        }`}
                                        title={c.name}
                                    />
                                ))}
                            </div>
                        </div>

                        <select
                            value={newHighlight.documentId}
                            onChange={(e) => setNewHighlight({ ...newHighlight, documentId: e.target.value })}
                            className="w-full px-3 py-2 bg-white border border-purple-200 rounded-lg focus:ring-2 focus:ring-purple-500 text-[#4A3B32]"
                        >
                            <option value="">No specific document</option>
                            {documents.map(doc => (
                                <option key={doc.id} value={doc.id}>{doc.filename}</option>
                            ))}
                        </select>
                        <div className="flex gap-2">
                            <button
                                onClick={addHighlight}
                                disabled={!newHighlight.highlightText}
                                className="flex-1 py-2 bg-purple-600 text-white rounded-lg font-medium hover:bg-purple-700 transition-colors disabled:opacity-50"
                            >
                                Save Highlight
                            </button>
                            <button
                                onClick={() => setShowAddForm(false)}
                                className="px-4 py-2 bg-white border border-purple-200 rounded-lg text-[#4A3B32] hover:bg-purple-50 transition-colors"
                            >
                                Cancel
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Search and Filter */}
            <div className="p-3 border-b border-[#E6D5CC] space-y-2">
                <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#8a6a5c]" />
                    <input
                        type="text"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        placeholder={activeTab === 'highlights' ? 'Search highlights...' : 'Search bookmarks...'}
                        className="w-full pl-9 pr-4 py-2 bg-[#FDF6F0] border-none rounded-lg focus:ring-2 focus:ring-[#C8A288] text-[#4A3B32] text-sm"
                    />
                </div>
                {documents.length > 1 && (
                    <select
                        value={filterDoc}
                        onChange={(e) => setFilterDoc(e.target.value)}
                        className="w-full px-3 py-2 bg-[#FDF6F0] border-none rounded-lg focus:ring-2 focus:ring-[#C8A288] text-[#4A3B32] text-sm"
                    >
                        <option value="all">All Documents</option>
                        {documents.map(doc => (
                            <option key={doc.id} value={doc.id}>
                                {doc.filename.length > 30 ? doc.filename.substring(0, 27) + '...' : doc.filename}
                            </option>
                        ))}
                    </select>
                )}
            </div>

            {/* Items List */}
            <div className="flex-1 overflow-y-auto p-3 space-y-2">
                {filteredBookmarks.length > 0 ? (
                    filteredBookmarks.map((bookmark) =>
                        bookmark.type === 'highlight'
                            ? renderHighlightCard(bookmark)
                            : renderBookmarkCard(bookmark)
                    )
                ) : (
                    <div className="flex flex-col items-center justify-center py-12 text-center">
                        <div className="h-16 w-16 bg-[#E6D5CC]/50 rounded-full flex items-center justify-center mb-4">
                            {activeTab === 'highlights' ? (
                                <Highlighter className="h-8 w-8 text-[#8a6a5c]" />
                            ) : (
                                <Bookmark className="h-8 w-8 text-[#8a6a5c]" />
                            )}
                        </div>
                        <p className="font-medium text-[#4A3B32]">{emptyMessages[activeTab].title}</p>
                        <p className="text-sm text-[#8a6a5c] mt-1">
                            {emptyMessages[activeTab].desc}
                        </p>
                        <button
                            onClick={() => {
                                setShowAddForm(true);
                                setAddMode(activeTab === 'highlights' ? 'highlight' : 'bookmark');
                            }}
                            className="mt-4 px-4 py-2 bg-[#C8A288] text-white rounded-lg font-medium hover:bg-[#B08B72] transition-colors flex items-center gap-2"
                        >
                            {activeTab === 'highlights' ? (
                                <><Highlighter className="h-4 w-4" /> Add Highlight</>
                            ) : (
                                <><BookmarkPlus className="h-4 w-4" /> Add Bookmark</>
                            )}
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
};

export default BookmarksPanel;
