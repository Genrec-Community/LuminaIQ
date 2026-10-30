import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    ArrowLeft, Building2, Copy, Check, Loader2, Plus, Users, BookOpen, ChevronRight, UserMinus,
    KeyRound, AlertTriangle, GraduationCap, Clock, ShieldCheck, Hourglass,
} from 'lucide-react';
import {
    getMyInstitution, createInstitution, joinWithCode, createClass, getClassDashboard,
    publishBookToClass, getPublishableBooks, removeInstitutionMember, startSeatsCheckout, verifyPayment,
    apiErrorText,
} from '../api';
import StudentsPanel from '../components/institution/StudentsPanel';
import { emitPlanChanged } from '../utils/plan';
import { openCheckout } from '../utils/razorpay';
import { inr } from '../utils/pricing';
import { isNativeApp } from '../utils/platform';

const errText = (e) => apiErrorText(e);
const fmtDate = (iso) => (iso ? new Date(iso).toLocaleDateString([], { day: 'numeric', month: 'short', year: 'numeric' }) : '');

const Card = ({ children, className = '' }) => (
    <div className={`rounded-3xl border border-[#E6D5CC] bg-white p-5 md:p-6 ${className}`}>{children}</div>
);

const CopyCode = ({ code, label }) => {
    const [done, setDone] = useState(false);
    return (
        <button onClick={() => { navigator.clipboard?.writeText(code); setDone(true); setTimeout(() => setDone(false), 1500); }}
            className="inline-flex items-center gap-2 rounded-xl border border-[#E6D5CC] bg-[#FDF6F0] px-3 py-1.5 font-mono text-sm font-bold tracking-wider text-[#163628] hover:border-[#1E5C42]"
            title={`Copy ${label}`}>
            {code} {done ? <Check className="h-4 w-4 text-emerald-600" /> : <Copy className="h-4 w-4 text-[#5E5046]" />}
        </button>
    );
};

const JoinBox = ({ onJoined }) => {
    const [code, setCode] = useState('');
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    const submit = async (e) => {
        e.preventDefault();
        setBusy(true); setError('');
        try {
            const r = await joinWithCode(code);
            emitPlanChanged();
            onJoined(r);
        } catch (err) {
            setError(errText(err));
        } finally {
            setBusy(false);
        }
    };
    return (
        <form onSubmit={submit}>
            <label className="text-sm font-semibold text-[#163628]" htmlFor="join-code">Have a code from your teacher or school?</label>
            <div className="mt-2 flex gap-2">
                <input id="join-code" value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} placeholder="C-ABC123"
                    className="flex-1 rounded-2xl border border-[#E6D5CC] bg-[#FDF6F0] px-4 py-3 font-mono tracking-wider outline-none focus:ring-2 focus:ring-[#1E5C42]" />
                <button disabled={busy || code.trim().length < 4}
                    className="rounded-2xl bg-[#1E5C42] px-5 font-semibold text-white hover:bg-[#163628] disabled:opacity-50">
                    {busy ? <Loader2 className="h-5 w-5 animate-spin" /> : 'Join'}
                </button>
            </div>
            {error && <p className="mt-2 text-sm text-rose-600">{error}</p>}
        </form>
    );
};

// ------------------------------------------------------- status and timer

/** Time left on the school's term, ticking every minute. */
const useCountdown = (endsAt) => {
    const [now, setNow] = useState(() => Date.now());
    useEffect(() => {
        const t = setInterval(() => setNow(Date.now()), 60000);
        return () => clearInterval(t);
    }, []);
    if (!endsAt) return null;
    const ms = Math.max(0, new Date(endsAt).getTime() - now);
    const days = Math.floor(ms / 86400000);
    const hours = Math.floor((ms % 86400000) / 3600000);
    const mins = Math.floor((ms % 3600000) / 60000);
    return { ms, days, hours, mins };
};

const StatusBanner = ({ inst, role }) => {
    const left = useCountdown(inst.timer?.ends_at || inst.paid_until);
    const st = inst.state;
    if (st === 'pending_approval') {
        return (
            <div className="rounded-2xl border border-sky-200 bg-sky-50 p-4 text-sky-900 flex gap-3">
                <Hourglass className="h-5 w-5 shrink-0 mt-0.5" />
                <div>
                    <div className="font-semibold">Waiting for approval</div>
                    <p className="text-sm">Lumina IQ checks every new school before switching it on. You can look around now; classes and student accounts open once you're approved{role === 'admin' ? ', and you can pay for seats in the meantime' : ''}.</p>
                </div>
            </div>
        );
    }
    if (st === 'suspended') {
        return (
            <div className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-rose-900 flex gap-3">
                <AlertTriangle className="h-5 w-5 shrink-0 mt-0.5" />
                <div>
                    <div className="font-semibold">Paused by Lumina IQ</div>
                    <p className="text-sm">Students can't sign in until it's switched back on.{inst.approval_note ? ` Note: ${inst.approval_note}` : ''} Contact Lumina IQ support.</p>
                </div>
            </div>
        );
    }
    if (st === 'expired') {
        return (
            <div className="rounded-2xl border border-amber-300 bg-amber-50 p-4 text-amber-900 flex gap-3">
                <AlertTriangle className="h-5 w-5 shrink-0 mt-0.5" />
                <div>
                    <div className="font-semibold">Your plan has ended</div>
                    <p className="text-sm">{inst.paid_until ? `It ended on ${fmtDate(inst.paid_until)}. ` : ''}School student accounts can't sign in and members lose the Institution plan until {role === 'admin' ? 'you renew' : 'your admin renews'}.</p>
                </div>
            </div>
        );
    }
    if (!left) return null;
    const soon = left.days < 7;
    return (
        <div className={`rounded-2xl border p-4 flex flex-wrap items-center gap-3 ${soon ? 'border-amber-300 bg-amber-50 text-amber-900' : 'border-emerald-200 bg-emerald-50 text-emerald-900'}`}>
            {soon ? <Clock className="h-5 w-5 shrink-0" /> : <ShieldCheck className="h-5 w-5 shrink-0" />}
            <div className="flex-1 min-w-0">
                <span className="font-semibold">{st === 'trial' ? 'Free trial' : 'Active'}</span>
                <span className="text-sm"> · ends {fmtDate(inst.paid_until)}</span>
            </div>
            <div className="font-mono text-sm font-bold tabular-nums" aria-label="Time left">
                {left.days}d {String(left.hours).padStart(2, '0')}h {String(left.mins).padStart(2, '0')}m left
            </div>
        </div>
    );
};

// ------------------------------------------------------------------ setup

const Setup = ({ onCreated, onJoined }) => {
    const [form, setForm] = useState({ name: '', billing_name: '', gstin: '', contact_email: '' });
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
    const submit = async (e) => {
        e.preventDefault();
        setBusy(true); setError('');
        try {
            onCreated(await createInstitution({ ...form, gstin: form.gstin || null }));
            emitPlanChanged();
        } catch (err) {
            setError(errText(err));
        } finally {
            setBusy(false);
        }
    };
    const input = 'w-full rounded-2xl border border-[#E6D5CC] bg-[#FDF6F0] px-4 py-3 outline-none focus:ring-2 focus:ring-[#1E5C42]';
    return (
        <div className="grid gap-5 md:grid-cols-[1.4fr_1fr]">
            <Card>
                <h2 className="text-xl font-bold text-[#163628] flex items-center gap-2"><Building2 className="h-5 w-5 text-[#1E5C42]" /> Set up your institution</h2>
                <p className="text-sm text-[#5E5046] mt-1">We review each new school, then switch on a free trial for up to 25 students. After that it's {inr(179)} per student per month, paid for 1, 3, 6 or 12 months at a time.</p>
                <form onSubmit={submit} className="mt-4 space-y-3">
                    <input required minLength={2} value={form.name} onChange={set('name')} placeholder="School or institute name" className={input} />
                    <input value={form.billing_name} onChange={set('billing_name')} placeholder="Billing name (for invoices, optional)" className={input} />
                    <div className="grid sm:grid-cols-2 gap-3">
                        <input value={form.gstin} onChange={set('gstin')} maxLength={15} placeholder="GSTIN (optional)" className={`${input} uppercase`} />
                        <input type="email" value={form.contact_email} onChange={set('contact_email')} placeholder="Billing email (optional)" className={input} />
                    </div>
                    {error && <p className="text-sm text-rose-600">{error}</p>}
                    <button disabled={busy} className="w-full rounded-2xl bg-[#163628] px-4 py-3 font-semibold text-white hover:bg-[#283B31] disabled:opacity-60">
                        {busy ? 'Sending…' : 'Request access'}
                    </button>
                </form>
            </Card>
            <Card>
                <h2 className="text-xl font-bold text-[#163628] flex items-center gap-2"><KeyRound className="h-5 w-5 text-[#1E5C42]" /> Join with a code</h2>
                <p className="text-sm text-[#5E5046] mt-1 mb-4">Students: use your class code. Teachers: use your institution's teacher code.</p>
                <JoinBox onJoined={onJoined} />
            </Card>
        </div>
    );
};

// -------------------------------------------------------------- staff home

const TERM_LABEL = { 1: '1 month', 3: '3 months', 6: '6 months', 12: '1 year' };

const SeatsBox = ({ data, onPaid }) => {
    const min = Math.max(data.pricing.min_seats, data.students);
    const inst = data.institution;
    const [seats, setSeats] = useState(Math.max(min, inst.status === 'active' ? inst.seats : min));
    const [months, setMonths] = useState(12);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    const [done, setDone] = useState('');
    const base = seats * data.pricing.per_seat_inr * months;
    const gstRate = data.pricing.gst_rate || 0;
    const gst = Math.round(base * gstRate);
    const renewing = inst.state === 'active';
    const pay = async () => {
        setBusy(true); setError(''); setDone('');
        try {
            const co = await startSeatsCheckout(seats, months);
            const resp = await openCheckout({
                key: co.key_id, order_id: co.order_id, amount: co.amount_paise, currency: 'INR',
                name: co.name, description: co.description, prefill: co.prefill,
            });
            await verifyPayment({ kind: 'seats', ...resp });
            emitPlanChanged();
            setDone('Payment received. Your new end date is shown above.');
            onPaid();
        } catch (e) {
            if (!e?.dismissed) setError(errText(e));
        } finally {
            setBusy(false);
        }
    };
    if (isNativeApp() || inst.state === 'suspended') return null;
    return (
        <Card>
            <div className="flex items-center justify-between gap-2">
                <h3 className="font-bold text-[#163628]">{renewing ? 'Renew or add seats' : 'Pay for student seats'}</h3>
                {data.pricing.test_mode && <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-800">Test mode</span>}
            </div>
            <p className="mt-1 text-xs text-[#5E5046]">
                {renewing ? 'Renewing early adds the new term after your current end date.' : 'The term starts the moment you pay.'}
            </p>
            <div className="mt-3 flex flex-wrap gap-2" role="radiogroup" aria-label="Term">
                {(data.pricing.terms || [12]).map((m) => (
                    <button key={m} type="button" role="radio" aria-checked={months === m} onClick={() => setMonths(m)}
                        className={`rounded-xl border px-3 py-1.5 text-sm font-semibold ${months === m ? 'border-[#1E5C42] bg-[#1E5C42] text-white' : 'border-[#E6D5CC] bg-[#FDF6F0] text-[#163628]'}`}>
                        {TERM_LABEL[m] || `${m} months`}
                    </button>
                ))}
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-3">
                <label className="text-sm text-[#5E5046]" htmlFor="seats">Students</label>
                <input id="seats" type="number" min={min} step={10} value={seats}
                    onChange={(e) => setSeats(Math.max(1, Number(e.target.value) || 0))}
                    className="w-28 rounded-xl border border-[#E6D5CC] bg-[#FDF6F0] px-3 py-2 tabular-nums" />
                <span className="text-sm text-[#5E5046]">× {inr(data.pricing.per_seat_inr)} × {months} month{months > 1 ? 's' : ''}</span>
            </div>
            <div className="mt-3 text-sm text-[#163628] space-y-0.5 tabular-nums">
                <div className="flex justify-between"><span>Subtotal</span><span>{inr(base)}</span></div>
                {gstRate > 0 && <div className="flex justify-between"><span>GST ({Math.round(gstRate * 100)}%)</span><span>{inr(gst)}</span></div>}
                <div className="flex justify-between font-bold"><span>Total for {TERM_LABEL[months] || `${months} months`}</span><span>{inr(base + gst)}</span></div>
            </div>
            {seats < min && <p className="mt-2 text-sm text-rose-600">Choose at least {min} students.</p>}
            {!data.pricing.payments_enabled && <p className="mt-2 text-sm text-[#5E5046]">Online payments aren't switched on yet. Contact Lumina IQ to pay by bank transfer.</p>}
            {error && <p className="mt-2 text-sm text-rose-600">{error}</p>}
            {done && <p className="mt-2 text-sm text-emerald-700">{done}</p>}
            <button onClick={pay} disabled={busy || seats < min || !data.pricing.payments_enabled}
                className="mt-4 w-full rounded-2xl bg-[#1E5C42] px-4 py-3 font-semibold text-white hover:bg-[#163628] disabled:opacity-50">
                {busy ? <Loader2 className="mx-auto h-5 w-5 animate-spin" /> : `Pay ${inr(base + gst)}`}
            </button>
        </Card>
    );
};

const StaffHome = ({ data, reload, openClass }) => {
    const [tab, setTab] = useState('classes');
    const [name, setName] = useState('');
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    const inst = data.institution;
    const add = async (e) => {
        e.preventDefault();
        setBusy(true); setError('');
        try {
            await createClass(name);
            setName('');
            reload();
        } catch (err) {
            setError(errText(err));
        } finally {
            setBusy(false);
        }
    };
    const removeTeacher = async (uid) => {
        if (!window.confirm('Remove this teacher from your institution?')) return;
        await removeInstitutionMember(uid).catch(() => {});
        reload();
    };
    return (
        <div className="space-y-5">
            <Card className="flex flex-wrap items-center justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold text-[#163628]">{inst.name}</h1>
                    <p className="text-sm text-[#5E5046]">{data.students} / {inst.seats} student seats used</p>
                </div>
                <div className="text-right">
                    <div className="text-xs font-semibold uppercase tracking-wide text-[#5E5046] mb-1">Teacher code</div>
                    <CopyCode code={inst.teacher_code} label="teacher code" />
                </div>
            </Card>
            <StatusBanner inst={inst} role={data.role} />
            <div className="flex gap-2" role="tablist">
                {[['classes', 'Classes'], ['students', 'Student accounts']].map(([id, label]) => (
                    <button key={id} role="tab" aria-selected={tab === id} onClick={() => setTab(id)}
                        className={`rounded-2xl px-4 py-2 text-sm font-semibold ${tab === id ? 'bg-[#163628] text-white' : 'bg-white border border-[#E6D5CC] text-[#163628]'}`}>
                        {label}
                    </button>
                ))}
            </div>
            {tab === 'students' ? (
                <StudentsPanel data={data} onChanged={reload} />
            ) : (
            <div className="grid gap-5 lg:grid-cols-[1.5fr_1fr]">
                <Card>
                    <div className="flex items-center justify-between mb-3">
                        <h2 className="text-lg font-bold text-[#163628] flex items-center gap-2"><GraduationCap className="h-5 w-5 text-[#1E5C42]" /> Classes</h2>
                    </div>
                    {data.classes.length === 0 && <p className="text-sm text-[#5E5046] mb-3">Create a class, then share its code with students.</p>}
                    <div className="divide-y divide-[#E6D5CC]">
                        {data.classes.map((c) => (
                            <button key={c.id} onClick={() => openClass(c.id)} className="w-full py-3 flex items-center gap-3 text-left hover:bg-[#FDF6F0] rounded-xl px-2">
                                <div className="flex-1 min-w-0">
                                    <div className="font-semibold text-[#163628] truncate">{c.name}</div>
                                    <div className="text-xs text-[#5E5046]">{c.students} students · code {c.invite_code}</div>
                                </div>
                                <ChevronRight className="h-5 w-5 text-[#5E5046]" />
                            </button>
                        ))}
                    </div>
                    <form onSubmit={add} className="mt-3 flex gap-2">
                        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="New class, e.g. 12 Science A"
                            className="flex-1 rounded-2xl border border-[#E6D5CC] bg-[#FDF6F0] px-4 py-2.5 outline-none focus:ring-2 focus:ring-[#1E5C42]" />
                        <button disabled={busy || !name.trim()} className="rounded-2xl bg-[#1E5C42] px-4 font-semibold text-white disabled:opacity-50 flex items-center gap-1">
                            <Plus className="h-4 w-4" /> Add
                        </button>
                    </form>
                    {error && <p className="mt-2 text-sm text-rose-600">{error}</p>}
                </Card>
                <div className="space-y-5">
                    {data.role === 'admin' && <SeatsBox data={data} onPaid={reload} />}
                    <Card>
                        <h2 className="text-lg font-bold text-[#163628] flex items-center gap-2 mb-2"><Users className="h-5 w-5 text-[#1E5C42]" /> Staff</h2>
                        <ul className="space-y-2">
                            {data.teachers.map((t) => (
                                <li key={t.user_id} className="flex items-center justify-between text-sm">
                                    <span className="text-[#163628]">{t.name || t.email} <span className="text-[#5E5046]">· {t.role}</span></span>
                                    {data.role === 'admin' && t.role === 'teacher' && (
                                        <button onClick={() => removeTeacher(t.user_id)} className="text-[#5E5046] hover:text-rose-600" title="Remove"><UserMinus className="h-4 w-4" /></button>
                                    )}
                                </li>
                            ))}
                        </ul>
                        <p className="mt-3 text-xs text-[#5E5046]">Teachers join with the teacher code above.</p>
                    </Card>
                </div>
            </div>
            )}
        </div>
    );
};

// ------------------------------------------------------------- class view

const ClassView = ({ classId, role, back }) => {
    const [data, setData] = useState(null);
    const [books, setBooks] = useState([]);
    const [pick, setPick] = useState('');
    const [busy, setBusy] = useState(false);
    const [msg, setMsg] = useState('');
    const load = useCallback(async () => {
        setData(await getClassDashboard(classId));
    }, [classId]);
    useEffect(() => {
        load();
        getPublishableBooks().then((r) => setBooks(r.documents || [])).catch(() => {});
    }, [load]);
    const publish = async () => {
        setBusy(true); setMsg('');
        try {
            const r = await publishBookToClass(classId, pick);
            setMsg(`Published. Copied to ${r.copied_to} student${r.copied_to === 1 ? '' : 's'}; new students get it when they join.`);
            setPick('');
            load();
        } catch (e) {
            setMsg(errText(e));
        } finally {
            setBusy(false);
        }
    };
    const remove = async (uid) => {
        if (!window.confirm('Remove this student? Their seat becomes free. (School-created accounts are switched off, not deleted.)')) return;
        await removeInstitutionMember(uid).catch(() => {});
        load();
    };
    if (!data) return <div className="flex items-center gap-2 text-[#5E5046]"><Loader2 className="h-4 w-4 animate-spin" /> Loading class…</div>;
    const link = `${window.location.origin}/join/${data.class.invite_code}`;
    const published = new Set(data.books.map((b) => b.document_id));
    return (
        <div className="space-y-5">
            <button onClick={back} className="flex items-center gap-1 text-sm font-semibold text-[#5E5046] hover:text-[#163628]"><ArrowLeft className="h-4 w-4" /> All classes</button>
            <Card className="flex flex-wrap items-center justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold text-[#163628]">{data.class.name}</h1>
                    <p className="text-sm text-[#5E5046]">{data.students.length} students</p>
                </div>
                <div className="flex flex-col items-end gap-1.5">
                    <CopyCode code={data.class.invite_code} label="class code" />
                    <button onClick={() => navigator.clipboard?.writeText(link)} className="text-xs font-semibold text-[#1E5C42] hover:underline">Copy invite link</button>
                </div>
            </Card>
            <div className="grid gap-5 lg:grid-cols-[1fr_1.6fr]">
                <div className="space-y-5">
                    <Card>
                        <h2 className="text-lg font-bold text-[#163628] flex items-center gap-2 mb-2"><BookOpen className="h-5 w-5 text-[#1E5C42]" /> Class books</h2>
                        {data.books.length === 0 && <p className="text-sm text-[#5E5046]">No books yet. Publish one from your projects.</p>}
                        <ul className="space-y-1.5 text-sm text-[#163628]">{data.books.map((b) => <li key={b.id}>📘 {b.title}</li>)}</ul>
                        <div className="mt-3 flex gap-2">
                            <select value={pick} onChange={(e) => setPick(e.target.value)} aria-label="Book to publish"
                                className="flex-1 min-w-0 rounded-xl border border-[#E6D5CC] bg-[#FDF6F0] px-3 py-2 text-sm">
                                <option value="">Choose one of your books…</option>
                                {books.filter((b) => !published.has(b.id)).map((b) => (
                                    <option key={b.id} value={b.id}>{b.filename} ({b.project})</option>
                                ))}
                            </select>
                            <button onClick={publish} disabled={!pick || busy}
                                className="rounded-xl bg-[#1E5C42] px-4 text-sm font-semibold text-white disabled:opacity-50">Publish</button>
                        </div>
                        {msg && <p className="mt-2 text-sm text-[#5E5046]">{msg}</p>}
                    </Card>
                    {data.class_weak_topics.length > 0 && (
                        <Card>
                            <h2 className="text-lg font-bold text-[#163628] mb-2">Where the class struggles</h2>
                            <ul className="space-y-1.5 text-sm">
                                {data.class_weak_topics.map(([t, n]) => (
                                    <li key={t} className="flex justify-between"><span className="text-[#163628]">{t}</span><span className="text-rose-600">{n} student{n === 1 ? '' : 's'}</span></li>
                                ))}
                            </ul>
                        </Card>
                    )}
                </div>
                <Card className="overflow-x-auto">
                    <h2 className="text-lg font-bold text-[#163628] mb-3">Students</h2>
                    {data.students.length === 0 ? (
                        <p className="text-sm text-[#5E5046]">Share the class code or invite link. Students appear here when they join.</p>
                    ) : (
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="text-left text-xs uppercase tracking-wide text-[#5E5046]">
                                    <th className="pb-2 pr-3">Student</th><th className="pb-2 pr-3">Mastered</th><th className="pb-2 pr-3">Accuracy</th>
                                    <th className="pb-2 pr-3">Days active (7d)</th><th className="pb-2 pr-3">Weak topics</th>{role === 'admin' && <th />}
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-[#E6D5CC]">
                                {data.students.map((s) => (
                                    <tr key={s.user_id} className="align-top">
                                        <td className="py-2 pr-3"><div className="font-semibold text-[#163628]">{s.name}{s.disabled && <span className="ml-1 text-xs font-normal text-rose-600">(off)</span>}</div><div className="text-xs text-[#5E5046] font-mono">{s.login_id || s.email}</div></td>
                                        <td className="py-2 pr-3 tabular-nums">{s.mastered}{s.total_topics ? ` / ${s.total_topics}` : ''}</td>
                                        <td className={`py-2 pr-3 tabular-nums ${s.accuracy != null && s.accuracy < 60 ? 'text-rose-600 font-semibold' : ''}`}>{s.accuracy != null ? `${s.accuracy}%` : '–'}</td>
                                        <td className="py-2 pr-3 tabular-nums">{s.active_days_7}</td>
                                        <td className="py-2 pr-3 text-xs text-[#5E5046]">{s.weak_topics.join(', ') || '–'}</td>
                                        {role === 'admin' && (
                                            <td className="py-2"><button onClick={() => remove(s.user_id)} className="text-[#5E5046] hover:text-rose-600" title="Remove student"><UserMinus className="h-4 w-4" /></button></td>
                                        )}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    )}
                </Card>
            </div>
        </div>
    );
};

// ----------------------------------------------------------- student home

const StudentHome = ({ data }) => {
    const navigate = useNavigate();
    return (
        <Card>
            <h1 className="text-2xl font-bold text-[#163628]">{data.institution.name}</h1>
            <p className="text-sm text-[#5E5046]">{data.live ? 'Your school gives you the Institution plan.' : (data.state_message || 'Your school\'s plan is paused. Ask your school.')}</p>
            <h2 className="mt-5 font-bold text-[#163628]">Your classes</h2>
            <div className="mt-2 divide-y divide-[#E6D5CC]">
                {data.classes.map((c) => (
                    <button key={c.id} onClick={() => navigate(`/project/${c.project_id}`)} className="w-full py-3 flex items-center justify-between text-left hover:bg-[#FDF6F0] rounded-xl px-2">
                        <span className="font-semibold text-[#163628]">{c.name}</span><ChevronRight className="h-5 w-5 text-[#5E5046]" />
                    </button>
                ))}
            </div>
            {data.live && <div className="mt-5"><JoinBox onJoined={(r) => r.project_id && navigate(`/project/${r.project_id}`)} /></div>}
        </Card>
    );
};

/** Institution plan: setup, staff dashboard, class dashboards and the student view. */
const Institution = () => {
    const navigate = useNavigate();
    const [data, setData] = useState(null);
    const [error, setError] = useState('');
    const [classId, setClassId] = useState(null);

    const load = useCallback(async () => {
        try {
            setData(await getMyInstitution());
        } catch (e) {
            setError(errText(e));
        }
    }, []);
    useEffect(() => { load(); }, [load]);

    const onJoined = (r) => {
        if (r.project_id) navigate(`/project/${r.project_id}`);
        else load();
    };

    return (
        <div className="min-h-[100dvh] bg-[#FDF6F0] text-[#163628]">
            <header className="mx-auto max-w-6xl px-4 py-5 flex items-center justify-between">
                <button onClick={() => navigate('/dashboard')} className="flex items-center gap-1.5 rounded-xl px-3 py-2 text-sm font-semibold hover:bg-white">
                    <ArrowLeft className="h-4 w-4" /> Dashboard
                </button>
                <span className="flex items-center gap-2 font-bold"><Building2 className="h-5 w-5 text-[#1E5C42]" /> Institution</span>
            </header>
            <main className="mx-auto max-w-6xl px-4 pb-16">
                {error && <p className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-rose-800">{error}</p>}
                {!data && !error && <div className="flex items-center gap-2 text-[#5E5046]"><Loader2 className="h-4 w-4 animate-spin" /> Loading…</div>}
                {data && !data.member && <Setup onCreated={setData} onJoined={onJoined} />}
                {data?.member && data.role === 'student' && <StudentHome data={data} />}
                {data?.member && data.role !== 'student' && (classId
                    ? <ClassView classId={classId} role={data.role} back={() => { setClassId(null); load(); }} />
                    : <StaffHome data={data} reload={load} openClass={setClassId} />)}
            </main>
        </div>
    );
};

export default Institution;
