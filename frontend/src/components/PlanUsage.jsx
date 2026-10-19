import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Crown, Loader2 } from 'lucide-react';
import usePlan from '../hooks/usePlan';
import { formatReset } from '../utils/plan';

const ORDER = ['chat', 'questions', 'tools', 'cram', 'visual', 'deep', 'books'];

/** Current plan with a meter per limit. Used in Settings → Plan. */
const PlanUsage = () => {
    const navigate = useNavigate();
    const { plan, loading } = usePlan();

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
                {plan.source !== 'institution' && (
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
        </div>
    );
};

export default PlanUsage;
