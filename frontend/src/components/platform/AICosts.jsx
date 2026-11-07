import React, { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { getPlatformCosts, apiErrorText } from '../../api';
import { Stat, Table, num, pct, usd } from './ui';

const FEATURE_NAMES = {
    chat: 'Chat', deep: 'Deep answers', questions: 'Quizzes', flashcards: 'Flashcards', notes: 'Notes',
    mindmap: 'Mindmaps', visual: 'Visual Lab', cram: 'Exam Tonight', other: 'Other',
};
const featureName = (f) => FEATURE_NAMES[f] || (f?.startsWith('job:') ? `Background: ${f.slice(4)}` : f);

/** Spend per day, with what caching saved stacked on top. */
const Daily = ({ daily }) => {
    if (!daily.length) return null;
    const max = Math.max(...daily.map((d) => Number(d.cost_usd) + Number(d.saved_usd)), 0.000001);
    return (
        <section className="mt-6">
            <h3 className="mb-1 font-bold">Per day</h3>
            <p className="mb-2 flex gap-4 text-xs text-[#5E5046]">
                <span className="flex items-center gap-1"><span className="inline-block h-2.5 w-2.5 rounded-sm bg-[#1E5C42]" /> Spent</span>
                <span className="flex items-center gap-1"><span className="inline-block h-2.5 w-2.5 rounded-sm bg-[#9BC9B0]" /> Saved by caching</span>
            </p>
            <div className="flex h-32 items-end gap-1 rounded-2xl border border-[#E6D5CC] bg-white p-3" role="img"
                aria-label="Daily AI spend and savings">
                {daily.map((d) => {
                    const spent = (Number(d.cost_usd) / max) * 100;
                    const saved = (Number(d.saved_usd) / max) * 100;
                    return (
                        <div key={d.day} className="flex h-full flex-1 flex-col justify-end"
                            title={`${d.day}: spent ${usd(d.cost_usd)}, saved ${usd(d.saved_usd)}, cache hits ${pct(d.cache_hit_rate)}`}>
                            <div className="rounded-t-sm bg-[#9BC9B0]" style={{ height: `${saved}%` }} />
                            <div className="bg-[#1E5C42]" style={{ height: `${spent}%` }} />
                        </div>
                    );
                })}
            </div>
        </section>
    );
};

/** Platform admin: what AI costs, where it goes, and how much caching saves. */
const AICosts = () => {
    const [days, setDays] = useState(30);
    const [data, setData] = useState(null);
    const [error, setError] = useState('');
    useEffect(() => {
        setData(null);
        getPlatformCosts(days).then((d) => { setData(d); setError(''); }).catch((e) => setError(apiErrorText(e)));
    }, [days]);

    return (
        <>
            <div className="mb-4 flex flex-wrap items-center gap-2">
                <p className="mr-auto text-[#5E5046]">Estimated from each call's tokens and the prices in your settings.</p>
                {[7, 30, 90].map((d) => (
                    <button key={d} onClick={() => setDays(d)}
                        className={`rounded-2xl px-3 py-1.5 text-sm font-semibold ${days === d ? 'bg-[#163628] text-white' : 'border border-[#E6D5CC] bg-white'}`}>
                        {d} days
                    </button>
                ))}
            </div>
            {error && <p className="text-sm text-rose-600">{error}</p>}
            {!data && !error && <div className="flex items-center gap-2 text-[#5E5046]"><Loader2 className="h-4 w-4 animate-spin" /> Loading…</div>}
            {data && (
                <>
                    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                        <Stat label="Spent" value={usd(data.totals.cost_usd)} hint={`${num(data.totals.calls)} AI calls`} />
                        <Stat label="Saved by caching" value={usd(data.totals.saved_usd)} hint={`${num(data.totals.cache_hits)} reuses`} />
                        <Stat label="Cache hit rate" value={pct(data.totals.cache_hit_rate)} hint="reuses ÷ (reuses + model calls)" />
                        <Stat label="Learners using AI" value={num(data.totals.users)}
                            hint={`${num(data.totals.tokens)} tokens · ${num(data.totals.errors)} errors`} />
                    </div>
                    <Daily daily={data.daily} />
                    <Table title="By feature" empty="No AI use yet." rows={data.by_feature} columns={[
                        ['feature', 'Feature', 'left', featureName],
                        ['llm_calls', 'Model calls', 'right', num],
                        ['cache_hits', 'Reuses', 'right', num],
                        ['cache_hit_rate', 'Hit rate', 'right', pct],
                        ['cost_usd', 'Spent', 'right', usd],
                        ['saved_usd', 'Saved', 'right', usd],
                    ]} />
                    <Table title="By model" empty="No AI calls yet." rows={data.by_model} columns={[
                        ['model', 'Model', 'left', (m, r) => `${m || '—'} (${r.role || r.kind})`],
                        ['calls', 'Calls', 'right', num],
                        ['input_tokens', 'Input tokens', 'right', num],
                        ['output_tokens', 'Output tokens', 'right', num],
                        ['avg_latency_ms', 'Avg time', 'right', (v) => `${num(v)} ms`],
                        ['cost_usd', 'Spent', 'right', usd],
                    ]} />
                    <Table title="Top learners by cost" empty="No learner has used AI yet." rows={data.by_user} columns={[
                        ['email', 'Learner', 'left', (e, r) => e || r.user_id],
                        ['calls', 'Calls', 'right', num],
                        ['cache_hits', 'Reuses', 'right', num],
                        ['tokens', 'Tokens', 'right', num],
                        ['cost_usd', 'Spent', 'right', usd],
                    ]} />
                </>
            )}
        </>
    );
};

export default AICosts;
