import React, { useCallback, useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import {
    MoreHorizontal, Plus, Zap, Moon, Target, MessageSquare, FlaskConical, Network, HelpCircle, CheckSquare,
    FileText, Layers, Brain, Flame, Trash2, AlertTriangle, FileCheck2, BookOpen,
} from 'lucide-react';
import { getDocuments, uploadDocument, subscribeDocumentProgress, deleteDocument, deleteProject, retryDocument } from '../../api';
import { useToast } from '../../context/ToastContext';
import { useSettings } from '../../context/SettingsContext';
import { aiName } from '../../utils/persona';
import { clearProjectsCache } from '../../utils/projectCache';
import { LAST_PROJECT_KEY } from '../../utils/dailyProgress';
import ProcessingProgress from '../../components/ProcessingProgress';
import { useBooks, coverFor, emojiFor } from '../data';
import { Screen, Sheet, IconButton } from '../ui';
import { tap, notify } from '../device';

const WORKING = ['pending', 'processing', 'embedding', 'queued'];
const isReady = (d) => d.upload_status === 'completed' || d.upload_status === 'ready';
const isFailed = (d) => d.upload_status === 'failed' || d.upload_status === 'error';

const tools = (ai) => [
    { id: 'power', icon: Zap, label: 'Power Hour', sub: 'Fastest way through', color: '#f59e0b' },
    { id: 'cram', icon: Moon, label: 'Exam Tonight', sub: 'A plan for your time', color: '#7c6fd6' },
    { id: 'chat', icon: MessageSquare, label: `Ask ${ai}`, sub: 'Answers with pages', color: '#3b8fd6' },
    { id: 'quiz', icon: CheckSquare, label: 'Quiz', sub: 'Test yourself', color: '#2f9e7a' },
    { id: 'flashcards', icon: Layers, label: 'Flashcards', sub: 'Flip & remember', color: '#e46a91' },
    { id: 'notes', icon: FileText, label: 'Notes', sub: 'Summaries in a tap', color: '#C8A288' },
    { id: 'mindmap', icon: Brain, label: 'Mind map', sub: 'See the big picture', color: '#e07a5f' },
    { id: 'path', icon: Target, label: 'Learning path', sub: 'Step by step', color: '#14b8a6' },
    { id: 'qa', icon: HelpCircle, label: 'Q&A practice', sub: 'Written answers, graded', color: '#a16207' },
    { id: 'lab', icon: FlaskConical, label: 'Visual Lab', sub: 'Interactive demos', color: '#0ea5e9' },
    { id: 'knowledge', icon: Network, label: 'Knowledge graph', sub: 'How ideas connect', color: '#64748b' },
];

/** A book's home: its files (with live progress) and every study tool. */
const Book = () => {
    const { bookId } = useParams();
    const navigate = useNavigate();
    const location = useLocation();
    const toast = useToast();
    const { settings } = useSettings();
    const { books } = useBooks();
    const book = books.find((b) => b.id === bookId);
    const [docs, setDocs] = useState(null);
    const [live, setLive] = useState({}); // docId -> { stage, progress, message }
    const [uploads, setUploads] = useState([]); // [{ key, name, pct }]
    const [menu, setMenu] = useState(false);
    const [readyName, setReadyName] = useState(null); // a file just finished: celebrate
    const [confirm, setConfirm] = useState(null); // { type: 'doc'|'book', doc }
    const streams = useRef({});
    const fileInput = useRef(null);

    useEffect(() => { try { localStorage.setItem(LAST_PROJECT_KEY, bookId); } catch { /* ignore */ } }, [bookId]);

    const [retrying, setRetrying] = useState(null);
    const retry = async (d) => {
        tap();
        setRetrying(d.id);
        try {
            await retryDocument(bookId, d.id);
            setDocs((list) => (list || []).map((x) => (x.id === d.id ? { ...x, upload_status: 'pending' } : x)));
            load();
        } catch (e) {
            const detail = e?.response?.data?.detail;
            toast.error(typeof detail === 'string' ? detail : "Couldn't retry. Try again in a moment.");
        } finally {
            setRetrying(null);
        }
    };
    const load = useCallback(async () => {
        try {
            const data = await getDocuments(bookId);
            setDocs(data.documents || []);
            return data.documents || [];
        } catch {
            setDocs((d) => d || []);
            return [];
        }
    }, [bookId]);

    useEffect(() => { load(); }, [load]);

    // Live progress for files being read; refresh the list while any are working
    useEffect(() => {
        if (!docs) return undefined;
        docs.filter((d) => WORKING.includes(d.upload_status) && !streams.current[d.id]).forEach((d) => {
            streams.current[d.id] = subscribeDocumentProgress(d.id, (ev) => {
                setLive((l) => ({ ...l, [d.id]: ev }));
                if (ev.stage === 'completed' || ev.stage === 'failed') {
                    delete streams.current[d.id];
                    if (ev.stage === 'completed') { notify('success'); setReadyName(d.filename); }
                    load();
                }
            }, () => { delete streams.current[d.id]; });
        });
        if (!docs.some((d) => WORKING.includes(d.upload_status))) return undefined;
        const t = setInterval(load, 8000);
        return () => clearInterval(t);
    }, [docs, load]);

    useEffect(() => () => Object.values(streams.current).forEach((close) => close?.()), []);

    const upload = useCallback(async (files) => {
        const entries = Array.from(files).map((f, i) => ({ key: `${Date.now()}-${i}`, name: f.name, size: f.size, pct: 0, file: f }));
        setUploads((u) => [...u, ...entries.map(({ file, ...e }) => e)]);
        await Promise.all(entries.map(async ({ key, file }) => {
            try {
                await uploadDocument(bookId, file, (pct) => setUploads((u) => u.map((x) => (x.key === key ? { ...x, pct: Math.max(x.pct, pct) } : x))));
                clearProjectsCache();
            } catch (e) {
                const d = e?.response?.data?.detail;
                toast.error(typeof d === 'string' ? d : (d?.message || `"${file.name}" didn't upload. Try again.`));
            } finally {
                setUploads((u) => u.filter((x) => x.key !== key));
            }
        }));
        load();
    }, [bookId, load, toast]);

    // Files handed over by the add sheet
    useEffect(() => {
        const files = location.state?.files;
        if (files?.length) {
            navigate(location.pathname, { replace: true, state: null });
            upload(files);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const openTool = (id) => { tap(); navigate(`/project/${bookId}?tool=${id}`); };

    const doDelete = async () => {
        const c = confirm;
        setConfirm(null);
        notify('warning');
        try {
            if (c.type === 'book') {
                await deleteProject(bookId);
                clearProjectsCache();
                navigate('/app/library', { replace: true });
            } else {
                await deleteDocument(bookId, c.doc.id);
                load();
            }
        } catch {
            toast.error('Could not delete. Try again.');
        }
    };

    const [a, b] = coverFor(bookId);
    const ready = (docs || []).filter(isReady).length;
    const working = (docs || []).some((d) => WORKING.includes(d.upload_status)) || uploads.length > 0;
    const name = book?.name || 'Book';

    return (
        <Screen className="pb-12">
            {/* Cover header */}
            <div className="relative overflow-hidden pb-6" style={{ background: `linear-gradient(160deg, ${a} 0%, ${b} 100%)` }}>
                <span className="pointer-events-none absolute -right-6 top-6 text-[150px] opacity-25">{emojiFor(name)}</span>
                <div className="m-safe-top relative">
                    <div className="flex h-14 items-center justify-between px-3 text-white">
                        <button onClick={() => { tap(); navigate(-1); }} aria-label="Back" className="m-pressable flex h-10 w-10 items-center justify-center rounded-full bg-black/20 backdrop-blur">
                            <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round"><path d="M15 18l-6-6 6-6" /></svg>
                        </button>
                        <button onClick={() => { tap(); setMenu(true); }} aria-label="More" className="m-pressable flex h-10 w-10 items-center justify-center rounded-full bg-black/20 backdrop-blur">
                            <MoreHorizontal className="h-6 w-6" />
                        </button>
                    </div>
                    <div className="px-5 pt-2 text-white">
                        <h1 className="text-[28px] font-extrabold leading-tight drop-shadow-sm">{name}</h1>
                        <p className="mt-1 text-[14px] font-medium text-white/80">
                            {docs == null ? 'Loading…' : `${docs.length} ${docs.length === 1 ? 'file' : 'files'}${working ? ' · reading now' : ready ? ' · ready to study' : ''}`}
                        </p>
                        <div className="mt-4 flex gap-2">
                            <button onClick={() => { tap('medium'); navigate('/app/feed', { state: { bookId } }); }} disabled={!ready}
                                className="m-pressable flex h-11 items-center gap-2 rounded-full m-white px-5 text-[14px] font-bold text-[#2a1d15] disabled:opacity-50">
                                <Flame className="h-4 w-4" fill="currentColor" /> Learn feed
                            </button>
                            <button onClick={() => { tap(); fileInput.current?.click(); }}
                                className="m-pressable flex h-11 items-center gap-2 rounded-full bg-black/25 px-5 text-[14px] font-bold text-white backdrop-blur">
                                <Plus className="h-4 w-4" /> Add file
                            </button>
                        </div>
                    </div>
                </div>
            </div>
            <input ref={fileInput} type="file" multiple accept=".pdf,.docx,.txt,application/pdf,text/plain" className="hidden"
                onChange={(e) => { if (e.target.files?.length) upload(e.target.files); e.target.value = ''; }} />

            <div className="-mt-3 space-y-6 rounded-t-[24px] px-4 pt-5" style={{ background: 'var(--m-bg)' }}>
                {/* Files */}
                <section className="space-y-2">
                    {uploads.map((u) => (
                        <div key={u.key} className="m-card p-3.5">
                            <p className="truncate text-[14px] font-bold">{u.name}</p>
                            <ProcessingProgress stage="uploading" stagePct={u.pct} message={`${((u.size * u.pct) / 100 / 1048576).toFixed(1)} of ${(u.size / 1048576).toFixed(1)} MB`} />
                        </div>
                    ))}
                    {docs == null && [0, 1].map((i) => <div key={i} className="m-skeleton h-16" />)}
                    {(docs || []).map((d) => {
                        const st = live[d.id];
                        const workingDoc = WORKING.includes(d.upload_status);
                        return (
                            <div key={d.id} className="m-card flex items-start gap-3 p-3.5">
                                <span className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl"
                                    style={{ background: isFailed(d) ? '#fee2e2' : 'var(--m-soft)', color: isFailed(d) ? '#dc2626' : 'var(--m-accent)' }}>
                                    {isFailed(d) ? <AlertTriangle className="h-5 w-5" /> : isReady(d) ? <FileCheck2 className="h-5 w-5" /> : <BookOpen className="h-5 w-5" />}
                                </span>
                                <div className="min-w-0 flex-1">
                                    <p className="truncate text-[14.5px] font-bold">{d.filename}</p>
                                    {workingDoc && <ProcessingProgress stage={st?.stage || d.upload_status} stagePct={st?.progress || 0} message={st?.message || ''} />}
                                    {isReady(d) && <p className="text-[12.5px]" style={{ color: 'var(--m-muted)' }}>Ready</p>}
                                    {isFailed(d) && (
                                        <div className="mt-1 flex items-center gap-2">
                                            <p className="text-[12.5px] text-red-500">Couldn't be read.</p>
                                            <button onClick={() => retry(d)} disabled={retrying === d.id}
                                                className="m-pressable rounded-full px-3 py-1 text-[12px] font-bold disabled:opacity-60"
                                                style={{ background: 'var(--m-accent)', color: 'var(--m-on-accent)' }}>
                                                {retrying === d.id ? 'Retrying…' : 'Retry'}
                                            </button>
                                        </div>
                                    )}
                                </div>
                                {!workingDoc && (
                                    <button onClick={() => { tap(); setConfirm({ type: 'doc', doc: d }); }} aria-label={`Delete ${d.filename}`} className="m-pressable p-2" style={{ color: 'var(--m-muted)' }}>
                                        <Trash2 className="h-4.5 w-4.5" />
                                    </button>
                                )}
                            </div>
                        );
                    })}
                    {docs && docs.length === 0 && !uploads.length && (
                        <button onClick={() => fileInput.current?.click()} className="m-pressable w-full rounded-[22px] border-2 border-dashed p-6 text-center" style={{ borderColor: 'var(--m-border)' }}>
                            <p className="text-[16px] font-extrabold">Add your first file</p>
                            <p className="mt-1 text-[13px]" style={{ color: 'var(--m-muted)' }}>PDF, Word or text. Ready in about a minute.</p>
                        </button>
                    )}
                </section>

                {/* Tools */}
                <section>
                    <h2 className="mb-3 px-1 text-[18px] font-extrabold">Study tools</h2>
                    <div className="grid grid-cols-2 gap-3">
                        {tools(aiName(settings)).map((t, i) => (
                            <motion.button key={t.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.03 }}
                                onClick={() => openTool(t.id)} className="m-card m-pressable flex flex-col items-start gap-2 p-4 text-left">
                                <span className="flex h-11 w-11 items-center justify-center rounded-2xl text-white" style={{ background: t.color }}><t.icon className="h-5.5 w-5.5" /></span>
                                <span>
                                    <span className="block text-[15px] font-extrabold leading-tight">{t.label}</span>
                                    <span className="block text-[12px]" style={{ color: 'var(--m-muted)' }}>{t.sub}</span>
                                </span>
                            </motion.button>
                        ))}
                    </div>
                    {!ready && docs?.length > 0 && <p className="mt-3 px-1 text-[12.5px]" style={{ color: 'var(--m-muted)' }}>Tools work best once a file says Ready.</p>}
                </section>
            </div>

            <Sheet open={menu} onClose={() => setMenu(false)} title={name}>
                <div className="space-y-2">
                    <button onClick={() => { setMenu(false); fileInput.current?.click(); }} className="m-pressable flex w-full items-center gap-3 rounded-2xl p-4 text-left text-[15px] font-bold" style={{ background: 'var(--m-soft)' }}>
                        <Plus className="h-5 w-5" /> Add a file
                    </button>
                    <button onClick={() => { setMenu(false); setConfirm({ type: 'book' }); }} className="m-pressable flex w-full items-center gap-3 rounded-2xl p-4 text-left text-[15px] font-bold text-red-500" style={{ background: 'var(--m-soft)' }}>
                        <Trash2 className="h-5 w-5" /> Delete book
                    </button>
                </div>
            </Sheet>

            <Sheet open={!!confirm} onClose={() => setConfirm(null)} title={confirm?.type === 'book' ? 'Delete this book?' : 'Delete this file?'}>
                <p className="px-2 text-[14px]" style={{ color: 'var(--m-muted)' }}>
                    {confirm?.type === 'book' ? 'The book, its files and everything made from them will be deleted.' : `"${confirm?.doc?.filename}" will be removed from this book.`}
                </p>
                <div className="mt-5 grid grid-cols-2 gap-3">
                    <button onClick={() => setConfirm(null)} className="m-pressable h-12 rounded-2xl text-[15px] font-bold" style={{ background: 'var(--m-soft)' }}>Cancel</button>
                    <button onClick={doDelete} className="m-pressable h-12 rounded-2xl bg-red-500 text-[15px] font-bold text-white">Delete</button>
                </div>
            </Sheet>
            <Sheet open={!!readyName} onClose={() => setReadyName(null)}>
                <div className="px-2 pb-2 text-center">
                    <motion.div initial={{ scale: 0.4, rotate: -20 }} animate={{ scale: 1, rotate: 0 }} transition={{ type: 'spring', damping: 9 }} className="text-[72px]">🎉</motion.div>
                    <h3 className="mt-2 text-[24px] font-extrabold">Your book is ready!</h3>
                    <p className="mt-1 text-[14.5px]" style={{ color: 'var(--m-muted)' }}>“{readyName}” is read and your first questions are waiting.</p>
                    <button onClick={() => { setReadyName(null); tap('medium'); navigate('/app/feed', { state: { bookId } }); }}
                        className="m-pressable mt-6 flex h-14 w-full items-center justify-center gap-2 rounded-2xl text-[16px] font-bold text-white"
                        style={{ background: 'linear-gradient(135deg, var(--m-accent), var(--m-accent-deep))' }}>
                        <Flame className="h-5 w-5" fill="currentColor" /> Start learning
                    </button>
                    <button onClick={() => setReadyName(null)} className="m-pressable mt-1 h-11 w-full text-[14px] font-semibold" style={{ color: 'var(--m-muted)' }}>See all study tools</button>
                </div>
            </Sheet>
        </Screen>
    );
};

export default Book;
