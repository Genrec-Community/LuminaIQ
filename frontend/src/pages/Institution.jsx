import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    ArrowLeft, Building2, Copy, Check, Loader2, Plus, Users, BookOpen, ChevronRight, UserMinus,
    KeyRound, AlertTriangle, GraduationCap,
} from 'lucide-react';
import {
    getMyInstitution, createInstitution, joinWithCode, createClass, getClassDashboard,
    publishBookToClass, getPublishableBooks, removeInstitutionMember, startSeatsCheckout, verifyPayment,
} from '../api';
import { emitPlanChanged } from '../utils/plan';
import { openCheckout } from '../utils/razorpay';
import { inr } from '../utils/pricing';
import { isNativeApp } from '../utils/platform';

const errText = (e) => e?.response?.data?.detail?.message || e?.response?.data?.detail || e?.message || 'Something went wrong.';
const fmtDate = (iso) => (iso ? new Date(iso).toLocaleDateString([], { day: 'numeric', month: 'short', year: 'numeric' }) : '');

const Card = ({ children, className = '' }) => (
    <div className={`rounded-3xl border border-[#E6D5CC] bg-white p-5 md:p-6 ${className}`}>{children}</div>
);

const CopyCode = ({ code, label }) => {
    const [done, setDone] = useState(false);
    return (
        <button onClick={() => { navigator.clipboard?.writeText(code); setDone(true); setTimeout(() => setDone(false), 1500); }}
            className="inline-flex items-center gap-2 rounded-xl border border-[#E6D5CC] bg-[#FDF6F0] px-3 py-1.5 font-mono text-sm font-bold tracking-wider text-[#4A3B32] hover:border-[#C8A288]"
            title={`Copy ${label}`}>
            {code} {done ? <Check className="h-4 w-4 text-emerald-600" /> : <Copy className="h-4 w-4 text-[#8a6a5c]" />}
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
            <label className="text-sm font-semibold text-[#4A3B32]" htmlFor="join-code">Have a code from your teacher or school?</label>
            <div className="mt-2 flex gap-2">
                <input id="join-code" value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} placeholder="C-ABC123"
                    className="flex-1 rounded-2xl border border-[#E6D5CC] bg-[#FDF6F0] px-4 py-3 font-mono tracking-wider outline-none focus:ring-2 focus:ring-[#C8A288]" />
                <button disabled={busy || code.trim().length < 4}
                    className="rounded-2xl bg-[#C8A288] px-5 font-semibold text-white hover:bg-[#B08B72] disabled:opacity-50">
                    {busy ? <Loader2 className="h-5 w-5 animate-spin" /> : 'Join'}
                </button>
            </div>
            {error && <p className="mt-2 text-sm text-rose-600">{error}</p>}
        </form>
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
    const input = 'w-full rounded-2xl border border-[#E6D5CC] bg-[#FDF6F0] px-4 py-3 outline-none focus:ring-2 focus:ring-[#C8A288]';
    return (
        <div className="grid gap-5 md:grid-cols-[1.4fr_1fr]">
            <Card>
                <h2 className="text-xl font-bold text-[#4A3B32] flex items-center gap-2"><Building2 className="h-5 w-5 text-[#C8A288]" /> Set up your institution</h2>
                <p className="text-sm text-[#8a6a5c] mt-1">Free 14-day trial for up to 25 students. Then {inr(179)} per student per month + GST, billed yearly.</p>
                <form onSubmit={submit} className="mt-4 space-y-3">
                    <input required minLength={2} value={form.name} onChange={set('name')} placeholder="School or institute name" className={input} />
                    <input value={form.billing_name} onChange={set('billing_name')} placeholder="Billing name (for invoices, optional)" className={input} />
                    <div className="grid sm:grid-cols-2 gap-3">
                        <input value={form.gstin} onChange={set('gstin')} maxLength={15} placeholder="GSTIN (optional)" className={`${input} uppercase`} />
                        <input type="email" value={form.contact_email} onChange={set('contact_email')} placeholder="Billing email (optional)" className={input} />
                    </div>
                    {error && <p className="text-sm text-rose-600">{error}</p>}
                    <button disabled={busy} className="w-full rounded-2xl bg-[#4A3B32] px-4 py-3 font-semibold text-white hover:bg-[#3a2e27] disabled:opacity-60">
                        {busy ? 'Creating…' : 'Start free trial'}
                    </button>
                </form>
            </Card>
            <Card>
                <h2 className="text-xl font-bold text-[#4A3B32] flex items-center gap-2"><KeyRound className="h-5 w-5 text-[#C8A288]" /> Join with a code</h2>
                <p className="text-sm text-[#8a6a5c] mt-1 mb-4">Students: use your class code. Teachers: use your institution's teacher code.</p>
                <JoinBox onJoined={onJoined} />
            </Card>
        </div>
    );
};

// -------------------------------------------------------------- staff home

const SeatsBox = ({ data, onPaid }) => {
    const min = Math.max(data.pricing.min_seats, data.students);
    const [seats, setSeats] = useState(Math.max(min, data.institution.status === 'active' ? data.institution.seats : min));
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    const base = seats * data.pricing.per_seat_inr * 12;
    const gst = Math.round(base * data.pricing.gst_rate);
    const pay = async () => {
        setBusy(true); setError('');
        try {
            const co = await startSeatsCheckout(seats);
            const resp = await openCheckout({
                key: co.key_id, order_id: co.order_id, amount: co.amount_paise, currency: 'INR',
                name: co.name, description: co.description, prefill: co.prefill,
            });
            await verifyPayment({ kind: 'seats', ...resp });
            emitPlanChanged();
            onPaid();
        } catch (e) {
            if (!e?.dismissed) setError(errText(e));
        } finally {
            setBusy(false);
        }
    };
    if (isNativeApp()) return null;
    return (
        <Card>
            <h3 className="font-bold text-[#4A3B32]">{data.institution.status === 'active' ? 'Renew or add seats' : 'Activate for a full year'}</h3>
            <div className="mt-3 flex flex-wrap items-center gap-3">
                <label className="text-sm text-[#8a6a5c]" htmlFor="seats">Students</label>
                <input id="seats" type="number" min={min} step={10} value={seats}
                    onChange={(e) => setSeats(Math.max(1, Number(e.target.value) || 0))}
                    className="w-28 rounded-xl border border-[#E6D5CC] bg-[#FDF6F0] px-3 py-2 tabular-nums" />
                <span className="text-sm text-[#8a6a5c]">× {inr(data.pricing.per_seat_inr)} × 12 months</span>
            </div>
            <div className="mt-3 text-sm text-[#4A3B32] space-y-0.5 tabular-nums">
                <div className="flex justify-between"><span>Subtotal</span><span>{inr(base)}</span></div>
                <div className="flex justify-between"><span>GST (18%)</span><span>{inr(gst)}</span></div>
                <div className="flex justify-between font-bold"><span>Total for 1 year</span><span>{inr(base + gst)}</span></div>
            </div>
            {seats < min && <p className="mt-2 text-sm text-rose-600">Choose at least {min} students.</p>}
            {error && <p className="mt-2 text-sm text-rose-600">{error}</p>}
            <button onClick={pay} disabled={busy || seats < min}
                className="mt-4 w-full rounded-2xl bg-[#C8A288] px-4 py-3 font-semibold text-white hover:bg-[#B08B72] disabled:opacity-50">
                {busy ? <Loader2 className="mx-auto h-5 w-5 animate-spin" /> : `Pay ${inr(base + gst)}`}
            </button>
        </Card>
    );
};

const StaffHome = ({ data, reload, openClass }) => {
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
                    <h1 className="text-2xl font-bold text-[#4A3B32]">{inst.name}</h1>
                    <p className="text-sm text-[#8a6a5c]">
                        {inst.status === 'trial' ? `Free trial until ${fmtDate(inst.paid_until)}` : `Active until ${fmtDate(inst.paid_until)}`}
                        {' · '}{data.students} / {inst.seats} students
                    </p>
                </div>
                <div className="text-right">
                    <div className="text-xs font-semibold uppercase tracking-wide text-[#8a6a5c] mb-1">Teacher code</div>
                    <CopyCode code={inst.teacher_code} label="teacher code" />
                </div>
            </Card>
            {!data.live && (
                <div className="rounded-2xl border border-amber-300 bg-amber-50 p-4 text-amber-900 flex gap-2">
                    <AlertTriangle className="h-5 w-5 shrink-0" /> Your plan has ended. Students keep their books but lose institution access until you renew.
                </div>
            )}
            <div className="grid gap-5 lg:grid-cols-[1.5fr_1fr]">
                <Card>
                    <div className="flex items-center justify-between mb-3">
                        <h2 className="text-lg font-bold text-[#4A3B32] flex items-center gap-2"><GraduationCap className="h-5 w-5 text-[#C8A288]" /> Classes</h2>
                    </div>
                    {data.classes.length === 0 && <p className="text-sm text-[#8a6a5c] mb-3">Create a class, then share its code with students.</p>}
                    <div className="divide-y divide-[#E6D5CC]">
                        {data.classes.map((c) => (
                            <button key={c.id} onClick={() => openClass(c.id)} className="w-full py-3 flex items-center gap-3 text-left hover:bg-[#FDF6F0] rounded-xl px-2">
                                <div className="flex-1 min-w-0">
                                    <div className="font-semibold text-[#4A3B32] truncate">{c.name}</div>
                                    <div className="text-xs text-[#8a6a5c]">{c.students} students · code {c.invite_code}</div>
                                </div>
                                <ChevronRight className="h-5 w-5 text-[#8a6a5c]" />
                            </button>
                        ))}
                    </div>
                    <form onSubmit={add} className="mt-3 flex gap-2">
                        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="New class, e.g. 12 Science A"
                            className="flex-1 rounded-2xl border border-[#E6D5CC] bg-[#FDF6F0] px-4 py-2.5 outline-none focus:ring-2 focus:ring-[#C8A288]" />
                        <button disabled={busy || !name.trim()} className="rounded-2xl bg-[#C8A288] px-4 font-semibold text-white disabled:opacity-50 flex items-center gap-1">
                            <Plus className="h-4 w-4" /> Add
                        </button>
                    </form>
                    {error && <p className="mt-2 text-sm text-rose-600">{error}</p>}
                </Card>
                <div className="space-y-5">
                    {data.role === 'admin' && <SeatsBox data={data} onPaid={reload} />}
                    <Card>
                        <h2 className="text-lg font-bold text-[#4A3B32] flex items-center gap-2 mb-2"><Users className="h-5 w-5 text-[#C8A288]" /> Staff</h2>
                        <ul className="space-y-2">
                            {data.teachers.map((t) => (
                                <li key={t.user_id} className="flex items-center justify-between text-sm">
                                    <span className="text-[#4A3B32]">{t.name || t.email} <span className="text-[#8a6a5c]">· {t.role}</span></span>
                                    {data.role === 'admin' && t.role === 'teacher' && (
                                        <button onClick={() => removeTeacher(t.user_id)} className="text-[#8a6a5c] hover:text-rose-600" title="Remove"><UserMinus className="h-4 w-4" /></button>
                                    )}
                                </li>
                            ))}
                        </ul>
                        <p className="mt-3 text-xs text-[#8a6a5c]">Teachers join with the teacher code above.</p>
                    </Card>
                </div>
            </div>
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
        if (!window.confirm('Remove this student? Their seat becomes free.')) return;
        await removeInstitutionMember(uid).catch(() => {});
        load();
    };
    if (!data) return <div className="flex items-center gap-2 text-[#8a6a5c]"><Loader2 className="h-4 w-4 animate-spin" /> Loading class…</div>;
    const link = `${window.location.origin}/join/${data.class.invite_code}`;
    const published = new Set(data.books.map((b) => b.document_id));
    return (
        <div className="space-y-5">
            <button onClick={back} className="flex items-center gap-1 text-sm font-semibold text-[#8a6a5c] hover:text-[#4A3B32]"><ArrowLeft className="h-4 w-4" /> All classes</button>
            <Card className="flex flex-wrap items-center justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold text-[#4A3B32]">{data.class.name}</h1>
                    <p className="text-sm text-[#8a6a5c]">{data.students.length} students</p>
                </div>
                <div className="flex flex-col items-end gap-1.5">
                    <CopyCode code={data.class.invite_code} label="class code" />
                    <button onClick={() => navigator.clipboard?.writeText(link)} className="text-xs font-semibold text-[#C8A288] hover:underline">Copy invite link</button>
                </div>
            </Card>
            <div className="grid gap-5 lg:grid-cols-[1fr_1.6fr]">
                <div className="space-y-5">
                    <Card>
                        <h2 className="text-lg font-bold text-[#4A3B32] flex items-center gap-2 mb-2"><BookOpen className="h-5 w-5 text-[#C8A288]" /> Class books</h2>
                        {data.books.length === 0 && <p className="text-sm text-[#8a6a5c]">No books yet. Publish one from your projects.</p>}
                        <ul className="space-y-1.5 text-sm text-[#4A3B32]">{data.books.map((b) => <li key={b.id}>📘 {b.title}</li>)}</ul>
                        <div className="mt-3 flex gap-2">
                            <select value={pick} onChange={(e) => setPick(e.target.value)} aria-label="Book to publish"
                                className="flex-1 min-w-0 rounded-xl border border-[#E6D5CC] bg-[#FDF6F0] px-3 py-2 text-sm">
                                <option value="">Choose one of your books…</option>
                                {books.filter((b) => !published.has(b.id)).map((b) => (
                                    <option key={b.id} value={b.id}>{b.filename} ({b.project})</option>
                                ))}
                            </select>
                            <button onClick={publish} disabled={!pick || busy}
                                className="rounded-xl bg-[#C8A288] px-4 text-sm font-semibold text-white disabled:opacity-50">Publish</button>
                        </div>
                        {msg && <p className="mt-2 text-sm text-[#8a6a5c]">{msg}</p>}
                    </Card>
                    {data.class_weak_topics.length > 0 && (
                        <Card>
                            <h2 className="text-lg font-bold text-[#4A3B32] mb-2">Where the class struggles</h2>
                            <ul className="space-y-1.5 text-sm">
                                {data.class_weak_topics.map(([t, n]) => (
                                    <li key={t} className="flex justify-between"><span className="text-[#4A3B32]">{t}</span><span className="text-rose-600">{n} student{n === 1 ? '' : 's'}</span></li>
                                ))}
                            </ul>
                        </Card>
                    )}
                </div>
                <Card className="overflow-x-auto">
                    <h2 className="text-lg font-bold text-[#4A3B32] mb-3">Students</h2>
                    {data.students.length === 0 ? (
                        <p className="text-sm text-[#8a6a5c]">Share the class code or invite link. Students appear here when they join.</p>
                    ) : (
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="text-left text-xs uppercase tracking-wide text-[#8a6a5c]">
                                    <th className="pb-2 pr-3">Student</th><th className="pb-2 pr-3">Mastered</th><th className="pb-2 pr-3">Accuracy</th>
                                    <th className="pb-2 pr-3">Days active (7d)</th><th className="pb-2 pr-3">Weak topics</th>{role === 'admin' && <th />}
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-[#E6D5CC]">
                                {data.students.map((s) => (
                                    <tr key={s.user_id} className="align-top">
                                        <td className="py-2 pr-3"><div className="font-semibold text-[#4A3B32]">{s.name}</div><div className="text-xs text-[#8a6a5c]">{s.email}</div></td>
                                        <td className="py-2 pr-3 tabular-nums">{s.mastered}{s.total_topics ? ` / ${s.total_topics}` : ''}</td>
                                        <td className={`py-2 pr-3 tabular-nums ${s.accuracy != null && s.accuracy < 60 ? 'text-rose-600 font-semibold' : ''}`}>{s.accuracy != null ? `${s.accuracy}%` : '–'}</td>
                                        <td className="py-2 pr-3 tabular-nums">{s.active_days_7}</td>
                                        <td className="py-2 pr-3 text-xs text-[#8a6a5c]">{s.weak_topics.join(', ') || '–'}</td>
                                        {role === 'admin' && (
                                            <td className="py-2"><button onClick={() => remove(s.user_id)} className="text-[#8a6a5c] hover:text-rose-600" title="Remove student"><UserMinus className="h-4 w-4" /></button></td>
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
            <h1 className="text-2xl font-bold text-[#4A3B32]">{data.institution.name}</h1>
            <p className="text-sm text-[#8a6a5c]">Your school gives you the Institution plan{data.live ? '' : ' (currently paused, so ask your school to renew)'}.</p>
            <h2 className="mt-5 font-bold text-[#4A3B32]">Your classes</h2>
            <div className="mt-2 divide-y divide-[#E6D5CC]">
                {data.classes.map((c) => (
                    <button key={c.id} onClick={() => navigate(`/project/${c.project_id}`)} className="w-full py-3 flex items-center justify-between text-left hover:bg-[#FDF6F0] rounded-xl px-2">
                        <span className="font-semibold text-[#4A3B32]">{c.name}</span><ChevronRight className="h-5 w-5 text-[#8a6a5c]" />
                    </button>
                ))}
            </div>
            <div className="mt-5"><JoinBox onJoined={(r) => r.project_id && navigate(`/project/${r.project_id}`)} /></div>
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
        <div className="min-h-[100dvh] bg-[#FDF6F0] text-[#4A3B32]">
            <header className="mx-auto max-w-6xl px-4 py-5 flex items-center justify-between">
                <button onClick={() => navigate('/dashboard')} className="flex items-center gap-1.5 rounded-xl px-3 py-2 text-sm font-semibold hover:bg-white">
                    <ArrowLeft className="h-4 w-4" /> Dashboard
                </button>
                <span className="flex items-center gap-2 font-bold"><Building2 className="h-5 w-5 text-[#C8A288]" /> Institution</span>
            </header>
            <main className="mx-auto max-w-6xl px-4 pb-16">
                {error && <p className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-rose-800">{error}</p>}
                {!data && !error && <div className="flex items-center gap-2 text-[#8a6a5c]"><Loader2 className="h-4 w-4 animate-spin" /> Loading…</div>}
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
