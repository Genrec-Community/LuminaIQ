import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import { X, ZoomIn, ZoomOut, Maximize2, Minimize2, ChevronLeft, ChevronRight, AlertCircle, FileText } from 'lucide-react';
import { createLogger } from '../../utils/logger';
import 'react-pdf/dist/esm/Page/AnnotationLayer.css';
import 'react-pdf/dist/esm/Page/TextLayer.css';

const logger = createLogger('PDFViewer');

// Initialize the worker to use the same version as the API to avoid version mismatch errors
pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

const PDFViewer = ({ url, highlightText, onClose, title = "PDF Viewer", initialPage = 1 }) => {
    const [numPages, setNumPages] = useState(null);
    const [pageNumber, setPageNumber] = useState(initialPage);
    const [scale, setScale] = useState(1.0);
    const [isFullscreen, setIsFullscreen] = useState(false);
    const [error, setError] = useState(null);
    const containerRef = useRef(null);

    const onDocumentLoadSuccess = (pdf) => {
        setNumPages(pdf.numPages);
        setError(null);
        
        // Custom search function to find the page of the text
        if (highlightText) {
            findMatchPage(pdf).then(pageObj => {
                if (pageObj && pageObj.pageIndex !== undefined && containerRef.current) {
                    // Small delay to ensure pages are rendered
                    setTimeout(() => {
                        const pageNode = document.getElementById(`pdf-page-${pageObj.pageIndex + 1}`);
                        if (pageNode) {
                            pageNode.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        }
                    }, 500);
                }
            });
        }
    };

    const findMatchPage = async (pdf) => {
        const cleanHighlight = highlightText.replace(/\.\.\.$/, '').trim();
        if (cleanHighlight.length < 5) return null;
        const anchor = cleanHighlight.length > 20 ? cleanHighlight.substring(0, 20).toLowerCase() : cleanHighlight.toLowerCase();

        for (let i = 1; i <= pdf.numPages; i++) {
            try {
                const page = await pdf.getPage(i);
                const textContent = await page.getTextContent();
                const pageText = textContent.items.map(item => item.str).join(' ').toLowerCase();
                
                if (pageText.includes(anchor)) {
                    return { pageIndex: i - 1 };
                }
            } catch (e) {
                logger.warn('Error extracting text for search on page', { page: i, error: e });
            }
        }
        return null;
    };

    const onDocumentLoadError = (err) => {
        logger.error('Failed to load PDF', err);
        setError("Failed to load the document. It might not be available or may be corrupted.");
    };

    const zoomIn = () => setScale(s => Math.min(s + 0.2, 3.0));
    const zoomOut = () => setScale(s => Math.max(s - 0.2, 0.5));

    const toggleFullscreen = () => {
        if (!document.fullscreenElement) {
            containerRef.current.requestFullscreen().catch(err => {
                logger.error('Failed to enable fullscreen', { error: err.message });
            });
        } else {
            document.exitFullscreen();
        }
    };

    useEffect(() => {
        const handleFullscreenChange = () => {
            setIsFullscreen(!!document.fullscreenElement);
        };
        document.addEventListener('fullscreenchange', handleFullscreenChange);
        return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
    }, []);

    // Simple custom text renderer to highlight matching text chunks.
    const textRenderer = useCallback((textItem) => {
        if (!highlightText || highlightText.trim() === '') return textItem.str;
        
        const str = textItem.str;
        const cleanHighlight = highlightText.replace(/\.\.\.$/, '').trim();
        
        if (cleanHighlight.length < 5) return str;

        const anchor = cleanHighlight.length > 20 ? cleanHighlight.substring(0, 20) : cleanHighlight;
        
        if (str.toLowerCase().includes(anchor.toLowerCase()) && anchor.length > 5) {
            return `<mark style="background-color: #ffeb3b80; border-radius: 2px;">${str}</mark>`;
        }
        
        if (str.length > 8 && cleanHighlight.toLowerCase().includes(str.trim().toLowerCase())) {
            return `<mark style="background-color: #ffeb3b80; border-radius: 2px;">${str}</mark>`;
        }
        
        return str;
    }, [highlightText]);

    return (
        <div className={`transition-all z-[100] ${isFullscreen ? 'fixed inset-0 bg-[#FDF6F0]' : 'fixed inset-0 bg-[#4A3B32]/40 backdrop-blur-sm flex items-center justify-center p-4 md:p-12'}`}>
            <div 
                ref={containerRef}
                className={`flex flex-col bg-[#FDF6F0] overflow-hidden shadow-2xl w-full ${isFullscreen ? 'h-full' : 'max-h-[85vh] h-[800px] max-w-5xl rounded-3xl border border-[#E6D5CC]'}`}
            >
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 bg-white border-b border-[#E6D5CC] shrink-0">
                <div className="flex items-center gap-2 overflow-hidden flex-1">
                    <FileText className="h-4 w-4 text-[#C8A288] shrink-0" />
                    <h3 className="text-sm font-bold text-[#4A3B32] truncate" title={title}>
                        {title}
                    </h3>
                </div>
                
                <div className="flex items-center gap-1.5 ml-4 shrink-0">
                    <button onClick={zoomOut} className="p-1.5 text-[#8a6a5c] hover:bg-[#E6D5CC]/50 rounded-lg transition-colors" title="Zoom Out">
                        <ZoomOut className="h-4 w-4" />
                    </button>
                    <span className="text-xs font-semibold text-[#4A3B32] min-w-[3ch] text-center">
                        {Math.round(scale * 100)}%
                    </span>
                    <button onClick={zoomIn} className="p-1.5 text-[#8a6a5c] hover:bg-[#E6D5CC]/50 rounded-lg transition-colors" title="Zoom In">
                        <ZoomIn className="h-4 w-4" />
                    </button>
                    
                    <div className="w-px h-4 bg-[#E6D5CC] mx-1" />
                    
                    <button onClick={toggleFullscreen} className="p-1.5 text-[#8a6a5c] hover:bg-[#E6D5CC]/50 rounded-lg transition-colors" title={isFullscreen ? "Exit Fullscreen" : "Fullscreen"}>
                        {isFullscreen ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
                    </button>
                    
                    <button onClick={onClose} className="p-1.5 text-[#8a6a5c] hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors ml-1" title="Close Viewer">
                        <X className="h-4 w-4" />
                    </button>
                </div>
            </div>

            {/* Document Area */}
            <div className="flex-1 overflow-auto custom-scrollbar p-4 text-center bg-[#FDF6F0]">
                {error ? (
                    <div className="flex flex-col items-center justify-center p-8 text-center max-w-sm mx-auto h-full">
                        <AlertCircle className="h-12 w-12 text-red-400 mb-3" />
                        <h4 className="text-sm font-bold text-[#4A3B32] mb-1">Failed to Load</h4>
                        <p className="text-xs text-[#8a6a5c]">{error}</p>
                    </div>
                ) : (
                    <Document
                        file={url}
                        onLoadSuccess={onDocumentLoadSuccess}
                        onLoadError={onDocumentLoadError}
                        loading={
                            <div className="flex items-center justify-center h-full min-h-[50vh]">
                                <div className="flex items-center gap-3 bg-white px-5 py-3 rounded-xl shadow-sm border border-[#E6D5CC] text-[#4A3B32]">
                                    <div className="h-5 w-5 border-2 border-[#C8A288] rounded-full border-t-transparent animate-spin"></div>
                                    <span className="text-sm font-semibold">Loading document...</span>
                                </div>
                            </div>
                        }
                        className="flex flex-col items-center mx-auto gap-4"
                    >
                        {numPages && Array.from(new Array(numPages), (el, index) => (
                            <div id={`pdf-page-${index + 1}`} key={`page_${index + 1}`} className="shadow-lg bg-white relative rounded overflow-hidden">
                                <Page 
                                    pageNumber={index + 1} 
                                    scale={scale}
                                    renderAnnotationLayer={false}
                                    renderTextLayer={true}
                                    customTextRenderer={textRenderer}
                                    className="min-h-full"
                                />
                                <div className="absolute bottom-2 right-2 bg-black/50 text-white text-[10px] px-2 py-0.5 rounded-full z-10 font-medium">
                                    {index + 1}
                                </div>
                            </div>
                        ))}
                    </Document>
                )}
            </div>
        </div>
        </div>
    );
};

export default PDFViewer;
