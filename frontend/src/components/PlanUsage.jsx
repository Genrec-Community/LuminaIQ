import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Crown, Loader2, FileText } from 'lucide-react';
import usePlan from '../hooks/usePlan';
import { formatReset, emitPlanChanged } from '../utils/plan';
import { cancelSubscription, getInvoices } from '../api';
import { isNativeApp } from '../utils/platform';

const ORDER = ['chat', 'questions', 'tools', 'cram', 'visual', 'deep', 'books'];

/** Current plan with a meter per limit. Used in Settings → Plan. */
const PlanUsage = () => {
    const navigate = useNavigate();
    const { plan, loading } = usePlan();
    const [invoices, setInvoices] = useState([]);
    const [confirmCancel, setConfirmCancel] = useState(false);
    const [cancelling, setCancelling] = useState(false);
    const [cancelError, setCancelError] = useState('');
    const native = isNativeApp();
    const subscribed = plan?.source === 'razorpay';

    useEffect(() => {
        if (subscribed) getInvoices().then((r) => setInvoices(r.invoices || [])).catch(() => {});
    }, [subscribed]);

    const doCancel = async () => {
        setCancelling(true); setCancelError('');
        try {
            await cancelSubscription();
            emitPlanChanged();
            setConfirmCancel(false);
        } catch (e) {
            setCancelError(e?.response?.data?.detail?.message || e?.response?.data?.detail || 'Could not cancel. Please try again.');
        } finally {
            setCancelling(false);
        }
    };

    if (loading) return <div className="flex items-center gap-2 text-[#8a6a5c]"><Loader2 className="h-4 w-4 animate-spin" /> Loading your plan…</div>;
    if (!plan) return <p className="text-[#8a6a5c]">Plan details are unavailable right now.</p>;

    const until = plan.current_period_end
        ? new Date(plan.current_period_end).toLocaleDateString([], { day: 'numeric', month: 'short', year: 'numeric' })
        : null;

    return (
        <div className="space-y-4">
            <div className="rounded-2xl border border-[#E6D5CC] bg-white p-5 flex flex-wrap items-center gap-4 justify-between">
                <div>
                    <div className="flex items-center gap-2 text-lg font-bold text-[#4A3B32]">
                        <Crown className="h-5 w-5 text-[#C8A288]" /> {plan.plan_name}
                    </div>
                    <p className="text-sm text-[#8a6a5c]">
                        {plan.source === 'pass' && until ? `Exam Night Pass active until ${until}` :
                            plan.source === 'institution' ? 'Provided by your institution' :
                                until ? `${plan.cancel_at_period_end ? 'Ends' : 'Renews'} on ${until}` :
                                    plan.plan === 'free' ? 'Free forever. Upgrade any time.' : ''}
                    </p>
                </div>
                {plan.source !== 'institution' && !native && (
                    <button onClick={() => navigate('/pricing')}
                        className="rounded-xl bg-[#C8A288] px-4 py-2 text-sm font-semibold text-white hover:bg-[#B08B72]">
                        {plan.plan === 'free' ? 'Upgrade' : 'Manage plan'}
                    </button>
                )}
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
                {ORDER.filter((k) => plan.usage[k] && !(plan.usage[k].limit === 0 && k === 'deep')).map((k) => {
                    const u = plan.usage[k];
                    const pct = u.limit ? Math.min(100, (u.used / u.limit) * 100) : 0;
                    return (
                        <div key={k} className="rounded-2xl border border-[#E6D5CC] bg-white p-4">
                            <div className="flex items-baseline justify-between gap-2">
                                <span className="text-sm font-semibold text-[#4A3B32] first-letter:uppercase">{u.label}</span>
                                <span className="text-sm tabular-nums text-[#8a6a5c]">{u.used}{u.limit != null ? ` / ${u.limit}` : ''}</span>
                            </div>
                            <div className="mt-2 h-2 rounded-full bg-[#E6D5CC]/60 overflow-hidden">
                                <div className={`h-full rounded-full ${pct >= 90 ? 'bg-rose-400' : 'bg-[#C8A288]'}`}
                                    style={{ width: u.limit == null ? '8%' : `${pct}%` }} />
                            </div>
                            <div className="mt-1 text-xs text-[#8a6a5c]">{u.limit == null ? 'Unlimited' : formatReset(u.resets_at)}</div>
                        </div>
                    );
                })}
            </div>

            {subscribed && !native && (
                <div className="rounded-2xl border border-[#E6D5CC] bg-white p-5 space-y-4">
                    {invoices.length > 0 && (
                        <div>
                            <h3 className="font-semibold text-[#4A3B32] mb-2">Invoices</h3>
                            <ul className="divide-y divide-[#E6D5CC]">
                                {invoices.map((inv) => (
                                    <li key={inv.id} className="py-2 flex items-center justify-between text-sm">
                                        <span className="text-[#4A3B32]">
                                            {inv.date ? new Date(inv.date * 1000).toLocaleDateString([], { day: 'numeric', month: 'short', year: 'numeric' }) : inv.id}
                                            {inv.amount_paise ? ` · ₹${(inv.amount_paise / 100).toLocaleString('en-IN')}` : ''}
                                        </span>
                                        {inv.url && (
                                            <a href={inv.url} target="_blank" rel="noopener noreferrer"
                                                className="flex items-center gap-1 font-semibold text-[#C8A288] hover:underline">
                                                <FileText className="h-4 w-4" /> GST invoice
                                            </a>
                                        )}
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}
                    {!plan.cancel_at_period_end && (
                        confirmCancel ? (
                            <div className="rounded-xl bg-rose-50 border border-rose-200 p-4 text-sm text-rose-900">
                                <p>You'll keep {plan.plan_name} until the end of this billing period, then move to Free. Your books and progress stay.</p>
                                {cancelError && <p className="mt-2 font-semibold">{cancelError}</p>}
                                <div className="mt-3 flex gap-2">
                                    <button onClick={doCancel} disabled={cancelling}
                                        className="rounded-xl bg-rose-600 px-4 py-2 font-semibold text-white disabled:opacity-60">
                                        {cancelling ? 'Cancelling…' : 'Cancel subscription'}
                                    </button>
                                    <button onClick={() => setConfirmCancel(false)} className="rounded-xl border border-rose-300 px-4 py-2 font-semibold">Keep it</button>
                                </div>
                            </div>
                        ) : (
                            <button onClick={() => setConfirmCancel(true)} className="text-sm font-semibold text-[#8a6a5c] hover:text-rose-600">
                                Cancel subscription
                            </button>
                        )
                    )}
                </div>
            )}
        </div>
    );
};

export default PlanUsage;
