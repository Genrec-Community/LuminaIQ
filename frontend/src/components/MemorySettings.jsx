import React, { useEffect, useState } from 'react';
import { Loader2, Pencil, Trash2, Plus, Check, X, MessageSquare } from 'lucide-react';
import { getMemory, addMemory, editMemory, deleteMemory, clearMemory, deleteChatSummary, apiErrorText } from '../api';

const KIND_LABEL = { goal: 'Goal', preference: 'Preference', struggle: 'Finds hard', interest: 'Interest', fact: 'Note' };

/**
 * "What Lumina remembers about you": every memory note and chat summary, editable and
 * deletable by the student. Teachers never see any of this.
 * Theme colours come from the Settings page; the two switches live in user settings.
 */
const MemorySettings = ({ colors, settings, updateSetting, Toggle, icons }) => {
    const { paper, border, muted, heading, inputBg } = colors;
    const [data, setData] = useState(null);
    const [error, setError] = useState('');
    const [draft, setDraft] = useState('');
    const [editing, setEditing] = useState(null);   // { id, text }
    const [confirmClear, setConfirmClear] = useState(false);
    const [busy, setBusy] = useState(false);

    const load = () => getMemory().then((d) => { setData(d); setError(''); }).catch((e) => setError(apiErrorText(e)));
    useEffect(() => { load(); }, []);

    const act = async (fn) => {
        setBusy(true);
        try { await fn(); await load(); } catch (e) { setError(apiErrorText(e)); } finally { setBusy(false); }
    };

    if (error && !data) return <p className="text-sm text-rose-600">{error}</p>;
    if (!data) return <div className="flex items-center gap-2 text-sm" style={{ color: muted }}><Loader2 className="h-4 w-4 animate-spin" /> Loading…</div>;

    const autoAvailable = data.auto_memory_available;
    return (
        <div className="space-y-5">
            <p className="text-sm leading-relaxed" style={{ color: muted }}>
                Lumina uses this to explain things the way that works for you. Only you can see it: teachers see your
                progress, never your chats or these notes. Notes you don't use for 6 months fade away on their own.
            </p>

            <div className="space-y-3">
                <Toggle
                    enabled={settings.memoryAcrossBooks !== false}
                    onChange={(v) => updateSetting('memoryAcrossBooks', v)}
                    label="Use memory across all my books"
                    description="Off: what Lumina learns in one book is only used in that book."
                    icon={icons.books}
                />
                {autoAvailable ? (
                    <Toggle
                        enabled={settings.autoMemory !== false}
                        onChange={(v) => updateSetting('autoMemory', v)}
                        label="Let Lumina take notes from our chats"
                        description="Things like your exam date or how you like explanations. You can edit or delete them below."
                        icon={icons.brain}
                    />
                ) : (
                    <p className="rounded-2xl border p-4 text-xs leading-relaxed" style={{ background: paper, borderColor: border, color: muted }}>
                        For Class 5–10, Lumina remembers only your quiz progress and a short summary of each chat, never notes about you.
                    </p>
                )}
            </div>

            {error && <p className="text-sm text-rose-600">{error}</p>}

            <section>
                <h3 className="mb-2 text-sm font-bold" style={{ color: heading }}>Notes about you ({data.memories.length})</h3>
                <form className="mb-3 flex gap-2" onSubmit={(e) => {
                    e.preventDefault();
                    const text = draft.trim();
                    if (text.length >= 2) act(async () => { await addMemory(text); setDraft(''); });
                }}>
                    <input value={draft} onChange={(e) => setDraft(e.target.value)} maxLength={300}
                        placeholder="Add something, e.g. “My board exam is on 12 March”" aria-label="Add a note"
                        className="min-w-0 flex-1 rounded-xl border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-[#1E5C42]"
                        style={{ background: inputBg, borderColor: border, color: heading }} />
                    <button type="submit" disabled={busy || draft.trim().length < 2}
                        className="flex items-center gap-1 rounded-xl bg-[#1E5C42] px-3 py-2 text-sm font-semibold text-white disabled:opacity-50">
                        <Plus className="h-4 w-4" /> Add
                    </button>
                </form>
                {data.memories.length === 0 ? (
                    <p className="text-sm" style={{ color: muted }}>Nothing yet.</p>
                ) : (
                    <ul className="space-y-2">
                        {data.memories.map((m) => (
                            <li key={m.id} className="flex items-start gap-3 rounded-2xl border p-3" style={{ background: paper, borderColor: border }}>
                                <span className="mt-0.5 shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide"
                                    style={{ background: inputBg, color: muted }}>{KIND_LABEL[m.kind] || 'Note'}</span>
                                {editing?.id === m.id ? (
                                    <form className="flex min-w-0 flex-1 gap-2" onSubmit={(e) => {
                                        e.preventDefault();
                                        const text = editing.text.trim();
                                        if (text.length >= 2) act(async () => { await editMemory(m.id, text); setEditing(null); });
                                    }}>
                                        <input autoFocus value={editing.text} maxLength={300} aria-label="Edit note"
                                            onChange={(e) => setEditing({ id: m.id, text: e.target.value })}
                                            className="min-w-0 flex-1 rounded-lg border px-2 py-1 text-sm outline-none"
                                            style={{ background: inputBg, borderColor: border, color: heading }} />
                                        <button type="submit" aria-label="Save" className="p-1 text-[#1E5C42]"><Check className="h-4 w-4" /></button>
                                        <button type="button" aria-label="Cancel" onClick={() => setEditing(null)} className="p-1" style={{ color: muted }}><X className="h-4 w-4" /></button>
                                    </form>
                                ) : (
                                    <>
                                        <p className="min-w-0 flex-1 break-words text-sm" style={{ color: heading }}>{m.content}</p>
                                        <button aria-label="Edit note" onClick={() => setEditing({ id: m.id, text: m.content })} className="p-1" style={{ color: muted }}><Pencil className="h-4 w-4" /></button>
                                        <button aria-label="Delete note" disabled={busy} onClick={() => act(() => deleteMemory(m.id))} className="p-1 text-rose-600"><Trash2 className="h-4 w-4" /></button>
                                    </>
                                )}
                            </li>
                        ))}
                    </ul>
                )}
            </section>

            {data.summaries.length > 0 && (
                <section>
                    <h3 className="mb-2 text-sm font-bold" style={{ color: heading }}>Chat summaries</h3>
                    <p className="mb-2 text-xs" style={{ color: muted }}>Long chats are summarised so Lumina remembers what you talked about earlier. Your chats themselves are not changed.</p>
                    <ul className="space-y-2">
                        {data.summaries.map((s) => (
                            <li key={s.project_id} className="rounded-2xl border p-3" style={{ background: paper, borderColor: border }}>
                                <div className="mb-1 flex items-center gap-2">
                                    <MessageSquare className="h-4 w-4 text-[#1E5C42]" />
                                    <span className="flex-1 text-sm font-semibold" style={{ color: heading }}>{s.project_name}</span>
                                    <button aria-label={`Forget the summary of ${s.project_name}`} disabled={busy}
                                        onClick={() => act(() => deleteChatSummary(s.project_id))} className="p-1 text-rose-600"><Trash2 className="h-4 w-4" /></button>
                                </div>
                                <p className="whitespace-pre-line text-xs leading-relaxed" style={{ color: muted }}>{s.summary}</p>
                            </li>
                        ))}
                    </ul>
                </section>
            )}

            <div className="rounded-2xl border border-rose-200 p-4">
                {confirmClear ? (
                    <div className="flex flex-wrap items-center gap-2">
                        <p className="flex-1 text-sm" style={{ color: heading }}>Forget all notes and chat summaries? Your chats stay.</p>
                        <button disabled={busy} onClick={() => act(async () => { await clearMemory(); setConfirmClear(false); })}
                            className="rounded-xl bg-rose-600 px-3 py-1.5 text-sm font-semibold text-white">Yes, forget everything</button>
                        <button onClick={() => setConfirmClear(false)} className="rounded-xl border px-3 py-1.5 text-sm" style={{ borderColor: border, color: heading }}>Cancel</button>
                    </div>
                ) : (
                    <button onClick={() => setConfirmClear(true)} className="text-sm font-semibold text-rose-600">Clear everything Lumina remembers</button>
                )}
            </div>
        </div>
    );
};

export default MemorySettings;
