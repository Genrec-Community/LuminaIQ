import { useEffect, useState } from 'react';
import { Loader2, SlidersHorizontal, Check } from 'lucide-react';
import { getClassSettings, updateClassSettings, getLevelCatalog, apiErrorText } from '../../api';
import ToolToggles, { SettingRow } from '../ToolToggles';
import { LEVEL_OPTIONS } from '../LevelPicker';

const HINT_MODES = [
    ['student_choice', 'Students choose'],
    ['always_on', 'Always hints first'],
    ['always_off', 'Never (full answers)'],
];

/**
 * School admins: the class's level (which sets every student's answer style),
 * hints-first, answers beyond the book, and which tools the class gets. Only
 * tools Lumina IQ allows for the level can be switched on.
 */
const ClassSettings = ({ classId }) => {
    const [catalog, setCatalog] = useState(null);
    const [form, setForm] = useState(null);
    const [allowed, setAllowed] = useState([]);
    const [busy, setBusy] = useState(false);
    const [msg, setMsg] = useState('');

    const apply = (s) => {
        setAllowed(s.allowed_tools);
        setForm({ level: s.level || '', hint_mode: s.hint_mode, allow_outside_book: s.allow_outside_book, tools: s.tools });
    };

    useEffect(() => {
        Promise.all([getLevelCatalog(), getClassSettings(classId)])
            .then(([cat, s]) => { setCatalog(cat); apply(s); })
            .catch((e) => setMsg(apiErrorText(e)));
    }, [classId]);

    const save = async () => {
        setBusy(true); setMsg('');
        try {
            const tools = Object.fromEntries(allowed.map((k) => [k, form.tools.includes(k)]));
            apply(await updateClassSettings(classId, {
                level: form.level || undefined, hint_mode: form.hint_mode,
                allow_outside_book: form.allow_outside_book, tools,
            }));
            setMsg('saved');
        } catch (e) {
            setMsg(apiErrorText(e));
        } finally {
            setBusy(false);
        }
    };

    if (!form || !catalog) {
        return msg ? <p className="text-sm text-rose-600">{msg}</p>
            : <div className="flex items-center gap-2 text-sm text-[#5E5046]"><Loader2 className="h-4 w-4 animate-spin" /> Loading settings…</div>;
    }
    const toolList = catalog.tools.filter((t) => allowed.includes(t.key));
    return (
        <div className="space-y-4">
            <h2 className="text-lg font-bold text-[#163628] flex items-center gap-2"><SlidersHorizontal className="h-5 w-5 text-[#1E5C42]" /> Level &amp; tools</h2>
            <label className="block">
                <span className="block text-sm font-semibold text-[#163628] mb-1">Class level</span>
                <select value={form.level} onChange={(e) => setForm({ ...form, level: e.target.value })}
                    className="w-full rounded-xl border border-[#E6D5CC] bg-[#FDF6F0] px-3 py-2 text-sm">
                    <option value="">Not set (each student chooses)</option>
                    {LEVEL_OPTIONS.map((o) => <option key={o.key} value={o.key}>{o.label} · {o.hint}</option>)}
                </select>
                <span className="block text-xs text-[#5E5046] mt-1">Students in this class get answers made for this level and can&apos;t change it.</span>
            </label>
            <label className="block">
                <span className="block text-sm font-semibold text-[#163628] mb-1">Hints first</span>
                <select value={form.hint_mode} onChange={(e) => setForm({ ...form, hint_mode: e.target.value })}
                    className="w-full rounded-xl border border-[#E6D5CC] bg-[#FDF6F0] px-3 py-2 text-sm">
                    {HINT_MODES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
                </select>
                <span className="block text-xs text-[#5E5046] mt-1">With hints first, the tutor gives a hint before the full solution.</span>
            </label>
            <SettingRow title="Answer beyond the book"
                description='Off: answers come only from class books. On: general knowledge too, labelled "Not from your book".'
                on={form.allow_outside_book} onChange={(v) => setForm({ ...form, allow_outside_book: v })} />
            <div>
                <p className="text-sm font-semibold text-[#163628] mb-2">Tools ({form.tools.length} of {toolList.length} on)</p>
                <ToolToggles tools={toolList} enabled={form.tools} onChange={(tools) => setForm({ ...form, tools })} columns={1} />
                {form.level === '' && <p className="mt-1 text-xs text-[#5E5046]">Set a level to see the tools Lumina IQ allows for it.</p>}
            </div>
            <div className="flex items-center justify-end gap-3">
                {msg === 'saved' ? <span className="flex items-center gap-1 text-sm font-semibold text-[#1E5C42]"><Check className="h-4 w-4" /> Saved</span>
                    : msg && <span className="text-sm text-rose-600">{msg}</span>}
                <button onClick={save} disabled={busy} className="rounded-xl bg-[#1E5C42] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">
                    {busy ? 'Saving…' : 'Save'}
                </button>
            </div>
        </div>
    );
};

export default ClassSettings;
