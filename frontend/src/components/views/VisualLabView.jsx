import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import {
    FlaskConical, Loader2, Search, Sparkles, RefreshCw, Maximize2, Minimize2, Download, AlertTriangle, Wand2,
} from 'lucide-react';
import { generateVisualLab } from '../../api';
import { useSettings } from '../../context/SettingsContext';
import { aiName } from '../../utils/persona';

const EXAMPLES = [
    'Simple pendulum',
    'Tyndall effect',
    'Human heart and the cardiac cycle',
    "Schrödinger's equation: particle in a box",
    'Projectile motion',
    'Refraction and Snell’s law',
    'Photoelectric effect',
    'Binary search',
];

const BUILD_STEPS = [
    'Reading what your book says about it…',
    'Working out the equations…',
    'Building the simulation…',
    'Wiring up the sliders…',
    'Writing the derivation and the why…',
    'Testing it runs…',
];

// Runs inside the sandboxed iframe: blocks all network access and reports
// runtime errors to the parent so a broken simulation can repair itself.
const GUARD = `<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; font-src data:; media-src data: blob:">
<script>(function(){var sent=0;function report(m){if(sent++<3){try{parent.postMessage({type:'lumina-lab-error',message:String(m).slice(0,1500)},'*')}catch(e){}}}
window.addEventListener('error',function(e){report((e.message||'Error')+(e.lineno?' (line '+e.lineno+')':''))});
window.addEventListener('unhandledrejection',function(e){report('Unhandled promise rejection: '+(e.reason&&e.reason.message||e.reason))});
window.alert=window.confirm=window.prompt=function(){};
function mem(){var d={};return{getItem:function(k){return k in d?d[k]:null},setItem:function(k,v){d[k]=String(v)},removeItem:function(k){delete d[k]},clear:function(){d={}},key:function(i){return Object.keys(d)[i]||null},get length(){return Object.keys(d).length}}}
['localStorage','sessionStorage'].forEach(function(n){try{window[n]}catch(e){try{Object.defineProperty(window,n,{value:mem(),configurable:true})}catch(_){}}});})();</script>`;

const withGuard = (html) => {
    const m = html.match(/<head[^>]*>/i);
    if (m) return html.replace(m[0], `${m[0]}\n${GUARD}`);
    return html.replace(/<html[^>]*>/i, (tag) => `${tag}<head>${GUARD}</head>`);
};

const errMsg = (e, fallback) => {
    if (e?.code === 'ECONNABORTED') return 'That took too long, so it was stopped. Try again: builds usually take under a minute.';
    if (!e?.response) return 'Lost the connection while building. Check your internet and try again.';
    const d = e.response.data?.detail;
    return typeof d === 'string' ? d : (d?.message || fallback);
};

/**
 * Visual Lab: turn any topic into a working interactive simulation (sliders,
 * live animation, formulas, derivation and the "why"), generated from the
 * student's own book and run in a locked-down sandbox. If the generated page
 * throws an error, it is sent back once for an automatic repair.
 */
const VisualLabView = ({ projectId, availableTopics = [], selectedDocuments = [], initialTopic = '', onConsumeInitialTopic }) => {
    const { settings } = useSettings();
    const companion = aiName(settings);

    const [query, setQuery] = useState(initialTopic || '');
    const [topic, setTopic] = useState('');
    const [html, setHtml] = useState('');
    const [loading, setLoading] = useState(false);
    const [repairing, setRepairing] = useState(false);
    const [error, setError] = useState('');
    const [runtimeError, setRuntimeError] = useState('');
    const [stepIdx, setStepIdx] = useState(0);
    const [full, setFull] = useState(false);
    const [elapsed, setElapsed] = useState(0);
    const iframeRef = useRef(null);
    const repairedRef = useRef(false);
    const abortRef = useRef(null);
    const buildIdRef = useRef(0);
    const htmlRef = useRef('');
    htmlRef.current = html;

    const suggestions = useMemo(() => {
        const q = query.trim().toLowerCase();
        const pool = availableTopics.length ? availableTopics : EXAMPLES;
        return (q ? pool.filter((t) => t.toLowerCase().includes(q)) : pool).slice(0, 12);
    }, [query, availableTopics]);

    const build = useCallback(async (t, { refresh = false } = {}) => {
        const name = (t || '').trim();
        if (!name) return;
        setTopic(name); setQuery(name);
        setLoading(true); setError(''); setRuntimeError(''); setHtml('');
        repairedRef.current = false;
        abortRef.current?.abort();
        const controller = new AbortController();
        abortRef.current = controller;
        const id = ++buildIdRef.current;
        try {
            const r = await generateVisualLab(projectId, name, { selectedDocuments, refresh, signal: controller.signal });
            if (id !== buildIdRef.current) return;
            if (!r?.html) throw Object.assign(new Error('empty'), { response: { data: { detail: 'The AI returned an empty simulation. Please try again.' } } });
            setHtml(r.html);
        } catch (e) {
            if (id !== buildIdRef.current || controller.signal.aborted) return;
            setError(errMsg(e, 'Could not build this simulation. Please try again.'));
        } finally {
            if (id === buildIdRef.current) setLoading(false);
        }
    }, [projectId, selectedDocuments]);

    const cancel = () => {
        buildIdRef.current++;
        abortRef.current?.abort();
        setLoading(false);
        setError('');
    };
    useEffect(() => () => abortRef.current?.abort(), []);

    // Opened from another screen with a topic ("See it in the Visual Lab")
    useEffect(() => {
        if (initialTopic) {
            build(initialTopic);
            onConsumeInitialTopic?.();
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [initialTopic]);

    // Rotate the "what's happening" line while generating
    useEffect(() => {
        if (!loading && !repairing) return undefined;
        setStepIdx(0);
        setElapsed(0);
        const started = Date.now();
        const id = setInterval(() => setStepIdx((i) => Math.min(i + 1, BUILD_STEPS.length - 1)), 6000);
        const tick = setInterval(() => setElapsed(Math.round((Date.now() - started) / 1000)), 1000);
        return () => { clearInterval(id); clearInterval(tick); };
    }, [loading, repairing]);

    // Errors from inside the simulation: repair once automatically
    useEffect(() => {
        const onMessage = async (ev) => {
            if (ev.source !== iframeRef.current?.contentWindow) return;
            if (ev.data?.type !== 'lumina-lab-error') return;
            const message = ev.data.message || 'Unknown error';
            if (repairedRef.current) { setRuntimeError(message); return; }
            repairedRef.current = true;
            setRepairing(true);
            try {
                const r = await generateVisualLab(projectId, topic, {
                    selectedDocuments, repair: { html: htmlRef.current, error: message },
                });
                setHtml(r.html);
            } catch {
                setRuntimeError(message);
            } finally {
                setRepairing(false);
            }
        };
        window.addEventListener('message', onMessage);
        return () => window.removeEventListener('message', onMessage);
    }, [projectId, topic, selectedDocuments]);

    const download = () => {
        const blob = new Blob([html], { type: 'text/html' });
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = `${topic.replace(/[^a-z0-9]+/gi, '-').toLowerCase() || 'simulation'}.html`;
        a.click();
        setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    };

    const busy = loading || repairing;

    return (
        <div className={`h-full flex flex-col ${full ? 'fixed inset-0 z-[70] bg-[#FDF6F0]' : ''}`}>
            {/* Topic bar */}
            <div className="shrink-0 p-3 md:p-4 border-b border-[#E6D5CC]">
                <form className="max-w-5xl mx-auto flex gap-2" onSubmit={(e) => { e.preventDefault(); build(query); }}>
                    <div className="relative flex-1">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#8a6a5c]" />
                        <input value={query} onChange={(e) => setQuery(e.target.value)}
                            placeholder="Any topic: pendulum, Tyndall effect, the human heart…"
                            className="w-full rounded-2xl border border-[#E6D5CC] bg-white pl-9 pr-3 py-2.5 text-[#4A3B32] placeholder-[#8a6a5c] outline-none focus:ring-2 focus:ring-[#C8A288]" />
                    </div>
                    <button type="submit" disabled={busy || !query.trim()}
                        className="inline-flex items-center gap-2 rounded-2xl bg-[#C8A288] px-4 py-2.5 font-semibold text-white hover:bg-[#B08B72] disabled:opacity-50">
                        <Wand2 className="h-4 w-4" /> <span className="hidden sm:inline">Visualize</span>
                    </button>
                    {html && (
                        <>
                            <button type="button" onClick={() => build(topic, { refresh: true })} disabled={busy} title="Build a fresh version"
                                className="rounded-2xl border border-[#E6D5CC] bg-white px-3 text-[#4A3B32] hover:border-[#C8A288] disabled:opacity-50"><RefreshCw className="h-4 w-4" /></button>
                            <button type="button" onClick={download} title="Download as an HTML file"
                                className="hidden sm:block rounded-2xl border border-[#E6D5CC] bg-white px-3 text-[#4A3B32] hover:border-[#C8A288]"><Download className="h-4 w-4" /></button>
                            <button type="button" onClick={() => setFull((f) => !f)} title={full ? 'Exit full screen' : 'Full screen'}
                                className="rounded-2xl border border-[#E6D5CC] bg-white px-3 text-[#4A3B32] hover:border-[#C8A288]">{full ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}</button>
                        </>
                    )}
                </form>
            </div>

            <div className="flex-1 min-h-0 relative">
                {html && (
                    <iframe ref={iframeRef} title={`Simulation: ${topic}`}
                        sandbox="allow-scripts" srcDoc={withGuard(html)}
                        className="absolute inset-0 h-full w-full border-0 bg-[#0f172a]" />
                )}

                {busy && (
                    <div className="absolute inset-0 flex items-center justify-center bg-[#FDF6F0]/90 p-6">
                        <div className="max-w-sm text-center">
                            <div className="relative mx-auto h-16 w-16">
                                <FlaskConical className="h-16 w-16 text-[#C8A288]" />
                                <Loader2 className="absolute -right-2 -bottom-2 h-6 w-6 animate-spin text-[#C8A288]" />
                            </div>
                            <h3 className="mt-3 text-lg font-bold text-[#4A3B32]">{repairing ? 'Fixing a glitch in the simulation…' : `${companion} is building “${topic}”`}</h3>
                            <p className="mt-1 text-sm text-[#8a6a5c]">{BUILD_STEPS[stepIdx]}</p>
                            <p className="mt-3 text-xs text-[#8a6a5c]">
                                {elapsed < 75 ? 'A first build takes up to a minute. Next time it opens instantly.' : 'Taking longer than usual. You can wait a bit more or try again.'}
                                <span className="ml-1 tabular-nums">({elapsed}s)</span>
                            </p>
                            {loading && (
                                <div className="mt-4 flex justify-center gap-2">
                                    {elapsed >= 75 && (
                                        <button onClick={() => build(topic)} className="rounded-xl bg-[#C8A288] px-4 py-2 text-sm font-semibold text-white hover:bg-[#B08B72]">Try again</button>
                                    )}
                                    <button onClick={cancel} className="rounded-xl border border-[#E6D5CC] bg-white px-4 py-2 text-sm font-semibold text-[#4A3B32] hover:border-[#C8A288]">Cancel</button>
                                </div>
                            )}
                        </div>
                    </div>
                )}

                {runtimeError && !busy && (
                    <div className="absolute bottom-3 left-3 right-3 md:left-auto md:max-w-md rounded-2xl border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 shadow-lg">
                        <div className="flex items-start gap-2">
                            <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
                            <div className="flex-1">Part of this simulation hit an error, so some controls might not work.
                                <button onClick={() => build(topic, { refresh: true })} className="ml-1 font-semibold underline">Build a fresh one</button>
                            </div>
                            <button onClick={() => setRuntimeError('')} className="font-bold" aria-label="Dismiss">×</button>
                        </div>
                    </div>
                )}

                {!html && !busy && (
                    <div className="h-full overflow-y-auto p-4 md:p-8">
                        <div className="max-w-3xl mx-auto">
                            <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
                                className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-[#0f172a] via-[#1e293b] to-[#134e4a] p-6 md:p-8 text-white shadow-xl">
                                <div className="absolute -right-12 -top-12 h-52 w-52 rounded-full bg-teal-400/20 blur-3xl" />
                                <div className="relative flex items-center gap-2 text-teal-200 text-sm font-semibold"><FlaskConical className="h-4 w-4" /> Visual Lab</div>
                                <h2 className="relative mt-2 text-3xl md:text-4xl font-bold leading-tight">See it. Play with it. Get it.</h2>
                                <p className="relative mt-2 text-white/80 max-w-xl">
                                    Pick a topic and get a working simulation built from your book, with sliders to experiment,
                                    the formulas, a step-by-step derivation and why it happens. Like a lab practical, on any screen.
                                </p>
                            </motion.div>
                            {error && <p className="mt-4 rounded-2xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}
                            <div className="mt-5 rounded-3xl border border-[#E6D5CC] bg-white p-5">
                                <h3 className="font-bold text-[#4A3B32] flex items-center gap-2"><Sparkles className="h-4 w-4 text-[#C8A288]" /> {availableTopics.length ? 'From your book' : 'Try one'}</h3>
                                <div className="mt-3 flex flex-wrap gap-2">
                                    {suggestions.map((t) => (
                                        <button key={t} onClick={() => build(t)}
                                            className="rounded-full border border-[#E6D5CC] bg-white px-3 py-1.5 text-sm text-[#4A3B32] hover:border-[#C8A288] hover:bg-[#FDF6F0]">{t}</button>
                                    ))}
                                    {!suggestions.length && <p className="text-sm text-[#8a6a5c]">No matching topic, so press Visualize to build “{query}” anyway.</p>}
                                </div>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default VisualLabView;
