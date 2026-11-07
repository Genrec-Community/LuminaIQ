import React, { useCallback, useEffect, useState } from 'react';
import { Download, Loader2, RefreshCw } from 'lucide-react';
import { getPlatformAnalytics, apiErrorText } from '../../api';
import { Change, Stat, Table, inr, num, pct, usd } from './ui';

/**
 * Platform admin: the whole journey in one place. Growth → activation → retention →
 * engagement → learning → revenue → system health. Counts and learning data only;
 * chats and memory notes are never shown.
 */

const INK = '#163628';
const MUTED = '#5E5046';
const BAR = '#1E5C42';
const GRID = '#EFE5DE';

const LEVEL_NAMES = {
    school: 'Class 5–10', higher_secondary: 'Class 11–12', ugpg: 'UG / PG', research: 'Research',
    general: 'General', not_set: 'Not chosen yet',
};
const STATE_NAMES = { active: 'Live (paid)', trial: 'Live (trial)', pending_approval: 'Waiting for approval', expired: 'Expired', suspended: 'Paused' };
const XP_NAMES = {
    mastery_gain: 'Mastery gained', mistake_fixed: 'Mistakes fixed', review_on_time: 'Reviews on time',
    daily_goal: 'Daily goals', exam_plan_step: 'Plan steps', comeback: 'Comebacks',
};
const SECTIONS = [
    ['overview', 'Overview'], ['growth', 'Growth'], ['activation', 'Activation'], ['retention', 'Retention'],
    ['engagement', 'Engagement'], ['learning', 'Learning'], ['revenue', 'Revenue'], ['health', 'Health'],
];

const shortDay = (d) => new Date(`${d}T00:00:00`).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
const compact = (v) => (v >= 10000 ? `${Math.round(v / 1000)}K` : v >= 1000 ? `${(v / 1000).toFixed(1)}K` : `${Math.round(v * 100) / 100}`);

/** One series per day as columns, with a hover/tap tooltip and the peak labelled. */
const DayColumns = ({ title, daily, field, format = num, note }) => {
    const [hover, setHover] = useState(null);
    const values = daily.map((d) => Number(d[field] || 0));
    const max = Math.max(...values, 0);
    const total = values.reduce((a, b) => a + b, 0);
    const peak = values.indexOf(max);
    const W = 100 / Math.max(values.length, 1);
    const shown = hover;
    return (
        <figure className="rounded-2xl border border-[#E6D5CC] bg-white p-4">
            <figcaption className="flex items-baseline justify-between gap-2">
                <span className="font-semibold">{title}</span>
                <span className="text-sm tabular-nums text-[#5E5046]">{format(total)} total</span>
            </figcaption>
            {note && <p className="text-xs text-[#5E5046]">{note}</p>}
            <div className="relative mt-6 h-28" onMouseLeave={() => setHover(null)}>
                {/* top gridline with its value, then the baseline */}
                <div className="absolute inset-x-0 top-0 border-t" style={{ borderColor: GRID }} />
                <span className="absolute left-0 -top-4 text-[10px] tabular-nums text-[#5E5046]">{max ? compact(max) : ''}</span>
                <div className="absolute inset-x-0 bottom-0 border-t" style={{ borderColor: '#D9CBC1' }} />
                <div className="absolute inset-0 flex items-end" role="img"
                    aria-label={`${title} per day: ${format(total)} in total, highest ${format(max)}`}>
                    {values.map((v, i) => (
                        <button key={daily[i].day} type="button" aria-label={`${shortDay(daily[i].day)}: ${format(v)}`}
                            className="flex h-full justify-center items-end focus:outline-none"
                            style={{ width: `${W}%`, padding: '0 1px' }}
                            onMouseEnter={() => setHover(i)} onFocus={() => setHover(i)} onClick={() => setHover(i)}>
                            <span className="block w-full max-w-[24px] rounded-t-[4px]"
                                style={{ height: max ? `${Math.max((v / max) * 100, v ? 2 : 0)}%` : 0,
                                    background: BAR, opacity: shown === null || shown === i ? 1 : 0.45 }} />
                        </button>
                    ))}
                </div>
                {shown !== null && (
                    <div className="pointer-events-none absolute -top-9 z-10 -translate-x-1/2 whitespace-nowrap rounded-lg bg-[#163628] px-2 py-1 text-xs text-white shadow"
                        style={{ left: `${Math.min(Math.max((shown + 0.5) * W, 12), 88)}%` }}>
                        {shortDay(daily[shown].day)} · <b className="tabular-nums">{format(values[shown])}</b>
                    </div>
                )}
            </div>
            <div className="mt-1 flex justify-between text-[10px] text-[#5E5046]">
                <span>{daily.length ? shortDay(daily[0].day) : ''}</span>
                {max > 0 && <span>Peak {format(max)} on {shortDay(daily[peak].day)}</span>}
                <span>{daily.length ? shortDay(daily[daily.length - 1].day) : ''}</span>
            </div>
        </figure>
    );
};

/** Horizontal bars for a ranked list (funnel steps, habit buckets). */
const Bars = ({ rows }) => {
    const max = Math.max(...rows.map((r) => r.value), 1);
    return (
        <ul className="space-y-2.5">
            {rows.map((r) => (
                <li key={r.label}>
                    <div className="flex items-baseline justify-between gap-2 text-sm">
                        <span>{r.label}</span>
                        <span className="tabular-nums"><b>{num(r.value)}</b>{r.extra && <span className="text-[#5E5046]"> · {r.extra}</span>}</span>
                    </div>
                    <div className="mt-1 h-2.5 rounded-full" style={{ background: GRID }}>
                        <div className="h-full rounded-full" style={{ width: `${(r.value / max) * 100}%`, background: BAR, minWidth: r.value ? 4 : 0 }} />
                    </div>
                    {r.sub && <div className="mt-0.5 text-xs text-[#5E5046]">{r.sub}</div>}
                </li>
            ))}
        </ul>
    );
};

/** Sequential single-hue scale for the retention grid (light → the brand green). */
const cellColor = (r) => {
    const t = Math.min(Math.max(r, 0), 1);
    const mix = (a, b) => Math.round(a + (b - a) * Math.sqrt(t));
    return `rgb(${mix(241, 30)}, ${mix(247, 92)}, ${mix(243, 66)})`;
};

const Retention = ({ cohorts }) => (
    <div className="overflow-x-auto rounded-2xl border border-[#E6D5CC] bg-white">
        <table className="w-full min-w-[640px] text-sm">
            <thead>
                <tr className="text-left text-[#5E5046]">
                    <th className="sticky left-0 z-[1] bg-white px-3 py-2 font-semibold">Week of</th>
                    <th className="px-3 py-2 text-right font-semibold">People</th>
                    {Array.from({ length: 8 }, (_, w) => (
                        <th key={w} className="px-1 py-2 text-center font-semibold">{w === 0 ? 'Week 0' : `+${w}`}</th>
                    ))}
                </tr>
            </thead>
            <tbody>
                {cohorts.map((c) => (
                    <tr key={c.week} className="border-t border-[#F3E9E2]">
                        <td className="sticky left-0 z-[1] whitespace-nowrap bg-white px-3 py-1.5">{shortDay(c.week)}</td>
                        <td className="px-3 py-1.5 text-right tabular-nums">{num(c.users)}</td>
                        {c.weeks.map((r, w) => (
                            <td key={w} className="p-0.5">
                                {r === null || !c.users ? <div className="h-8 rounded-md" /> : (
                                    <div className="flex h-8 items-center justify-center rounded-md text-xs font-semibold tabular-nums"
                                        title={`${pct(r)} of the ${num(c.users)} who signed up were active ${w === 0 ? 'in their first week' : `${w} week${w > 1 ? 's' : ''} later`}`}
                                        style={{ background: cellColor(r), color: r > 0.45 ? '#fff' : INK }}>
                                        {pct(r)}
                                    </div>
                                )}
                            </td>
                        ))}
                    </tr>
                ))}
            </tbody>
        </table>
    </div>
);

const Section = ({ id, title, intro, children }) => (
    <section id={`an-${id}`} className="mt-10 scroll-mt-4">
        <h2 className="text-lg font-bold">{title}</h2>
        {intro && <p className="mb-3 text-sm text-[#5E5046]">{intro}</p>}
        {children}
    </section>
);

const csvDaily = (daily) => {
    const head = ['day', 'signups', 'active', 'questions', 'chat_questions', 'revenue_inr', 'ai_cost_usd'];
    const lines = [head.join(','), ...daily.map((d) => head.map((h) => d[h]).join(','))];
    const url = URL.createObjectURL(new Blob([lines.join('\n')], { type: 'text/csv' }));
    const a = document.createElement('a');
    a.href = url;
    a.download = `lumina-daily-${daily[0]?.day}-to-${daily[daily.length - 1]?.day}.csv`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
};

const Analytics = () => {
    const [days, setDays] = useState(30);
    const [data, setData] = useState(null);
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    const load = useCallback(async () => {
        setLoading(true);
        try { setData(await getPlatformAnalytics(days)); setError(''); } catch (e) { setError(apiErrorText(e)); }
        setLoading(false);
    }, [days]);
    useEffect(() => { setData(null); load(); }, [load]);

    const jump = (id) => document.getElementById(`an-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' });

    return (
        <div className="text-[#163628]">
            <div className="mb-3 flex flex-wrap items-center gap-2">
                <p className="mr-auto text-sm text-[#5E5046]">
                    {data ? `${shortDay(data.from)} – ${shortDay(data.to)} (${data.timezone}) · updated ${new Date(data.generated_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}` : 'Sign-ups, learning, revenue and system health.'}
                </p>
                {[7, 30, 90].map((d) => (
                    <button key={d} onClick={() => setDays(d)}
                        className={`rounded-2xl px-3 py-1.5 text-sm font-semibold ${days === d ? 'bg-[#163628] text-white' : 'border border-[#E6D5CC] bg-white'}`}>
                        {d} days
                    </button>
                ))}
                <button onClick={load} disabled={loading} aria-label="Refresh"
                    className="rounded-2xl border border-[#E6D5CC] bg-white p-2 disabled:opacity-50">
                    <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                </button>
                {data && (
                    <button onClick={() => csvDaily(data.daily)}
                        className="flex items-center gap-1.5 rounded-2xl border border-[#E6D5CC] bg-white px-3 py-1.5 text-sm font-semibold">
                        <Download className="h-4 w-4" /> CSV
                    </button>
                )}
            </div>
            {data && (
                <nav aria-label="Analytics sections" className="sticky top-0 z-20 -mx-4 mb-2 flex gap-1.5 overflow-x-auto bg-[#FDF6F0]/95 px-4 py-2 backdrop-blur">
                    {SECTIONS.map(([id, label]) => (
                        <button key={id} onClick={() => jump(id)}
                            className="whitespace-nowrap rounded-full border border-[#E6D5CC] bg-white px-3 py-1 text-xs font-semibold text-[#5E5046] hover:text-[#163628]">
                            {label}
                        </button>
                    ))}
                </nav>
            )}
            {error && <p className="text-sm text-rose-600">{error}</p>}
            {!data && !error && <div className="flex items-center gap-2 text-[#5E5046]"><Loader2 className="h-4 w-4 animate-spin" /> Loading…</div>}
            {data && <Report data={data} days={days} />}
        </div>
    );
};

const Report = ({ data, days }) => {
    const { overview: o, daily, funnel, retention, engagement: e, learning: l, revenue: r, health: h } = data;
    const signups = funnel[0]?.users || 0;
    return (
        <>
            <Section id="overview" title="Overview">
                <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                    <Stat label="Total learners" value={num(o.total_users)} hint={`${num(o.paying_users)} paying (${pct(o.paying_share)})`} />
                    <Stat label="New sign-ups" value={num(o.new_users.value)}><Change change={o.new_users.change} days={days} /></Stat>
                    <Stat label="Active learners" value={num(o.active_users.value)}><Change change={o.active_users.change} days={days} /></Stat>
                    <Stat label="Questions practised" value={num(o.questions.value)}><Change change={o.questions.change} days={days} /></Stat>
                    <Stat label="Chat questions" value={num(o.chat_questions.value)}><Change change={o.chat_questions.change} days={days} /></Stat>
                    <Stat label="Books uploaded" value={num(o.documents.value)}><Change change={o.documents.change} days={days} /></Stat>
                    <Stat label="Revenue" value={inr(o.revenue_inr.value)}><Change change={o.revenue_inr.change} days={days} /></Stat>
                    <Stat label="AI spend" value={usd(o.ai_cost_usd.value)} hint={`${usd(o.ai_cost_per_active_usd)} per active learner`}>
                        <Change change={o.ai_cost_usd.change} days={days} invert />
                    </Stat>
                </div>
            </Section>

            <Section id="growth" title="Growth and activity" intro="Active = opened the app that day. Stickiness = average daily actives over the last week ÷ monthly actives.">
                <div className="mb-3 grid grid-cols-2 gap-3 md:grid-cols-4">
                    <Stat label="Active today" value={num(o.dau)} />
                    <Stat label="Active this week" value={num(o.wau)} hint="last 7 days" />
                    <Stat label="Active this month" value={num(o.mau)} hint="last 30 days" />
                    <Stat label="Stickiness" value={pct(o.stickiness)} hint="20%+ is healthy for study apps" />
                </div>
                <div className="grid gap-3 md:grid-cols-2">
                    <DayColumns title="New sign-ups" daily={daily} field="signups" />
                    <DayColumns title="Active learners" daily={daily} field="active" note="Unique learners per day" />
                    <DayColumns title="Questions practised" daily={daily} field="questions" />
                    <DayColumns title="Chat questions" daily={daily} field="chat_questions" />
                    <DayColumns title="Revenue" daily={daily} field="revenue_inr" format={inr} />
                    <DayColumns title="AI spend" daily={daily} field="ai_cost_usd" format={usd} />
                </div>
                <details className="mt-3 rounded-2xl border border-[#E6D5CC] bg-white p-3 text-sm">
                    <summary className="cursor-pointer font-semibold">Daily numbers as a table</summary>
                    <Table rows={[...daily].reverse()} minWidth={560} empty="No data." columns={[
                        ['day', 'Day', 'left', shortDay], ['signups', 'Sign-ups', 'right', num], ['active', 'Active', 'right', num],
                        ['questions', 'Questions', 'right', num], ['chat_questions', 'Chats', 'right', num],
                        ['revenue_inr', 'Revenue', 'right', inr], ['ai_cost_usd', 'AI spend', 'right', usd],
                    ]} />
                </details>
            </Section>

            <Section id="activation" title="Activation funnel"
                intro={`Of the ${num(signups)} people who signed up in this period, how many reached each step so far.`}>
                <div className="rounded-2xl border border-[#E6D5CC] bg-white p-4">
                    {signups === 0 ? <p className="text-sm text-[#5E5046]">No sign-ups in this period.</p> : (
                        <Bars rows={funnel.map((s, i) => ({
                            label: s.label, value: s.users, extra: pct(s.of_signups),
                            sub: i > 0 && s.of_previous < 1 ? `${pct(1 - s.of_previous)} dropped off after the previous step` : null,
                        }))} />
                    )}
                </div>
            </Section>

            <Section id="retention" title="Retention by sign-up week"
                intro="Share of each week's new learners who used the app again in later weeks. Darker = more came back.">
                <Retention cohorts={retention} />
            </Section>

            <Section id="engagement" title="Engagement">
                <div className="grid gap-3 md:grid-cols-2">
                    <div className="rounded-2xl border border-[#E6D5CC] bg-white p-4">
                        <div className="mb-3 flex items-baseline justify-between">
                            <span className="font-semibold">How often learners came</span>
                            <span className="text-sm text-[#5E5046]">avg {e.avg_active_days} days</span>
                        </div>
                        <Bars rows={[
                            { label: '1 day', value: e.habit.one_day },
                            { label: '2–3 days', value: e.habit.two_three },
                            { label: '4–9 days', value: e.habit.four_nine },
                            { label: '10+ days', value: e.habit.ten_plus },
                        ]} />
                    </div>
                    <div className="rounded-2xl border border-[#E6D5CC] bg-white p-4">
                        <div className="mb-3 font-semibold">Practice by tool</div>
                        {e.practice.length === 0 ? <p className="text-sm text-[#5E5046]">No practice yet.</p> : (
                            <Bars rows={e.practice.slice(0, 6).map((p) => ({
                                label: p.source, value: p.answers, extra: `${num(p.users)} learners · ${pct(p.accuracy)} right`,
                            }))} />
                        )}
                    </div>
                </div>
                <Table title="AI features used" note="Learners who used each feature, and how often it came from the model or the shared cache."
                    empty="No AI use yet." rows={e.features} columns={[
                        ['feature', 'Feature'], ['users', 'Learners', 'right', num],
                        ['model_calls', 'Model calls', 'right', num], ['cache_hits', 'From cache', 'right', num],
                    ]} />
                <Table title="Most active learners" note="Ranked by questions practised + chat questions in this period."
                    empty="No activity yet." minWidth={680} rows={e.top_learners} columns={[
                        ['email', 'Learner', 'left', (v, row) => v || row.user_id.slice(0, 8)],
                        ['active_days', 'Days active', 'right', num], ['answers', 'Questions', 'right', num],
                        ['accuracy', 'Right', 'right', pct], ['mastery_points', 'Mastery +', 'right', num],
                        ['chat_questions', 'Chats', 'right', num], ['xp', 'XP', 'right', num],
                    ]} />
            </Section>

            <Section id="learning" title="Learning outcomes" intro="Is studying working? Mastery points = how much topic mastery rose, in percentage points.">
                <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                    <Stat label="Questions answered" value={num(l.answers)} hint={`${num(l.learners)} learners · ${pct(l.hinted_share)} with a hint`} />
                    <Stat label="Answered correctly" value={pct(l.accuracy)} />
                    <Stat label="Mastery points gained" value={num(Math.round(l.mastery_points))} hint={`${l.mastery_per_learner} per learner`} />
                    <Stat label="Topics mastered" value={num(l.topics_mastered)} hint="mastery ≥ 95%" />
                    <Stat label="Mistakes fixed" value={num(l.mistakes.fixed)} hint={`${num(l.mistakes.opened)} new mistakes · ${num(l.mistakes.tagged)} with a misconception`} />
                    <Stat label="Daily goals met" value={pct(l.goals.rate)} hint={`${num(l.goals.completed)} of ${num(l.goals.set)}`} />
                    <Stat label="Reviews due now" value={num(l.reviews_due_now)} hint="spaced-repetition backlog" />
                    <Stat label="XP awarded" value={num(l.xp_by_kind.reduce((a, x) => a + x.xp, 0))} hint="for learning only" />
                </div>
                <Table title="By level" empty="No learners yet." rows={l.by_level} columns={[
                    ['level', 'Level', 'left', (v) => LEVEL_NAMES[v] || v], ['users', 'Learners', 'right', num],
                    ['active', 'Active', 'right', num], ['answers', 'Questions', 'right', num],
                    ['accuracy', 'Right', 'right', pct], ['mastery_per_active', 'Mastery + per active', 'right', num],
                ]} />
                <Table title="Hardest topics" note="Topics with 5+ answers in this period, lowest share right first: good candidates for better content."
                    empty="Not enough answers yet." rows={l.hardest_topics} columns={[
                        ['topic', 'Topic'], ['answers', 'Answers', 'right', num], ['learners', 'Learners', 'right', num],
                        ['accuracy', 'Right', 'right', pct],
                    ]} />
                <Table title="XP by reason" empty="No XP awarded yet." rows={l.xp_by_kind} columns={[
                    ['kind', 'Reason', 'left', (v) => XP_NAMES[v] || v], ['events', 'Times', 'right', num],
                    ['users', 'Learners', 'right', num], ['xp', 'XP', 'right', num],
                ]} />
            </Section>

            <Section id="revenue" title="Revenue" intro="MRR = monthly value of active subscriptions (yearly plans ÷ 12). School MRR = paid seats × seat price.">
                <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                    <Stat label="Collected" value={inr(o.revenue_inr.value)} hint={`${num(r.failed_payments)} failed payment${r.failed_payments === 1 ? '' : 's'}`} />
                    <Stat label="Personal MRR" value={inr(r.mrr_inr)} hint={`${num(r.subscriptions.reduce((a, s) => a + s.subscribers, 0))} subscribers`} />
                    <Stat label="School MRR" value={inr(r.school_mrr_inr)} />
                    <Stat label="New paying learners" value={num(r.new_payers)} hint={`${num(r.pass_holders)} Exam Night Pass${r.pass_holders === 1 ? '' : 'es'} active`} />
                </div>
                <Table title="Payments" empty="No payments in this period." rows={r.payments} columns={[
                    ['kind', 'Type'], ['plan', 'Plan', 'left', (v) => v || '—'], ['count', 'Payments', 'right', num], ['amount_inr', 'Amount', 'right', inr],
                ]} />
                <Table title="Active subscriptions" empty="No active subscriptions." rows={r.subscriptions} columns={[
                    ['plan', 'Plan'], ['cycle', 'Billing'], ['subscribers', 'Subscribers', 'right', num],
                    ['cancelling', 'Cancelling', 'right', num], ['mrr_inr', 'MRR', 'right', inr],
                ]} />
                <Table title="Schools" empty="No schools yet." rows={r.schools} columns={[
                    ['state', 'Status', 'left', (v) => STATE_NAMES[v] || v], ['schools', 'Schools', 'right', num],
                    ['seats', 'Seats', 'right', num], ['students', 'Students', 'right', num],
                ]} />
            </Section>

            <Section id="health" title="System health" intro="Background work, book processing and the AI provider.">
                <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                    <Stat label="Jobs waiting now" value={num(h.queue.queued)}
                        hint={`${num(h.queue.running)} running · oldest waiting ${Math.round(h.queue.oldest_waiting_seconds / 60)} min`} />
                    <Stat label="Book processing failures" value={pct(h.documents.failure_rate)} hint={`${num(h.documents.failed)} of ${num(h.documents.total)}`} />
                    <Stat label="AI errors" value={pct(h.ai.error_rate)} hint={`${num(h.ai.errors)} of ${num(h.ai.calls)} model calls`} />
                    <Stat label="AI response time" value={`${(h.ai.p95_latency_ms / 1000).toFixed(1)} s`} hint={`95% of calls faster · avg ${(h.ai.avg_latency_ms / 1000).toFixed(1)} s`} />
                </div>
                <Table title="Background jobs" empty="No jobs in this period." rows={h.jobs} columns={[
                    ['kind', 'Job'], ['total', 'Runs', 'right', num], ['failed', 'Failed', 'right', num],
                    ['failure_rate', 'Failure rate', 'right', pct], ['avg_seconds', 'Avg time', 'right', (v) => `${v} s`],
                ]} />
                <Table title="Child-safety flags (Class 5–10)" note="Counts only; the content is never stored."
                    empty="No safety flags in this period." rows={h.safety} columns={[
                        ['category', 'Category'], ['level', 'Level', 'left', (v) => LEVEL_NAMES[v] || v], ['count', 'Times', 'right', num],
                    ]} />
            </Section>
        </>
    );
};

export default Analytics;
