import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Loader2, Search, UserPlus, Upload, Download, Copy, Check, KeyRound, Power, ChevronLeft, ChevronRight } from 'lucide-react';
import {
    listStudents, createStudents, resetStudentPassword, setStudentDisabled, addStudentToClass, apiErrorText,
} from '../../api';

const card = 'rounded-3xl border border-[#E6D5CC] bg-white p-5 md:p-6';
const input = 'w-full rounded-2xl border border-[#E6D5CC] bg-[#FDF6F0] px-4 py-2.5 outline-none focus:ring-2 focus:ring-[#C8A288]';

/** Minimal CSV reader: commas or tabs, quoted fields, first row may be a header. */
export const parseStudentCsv = (text, classes = []) => {
    const rows = [];
    for (const line of text.split(/\r?\n/)) {
        if (!line.trim()) continue;
        const sep = line.includes('\t') ? '\t' : ',';
        const cells = [];
        let cur = '';
        let quoted = false;
        for (let i = 0; i < line.length; i++) {
            const ch = line[i];
            if (ch === '"') {
                if (quoted && line[i + 1] === '"') { cur += '"'; i++; } else quoted = !quoted;
            } else if (ch === sep && !quoted) { cells.push(cur.trim()); cur = ''; } else cur += ch;
        }
        cells.push(cur.trim());
        rows.push(cells);
    }
    if (!rows.length) return { students: [], problems: [] };
    let cols = { name: 0, reg_no: 1, password: 2, class: 3 };
    const head = rows[0].map((h) => h.toLowerCase().replace(/[^a-z]/g, ''));
    if (head.some((h) => ['name', 'studentname', 'regno', 'registernumber', 'rollno', 'registerno'].includes(h))) {
        const find = (...keys) => head.findIndex((h) => keys.includes(h));
        cols = {
            name: find('name', 'studentname', 'fullname'),
            reg_no: find('regno', 'registernumber', 'registerno', 'rollno', 'rollnumber', 'regnumber'),
            password: find('password', 'pass'),
            class: find('class', 'classname', 'section'),
        };
        rows.shift();
    }
    const byName = Object.fromEntries(classes.map((c) => [c.name.trim().toLowerCase(), c.id]));
    const problems = [];
    const students = rows.map((r, i) => {
        const s = { name: r[cols.name] || '', reg_no: r[cols.reg_no] || '' };
        if (cols.password >= 0 && r[cols.password]) s.password = r[cols.password];
        const cls = cols.class >= 0 ? (r[cols.class] || '').trim() : '';
        if (cls) {
            if (byName[cls.toLowerCase()]) s.class_id = byName[cls.toLowerCase()];
            else problems.push(`Row ${i + 1}: no class called "${cls}" (create it first).`);
        }
        return s;
    }).filter((s) => s.name || s.reg_no);
    return { students, problems };
};

const csvCell = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`;

const download = (filename, text) => {
    const url = URL.createObjectURL(new Blob([text], { type: 'text/csv' }));
    const a = Object.assign(document.createElement('a'), { href: url, download: filename });
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
};

/** New sign-ins with their passwords: shown once, to copy or download. */
const Credentials = ({ result, onClose }) => {
    const [copied, setCopied] = useState(false);
    const rows = result.created || [];
    const text = rows.map((r) => `${r.name}\t${r.login_id}\t${r.password}`).join('\n');
    const csv = ['Name,Register no,Sign-in ID,Password,Class', ...rows.map((r) =>
        [r.name, r.reg_no, r.login_id, r.password, r.class || ''].map(csvCell).join(','))].join('\n');
    return (
        <div className={`${card} border-emerald-300`}>
            <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="font-bold text-[#4A3B32]">{rows.length} account{rows.length === 1 ? '' : 's'} ready</h3>
                <div className="flex gap-2">
                    {rows.length > 0 && (
                        <>
                            <button onClick={() => { navigator.clipboard?.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1500); }}
                                className="inline-flex items-center gap-1 rounded-xl border border-[#E6D5CC] px-3 py-1.5 text-sm font-semibold">
                                {copied ? <Check className="h-4 w-4 text-emerald-600" /> : <Copy className="h-4 w-4" />} Copy
                            </button>
                            <button onClick={() => download('student-sign-ins.csv', csv)}
                                className="inline-flex items-center gap-1 rounded-xl bg-[#4A3B32] px-3 py-1.5 text-sm font-semibold text-white">
                                <Download className="h-4 w-4" /> Download CSV
                            </button>
                        </>
                    )}
                    <button onClick={onClose} className="rounded-xl px-3 py-1.5 text-sm font-semibold text-[#8a6a5c]">Done</button>
                </div>
            </div>
            {rows.length > 0 && (
                <p className="mt-1 text-sm text-amber-800">Save these now: passwords aren't shown again. Students choose their own password at first sign-in.</p>
            )}
            {rows.length > 0 && (
                <div className="mt-3 max-h-72 overflow-auto">
                    <table className="w-full text-sm">
                        <thead><tr className="text-left text-xs uppercase tracking-wide text-[#8a6a5c]"><th className="pb-2 pr-3">Student</th><th className="pb-2 pr-3">Sign-in ID</th><th className="pb-2">Password</th></tr></thead>
                        <tbody className="divide-y divide-[#E6D5CC]">
                            {rows.map((r) => (
                                <tr key={r.user_id}><td className="py-1.5 pr-3">{r.name}</td><td className="py-1.5 pr-3 font-mono">{r.login_id}</td><td className="py-1.5 font-mono">{r.password}</td></tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
            {result.failed?.length > 0 && (
                <div className="mt-3 rounded-2xl bg-rose-50 p-3 text-sm text-rose-800">
                    <div className="font-semibold">{result.failed.length} not created</div>
                    <ul className="mt-1 space-y-0.5">
                        {result.failed.map((f, i) => <li key={i}>{f.name || '(no name)'} {f.reg_no ? `(${f.reg_no})` : ''}: {f.error}</li>)}
                    </ul>
                </div>
            )}
        </div>
    );
};

const AddStudents = ({ classes, domain, onCreated, disabled }) => {
    const [mode, setMode] = useState('one');
    const [one, setOne] = useState({ name: '', reg_no: '', password: '', class_id: '', login_id: '' });
    const [csv, setCsv] = useState('');
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    const parsed = useMemo(() => parseStudentCsv(csv, classes), [csv, classes]);
    const preview = useMemo(() => {
        const slug = (one.name || '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]/g, '').slice(0, 24) || 'student';
        const digits = (one.reg_no || '').replace(/\D/g, '');
        return digits ? `${slug}-${digits.slice(-2).padStart(2, '0')}@${domain}` : '';
    }, [one.name, one.reg_no, domain]);

    const submit = async (students) => {
        setBusy(true); setError('');
        try {
            const r = await createStudents(students);
            onCreated(r);
            setOne({ name: '', reg_no: '', password: '', class_id: '', login_id: '' });
            setCsv('');
        } catch (e) {
            setError(apiErrorText(e));
        } finally {
            setBusy(false);
        }
    };
    const set = (k) => (e) => setOne({ ...one, [k]: e.target.value });
    const readFile = async (e) => {
        const f = e.target.files?.[0];
        if (f) setCsv(await f.text());
        e.target.value = '';
    };

    return (
        <div className={card}>
            <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 className="text-lg font-bold text-[#4A3B32] flex items-center gap-2"><UserPlus className="h-5 w-5 text-[#C8A288]" /> Create student sign-ins</h2>
                <div className="flex gap-1 rounded-2xl bg-[#FDF6F0] p-1">
                    {[['one', 'One student'], ['many', 'Many (CSV)']].map(([id, label]) => (
                        <button key={id} onClick={() => setMode(id)}
                            className={`rounded-xl px-3 py-1 text-sm font-semibold ${mode === id ? 'bg-white shadow text-[#4A3B32]' : 'text-[#8a6a5c]'}`}>{label}</button>
                    ))}
                </div>
            </div>
            <p className="mt-1 text-sm text-[#8a6a5c]">
                Each student gets an ID like <span className="font-mono">name-07@{domain}</span> (07 = last two digits of the register number). It's only for signing in; no email is sent.
            </p>
            {disabled && <p className="mt-2 text-sm text-amber-800">Available once your school is approved and paid up.</p>}

            {mode === 'one' ? (
                <form onSubmit={(e) => { e.preventDefault(); submit([{ ...one, password: one.password || null, class_id: one.class_id || null, login_id: one.login_id || null }]); }}
                    className="mt-4 grid gap-3 sm:grid-cols-2">
                    <input required value={one.name} onChange={set('name')} placeholder="Student name" className={input} aria-label="Student name" />
                    <input required value={one.reg_no} onChange={set('reg_no')} placeholder="Register number" className={input} aria-label="Register number" />
                    <input value={one.password} onChange={set('password')} placeholder="Password (blank = we make one)" className={input} aria-label="Password" />
                    <select value={one.class_id} onChange={set('class_id')} className={input} aria-label="Class">
                        <option value="">No class yet</option>
                        {classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                    </select>
                    <input value={one.login_id} onChange={set('login_id')} placeholder={preview ? `ID: ${preview}` : 'Custom ID (optional)'}
                        className={`${input} sm:col-span-2 font-mono text-sm`} aria-label="Custom sign-in ID" />
                    {error && <p className="text-sm text-rose-600 sm:col-span-2">{error}</p>}
                    <button disabled={busy || disabled} className="sm:col-span-2 rounded-2xl bg-[#4A3B32] px-4 py-3 font-semibold text-white disabled:opacity-50">
                        {busy ? <Loader2 className="mx-auto h-5 w-5 animate-spin" /> : 'Create sign-in'}
                    </button>
                </form>
            ) : (
                <div className="mt-4 space-y-3">
                    <p className="text-xs text-[#8a6a5c]">Columns: <span className="font-mono">name, reg_no, password, class</span>. Password and class are optional; class must match a class name. Up to 500 at a time.</p>
                    <textarea value={csv} onChange={(e) => setCsv(e.target.value)} rows={6} className={`${input} font-mono text-sm`}
                        placeholder={'name,reg_no,password,class\nArun Kumar,21CS107,,10 A\nPriya S,21CS112,Welcome123,10 A'} aria-label="Students CSV" />
                    <div className="flex flex-wrap items-center gap-3">
                        <label className="inline-flex cursor-pointer items-center gap-1 rounded-xl border border-[#E6D5CC] px-3 py-1.5 text-sm font-semibold">
                            <Upload className="h-4 w-4" /> Upload .csv
                            <input type="file" accept=".csv,.txt,text/csv" onChange={readFile} className="hidden" />
                        </label>
                        <span className="text-sm text-[#8a6a5c]">{parsed.students.length} student{parsed.students.length === 1 ? '' : 's'} found</span>
                    </div>
                    {parsed.problems.length > 0 && <ul className="text-sm text-amber-800">{parsed.problems.slice(0, 5).map((p) => <li key={p}>{p}</li>)}</ul>}
                    {error && <p className="text-sm text-rose-600">{error}</p>}
                    <button onClick={() => submit(parsed.students)} disabled={busy || disabled || !parsed.students.length || parsed.students.length > 500 || parsed.problems.length > 0}
                        className="w-full rounded-2xl bg-[#4A3B32] px-4 py-3 font-semibold text-white disabled:opacity-50">
                        {busy ? <span className="inline-flex items-center gap-2"><Loader2 className="h-5 w-5 animate-spin" /> Creating…</span> : `Create ${parsed.students.length || ''} sign-ins`}
                    </button>
                </div>
            )}
        </div>
    );
};

const StudentRow = ({ s, role, classes, onChanged, onReset }) => {
    const [busy, setBusy] = useState('');
    const [pick, setPick] = useState('');
    const [error, setError] = useState('');
    const act = async (name, fn) => {
        setBusy(name); setError('');
        try { await fn(); onChanged(); } catch (e) { setError(apiErrorText(e)); } finally { setBusy(''); }
    };
    return (
        <tr className="align-top">
            <td className="py-2 pr-3">
                <div className={`font-semibold ${s.disabled ? 'text-[#8a6a5c] line-through' : 'text-[#4A3B32]'}`}>{s.display_name || '—'}</div>
                <div className="text-xs text-[#8a6a5c]">{s.reg_no || ''}{s.classes?.length ? ` · ${s.classes.join(', ')}` : ''}</div>
                {error && <div className="text-xs text-rose-600">{error}</div>}
            </td>
            <td className="py-2 pr-3 font-mono text-xs break-all">
                {s.login_id || s.email}
                {s.managed && s.must_change_password && !s.disabled && <div className="font-sans text-[11px] text-amber-700">Hasn't set own password yet</div>}
                {!s.managed && <div className="font-sans text-[11px] text-[#8a6a5c]">Own account</div>}
            </td>
            <td className="py-2">
                <div className="flex flex-wrap items-center gap-1.5">
                    {s.managed && !s.disabled && (
                        <button onClick={() => act('reset', async () => onReset(s, await resetStudentPassword(s.user_id)))} disabled={!!busy}
                            className="inline-flex items-center gap-1 rounded-lg border border-[#E6D5CC] px-2 py-1 text-xs font-semibold" title="Set a new password">
                            {busy === 'reset' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <KeyRound className="h-3.5 w-3.5" />} Reset password
                        </button>
                    )}
                    {role === 'admin' && (
                        <button onClick={() => act('power', () => setStudentDisabled(s.user_id, !s.disabled))} disabled={!!busy}
                            className={`inline-flex items-center gap-1 rounded-lg border px-2 py-1 text-xs font-semibold ${s.disabled ? 'border-emerald-300 text-emerald-700' : 'border-rose-200 text-rose-700'}`}>
                            {busy === 'power' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Power className="h-3.5 w-3.5" />} {s.disabled ? 'Switch on' : 'Switch off'}
                        </button>
                    )}
                    {!s.disabled && classes.length > 0 && (
                        <select value={pick} disabled={!!busy} aria-label="Add to class"
                            onChange={(e) => { const c = e.target.value; setPick(''); if (c) act('class', () => addStudentToClass(s.user_id, c)); }}
                            className="rounded-lg border border-[#E6D5CC] bg-white px-1.5 py-1 text-xs">
                            <option value="">+ Class</option>
                            {classes.filter((c) => !(s.classes || []).includes(c.name)).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                        </select>
                    )}
                </div>
            </td>
        </tr>
    );
};

/** Staff view of every student: create sign-ins, search, reset passwords, switch accounts off. */
const StudentsPanel = ({ data, onChanged }) => {
    const [q, setQ] = useState('');
    const [classId, setClassId] = useState('');
    const [page, setPage] = useState(1);
    const [list, setList] = useState(null);
    const [error, setError] = useState('');
    const [result, setResult] = useState(null);
    const [reset, setReset] = useState(null);
    const classes = data.classes || [];
    const live = data.live;

    const load = useCallback(async () => {
        try {
            setList(await listStudents({ q, classId, page, pageSize: 50 }));
            setError('');
        } catch (e) {
            setError(apiErrorText(e));
        }
    }, [q, classId, page]);
    useEffect(() => {
        const t = setTimeout(load, q ? 300 : 0);
        return () => clearTimeout(t);
    }, [load, q]);

    const pages = list ? Math.max(1, Math.ceil(list.total / list.page_size)) : 1;
    const created = (r) => { setResult(r); setReset(null); load(); onChanged?.(); };

    return (
        <div className="space-y-5">
            {result && <Credentials result={result} onClose={() => setResult(null)} />}
            {reset && (
                <div className={`${card} border-emerald-300 flex flex-wrap items-center justify-between gap-3`}>
                    <div className="text-sm">
                        New password for <span className="font-mono">{reset.login_id}</span>: <span className="font-mono font-bold text-base">{reset.password}</span>
                        <div className="text-xs text-[#8a6a5c]">They'll be asked to choose their own after signing in.</div>
                    </div>
                    <div className="flex gap-2">
                        <button onClick={() => navigator.clipboard?.writeText(`${reset.login_id}\t${reset.password}`)} className="rounded-xl border border-[#E6D5CC] px-3 py-1.5 text-sm font-semibold"><Copy className="inline h-4 w-4" /> Copy</button>
                        <button onClick={() => setReset(null)} className="rounded-xl px-3 py-1.5 text-sm font-semibold text-[#8a6a5c]">Done</button>
                    </div>
                </div>
            )}
            <AddStudents classes={classes} domain={data.login_domain || 'luminaiq.fun'} onCreated={created} disabled={!live} />
            <div className={card}>
                <div className="flex flex-wrap items-center gap-3">
                    <h2 className="text-lg font-bold text-[#4A3B32] mr-auto">Students {list ? <span className="text-sm font-normal text-[#8a6a5c]">({list.total})</span> : null}</h2>
                    <div className="relative">
                        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#8a6a5c]" />
                        <input value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} placeholder="Name, ID or reg. no"
                            className="w-56 rounded-2xl border border-[#E6D5CC] bg-[#FDF6F0] py-2 pl-9 pr-3 text-sm outline-none focus:ring-2 focus:ring-[#C8A288]" aria-label="Search students" />
                    </div>
                    <select value={classId} onChange={(e) => { setClassId(e.target.value); setPage(1); }} aria-label="Filter by class"
                        className="rounded-2xl border border-[#E6D5CC] bg-[#FDF6F0] px-3 py-2 text-sm">
                        <option value="">All classes</option>
                        {classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                    </select>
                </div>
                {error && <p className="mt-3 text-sm text-rose-600">{error}</p>}
                {!list ? (
                    <div className="mt-4 flex items-center gap-2 text-[#8a6a5c]"><Loader2 className="h-4 w-4 animate-spin" /> Loading…</div>
                ) : list.students.length === 0 ? (
                    <p className="mt-4 text-sm text-[#8a6a5c]">{q || classId ? 'No students match.' : 'No students yet. Create sign-ins above or share a class code.'}</p>
                ) : (
                    <div className="mt-3 overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="text-left text-xs uppercase tracking-wide text-[#8a6a5c]"><th className="pb-2 pr-3">Student</th><th className="pb-2 pr-3">Sign-in</th><th className="pb-2" /></tr>
                            </thead>
                            <tbody className="divide-y divide-[#E6D5CC]">
                                {list.students.map((s) => (
                                    <StudentRow key={s.user_id} s={s} role={data.role} classes={classes} onChanged={() => { load(); onChanged?.(); }}
                                        onReset={(st, r) => { setResult(null); setReset({ login_id: r.login_id || st.login_id, password: r.password }); }} />
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
                {pages > 1 && (
                    <div className="mt-3 flex items-center justify-end gap-2 text-sm">
                        <button onClick={() => setPage(page - 1)} disabled={page <= 1} className="rounded-lg border border-[#E6D5CC] p-1 disabled:opacity-40" aria-label="Previous page"><ChevronLeft className="h-4 w-4" /></button>
                        <span className="tabular-nums">{page} / {pages}</span>
                        <button onClick={() => setPage(page + 1)} disabled={page >= pages} className="rounded-lg border border-[#E6D5CC] p-1 disabled:opacity-40" aria-label="Next page"><ChevronRight className="h-4 w-4" /></button>
                    </div>
                )}
            </div>
        </div>
    );
};

export default StudentsPanel;
