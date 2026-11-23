import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getConsent, giveConsent } from '../api';
import { useTools } from '../context/ToolsContext';

/**
 * Asks once for what the learner still has to agree to: the Terms and Privacy Policy
 * (again when they change) and, for Class 5–12 learners, a parent's or guardian's consent
 * (India's DPDP Act treats everyone under 18 as a child). School-created accounts are
 * covered by the school's agreement and never see this. Each answer is stored with its
 * version (backend: services/product_analytics.py).
 */
const ConsentGate = () => {
    const { level } = useTools();
    const [missing, setMissing] = useState([]);
    const [agree, setAgree] = useState(false);
    const [guardian, setGuardian] = useState({ name: '', email: '', relation: 'Parent', confirm: false });
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');

    useEffect(() => {
        let alive = true;
        getConsent().then((r) => { if (alive) setMissing(r.missing || []); }).catch(() => {});
        return () => { alive = false; };
    }, [level]);

    if (!missing.length) return null;
    const needsTerms = missing.includes('terms') || missing.includes('privacy');
    const needsParent = missing.includes('parental');
    const guardianOk = !needsParent || (guardian.name.trim() && /\S+@\S+\.\S+/.test(guardian.email) && guardian.confirm);
    const ready = (!needsTerms || agree) && guardianOk;

    const save = async () => {
        setSaving(true);
        setError('');
        try {
            if (needsTerms) {
                for (const kind of ['terms', 'privacy']) {
                    if (missing.includes(kind)) await giveConsent({ kind, method: 'consent_prompt' });
                }
            }
            if (needsParent) {
                await giveConsent({ kind: 'parental', method: 'guardian_declaration', guardian_name: guardian.name.trim(),
                                    guardian_email: guardian.email.trim(), guardian_relation: guardian.relation });
            }
            setMissing([]);
        } catch {
            setError("Couldn't save that. Please try again.");
        } finally {
            setSaving(false);
        }
    };

    const field = 'w-full rounded-xl border border-[#D8CFC4] px-3 py-2.5 text-base text-[#163628] focus:border-[#1E5C42] focus:outline-none';

    return (
        <div className="fixed inset-0 z-[9997] flex items-center justify-center bg-[#182B22]/50 backdrop-blur-md p-3"
            role="dialog" aria-modal="true" aria-labelledby="consent-title">
            <div className="w-full max-w-lg max-h-[calc(100dvh-1.5rem)] overflow-y-auto rounded-3xl bg-white p-5 sm:p-6 shadow-2xl">
                <h2 id="consent-title" className="text-xl sm:text-2xl font-bold text-[#163628]">
                    {needsParent ? 'A grown-up needs to say yes' : 'Before you continue'}
                </h2>
                <p className="mt-1 text-[#5E5046]">
                    {needsParent
                        ? 'Lumina IQ is for learners of every age. For students under 18, a parent or guardian agrees to how we use their study data.'
                        : 'Please read and agree to how Lumina IQ works and how we look after your data.'}
                </p>

                {needsTerms && (
                    <label className="mt-4 flex items-start gap-3 text-[#163628]">
                        <input type="checkbox" className="mt-1 h-5 w-5 accent-[#1E5C42]" checked={agree}
                            onChange={(e) => setAgree(e.target.checked)} disabled={saving} />
                        <span>
                            I agree to the <Link to="/terms" target="_blank" className="underline underline-offset-2">Terms</Link> and
                            the <Link to="/privacy" target="_blank" className="underline underline-offset-2">Privacy Policy</Link>.
                        </span>
                    </label>
                )}

                {needsParent && (
                    <div className="mt-4 space-y-3 rounded-2xl bg-[#F6F1EA] p-4">
                        <p className="text-sm font-semibold text-[#163628]">For the parent or guardian</p>
                        <input className={field} placeholder="Your name" autoComplete="name" value={guardian.name}
                            onChange={(e) => setGuardian({ ...guardian, name: e.target.value })} disabled={saving} />
                        <input className={field} placeholder="Your email" type="email" autoComplete="email" value={guardian.email}
                            onChange={(e) => setGuardian({ ...guardian, email: e.target.value })} disabled={saving} />
                        <select className={field} value={guardian.relation} disabled={saving}
                            onChange={(e) => setGuardian({ ...guardian, relation: e.target.value })}>
                            <option>Parent</option>
                            <option>Guardian</option>
                        </select>
                        <label className="flex items-start gap-3 text-sm text-[#163628]">
                            <input type="checkbox" className="mt-0.5 h-5 w-5 accent-[#1E5C42]" checked={guardian.confirm}
                                onChange={(e) => setGuardian({ ...guardian, confirm: e.target.checked })} disabled={saving} />
                            <span>
                                I am this student's parent or guardian. I agree to Lumina IQ using their study data to help them
                                learn, as described in the Privacy Policy. No ads, and their data is never sold.
                            </span>
                        </label>
                    </div>
                )}

                {error && <p className="mt-3 text-sm text-red-700" role="alert">{error}</p>}
                <button type="button" onClick={save} disabled={!ready || saving}
                    className="mt-5 w-full rounded-2xl bg-[#1E5C42] py-3.5 text-lg font-bold text-white transition-colors hover:bg-[#163628] disabled:opacity-50">
                    {saving ? 'Saving…' : 'Agree and continue'}
                </button>
            </div>
        </div>
    );
};

export default ConsentGate;
