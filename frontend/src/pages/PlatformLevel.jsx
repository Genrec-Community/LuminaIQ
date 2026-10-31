import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Loader2, Check } from 'lucide-react';
import { getPlatformMe, getPlatformLevels, updatePlatformLevel, apiErrorText } from '../api';
import ToolToggles, { SettingRow } from '../components/ToolToggles';

/**
 * Platform admin: one level (e.g. Class 5-10). Choose which tools learners at
 * this level get, whether hints-first starts on, and whether answers may go
 * beyond the book. Schools can narrow these per class, never widen them.
 */
const PlatformLevel = () => {
    const { level } = useParams();
    const navigate = useNavigate();
    const [allowed, setAllowed] = useState(null);
    const [catalog, setCatalog] = useState(null);
    const [form, setForm] = useState(null);
    const [saved, setSaved] = useState(null);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    const [done, setDone] = useState(false);

    useEffect(() => { getPlatformMe().then((r) => setAllowed(r.platform_admin)).catch(() => setAllowed(false)); }, []);
    useEffect(() => {
        if (!allowed) return;
        getPlatformLevels().then((data) => {
            setCatalog(data);
            const lv = data.levels.find((l) => l.key === level);
            if (!lv) { setError('Unknown level.'); return; }
            const state = { tools: lv.tools, hints_default: lv.hints_default, outside_book: lv.outside_book };
            setForm(state);
            setSaved(state);
        }).catch((e) => setError(apiErrorText(e)));
    }, [allowed, level]);

    const meta = catalog?.levels.find((l) => l.key === level);
    const dirty = form && saved && JSON.stringify(form) !== JSON.stringify(saved);

    const save = async () => {
        setBusy(true); setError(''); setDone(false);
        try {
            const tools = Object.fromEntries(catalog.tools.map((t) => [t.key, form.tools.includes(t.key)]));
            const res = await updatePlatformLevel(level, { tools, hints_default: form.hints_default, outside_book: form.outside_book });
            const state = { tools: res.tools, hints_default: res.hints_default, outside_book: res.outside_book };
            setForm(state); setSaved(state); setDone(true);
        } catch (e) {
            setError(apiErrorText(e));
        } finally {
            setBusy(false);
        }
    };

    return (
        <div className="min-h-[100dvh] bg-[#FDF6F0] text-[#163628]">
            <header className="mx-auto max-w-4xl px-4 py-5 flex items-center justify-between">
                <button onClick={() => navigate('/platform?tab=levels')} className="flex items-center gap-1.5 rounded-xl px-3 py-2 text-sm font-semibold hover:bg-white">
                    <ArrowLeft className="h-4 w-4" /> All levels
                </button>
                <span className="font-bold">Levels &amp; tools</span>
            </header>
            <main className="mx-auto max-w-4xl px-4 pb-16">
                {allowed === null && <div className="flex items-center gap-2 text-[#5E5046]"><Loader2 className="h-4 w-4 animate-spin" /> Checking access…</div>}
                {allowed === false && <p className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-rose-800">This page is for Lumina IQ staff.</p>}
                {error && <p className="mb-3 rounded-xl bg-rose-50 p-3 text-sm text-rose-700" role="alert">{error}</p>}
                {allowed && !form && !error && <div className="flex items-center gap-2 text-[#5E5046]"><Loader2 className="h-4 w-4 animate-spin" /> Loading…</div>}
                {form && meta && (
                    <>
                        <h1 className="text-3xl font-bold">{meta.label}</h1>
                        <p className="mb-6 text-[#5E5046]">
                            What every {meta.label} learner gets. Schools can switch tools off for a class, never on.
                        </p>

                        <h2 className="mb-2 text-sm font-bold uppercase tracking-wide text-[#5E5046]">Answers</h2>
                        <div className="mb-6 grid gap-2">
                            <SettingRow title="Hints first, by default"
                                description="Learners get a hint before the full answer. They can switch it off in chat unless their class forces it."
                                on={form.hints_default} onChange={(v) => setForm({ ...form, hints_default: v })} />
                            <SettingRow title="Answer beyond the book"
                                description='When the book does not cover a question, answer from general knowledge with a "Not from your book" label.'
                                on={form.outside_book} onChange={(v) => setForm({ ...form, outside_book: v })} />
                        </div>

                        <h2 className="mb-2 text-sm font-bold uppercase tracking-wide text-[#5E5046]">
                            Tools · {form.tools.length} of {catalog.tools.length} on
                        </h2>
                        <ToolToggles tools={catalog.tools} enabled={form.tools} onChange={(tools) => setForm({ ...form, tools })} />

                        <div className="sticky bottom-4 mt-6 flex items-center justify-end gap-3">
                            {done && !dirty && <span className="flex items-center gap-1 text-sm font-semibold text-[#1E5C42]"><Check className="h-4 w-4" /> Saved. Learners see it within a couple of minutes.</span>}
                            <button onClick={() => setForm(saved)} disabled={!dirty || busy}
                                className="rounded-2xl border border-[#E6D5CC] bg-white px-4 py-2.5 text-sm font-semibold disabled:opacity-40">Undo changes</button>
                            <button onClick={save} disabled={!dirty || busy}
                                className="rounded-2xl bg-[#1E5C42] px-5 py-2.5 text-sm font-bold text-white shadow-md hover:bg-[#163628] disabled:opacity-40">
                                {busy ? 'Saving…' : 'Save'}
                            </button>
                        </div>
                    </>
                )}
            </main>
        </div>
    );
};

export default PlatformLevel;
