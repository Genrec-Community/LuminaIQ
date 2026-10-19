import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import {
    X, ZoomIn, ZoomOut, ChevronLeft, ChevronRight, AlertCircle, FileText, Loader2, Quote, Crosshair, ChevronDown, ChevronUp,
} from 'lucide-react';
import 'react-pdf/dist/esm/Page/AnnotationLayer.css';
import 'react-pdf/dist/esm/Page/TextLayer.css';
// Bundled worker (same pdf.js version as react-pdf): works offline and in the Android app
import workerSrc from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
import { getDocumentUrl, getDocumentText } from '../../api';

pdfjs.GlobalWorkerOptions.workerSrc = workerSrc;

// ------------------------------------------------------------- matching

const norm = (s) => (s || '')
    .toLowerCase()
    .replace(/-\s+/g, '')            // words hyphenated across lines
    .replace(/[^a-z0-9]+/g, ' ')
    .trim();

const SHINGLE = 5;

/** Character range [start, end) of `haystackNorm` that best matches the passage. */
export function findPassage(haystackNorm, passage) {
    const words = norm(passage).replace(/\.\.\.$/, '').split(' ').filter(Boolean);
    if (words.length < 3) return null;
    const size = Math.min(SHINGLE, words.length);
    const hits = [];
    for (let i = 0; i + size <= words.length; i += 2) {
        const sh = words.slice(i, i + size).join(' ');
        let at = haystackNorm.indexOf(sh);
        while (at !== -1 && hits.length < 400) {
            hits.push({ at, end: at + sh.length });
            at = haystackNorm.indexOf(sh, at + 1);
        }
    }
    if (!hits.length) return null;
    // Densest cluster no longer than the passage itself (+30%)
    const span = Math.max(words.join(' ').length * 1.3, 40);
    hits.sort((a, b) => a.at - b.at);
    let best = null;
    for (let i = 0, j = 0; i < hits.length; i++) {
        while (hits[j].at < hits[i].at - span) j++;
        const count = i - j + 1;
        if (!best || count > best.count) best = { count, start: hits[j].at, end: Math.max(...hits.slice(j, i + 1).map((h) => h.end)) };
    }
    return { start: best.start, end: best.end, score: best.count };
}

/** Normalised page text with each text item's range, so matches map back to items. */
function indexItems(items) {
    let pos = 0;
    const ranges = [];
    const parts = [];
    for (const it of items) {
        const n = norm(it.str);
        ranges.push([pos, pos + n.length]);
        parts.push(n);
        pos += n.length + 1;
    }
    return { text: parts.join(' '), ranges };
}

// ------------------------------------------------------------- PDF view

const LazyPage = ({ pageNumber, width, estHeight, active, target, highlight, onVisible, registerRef }) => {
    const ref = useRef(null);
    const [near, setNear] = useState(pageNumber <= 2 || target);

    useEffect(() => {
        const el = ref.current;
        registerRef(pageNumber, el);
        const io = new IntersectionObserver(([e]) => {
            if (e.isIntersecting) setNear(true);
            if (e.intersectionRatio > 0.4) onVisible(pageNumber);
        }, { rootMargin: '1200px 0px', threshold: [0, 0.4] });
        io.observe(el);
        return () => io.disconnect();
    }, [pageNumber, onVisible, registerRef]);

    useEffect(() => { if (target) setNear(true); }, [target]);

    const renderer = useCallback((item) => {
        if (!highlight || !highlight.items.has(item.itemIndex)) return item.str;
        return `<mark class="lumina-cite">${item.str}</mark>`;
    }, [highlight]);

    return (
        <div ref={ref} data-page={pageNumber}
            className={`relative mx-auto bg-white shadow-md rounded ${active ? 'ring-2 ring-[#C8A288]/40' : ''}`}
            style={{ width, minHeight: near ? undefined : estHeight }}>
            {near && (
                <Page pageNumber={pageNumber} width={width} renderAnnotationLayer={false} renderTextLayer
                    customTextRenderer={highlight ? renderer : undefined}
                    loading={<div style={{ height: estHeight }} className="flex items-center justify-center text-[#8a6a5c] text-sm">Page {pageNumber}…</div>} />
            )}
            <span className="absolute -left-1 top-2 -translate-x-full pr-2 text-[10px] tabular-nums text-[#8a6a5c] hidden md:block">{pageNumber}</span>
        </div>
    );
};

const PdfView = ({ url, passage, onLocated, jumpSignal }) => {
    const scrollRef = useRef(null);
    const pageEls = useRef({});
    const [pdf, setPdf] = useState(null);
    const [numPages, setNumPages] = useState(0);
    const [aspect, setAspect] = useState(1.414);
    const [containerW, setContainerW] = useState(800);
    const [zoom, setZoom] = useState(1);
    const [current, setCurrent] = useState(1);
    const [target, setTarget] = useState(null); // { page, items:Set }
    const [searching, setSearching] = useState(false);
    const [error, setError] = useState('');

    useEffect(() => {
        const el = scrollRef.current;
        if (!el) return undefined;
        const ro = new ResizeObserver(() => setContainerW(el.clientWidth));
        ro.observe(el);
        setContainerW(el.clientWidth);
        return () => ro.disconnect();
    }, []);

    const width = Math.round(Math.min(containerW - 32, 900) * zoom);
    const registerRef = useCallback((n, el) => { pageEls.current[n] = el; }, []);
    const onVisible = useCallback((n) => setCurrent(n), []);

    const scrollToPage = useCallback((n, smooth = true) => {
        pageEls.current[n]?.scrollIntoView({ behavior: smooth ? 'smooth' : 'auto', block: 'start' });
    }, []);

    const onLoad = async (doc) => {
        setPdf(doc);
        setNumPages(doc.numPages);
        try {
            const first = await doc.getPage(1);
            const vp = first.getViewport({ scale: 1 });
            setAspect(vp.height / vp.width);
        } catch { /* keep default */ }
    };

    // Find the cited passage: score every page, highlight the best match
    useEffect(() => {
        if (!pdf || !passage) return undefined;
        let cancelled = false;
        (async () => {
            setSearching(true);
            let best = null;
            for (let i = 1; i <= pdf.numPages && !cancelled; i++) {
                try {
                    const page = await pdf.getPage(i);
                    const content = await page.getTextContent();
                    const { text, ranges } = indexItems(content.items);
                    const m = findPassage(text, passage);
                    if (m && (!best || m.score > best.score)) {
                        const items = new Set();
                        ranges.forEach(([a, b], idx) => { if (b > m.start && a < m.end && b > a) items.add(idx); });
                        best = { page: i, score: m.score, items };
                        if (m.score >= 6) break; // clearly the right place
                    }
                } catch { /* unreadable page */ }
            }
            if (cancelled) return;
            setSearching(false);
            if (best) {
                setTarget(best);
                onLocated?.(best.page);
                setTimeout(() => scrollToPage(best.page, false), 50);
            } else {
                onLocated?.(null);
            }
        })();
        return () => { cancelled = true; };
    }, [pdf, passage, onLocated, scrollToPage]);

    // After the target page renders, bring the highlighted lines into view
    useEffect(() => {
        if (!target) return undefined;
        let tries = 0;
        const id = setInterval(() => {
            const mark = pageEls.current[target.page]?.querySelector('mark.lumina-cite');
            if (mark) {
                mark.scrollIntoView({ behavior: 'smooth', block: 'center' });
                clearInterval(id);
            } else if (++tries > 40) clearInterval(id);
        }, 150);
        return () => clearInterval(id);
    }, [target, jumpSignal, width]);

    return (
        <div className="flex-1 min-h-0 flex flex-col">
            <div className="flex items-center justify-between gap-2 px-3 py-2 bg-white border-b border-[#E6D5CC] text-[#4A3B32]">
                <div className="flex items-center gap-1">
                    <button onClick={() => scrollToPage(Math.max(1, current - 1))} disabled={current <= 1}
                        className="p-1.5 rounded-lg hover:bg-[#FDF6F0] disabled:opacity-40" aria-label="Previous page"><ChevronLeft className="h-4 w-4" /></button>
                    <span className="text-xs font-semibold tabular-nums">{current} / {numPages || '–'}</span>
                    <button onClick={() => scrollToPage(Math.min(numPages, current + 1))} disabled={current >= numPages}
                        className="p-1.5 rounded-lg hover:bg-[#FDF6F0] disabled:opacity-40" aria-label="Next page"><ChevronRight className="h-4 w-4" /></button>
                </div>
                {searching && <span className="flex items-center gap-1.5 text-xs text-[#8a6a5c]"><Loader2 className="h-3.5 w-3.5 animate-spin" /> Finding the passage…</span>}
                <div className="flex items-center gap-1">
                    <button onClick={() => setZoom((z) => Math.max(0.5, +(z - 0.15).toFixed(2)))} className="p-1.5 rounded-lg hover:bg-[#FDF6F0]" aria-label="Zoom out"><ZoomOut className="h-4 w-4" /></button>
                    <span className="text-xs font-semibold w-10 text-center tabular-nums">{Math.round(zoom * 100)}%</span>
                    <button onClick={() => setZoom((z) => Math.min(3, +(z + 0.15).toFixed(2)))} className="p-1.5 rounded-lg hover:bg-[#FDF6F0]" aria-label="Zoom in"><ZoomIn className="h-4 w-4" /></button>
                </div>
            </div>
            <div ref={scrollRef} className="flex-1 overflow-auto bg-[#EFE6DF] px-4 py-4">
                {error ? (
                    <div className="flex flex-col items-center justify-center p-8 text-center max-w-sm mx-auto">
                        <AlertCircle className="h-10 w-10 text-red-400 mb-2" />
                        <p className="text-sm text-[#4A3B32]">{error}</p>
                    </div>
                ) : (
                    <Document file={url} onLoadSuccess={onLoad}
                        onLoadError={() => setError("This PDF couldn't be opened. It may have been removed.")}
                        loading={<div className="flex items-center justify-center gap-2 py-24 text-[#8a6a5c]"><Loader2 className="h-5 w-5 animate-spin" /> Opening the book…</div>}
                        className="flex flex-col gap-4">
                        {Array.from({ length: numPages }, (_, i) => i + 1).map((n) => (
                            <LazyPage key={n} pageNumber={n} width={width} estHeight={Math.round(width * aspect)}
                                active={target?.page === n} target={target?.page === n}
                                highlight={target?.page === n ? target : null}
                                onVisible={onVisible} registerRef={registerRef} />
                        ))}
                    </Document>
                )}
            </div>
        </div>
    );
};

// ------------------------------------------------------------ text view

const TextView = ({ text, passage, onLocated, jumpSignal }) => {
    const markRef = useRef(null);

    // Map the normalised text back to the original to highlight the exact span
    const parts = useMemo(() => {
        if (!passage) return { before: text, hit: '', after: '' };
        const map = [];
        let normText = '';
        let lastSpace = true;
        for (let i = 0; i < text.length; i++) {
            const ch = text[i].toLowerCase();
            if (/[a-z0-9]/.test(ch)) { normText += ch; map.push(i); lastSpace = false; }
            else if (!lastSpace) { normText += ' '; map.push(i); lastSpace = true; }
        }
        const m = findPassage(normText, passage);
        if (!m) return { before: text, hit: '', after: '' };
        const a = map[m.start] ?? 0;
        const b = (map[Math.min(m.end, map.length) - 1] ?? text.length - 1) + 1;
        return { before: text.slice(0, a), hit: text.slice(a, b), after: text.slice(b) };
    }, [text, passage]);

    useEffect(() => { onLocated?.(parts.hit ? 'text' : null); }, [parts.hit, onLocated]);
    useEffect(() => {
        const t = setTimeout(() => markRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 80);
        return () => clearTimeout(t);
    }, [parts, jumpSignal]);

    return (
        <div className="flex-1 overflow-auto bg-[#EFE6DF] p-4">
            <article className="mx-auto max-w-3xl rounded bg-white p-6 md:p-10 shadow-md text-[15px] leading-7 text-[#2f2620] whitespace-pre-wrap break-words">
                {parts.before}
                {parts.hit && <mark ref={markRef} className="lumina-cite">{parts.hit}</mark>}
                {parts.after}
            </article>
        </div>
    );
};

// ------------------------------------------------------------- reader

/**
 * In-app reader for a project document. Shows the whole book (the original PDF
 * when we have it, otherwise its full text) and, when opened from a citation,
 * jumps to and highlights the cited passage, with the passage itself shown as
 * proof above the book.
 */
const DocumentReader = ({ projectId, documentId, title, passage, onClose }) => {
    const [source, setSource] = useState(null); // {kind, url} | {kind:'text', text}
    const [error, setError] = useState('');
    const [located, setLocated] = useState(undefined); // page number | 'text' | null
    const [showProof, setShowProof] = useState(true);
    const [jump, setJump] = useState(0);

    useEffect(() => {
        let alive = true;
        (async () => {
            try {
                const r = await getDocumentUrl(projectId, documentId);
                if (r.kind === 'pdf' && r.url) { if (alive) setSource({ kind: 'pdf', url: r.url }); return; }
                const t = await getDocumentText(projectId, documentId);
                if (alive) setSource({ kind: 'text', text: t.text });
            } catch (e) {
                if (alive) setError(e?.response?.data?.detail || "This document couldn't be opened.");
            }
        })();
        return () => { alive = false; };
    }, [projectId, documentId]);

    useEffect(() => {
        const onKey = (e) => { if (e.key === 'Escape') onClose(); };
        window.addEventListener('keydown', onKey);
        return () => window.removeEventListener('keydown', onKey);
    }, [onClose]);

    const onLocated = useCallback((v) => setLocated(v), []);
    const cleanPassage = passage ? passage.replace(/\.\.\.$/, '').trim() : '';

    return (
        <div className="fixed inset-0 z-[100] bg-[#4A3B32]/40 backdrop-blur-sm flex items-stretch md:items-center justify-center md:p-6"
            role="dialog" aria-modal="true" aria-label={title}>
            <div className="flex flex-col bg-[#FDF6F0] w-full md:max-w-5xl h-full md:h-[92vh] md:rounded-3xl md:border border-[#E6D5CC] overflow-hidden shadow-2xl">
                <div className="flex items-center gap-2 px-4 py-3 bg-white border-b border-[#E6D5CC]">
                    <FileText className="h-4 w-4 text-[#C8A288] shrink-0" />
                    <h3 className="flex-1 text-sm font-bold text-[#4A3B32] truncate" title={title}>{title}</h3>
                    <button onClick={onClose} className="p-1.5 rounded-lg text-[#8a6a5c] hover:text-red-500 hover:bg-red-50" aria-label="Close reader"><X className="h-5 w-5" /></button>
                </div>

                {cleanPassage && (
                    <div className="px-4 py-3 bg-amber-50 border-b border-amber-200 text-[#4A3B32]">
                        <div className="flex items-center gap-2">
                            <Quote className="h-4 w-4 text-amber-600 shrink-0" />
                            <span className="text-xs font-bold uppercase tracking-wide text-amber-800">Cited passage</span>
                            <span className="text-xs text-amber-800">
                                {located === undefined ? '· locating…' : located === null ? "· couldn't pinpoint it, showing the whole book"
                                    : typeof located === 'number' ? `· page ${located}` : '· highlighted below'}
                            </span>
                            <div className="flex-1" />
                            {located && (
                                <button onClick={() => setJump((j) => j + 1)} className="flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-semibold text-amber-900 hover:bg-amber-100">
                                    <Crosshair className="h-3.5 w-3.5" /> Jump to it
                                </button>
                            )}
                            <button onClick={() => setShowProof((s) => !s)} className="p-1 rounded-lg hover:bg-amber-100" aria-label={showProof ? 'Hide passage' : 'Show passage'}>
                                {showProof ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                            </button>
                        </div>
                        {showProof && <p className="mt-1.5 text-sm leading-relaxed max-h-28 overflow-auto italic">“{cleanPassage}”</p>}
                    </div>
                )}

                {error ? (
                    <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
                        <AlertCircle className="h-10 w-10 text-red-400 mb-2" />
                        <p className="text-sm text-[#4A3B32]">{error}</p>
                    </div>
                ) : !source ? (
                    <div className="flex-1 flex items-center justify-center gap-2 text-[#8a6a5c]"><Loader2 className="h-5 w-5 animate-spin" /> Opening…</div>
                ) : source.kind === 'pdf' ? (
                    <PdfView url={source.url} passage={cleanPassage} onLocated={onLocated} jumpSignal={jump} />
                ) : (
                    <TextView text={source.text} passage={cleanPassage} onLocated={onLocated} jumpSignal={jump} />
                )}
            </div>
        </div>
    );
};

export default DocumentReader;
