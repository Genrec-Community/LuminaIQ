import React, { useState, useEffect } from 'react';
import {
    Bookmark, BookmarkPlus, Search, X, ChevronRight,
    FileText, Tag, Clock, Trash2, Edit2, Check,
    FolderOpen, Star, Filter
} from 'lucide-react';
import { getBookmarks, addBookmark as addBookmarkApi, updateBookmark as updateBookmarkApi, deleteBookmark as deleteBookmarkApi } from '../api';

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
    const [showAddForm, setShowAddForm] = useState(false);
    const [newBookmark, setNewBookmark] = useState({ title: '', note: '', documentId: '', type: 'topic' });

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
            // Add document name for display
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

    const deleteBookmark = async (id) => {
        try {
            await deleteBookmarkApi(id);
            setBookmarks(bookmarks.filter(b => b.id !== id));
        } catch (err) {
            console.error('Failed to delete bookmark:', err);
        }
    };

    const toggleStar = (id) => {
        // Star is a UI-only feature (not stored in DB), keep local
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

    // Filter and search
    const filteredBookmarks = bookmarks
        .filter(b => filterDoc === 'all' || b.document_id === filterDoc || b.documentId === filterDoc)
        .filter(b => 
            b.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
            b.note?.toLowerCase().includes(searchQuery.toLowerCase())
        )
        .sort((a, b) => {
            // Starred first, then by date
            if (a.starred && !b.starred) return -1;
            if (!a.starred && b.starred) return 1;
            return new Date(b.createdAt || b.created_at) - new Date(a.createdAt || a.created_at);
        });

    const getDocName = (docId) => {
        const doc = documents.find(d => d.id === docId);
        return doc?.filename || 'Unknown';
    };

    return (
        <div className="h-full flex flex-col bg-white rounded-2xl border border-[#E6D5CC] overflow-hidden">
            {/* Header */}
            <div className="p-4 border-b border-[#E6D5CC] bg-gradient-to-r from-amber-500 to-orange-500 text-white">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <Bookmark className="h-6 w-6" />
                        <div>
                            <h3 className="font-bold">Bookmarks</h3>
                            <p className="text-sm opacity-90">{bookmarks.length} saved items</p>
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                        <button
                            onClick={() => setShowAddForm(!showAddForm)}
                            className="p-2 hover:bg-white/20 rounded-lg transition-colors"
                        >
                            <BookmarkPlus className="h-5 w-5" />
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

            {/* Add Form */}
            {showAddForm && (
                <div className="p-4 bg-amber-50 border-b border-amber-200">
                    <div className="space-y-3">
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

            {/* Search and Filter */}
            <div className="p-3 border-b border-[#E6D5CC] space-y-2">
                <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#8a6a5c]" />
                    <input
                        type="text"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        placeholder="Search bookmarks..."
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

            {/* Bookmarks List */}
            <div className="flex-1 overflow-y-auto p-3 space-y-2">
                {filteredBookmarks.length > 0 ? (
                    filteredBookmarks.map((bookmark) => (
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
                                        {bookmark.documentName && (
                                            <span className="flex items-center gap-1 bg-white px-2 py-0.5 rounded-full">
                                                <FileText className="h-3 w-3" />
                                                {bookmark.documentName.length > 20 
                                                    ? bookmark.documentName.substring(0, 17) + '...' 
                                                    : bookmark.documentName
                                                }
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
                    ))
                ) : (
                    <div className="flex flex-col items-center justify-center py-12 text-center">
                        <div className="h-16 w-16 bg-[#E6D5CC]/50 rounded-full flex items-center justify-center mb-4">
                            <Bookmark className="h-8 w-8 text-[#8a6a5c]" />
                        </div>
                        <p className="font-medium text-[#4A3B32]">No bookmarks yet</p>
                        <p className="text-sm text-[#8a6a5c] mt-1">
                            Save important topics and concepts for quick access
                        </p>
                        <button
                            onClick={() => setShowAddForm(true)}
                            className="mt-4 px-4 py-2 bg-[#C8A288] text-white rounded-lg font-medium hover:bg-[#B08B72] transition-colors flex items-center gap-2"
                        >
                            <BookmarkPlus className="h-4 w-4" />
                            Add Bookmark
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
};

export default BookmarksPanel;
