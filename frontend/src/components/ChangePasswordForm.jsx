import React, { useState } from 'react';
import { Loader2, Lock, Eye, EyeOff } from 'lucide-react';
import { changePassword, apiErrorText } from '../api';

const field = 'w-full rounded-2xl border border-[#E6D5CC] bg-[#FDF6F0] px-4 py-3 pr-11 outline-none focus:ring-2 focus:ring-[#1E5C42] text-[#163628]';

/** Current + new password, used in Settings and on the first sign-in of a school account. */
const ChangePasswordForm = ({ onDone, submitLabel = 'Change password' }) => {
    const [current, setCurrent] = useState('');
    const [next, setNext] = useState('');
    const [again, setAgain] = useState('');
    const [show, setShow] = useState(false);
    const [busy, setBusy] = useState(false);
    const [msg, setMsg] = useState(null);

    const problem = next && (next.length < 8 || !/[A-Za-z]/.test(next) || !/\d/.test(next))
        ? 'At least 8 characters, with a letter and a number.'
        : again && next !== again ? "The new passwords don't match." : '';

    const submit = async (e) => {
        e.preventDefault();
        if (problem) return;
        setBusy(true); setMsg(null);
        try {
            await changePassword(current, next);
            setCurrent(''); setNext(''); setAgain('');
            setMsg({ ok: true, text: 'Password changed.' });
            onDone?.();
        } catch (err) {
            setMsg({ ok: false, text: apiErrorText(err) });
        } finally {
            setBusy(false);
        }
    };

    const type = show ? 'text' : 'password';
    return (
        <form onSubmit={submit} className="space-y-3">
            <div className="relative">
                <input type={type} required autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)}
                    placeholder="Current password" aria-label="Current password" className={field} />
                <button type="button" onClick={() => setShow(!show)} className="absolute right-3 top-1/2 -translate-y-1/2 text-[#5E5046]"
                    aria-label={show ? 'Hide passwords' : 'Show passwords'}>
                    {show ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                </button>
            </div>
            <input type={type} required autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)}
                placeholder="New password" aria-label="New password" className={field} />
            <input type={type} required autoComplete="new-password" value={again} onChange={(e) => setAgain(e.target.value)}
                placeholder="New password again" aria-label="New password again" className={field} />
            {problem && <p className="text-sm text-amber-700">{problem}</p>}
            {msg && <p className={`text-sm ${msg.ok ? 'text-emerald-700' : 'text-rose-600'}`}>{msg.text}</p>}
            <button disabled={busy || !current || !next || !again || !!problem}
                className="w-full rounded-2xl bg-[#1E5C42] px-4 py-3 font-semibold text-white hover:bg-[#163628] disabled:opacity-50 flex items-center justify-center gap-2">
                {busy ? <Loader2 className="h-5 w-5 animate-spin" /> : <><Lock className="h-4 w-4" /> {submitLabel}</>}
            </button>
        </form>
    );
};

export default ChangePasswordForm;
