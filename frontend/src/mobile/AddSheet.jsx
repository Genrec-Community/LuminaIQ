import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FileUp, ClipboardPaste, Store, Plus, ChevronRight, Loader2, ChevronLeft } from 'lucide-react';
import { createProject } from '../api';
import { useToast } from '../context/ToastContext';
import { clearProjectsCache } from '../utils/projectCache';
import { MAX_UPLOAD_MB } from '../utils/pricing';
import { useBooks, coverFor, emojiFor } from './data';
import { Sheet } from './ui';
import { tap } from './device';

const ACCEPT = '.pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain';
const bookName = (file) => file.name.replace(/\.(pdf|docx|txt)$/i, '').replace(/[_-]+/g, ' ').trim().slice(0, 80) || 'My book';

/**
 * The "+" button: add a file or pasted text to a new or existing book. The
 * book screen then uploads it and shows the progress.
 */
const AddSheet = ({ open, onClose }) => {
    const navigate = useNavigate();
    const toast = useToast();
    const { books } = useBooks();
    const inputRef = useRef(null);
    const [step, setStep] = useState('source'); // source | paste | where
    const [pending, setPending] = useState(null); // { files, name }
    const [title, setTitle] = useState('');
    const [text, setText] = useState('');
    const [busy, setBusy] = useState(false);

    useEffect(() => {
        if (!open) { setStep('source'); setPending(null); setTitle(''); setText(''); setBusy(false); }
    }, [open]);

    const onFiles = (list) => {
        const files = Array.from(list || []);
        if (!files.length) return;
        const big = files.find((f) => f.size > MAX_UPLOAD_MB * 1024 * 1024);
        if (big) { toast.error(`"${big.name}" is over ${MAX_UPLOAD_MB} MB.`); return; }
        setPending({ files, name: bookName(files[0]) });
        setStep('where');
    };

    const fromPaste = () => {
        const words = text.trim().split(/\s+/).filter(Boolean).length;
        if (words < 30) { toast.error('Paste at least 30 words so there is something to learn from.'); return; }
        const name = title.trim() || text.trim().split(/\s+/).slice(0, 6).join(' ');
        const file = new globalThis.File([text], `${name.replace(/[\\/:*?"<>|]+/g, ' ').slice(0, 80)}.txt`, { type: 'text/plain' });
        setPending({ files: [file], name });
        setStep('where');
    };

    const sendTo = async (bookId) => {
        tap('medium');
        setBusy(true);
        try {
            let id = bookId;
            if (!id) {
                const created = await createProject(pending.name);
                id = created?.id || created?.project?.id;
                clearProjectsCache();
            }
            onClose();
            navigate(`/app/book/${id}`, { state: { files: pending.files } });
        } catch (e) {
            const d = e?.response?.data?.detail;
            toast.error(typeof d === 'string' ? d : (d?.message || 'Could not create the book. Try again.'));
            setBusy(false);
        }
    };

    const Row = ({ icon: Icon, color, title: t, sub, onClick }) => (
        <button onClick={() => { tap(); onClick(); }} className="m-pressable flex w-full items-center gap-4 rounded-2xl p-3.5 text-left" style={{ background: 'var(--m-soft)' }}>
            <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl text-white" style={{ background: color }}><Icon className="h-6 w-6" /></span>
            <span className="min-w-0 flex-1">
                <span className="block text-[16px] font-bold">{t}</span>
                <span className="block text-[13px]" style={{ color: 'var(--m-muted)' }}>{sub}</span>
            </span>
            <ChevronRight className="h-5 w-5" style={{ color: 'var(--m-muted)' }} />
        </button>
    );

    const titles = { source: 'Add to Lumina IQ', paste: 'Paste text', where: 'Which book?' };

    return (
        <Sheet open={open} onClose={onClose} title={titles[step]}>
            <input ref={inputRef} type="file" accept={ACCEPT} multiple className="hidden" onChange={(e) => { onFiles(e.target.files); e.target.value = ''; }} />

            {step === 'source' && (
                <div className="space-y-2.5">
                    <Row icon={FileUp} color="var(--m-accent)" title="Upload a file" sub={`PDF, Word or text, up to ${MAX_UPLOAD_MB} MB. Scanned books work too.`} onClick={() => inputRef.current?.click()} />
                    <Row icon={ClipboardPaste} color="#7c6fd6" title="Paste text" sub="Notes, an article, a chapter you copied" onClick={() => setStep('paste')} />
                    <Row icon={Store} color="#2f9e7a" title="Free books" sub="Pick a ready-made book from the library" onClick={() => { onClose(); navigate('/bookstore'); }} />
                </div>
            )}

            {step === 'paste' && (
                <div className="space-y-3">
                    <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Title (optional)"
                        className="h-12 w-full rounded-2xl px-4 text-[15px] outline-none" style={{ background: 'var(--m-soft)', color: 'var(--m-text)' }} />
                    <textarea value={text} onChange={(e) => setText(e.target.value.slice(0, 4000000))} placeholder="Paste here…" rows={9}
                        className="w-full resize-none rounded-2xl p-4 text-[15px] leading-relaxed outline-none" style={{ background: 'var(--m-soft)', color: 'var(--m-text)' }} />
                    <div className="flex items-center gap-2">
                        <button onClick={() => setStep('source')} className="m-pressable flex h-12 w-12 items-center justify-center rounded-2xl" style={{ background: 'var(--m-soft)' }} aria-label="Back"><ChevronLeft className="h-5 w-5" /></button>
                        <span className="flex-1 text-[12.5px]" style={{ color: 'var(--m-muted)' }}>{text.trim() ? text.trim().split(/\s+/).length.toLocaleString() : 0} words</span>
                        <button onClick={fromPaste} className="m-pressable h-12 rounded-2xl px-6 text-[15px] font-bold text-white" style={{ background: 'var(--m-accent)' }}>Next</button>
                    </div>
                </div>
            )}

            {step === 'where' && pending && (
                <div className="space-y-2">
                    <p className="px-1 pb-1 text-[13px]" style={{ color: 'var(--m-muted)' }}>
                        {pending.files.length === 1 ? pending.files[0].name : `${pending.files.length} files`}
                    </p>
                    <button disabled={busy} onClick={() => sendTo(null)} className="m-pressable flex w-full items-center gap-3 rounded-2xl p-3 text-left text-white disabled:opacity-70" style={{ background: 'var(--m-accent)' }}>
                        <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-white/20">{busy ? <Loader2 className="h-5 w-5 animate-spin" /> : <Plus className="h-6 w-6" />}</span>
                        <span className="min-w-0 flex-1">
                            <span className="block text-[15px] font-bold">New book</span>
                            <span className="block truncate text-[12.5px] text-white/80">"{pending.name}"</span>
                        </span>
                    </button>
                    {books.map((b) => (
                        <button key={b.id} disabled={busy} onClick={() => sendTo(b.id)} className="m-pressable flex w-full items-center gap-3 rounded-2xl p-3 text-left" style={{ background: 'var(--m-soft)' }}>
                            <span className="flex h-11 w-11 items-center justify-center rounded-xl text-xl" style={{ background: coverFor(b.id)[0] }}>{emojiFor(b.name)}</span>
                            <span className="min-w-0 flex-1">
                                <span className="block truncate text-[15px] font-bold">{b.name}</span>
                                <span className="block text-[12.5px]" style={{ color: 'var(--m-muted)' }}>{b.docs || 0} {b.docs === 1 ? 'file' : 'files'}</span>
                            </span>
                        </button>
                    ))}
                </div>
            )}
        </Sheet>
    );
};

export default AddSheet;
