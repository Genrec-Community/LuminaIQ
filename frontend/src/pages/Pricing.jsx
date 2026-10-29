import React, { useEffect, useState } from 'react';
import SiteHeader from '../components/site/SiteHeader';
import Logo from '../components/brand/Logo';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowLeft, Check, Crown, Loader2, Moon, Building2, PartyPopper } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { getPlans, startCheckout, startPassCheckout, verifyPayment } from '../api';
import usePlan from '../hooks/usePlan';
import { emitPlanChanged } from '../utils/plan';
import { openCheckout } from '../utils/razorpay';
import { STUDENT_PLANS, INSTITUTION_PLAN, EXAM_NIGHT_PASS, yearlySaving, inr } from '../utils/pricing';
import { isNativeApp } from '../utils/platform';

const fmtDate = (iso) => new Date(iso).toLocaleDateString([], { day: 'numeric', month: 'short', year: 'numeric' });

const errText = (e) => e?.response?.data?.detail?.message || e?.response?.data?.detail || e?.message || 'Something went wrong.';

/**
 * Plans and checkout. Works signed out (buttons lead to sign-in first).
 * Payments run through Razorpay Checkout; the backend verifies every payment.
 */
const Pricing = () => {
    const { user } = useAuth();
    const navigate = useNavigate();
    const [params] = useSearchParams();
    const { plan: myPlan } = usePlan();
    const [cycle, setCycle] = useState(params.get('cycle') === 'yearly' ? 'yearly' : 'monthly');
    const [enabled, setEnabled] = useState(true);
    const [mode, setMode] = useState('one_time');
    const [testMode, setTestMode] = useState(false);
    const [busy, setBusy] = useState('');
    const [error, setError] = useState('');
    const [success, setSuccess] = useState(null);
    const highlight = params.get('plan');
    const native = isNativeApp();

    useEffect(() => {
        getPlans().then((c) => {
            setEnabled(c.payments_enabled !== false);
            if (c.payment_mode) setMode(c.payment_mode);
            setTestMode(!!c.test_mode);
        }).catch(() => {});
    }, []);

    const requireLogin = (next) => {
        if (user) return false;
        navigate(`/login?next=${encodeURIComponent(next)}`);
        return true;
    };

    const buyPlan = async (key) => {
        setError('');
        if (requireLogin(`/pricing?plan=${key}&cycle=${cycle}`)) return;
        setBusy(key);
        try {
            const co = await startCheckout(key, cycle);
            const renewing = co.mode === 'subscription';
            const resp = await openCheckout(renewing ? {
                key: co.key_id, subscription_id: co.subscription_id,
                name: co.name, description: co.description, prefill: co.prefill,
            } : {
                key: co.key_id, order_id: co.order_id, amount: co.amount_paise, currency: 'INR',
                name: co.name, description: co.description, prefill: co.prefill,
            });
            const summary = await verifyPayment({ kind: renewing ? 'subscription' : 'plan', ...resp });
            emitPlanChanged();
            const until = summary.current_period_end ? fmtDate(summary.current_period_end) : null;
            setSuccess({
                title: `Welcome to ${summary.plan_name}!`,
                body: renewing
                    ? 'Your new limits are active right now.'
                    : `Your new limits are active right now${until ? `, until ${until}` : ''}. Nothing renews by itself.`,
            });
        } catch (e) {
            if (!e?.dismissed) setError(errText(e));
        } finally {
            setBusy('');
        }
    };

    const buyPass = async () => {
        setError('');
        if (requireLogin('/pricing#pass')) return;
        setBusy('pass');
        try {
            const co = await startPassCheckout();
            const resp = await openCheckout({
                key: co.key_id, order_id: co.order_id, amount: co.amount_paise, currency: 'INR',
                name: co.name, description: co.description, prefill: co.prefill,
            });
            await verifyPayment({ kind: 'pass', ...resp });
            emitPlanChanged();
            setSuccess({ title: 'Exam Night Pass active', body: `You have Topper for the next ${EXAM_NIGHT_PASS.hours} hours. Go ace it!` });
        } catch (e) {
            if (!e?.dismissed) setError(errText(e));
        } finally {
            setBusy('');
        }
    };

    const current = myPlan?.plan;
    const paidByMe = myPlan?.source === 'razorpay';
    const school = myPlan?.source === 'institution';

    if (success) {
        return (
            <div className="min-h-[100dvh] bg-[#FDF6F0] flex items-center justify-center p-6">
                <motion.div initial={{ scale: 0.95, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}
                    className="max-w-md w-full rounded-3xl border border-[#E6D5CC] bg-white p-8 text-center">
                    <PartyPopper className="mx-auto h-12 w-12 text-[#1E5C42]" />
                    <h1 className="mt-3 text-2xl font-bold text-[#163628]">{success.title}</h1>
                    <p className="mt-1 text-[#5E5046]">{success.body}</p>
                    <button onClick={() => navigate('/dashboard')}
                        className="mt-6 w-full rounded-2xl bg-[#1E5C42] px-4 py-3 font-semibold text-white hover:bg-[#163628]">
                        Start studying
                    </button>
                </motion.div>
            </div>
        );
    }

    return (
        <div className="min-h-[100dvh] bg-[#FDF6F0] text-[#163628]">
            {user ? (
                <header className="app-header sticky top-0 z-30 border-b border-[#163628]/10 bg-[#FDF6F0]/90 backdrop-blur-md">
                    <div className="site-wrap flex h-[4.5rem] items-center justify-between">
                        <button onClick={() => navigate('/dashboard')} className="flex items-center gap-3 rounded-xl" aria-label="Back to your books">
                            <ArrowLeft className="h-4 w-4" /><Logo />
                        </button>
                        {myPlan && (
                            <span className="rounded-full bg-[#F2E6DB] px-3 py-1.5 text-sm">You're on <b>{myPlan.plan_name}</b></span>
                        )}
                    </div>
                </header>
            ) : <SiteHeader />}

            <main className="mx-auto max-w-6xl px-4 pb-16">
                <div className="text-center max-w-2xl mx-auto">
                    <h1 className="display h-xl mark-em pt-6">Pick your <em>plan</em>.</h1>
                    <p className="mt-3 text-[#5E5046]">
                        {mode === 'subscription'
                            ? 'Pay by UPI, card or netbanking. Cancel any time.'
                            : 'Pay once for a month or a year by UPI, card or netbanking. Nothing renews by itself.'}
                    </p>
                    {testMode && enabled && !native && (
                        <span className="mt-2 inline-block rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-800">Test mode: no real money is charged</span>
                    )}
                    {!native && (
                        <div className="mt-6 inline-flex rounded-full border border-[#E6D5CC] bg-white p-1" role="tablist" aria-label="Billing cycle">
                            {['monthly', 'yearly'].map((c) => (
                                <button key={c} role="tab" aria-selected={cycle === c} onClick={() => setCycle(c)}
                                    className={`chip capitalize ${cycle === c ? 'chip--on' : ''}`}>
                                    {c}{c === 'yearly' && <span className="ml-1.5 text-xs opacity-90">save ~30%</span>}
                                </button>
                            ))}
                        </div>
                    )}
                </div>

                {native && (
                    <p className="mt-6 mx-auto max-w-xl rounded-2xl border border-[#E6D5CC] bg-white p-4 text-center text-sm text-[#5E5046]">
                        Plans can't be bought inside the app. Your plan works everywhere you sign in.
                    </p>
                )}
                {!enabled && !native && (
                    <p className="mt-6 mx-auto max-w-xl rounded-2xl border border-amber-200 bg-amber-50 p-4 text-center text-sm text-amber-900">
                        Payments are being switched on. You can explore everything on the Free plan meanwhile.
                    </p>
                )}
                {school && !native && (
                    <p className="mt-6 mx-auto max-w-xl rounded-2xl border border-[#E6D5CC] bg-white p-4 text-center text-sm text-[#5E5046]">
                        Your school gives you the {myPlan.plan_name} plan. The Exam Night Pass still works on top of it.
                    </p>
                )}
                {error && (
                    <p className="mt-6 mx-auto max-w-xl rounded-2xl border border-rose-200 bg-rose-50 p-4 text-center text-sm text-rose-800">{error}</p>
                )}

                <div className="mt-10 grid gap-5 md:grid-cols-3">
                    {STUDENT_PLANS.map((p) => {
                        const price = cycle === 'monthly' ? p.monthly : p.yearly;
                        const mine = current === p.key && (paidByMe || myPlan?.source === 'manual');
                        // A renewing plan can't be bought twice; a one-time plan can be extended
                        const isCurrent = mine && (myPlan?.auto_renew || myPlan?.source === 'manual');
                        const extend = mine && !isCurrent;
                        const featured = highlight ? highlight === p.key : p.popular;
                        return (
                            <div key={p.key}
                                className={`relative rounded-3xl border-2 bg-white p-6 flex flex-col ${featured ? 'border-[#1E5C42] shadow-xl shadow-[#1E5C42]/15' : 'border-[#E6D5CC]'}`}>
                                {p.popular && (
                                    <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-[#1E5C42] px-3 py-1 text-xs font-bold text-white">Most popular</span>
                                )}
                                <h2 className="text-xl font-bold flex items-center gap-2">
                                    {p.key === 'topper' && <Crown className="h-5 w-5 text-[#1E5C42]" />}{p.name}
                                </h2>
                                <p className="text-sm text-[#5E5046]">{p.tagline}</p>
                                <div className="mt-4 flex items-baseline gap-1">
                                    <span className="text-4xl font-bold">{inr(price)}</span>
                                    <span className="text-sm text-[#5E5046]">{p.monthly ? (cycle === 'monthly' ? '/month' : '/year') : 'forever'}</span>
                                </div>
                                {cycle === 'yearly' && p.monthly > 0 && (
                                    <p className="text-xs text-emerald-700 mt-1">{inr(Math.round(p.yearly / 12))}/month · save {yearlySaving(p)}%</p>
                                )}
                                <ul className="mt-5 space-y-2.5 flex-1">
                                    {p.features.map((f) => (
                                        <li key={f} className="flex gap-2 text-sm"><Check className="h-4 w-4 mt-0.5 shrink-0 text-emerald-600" />{f}</li>
                                    ))}
                                </ul>
                                {p.key === 'free' ? (
                                    <Link to={user ? '/dashboard' : '/login'}
                                        className="mt-6 block rounded-2xl border-2 border-[#E6D5CC] px-4 py-3 text-center font-semibold hover:border-[#1E5C42]">
                                        {current === 'free' ? 'Your plan' : user ? 'Go to dashboard' : 'Start free'}
                                    </Link>
                                ) : native ? null : (
                                    <button onClick={() => buyPlan(p.key)} disabled={!enabled || !!busy || isCurrent || school}
                                        className={`mt-6 flex items-center justify-center gap-2 rounded-2xl px-4 py-3 font-semibold transition-colors disabled:opacity-60 ${featured ? 'bg-[#1E5C42] text-white hover:bg-[#163628]' : 'border-2 border-[#1E5C42] hover:bg-[#FDF6F0]'}`}>
                                        {busy === p.key ? <Loader2 className="h-5 w-5 animate-spin" /> : isCurrent ? 'Your plan'
                                            : extend ? `Add 1 ${cycle === 'monthly' ? 'month' : 'year'}` : `Get ${p.name}`}
                                    </button>
                                )}
                            </div>
                        );
                    })}
                </div>

                <div id="pass" className="mt-8 rounded-3xl bg-gradient-to-br from-[#163628] via-[#1b4331] to-[#0f271c] p-6 md:p-8 text-white flex flex-col md:flex-row md:items-center gap-5 justify-between">
                    <div>
                        <div className="flex items-center gap-2 text-[#D3EE6A] text-sm font-semibold"><Moon className="h-4 w-4" /> Exam Night Pass</div>
                        <h2 className="mt-1 text-2xl font-bold">Exam tomorrow? {inr(EXAM_NIGHT_PASS.price)} for {EXAM_NIGHT_PASS.hours} hours of Topper.</h2>
                        <p className="mt-1 text-white/75">Deep answers, unlimited books and Deep cram cards for the night that counts. One payment, no subscription.</p>
                    </div>
                    {!native && (
                        <button onClick={buyPass} disabled={!enabled || !!busy}
                            className="shrink-0 rounded-2xl bg-[#D3EE6A] px-6 py-3 font-bold text-[#0f271c] hover:bg-[#e0f590] disabled:opacity-60 flex items-center justify-center gap-2">
                            {busy === 'pass' ? <Loader2 className="h-5 w-5 animate-spin" /> : `Get the pass · ${inr(EXAM_NIGHT_PASS.price)}`}
                        </button>
                    )}
                </div>

                <div className="mt-8 rounded-3xl border-2 border-[#E6D5CC] bg-white p-6 md:p-8 grid md:grid-cols-[1fr_auto] gap-6 items-center">
                    <div>
                        <h2 className="text-2xl font-bold flex items-center gap-2"><Building2 className="h-6 w-6 text-[#1E5C42]" /> {INSTITUTION_PLAN.name}</h2>
                        <p className="text-[#5E5046]">{INSTITUTION_PLAN.tagline} · {inr(INSTITUTION_PLAN.perSeat)} per student per month, paid for 1, 3, 6 or 12 months, from {INSTITUTION_PLAN.minSeats} students</p>
                        <ul className="mt-4 grid sm:grid-cols-2 gap-2">
                            {INSTITUTION_PLAN.features.map((f) => (
                                <li key={f} className="flex gap-2 text-sm"><Check className="h-4 w-4 mt-0.5 shrink-0 text-emerald-600" />{f}</li>
                            ))}
                        </ul>
                    </div>
                    <Link to="/institution"
                        className="rounded-2xl bg-[#163628] px-6 py-3 text-center font-semibold text-white hover:bg-[#283B31]">
                        Set up your institution
                    </Link>
                </div>
            </main>
        </div>
    );
};

export default Pricing;
