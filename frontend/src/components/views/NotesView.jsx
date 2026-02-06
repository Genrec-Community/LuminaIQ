import React, { useState } from 'react';
import { BookOpen, Copy, Download, Loader2, ChevronDown } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { generateNotes } from '../../api';
import { useToast } from '../../context/ToastContext';

const NotesView = ({ projectId, availableTopics, selectedDocuments }) => {
    const toast = useToast();
    // Notes State
    const [notesType, setNotesType] = useState('Comprehensive Summary');
    const [notesTopic, setNotesTopic] = useState('');
    const [notesTopicSelection, setNotesTopicSelection] = useState('');
    const [notesContent, setNotesContent] = useState('');
    const [notesLoading, setNotesLoading] = useState(false);

    const handleGenerateNotes = async () => {
        setNotesLoading(true);
        setNotesContent('');

        // If specific topic selected/entered, use it. Otherwise general.
        // Actually backend expects `topic` for targeted notes.
        const effectiveTopic = notesTopicSelection === '__custom__' ? notesTopic : notesTopicSelection;

        try {
            const data = await generateNotes(
                projectId,
                notesType,
                effectiveTopic,
                selectedDocuments
            );
            // Assuming data is an object with { notes: "..." } or just the text
            // Based on other endpoints, it likely returns an object. 
            // If it returns raw text, data would be the string.
            // Let's assume it returns { notes: "..." } for now, but if it just returns the string from api.js (response.data), check structure.
            // Actually, let's look at api.js again. It returns response.data.
            // If the backend returns { notes: "content" }, then we use data.notes.
            // If the backend returns "content", we use data.
            // API returns { content: "..." } based on user report
            setNotesContent(typeof data === 'string' ? data : (data.notes || data.content || JSON.stringify(data)));
        } catch (error) {
            console.error("Notes gen error", error);
            toast.error('Failed to generate notes');
        } finally {
            setNotesLoading(false);
        }
    };

    const copyToClipboard = () => {
        navigator.clipboard.writeText(notesContent);
        toast.success('Notes copied to clipboard!');
    };

    return (
        <div className="h-full overflow-y-auto p-4 md:p-8 max-w-4xl mx-auto custom-scrollbar relative">
            {/* Full-screen Loading Overlay */}
            {notesLoading && !notesContent && (
                <div className="absolute inset-0 z-50 bg-white/90 backdrop-blur-sm flex flex-col items-center justify-center animate-in fade-in duration-300">
                    <div className="relative mb-6">
                        <div className="h-20 w-20 border-4 border-[#E6D5CC] rounded-full"></div>
                        <div className="absolute inset-0 h-20 w-20 border-4 border-[#C8A288] rounded-full border-t-transparent animate-spin"></div>
                        <BookOpen className="absolute inset-0 m-auto h-8 w-8 text-[#C8A288]" />
                    </div>
                    <h3 className="text-xl font-bold text-[#4A3B32] mb-2">Generating Notes</h3>
                    <p className="text-[#8a6a5c] text-center max-w-xs">
                        Creating <span className="font-semibold">{notesType}</span> {notesTopic || notesTopicSelection ? `about ${notesTopic || notesTopicSelection}` : 'from your documents'}...
                    </p>
                    <div className="flex gap-1.5 mt-6">
                        <div className="h-2 w-2 bg-[#C8A288] rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                        <div className="h-2 w-2 bg-[#C8A288] rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                        <div className="h-2 w-2 bg-[#C8A288] rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                    </div>
                </div>
            )}

            {!notesContent && !notesLoading ? (
                <div className="text-center py-12 animate-in fade-in slide-in-from-bottom-4">
                    <div className="h-20 w-20 bg-[#FDF6F0] rounded-full flex items-center justify-center mx-auto mb-6">
                        <BookOpen className="h-10 w-10 text-[#C8A288]" />
                    </div>
                    <h3 className="text-2xl font-bold mb-2 text-[#4A3B32]">Study Notes</h3>
                    <p className="text-[#8a6a5c] mb-8">Generate comprehensive summaries or targeted study guides.</p>

                    <div className="max-w-md mx-auto space-y-4 bg-white p-8 rounded-3xl border border-[#E6D5CC] shadow-sm text-left">
                        <div>
                            <label className="block text-sm font-bold mb-2 text-[#4A3B32] uppercase tracking-wide opacity-80">Focus Topic (Optional)</label>
                            {availableTopics.length > 0 ? (
                                <div className="relative">
                                    <select
                                        value={notesTopicSelection}
                                        onChange={(e) => {
                                            const val = e.target.value;
                                            setNotesTopicSelection(val);
                                            if (val !== '__custom__') setNotesTopic(val);
                                            else setNotesTopic('');
                                        }}
                                        className="w-full px-5 py-3.5 bg-[#FDF6F0] border-0 rounded-xl focus:ring-2 focus:ring-[#C8A288] text-[#4A3B32] font-medium appearance-none"
                                    >
                                        <option value="">General Summary (All)</option>
                                        {availableTopics.map((topic, idx) => (
                                            <option key={idx} value={topic}>{topic}</option>
                                        ))}
                                        <option value="__custom__">Custom Topic...</option>
                                    </select>
                                    <ChevronDown className="absolute right-4 top-1/2 -translate-y-1/2 h-4 w-4 text-[#8a6a5c] pointer-events-none" />
                                    {notesTopicSelection === '__custom__' && (
                                        <input
                                            type="text"
                                            value={notesTopic}
                                            onChange={(e) => setNotesTopic(e.target.value)}
                                            placeholder="Enter custom topic..."
                                            className="w-full px-5 py-3.5 bg-[#FDF6F0] border-0 rounded-xl focus:ring-2 focus:ring-[#C8A288] mt-3 animate-in fade-in"
                                            autoFocus
                                        />
                                    )}
                                </div>
                            ) : (
                                <input
                                    type="text"
                                    value={notesTopic}
                                    onChange={(e) => setNotesTopic(e.target.value)}
                                    placeholder="e.g. Chapter 4, Photosynthesis..."
                                    className="w-full px-5 py-3.5 bg-[#FDF6F0] border-0 rounded-xl focus:ring-2 focus:ring-[#C8A288] mb-4"
                                />
                            )}
                        </div>

                        <div>
                            <label className="block text-sm font-bold mb-2 text-[#4A3B32] uppercase tracking-wide opacity-80">Note Type</label>
                            <div className="relative">
                                <select
                                    value={notesType}
                                    onChange={(e) => setNotesType(e.target.value)}
                                    className="w-full px-5 py-3.5 bg-[#FDF6F0] border-0 rounded-xl focus:ring-2 focus:ring-[#C8A288] text-[#4A3B32] font-medium appearance-none"
                                >
                                    <option>Comprehensive Summary</option>
                                    <option>Bullet Point Key Facts</option>
                                    <option>Glossary of Terms</option>
                                    <option>Exam Cheat Sheet</option>
                                </select>
                                <ChevronDown className="absolute right-4 top-1/2 -translate-y-1/2 h-4 w-4 text-[#8a6a5c] pointer-events-none" />
                            </div>
                        </div>

                        <button
                            onClick={handleGenerateNotes}
                            disabled={notesLoading}
                            className="w-full py-4 bg-[#C8A288] text-white rounded-xl hover:bg-[#B08B72] font-bold shadow-lg shadow-[#C8A288]/20 disabled:opacity-50 transition-colors mt-4 flex items-center justify-center gap-2"
                        >
                            {notesLoading ? <Loader2 className="h-5 w-5 animate-spin" /> : <BookOpen className="h-5 w-5" />}
                            {notesLoading ? 'Generating Notes...' : 'Generate Notes'}
                        </button>
                    </div>
                </div>
            ) : (
                <div className="pb-12 animate-in fade-in slide-in-from-bottom-8 duration-500 h-full flex flex-col">
                    <div className="flex justify-between items-center mb-6">
                        <div>
                            <h3 className="text-2xl font-bold text-[#4A3B32]">{notesType}</h3>
                            <p className="text-sm text-[#8a6a5c] font-medium">{notesTopic || notesTopicSelection || 'General'}</p>
                        </div>
                        <div className="flex gap-2">
                            <button
                                onClick={copyToClipboard}
                                className="p-2 border border-[#E6D5CC] rounded-lg hover:bg-[#FDF6F0] text-[#8a6a5c] transition-colors"
                                title="Copy to Clipboard"
                            >
                                <Copy className="h-5 w-5" />
                            </button>
                            <button
                                onClick={() => { setNotesContent(''); setNotesTopic(''); setNotesTopicSelection(''); }}
                                className="px-4 py-2 bg-[#C8A288] text-white rounded-lg hover:bg-[#B08B72] font-medium transition-colors"
                            >
                                New Notes
                            </button>
                        </div>
                    </div>

                    <div className="bg-white p-8 rounded-3xl border border-[#E6D5CC] shadow-sm flex-1 overflow-y-auto prose prose-lg max-w-none text-[#4A3B32]">
                        {notesLoading && !notesContent ? (
                            <div className="flex items-center justify-center h-40 gap-3 text-[#8a6a5c]">
                                <Loader2 className="h-6 w-6 animate-spin" />
                                <span className="font-medium">Writing your notes...</span>
                            </div>
                        ) : (
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                {notesContent}
                            </ReactMarkdown>
                        )}
                        {notesLoading && notesContent && (
                            <div className="mt-4 flex items-center gap-2 text-[#C8A288] animate-pulse">
                                <span className="h-2 w-2 bg-[#C8A288] rounded-full" />
                                <span className="text-sm font-bold uppercase tracking-wider">Continuing...</span>
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
};

export default NotesView;
