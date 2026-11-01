import React, { useEffect, useRef, useState } from 'react';
import { ChevronDown, Plus, Pencil, Trash2, Check, X, MessageSquare } from 'lucide-react';
import { listChatThreads, renameChatThread, deleteChatThread } from '../../api';

const when = (iso) => {
    if (!iso) return '';
    const d = new Date(iso);
    const days = Math.floor((Date.now() - d.getTime()) / 86400000);
    if (days <= 0) return d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
    if (days === 1) return 'Yesterday';
    if (days < 7) return d.toLocaleDateString([], { weekday: 'short' });
    return d.toLocaleDateString([], { day: 'numeric', month: 'short' });
};

/**
 * The book's chats, like ChatGPT's sidebar: the current chat's name opens the list,
 * "New chat" starts a fresh conversation. Empty chats other than the current one are hidden.
 */
const ChatThreads = ({ projectId, threadId, version, onSelect, onNew, onAdopt, onDeleted, isDark }) => {
    const [threads, setThreads] = useState([]);
    const [open, setOpen] = useState(false);
    const [editing, setEditing] = useState(null);   // { id, title }
    const boxRef = useRef(null);

    useEffect(() => {
        let alive = true;
        listChatThreads(projectId).then((list) => {
            if (!alive) return;
            setThreads(list);
            // The chat shown on load is the latest one: learn its id
            if (!threadId && list.length) onAdopt?.(list[0].id);
        }).catch(() => {});
        return () => { alive = false; };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [projectId, version]);

    useEffect(() => {
        if (!open) return undefined;
        const close = (e) => { if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false); };
        document.addEventListener('mousedown', close);
        return () => document.removeEventListener('mousedown', close);
    }, [open]);

    const current = threads.find((t) => t.id === threadId);
    const visible = threads.filter((t) => t.message_count > 0 || t.id === threadId);
    const text = isDark ? 'text-[#E9EFD6]' : 'text-[#163628]';
    const panel = isDark ? 'bg-[#182C21] border-[#293E34]' : 'bg-white border-[#E6D5CC]';
    const muted = isDark ? 'text-[#9fb3a6]' : 'text-[#5E5046]';

    const save = async (id) => {
        const title = editing?.title?.trim();
        if (title) {
            const row = await renameChatThread(id, title).catch(() => null);
            if (row) setThreads((list) => list.map((t) => (t.id === id ? { ...t, title: row.title } : t)));
        }
        setEditing(null);
    };

    const remove = async (id) => {
        await deleteChatThread(id).catch(() => null);
        setThreads((list) => list.filter((t) => t.id !== id));
        if (id === threadId) onDeleted?.();
    };

    return (
        <div ref={boxRef} className="relative flex items-center gap-2 px-2 pt-3 md:px-6">
            <button onClick={() => setOpen((v) => !v)} aria-expanded={open} aria-haspopup="listbox"
                className={`flex min-w-0 max-w-[60vw] items-center gap-1.5 rounded-xl border px-3 py-1.5 text-sm font-semibold md:max-w-md ${panel} ${text}`}>
                <MessageSquare className="h-4 w-4 shrink-0 text-[#1E5C42]" />
                <span className="truncate">{current?.title || 'New chat'}</span>
                <ChevronDown className="h-4 w-4 shrink-0" />
            </button>
            <button onClick={() => { setOpen(false); onNew(); }}
                className="flex shrink-0 items-center gap-1 rounded-xl bg-[#1E5C42] px-3 py-1.5 text-sm font-semibold text-white">
                <Plus className="h-4 w-4" /> New chat
            </button>

            {open && (
                <div role="listbox" aria-label="Your chats about this book"
                    className={`absolute left-2 right-2 top-full z-30 mt-2 max-h-[60vh] overflow-y-auto rounded-2xl border p-2 shadow-lg md:left-6 md:right-auto md:w-[420px] ${panel}`}>
                    {visible.length === 0 && <p className={`p-3 text-sm ${muted}`}>No chats yet. Ask a question to start one.</p>}
                    {visible.map((t) => (
                        <div key={t.id} role="option" aria-selected={t.id === threadId}
                            className={`group flex items-center gap-2 rounded-xl px-3 py-2 ${t.id === threadId ? 'bg-[#1E5C42]/10' : 'hover:bg-[#1E5C42]/5'}`}>
                            {editing?.id === t.id ? (
                                <form className="flex min-w-0 flex-1 items-center gap-1" onSubmit={(e) => { e.preventDefault(); save(t.id); }}>
                                    <input autoFocus value={editing.title} maxLength={120} aria-label="Chat name"
                                        onChange={(e) => setEditing({ id: t.id, title: e.target.value })}
                                        className={`min-w-0 flex-1 rounded-lg border px-2 py-1 text-sm outline-none ${panel} ${text}`} />
                                    <button type="submit" aria-label="Save name" className="p-1 text-[#1E5C42]"><Check className="h-4 w-4" /></button>
                                    <button type="button" aria-label="Cancel" onClick={() => setEditing(null)} className={`p-1 ${muted}`}><X className="h-4 w-4" /></button>
                                </form>
                            ) : (
                                <>
                                    <button className="min-w-0 flex-1 text-left" onClick={() => { setOpen(false); if (t.id !== threadId) onSelect(t.id); }}>
                                        <span className={`block truncate text-sm font-medium ${text}`}>{t.title}</span>
                                        <span className={`text-xs ${muted}`}>{when(t.updated_at)}</span>
                                    </button>
                                    <button aria-label={`Rename ${t.title}`} onClick={() => setEditing({ id: t.id, title: t.title })}
                                        className={`p-1 ${muted}`}><Pencil className="h-4 w-4" /></button>
                                    <button aria-label={`Delete ${t.title}`} onClick={() => remove(t.id)}
                                        className="p-1 text-rose-600"><Trash2 className="h-4 w-4" /></button>
                                </>
                            )}
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};

export default ChatThreads;
