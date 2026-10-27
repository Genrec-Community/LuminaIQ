import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Loader2, Search, ShieldCheck, Ban, CalendarPlus, History, ChevronLeft, ChevronRight } from 'lucide-react';
import {
    getPlatformMe, listPlatformSchools, approveSchool, suspendSchool, extendSchool, getSchoolAudit, apiErrorText,
} from '../api';

const fmtDate = (iso) => (iso ? new Date(iso).toLocaleDateString([], { day: 'numeric', month: 'short', year: 'numeric' }) : '—');

const STATE = {
    pending_approval: ['Waiting', 'bg-sky-100 text-sky-800'],
    trial: ['Trial', 'bg-violet-100 text-violet-800'],
    active: ['Active', 'bg-emerald-100 text-emerald-800'],
    expired: ['Expired', 'bg-amber-100 text-amber-800'],
    suspended: ['Paused', 'bg-rose-100 text-rose-800'],
};

const FILTERS = [['', 'All'], ['pending', 'Waiting'], ['live', 'Working'], ['expired', 'Expired'], ['suspended', 'Paused']];

const School = ({ s, onChanged }) => {
    const [busy, setBusy] = useState('');
    const [error, setError] = useState('');
    const [extend, setExtend] = useState(false);
    const [form, setForm] = useState({ days: 365, seats: s.seats, note: '' });
    const [audit, setAudit] = useState(null);
    const [label, cls] = STATE[s.state] || [s.state, 'bg-gray-100'];

    const act = async (name, fn) => {
        setBusy(name); setError('');
        try { await fn(); onChanged(); } catch (e) { setError(apiErrorText(e)); } finally { setBusy(''); }
    };
    const approve = () => act('approve', () => approveSchool(s.id, window.prompt('Note for the school (optional)') || ''));
    const suspend = () => {
        const note = window.prompt(`Pause ${s.name}? Students can't sign in until you switch it back on.\nReason (shown to the school):`);
        if (note === null) return;
        act('suspend', () => suspendSchool(s.id, note));
    };
    const toggleAudit = async () => {
        if (audit) { setAudit(null); return; }
        try { setAudit((await getSchoolAudit(s.id)).events); } catch (e) { setError(apiErrorText(e)); }
    };

    return (
        <li className="rounded-3xl border border-[#E6D5CC] bg-white p-4 md:p-5">
            <div className="flex flex-wrap items-start gap-3">
                <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                        <h3 className="font-bold text-[#4A3B32]">{s.name}</h3>
                        <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${cls}`}>{label}</span>
                    </div>
                    <div className="mt-0.5 text-sm text-[#8a6a5c]">
                        {s.contact_email || 'no email'} · {s.students} / {s.seats} students · created {fmtDate(s.created_at)}
                    </div>
                    <div className="text-sm text-[#8a6a5c]">
                        Paid until {fmtDate(s.paid_until)}{s.timer?.days_left != null && s.timer.seconds_left > 0 ? ` (${s.timer.days_left} days left)` : ''}
                        {s.last_payment_at ? ` · last payment ${fmtDate(s.last_payment_at)}` : ''}
                        {s.gstin ? ` · GSTIN ${s.gstin}` : ''}
                    </div>
                    {s.approval_note && <div className="text-sm text-[#8a6a5c]">Note: {s.approval_note}</div>}
                </div>
                <div className="flex flex-wrap gap-2">
                    {s.approval_status !== 'approved' && (
                        <button onClick={approve} disabled={!!busy} className="inline-flex items-center gap-1 rounded-xl bg-emerald-600 px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50">
                            {busy === 'approve' ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />} {s.approval_status === 'suspended' ? 'Switch on' : 'Approve'}
                        </button>
                    )}
                    {s.approval_status !== 'suspended' && (
                        <button onClick={suspend} disabled={!!busy} className="inline-flex items-center gap-1 rounded-xl border border-rose-200 px-3 py-1.5 text-sm font-semibold text-rose-700 disabled:opacity-50">
                            {busy === 'suspend' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Ban className="h-4 w-4" />} Pause
                        </button>
                    )}
                    <button onClick={() => setExtend(!extend)} className="inline-flex items-center gap-1 rounded-xl border border-[#E6D5CC] px-3 py-1.5 text-sm font-semibold">
                        <CalendarPlus className="h-4 w-4" /> Extend
                    </button>
                    <button onClick={toggleAudit} className="inline-flex items-center gap-1 rounded-xl border border-[#E6D5CC] px-3 py-1.5 text-sm font-semibold">
                        <History className="h-4 w-4" /> History
                    </button>
                </div>
            </div>
            {extend && (
                <form onSubmit={(e) => { e.preventDefault(); act('extend', () => extendSchool(s.id, { days: Number(form.days) || null, seats: Number(form.seats) || null, note: form.note })).then(() => setExtend(false)); }}
                    className="mt-3 flex flex-wrap items-end gap-3 rounded-2xl bg-[#FDF6F0] p-3">
                    <label className="text-xs text-[#8a6a5c]">Add days<input type="number" min={1} value={form.days} onChange={(e) => setForm({ ...form, days: e.target.value })} className="mt-1 block w-24 rounded-xl border border-[#E6D5CC] px-2 py-1.5 text-sm" /></label>
                    <label className="text-xs text-[#8a6a5c]">Seats<input type="number" min={1} value={form.seats} onChange={(e) => setForm({ ...form, seats: e.target.value })} className="mt-1 block w-24 rounded-xl border border-[#E6D5CC] px-2 py-1.5 text-sm" /></label>
                    <label className="text-xs text-[#8a6a5c] flex-1 min-w-[10rem]">Note (e.g. bank transfer ref.)<input value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} className="mt-1 block w-full rounded-xl border border-[#E6D5CC] px-2 py-1.5 text-sm" /></label>
                    <button disabled={!!busy} className="rounded-xl bg-[#4A3B32] px-3 py-2 text-sm font-semibold text-white disabled:opacity-50">{busy === 'extend' ? 'Saving…' : 'Save'}</button>
                </form>
            )}
            {error && <p className="mt-2 text-sm text-rose-600">{error}</p>}
            {audit && (
                <ul className="mt-3 max-h-56 space-y-1 overflow-auto rounded-2xl bg-[#FDF6F0] p-3 text-xs text-[#4A3B32]">
                    {audit.length === 0 && <li>Nothing yet.</li>}
                    {audit.map((a) => (
                        <li key={a.id}><span className="text-[#8a6a5c]">{new Date(a.created_at).toLocaleString()}</span> · <span className="font-semibold">{a.action}</span>{a.detail && Object.keys(a.detail).length ? ` · ${JSON.stringify(a.detail)}` : ''}</li>
                    ))}
                </ul>
            )}
        </li>
    );
};

/** LuminaIQ staff console: approve, pause and extend schools. */
const Platform = () => {
    const navigate = useNavigate();
    const [allowed, setAllowed] = useState(null);
    const [status, setStatus] = useState('pending');
    const [q, setQ] = useState('');
    const [page, setPage] = useState(1);
    const [data, setData] = useState(null);
    const [error, setError] = useState('');

    useEffect(() => { getPlatformMe().then((r) => setAllowed(r.platform_admin)).catch(() => setAllowed(false)); }, []);
    const load = useCallback(async () => {
        try { setData(await listPlatformSchools({ status, q, page })); setError(''); } catch (e) { setError(apiErrorText(e)); }
    }, [status, q, page]);
    useEffect(() => {
        if (!allowed) return undefined;
        const t = setTimeout(load, q ? 300 : 0);
        return () => clearTimeout(t);
    }, [allowed, load, q]);

    const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
    return (
        <div className="min-h-[100dvh] bg-[#FDF6F0] text-[#4A3B32]">
            <header className="mx-auto max-w-5xl px-4 py-5 flex items-center justify-between">
                <button onClick={() => navigate('/dashboard')} className="flex items-center gap-1.5 rounded-xl px-3 py-2 text-sm font-semibold hover:bg-white">
                    <ArrowLeft className="h-4 w-4" /> Dashboard
                </button>
                <span className="font-bold">Schools console</span>
            </header>
            <main className="mx-auto max-w-5xl px-4 pb-16">
                {allowed === null && <div className="flex items-center gap-2 text-[#8a6a5c]"><Loader2 className="h-4 w-4 animate-spin" /> Checking access…</div>}
                {allowed === false && <p className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-rose-800">This page is for LuminaIQ staff.</p>}
                {allowed && (
                    <>
                        <div className="mb-4 flex flex-wrap items-center gap-2">
                            {FILTERS.map(([id, label]) => (
                                <button key={id} onClick={() => { setStatus(id); setPage(1); }}
                                    className={`rounded-2xl px-3 py-1.5 text-sm font-semibold ${status === id ? 'bg-[#4A3B32] text-white' : 'border border-[#E6D5CC] bg-white'}`}>{label}</button>
                            ))}
                            <div className="relative ml-auto">
                                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#8a6a5c]" />
                                <input value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} placeholder="School or email" aria-label="Search schools"
                                    className="w-56 rounded-2xl border border-[#E6D5CC] bg-white py-2 pl-9 pr-3 text-sm outline-none focus:ring-2 focus:ring-[#C8A288]" />
                            </div>
                        </div>
                        {error && <p className="mb-3 text-sm text-rose-600">{error}</p>}
                        {!data ? <div className="flex items-center gap-2 text-[#8a6a5c]"><Loader2 className="h-4 w-4 animate-spin" /> Loading…</div> : (
                            <>
                                <p className="mb-2 text-sm text-[#8a6a5c]">{data.total} school{data.total === 1 ? '' : 's'}</p>
                                <ul className="space-y-3">{data.institutions.map((s) => <School key={s.id} s={s} onChanged={load} />)}</ul>
                                {pages > 1 && (
                                    <div className="mt-4 flex items-center justify-end gap-2 text-sm">
                                        <button onClick={() => setPage(page - 1)} disabled={page <= 1} className="rounded-lg border border-[#E6D5CC] bg-white p-1 disabled:opacity-40" aria-label="Previous page"><ChevronLeft className="h-4 w-4" /></button>
                                        <span className="tabular-nums">{page} / {pages}</span>
                                        <button onClick={() => setPage(page + 1)} disabled={page >= pages} className="rounded-lg border border-[#E6D5CC] bg-white p-1 disabled:opacity-40" aria-label="Next page"><ChevronRight className="h-4 w-4" /></button>
                                    </div>
                                )}
                            </>
                        )}
                    </>
                )}
            </main>
        </div>
    );
};

export default Platform;
