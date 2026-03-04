import React, { useState, useRef, useEffect } from 'react';
import { BookOpen, Copy, Download, Loader2, ChevronDown, FileDown } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { generateNotes } from '../../api';
import { useToast } from '../../context/ToastContext';
import { recordActivity } from '../../utils/studyActivity';

const NotesView = ({ projectId, availableTopics, selectedDocuments, preSelectedTopic = null, preGeneratedData = null, onConsumePreGenerated = null }) => {
    const toast = useToast();
    // Notes State
    const [notesType, setNotesType] = useState('Comprehensive Summary');
    const [notesTopic, setNotesTopic] = useState('');
    const [notesTopicSelection, setNotesTopicSelection] = useState('');
    const [notesContent, setNotesContent] = useState('');
    const [notesLoading, setNotesLoading] = useState(false);
    const [pdfLoading, setPdfLoading] = useState(false);

    // Pre-select topic when navigating from Learning Path
    useEffect(() => {
        if (preSelectedTopic && availableTopics?.includes(preSelectedTopic)) {
            setNotesTopicSelection(preSelectedTopic);
            setNotesTopic(preSelectedTopic);
        }
    }, [preSelectedTopic]);

    // Load pre-generated notes from chat @ command "Open" button
    useEffect(() => {
        if (preGeneratedData && preGeneratedData.content) {
            setNotesContent(preGeneratedData.content);
            setNotesType(preGeneratedData.noteType || 'Comprehensive Summary');
            const topic = preGeneratedData.topic || '';
            setNotesTopic(topic);
            setNotesTopicSelection(topic);
            // Signal parent to clear pre-generated data so it doesn't re-apply on re-render
            if (onConsumePreGenerated) onConsumePreGenerated();
        }
    }, [preGeneratedData]);

    // Ref for the rendered notes content
    const notesRef = useRef(null);

    const handleGenerateNotes = async () => {
        setNotesLoading(true);
        setNotesContent('');

        const effectiveTopic = notesTopicSelection === '__custom__' ? notesTopic : notesTopicSelection;

        try {
            const data = await generateNotes(
                projectId,
                notesType,
                effectiveTopic,
                selectedDocuments
            );
            setNotesContent(typeof data === 'string' ? data : (data.notes || data.content || JSON.stringify(data)));
            
            // Track notes generation activity for heatmap
            recordActivity(projectId, 'notes');
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

    const handleDownloadPDF = async () => {
        if (!notesRef.current || !notesContent) return;

        setPdfLoading(true);
        try {
            const html2pdf = (await import('html2pdf.js')).default;

            // Build a clean filename
            const topicLabel = notesTopic || notesTopicSelection || 'General';
            const safeFilename = `${notesType} - ${topicLabel}`
                .replace(/[^a-zA-Z0-9 _-]/g, '')
                .replace(/\s+/g, '_')
                .substring(0, 80);

            // Create a temporary container with PDF-optimized styles
            const container = document.createElement('div');
            container.innerHTML = `
                <style>
                    .pdf-wrapper {
                        font-family: 'Georgia', 'Times New Roman', serif;
                        color: #1a1a1a;
                        line-height: 1.7;
                        padding: 0;
                    }
                    .pdf-header {
                        text-align: center;
                        margin-bottom: 24px;
                        padding-bottom: 16px;
                        border-bottom: 2px solid #C8A288;
                    }
                    .pdf-header h1 {
                        font-size: 22px;
                        font-weight: 700;
                        color: #4A3B32;
                        margin: 0 0 4px 0;
                    }
                    .pdf-header p {
                        font-size: 13px;
                        color: #8a6a5c;
                        margin: 0;
                    }
                    .pdf-body h1 { font-size: 20px; font-weight: 700; color: #4A3B32; margin: 24px 0 10px 0; border-bottom: 1px solid #E6D5CC; padding-bottom: 6px; }
                    .pdf-body h2 { font-size: 17px; font-weight: 700; color: #4A3B32; margin: 20px 0 8px 0; }
                    .pdf-body h3 { font-size: 15px; font-weight: 600; color: #5a4a42; margin: 16px 0 6px 0; }
                    .pdf-body p { font-size: 12px; margin: 6px 0; }
                    .pdf-body ul, .pdf-body ol { font-size: 12px; padding-left: 22px; margin: 6px 0; }
                    .pdf-body li { margin-bottom: 4px; }
                    .pdf-body strong { color: #4A3B32; }
                    .pdf-body blockquote {
                        border-left: 3px solid #C8A288;
                        padding: 8px 14px;
                        margin: 10px 0;
                        background: #FDF6F0;
                        font-size: 12px;
                    }
                    .pdf-body code {
                        background: #f0ebe6;
                        padding: 1px 5px;
                        border-radius: 3px;
                        font-size: 11px;
                        font-family: 'Courier New', monospace;
                    }
                    .pdf-body pre {
                        background: #f8f4f0;
                        padding: 12px;
                        border-radius: 6px;
                        overflow-x: auto;
                        font-size: 11px;
                        border: 1px solid #E6D5CC;
                    }
                    .pdf-body pre code {
                        background: none;
                        padding: 0;
                    }
                    .pdf-body table {
                        width: 100%;
                        border-collapse: collapse;
                        margin: 12px 0;
                        font-size: 11px;
                    }
                    .pdf-body th {
                        background: #C8A288;
                        color: white;
                        font-weight: 600;
                        padding: 8px 10px;
                        text-align: left;
                        border: 1px solid #b0917a;
                    }
                    .pdf-body td {
                        padding: 7px 10px;
                        border: 1px solid #E6D5CC;
                    }
                    .pdf-body tr:nth-child(even) td {
                        background: #FDF6F0;
                    }
                    .pdf-body hr {
                        border: none;
                        border-top: 1px solid #E6D5CC;
                        margin: 16px 0;
                    }
                    .pdf-footer {
                        margin-top: 24px;
                        padding-top: 12px;
                        border-top: 1px solid #E6D5CC;
                        text-align: center;
                        font-size: 10px;
                        color: #8a6a5c;
                    }
                </style>
                <div class="pdf-wrapper">
                    <div class="pdf-header">
                        <h1>${notesType}</h1>
                        <p>${topicLabel !== 'General' ? topicLabel + ' | ' : ''}Generated by Lumina IQ | ${new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}</p>
                    </div>
                    <div class="pdf-body">
                        ${notesRef.current.innerHTML}
                    </div>
                    <div class="pdf-footer">
                        Generated with Lumina IQ &mdash; AI-Powered Study Notes
                    </div>
                </div>
            `;

            const opt = {
                margin: [12, 14, 12, 14],
                filename: `${safeFilename}.pdf`,
                image: { type: 'jpeg', quality: 0.98 },
                html2canvas: {
                    scale: 2,
                    useCORS: true,
                    logging: false,
                    letterRendering: true,
                },
                jsPDF: {
                    unit: 'mm',
                    format: 'a4',
                    orientation: 'portrait',
                },
                pagebreak: { mode: ['avoid-all', 'css', 'legacy'] },
            };

            await html2pdf().set(opt).from(container).save();
            toast.success('PDF downloaded successfully!');
        } catch (error) {
            console.error('PDF generation error:', error);
            toast.error('Failed to generate PDF. Please try again.');
        } finally {
            setPdfLoading(false);
        }
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
                                onClick={handleDownloadPDF}
                                disabled={pdfLoading || notesLoading}
                                className="flex items-center gap-2 px-4 py-2 border border-[#C8A288] text-[#C8A288] rounded-lg hover:bg-[#C8A288] hover:text-white font-medium transition-colors disabled:opacity-50"
                                title="Download as PDF"
                            >
                                {pdfLoading ? (
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                ) : (
                                    <FileDown className="h-4 w-4" />
                                )}
                                <span className="hidden sm:inline">{pdfLoading ? 'Generating...' : 'PDF'}</span>
                            </button>
                            <button
                                onClick={() => { setNotesContent(''); setNotesTopic(''); setNotesTopicSelection(''); }}
                                className="px-4 py-2 bg-[#C8A288] text-white rounded-lg hover:bg-[#B08B72] font-medium transition-colors"
                            >
                                New Notes
                            </button>
                        </div>
                    </div>

                    <div
                        ref={notesRef}
                        className="bg-white p-8 rounded-3xl border border-[#E6D5CC] shadow-sm flex-1 overflow-y-auto overflow-x-auto prose prose-lg max-w-none text-[#4A3B32]"
                    >
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
