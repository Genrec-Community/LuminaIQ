import React, { useCallback, useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    X, Loader2, Stethoscope, Lightbulb, Footprints, PenLine, Shuffle, CalendarClock, ArrowRight, CheckCircle2,
    XCircle, Eye, Sparkles, RotateCcw, Scale,
} from 'lucide-react';
import { getLesson, gradeRecall, recordLearning, getLearningPlan } from '../api';

/*
 * The six-step lesson the learning engine sends a student to:
 * diagnose → mental model → worked example (then guided, support faded) →
 * explain from memory → apply + contrast → next review scheduled.
 * Every answer is evidence for the learner model.
 */

const STEPS = [
    { id: 'diagnose', label: 'Check', icon: Stethoscope },
    { id: 'model', label: 'Understand', icon: Lightbulb },
    { id: 'worked', label: 'Example', icon: Footprints },
    { id: 'recall', label: 'Recall', icon: PenLine },
    { id: 'apply', label: 'Apply', icon: Shuffle },
    { id: 'done', label: 'Schedule', icon: CalendarClock },
];

const Card = ({ children, className = '' }) => (
    <div className={`rounded-2xl border border-[#E6D5CC] bg-white p-4 md:p-5 ${className}`}>{children}</div>
);

const Label = ({ children }) => (
    <div className="mb-1.5 text-xs font-bold uppercase tracking-wide text-[#1E5C42]">{children}</div>
);

const Primary = ({ children, ...props }) => (
    <button {...props} className={`inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-[#1E5C42] px-5 py-3 font-semibold text-white hover:bg-[#163628] disabled:opacity-50 sm:w-auto ${props.className || ''}`}>{children}</button>
);

const Secondary = ({ children, ...props }) => (
    <button {...props} className={`inline-flex w-full items-center justify-center gap-2 rounded-2xl border-2 border-[#E6D5CC] px-5 py-3 font-semibold text-[#163628] hover:border-[#1E5C42] hover:bg-[#FDF6F0] sm:w-auto ${props.className || ''}`}>{children}</button>
);

/** One multiple-choice question; reports right/wrong once. */
const Question = ({ item, index, total, onAnswered, badge }) => {
    const [picked, setPicked] = useState(null);
    const answered = picked !== null;
    const choose = (i) => {
        if (answered) return;
        setPicked(i);
        onAnswered(i === item.answer_index);
    };
    return (
        <Card>
            <div className="mb-2 flex items-center justify-between text-xs text-[#5E5046]">
                <span>{badge || `Question ${index + 1} of ${total}`}</span>
                {item.difficulty === 'hard' && <span className="rounded-full bg-[#FDF6F0] px-2 py-0.5 font-semibold">harder</span>}
            </div>
            <p className="font-semibold leading-relaxed text-[#163628]">{item.q}</p>
            <div className="mt-3 space-y-2">
                {item.options.map((o, i) => {
                    const right = answered && i === item.answer_index;
                    const wrong = answered && i === picked && i !== item.answer_index;
                    return (
                        <button key={i} onClick={() => choose(i)} disabled={answered}
                            className={`flex w-full items-start gap-2 rounded-xl border-2 px-3 py-2.5 text-left text-sm transition-colors ${right ? 'border-emerald-400 bg-emerald-50' : wrong ? 'border-rose-300 bg-rose-50' : 'border-[#E6D5CC] hover:border-[#1E5C42]'}`}>
                            {right ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" /> : wrong ? <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-rose-500" /> : <span className="mt-0.5 h-4 w-4 shrink-0 rounded-full border-2 border-[#E6D5CC]" />}
                            <span className="text-[#163628]">{o}</span>
                        </button>
                    );
                })}
            </div>
            {answered && item.why && <p className="mt-3 rounded-xl bg-[#FDF6F0] p-3 text-sm text-[#163628]">{item.why}</p>}
        </Card>
    );
};

/** A run of questions shown one after another; calls onDone(rightCount). */
const QuestionRun = ({ items, onAnswer, onDone, doneLabel = 'Continue', badges = [] }) => {
    const [i, setI] = useState(0);
    const [answered, setAnswered] = useState(false);
    const right = useRef(0);
    if (!items.length) return <Primary onClick={() => onDone(0)}>{doneLabel} <ArrowRight className="h-4 w-4" /></Primary>;
    const item = items[i];
    return (
        <div className="space-y-3">
            <Question key={i} item={item} index={i} total={items.length} badge={badges[i]}
                onAnswered={(ok) => { if (ok) right.current += 1; setAnswered(true); onAnswer?.(item, ok); }} />
            {answered && (
                <Primary onClick={() => {
                    if (i + 1 < items.length) { setI(i + 1); setAnswered(false); } else onDone(right.current);
                }}>
                    {i + 1 < items.length ? 'Next question' : doneLabel} <ArrowRight className="h-4 w-4" />
                </Primary>
            )}
        </div>
    );
};

const LessonView = ({ projectId, topic, selectedDocuments = [], onClose, onNextTopic }) => {
    const [lesson, setLesson] = useState(null);
    const [error, setError] = useState('');
    const [step, setStep] = useState('diagnose');
    const [diagRight, setDiagRight] = useState(null);
    const [workedShown, setWorkedShown] = useState(1);
    const [guidedTry, setGuidedTry] = useState('');
    const [hintShown, setHintShown] = useState(false);
    const [solutionShown, setSolutionShown] = useState(false);
    const [selfGraded, setSelfGraded] = useState(false);
    const [recallText, setRecallText] = useState('');
    const [grading, setGrading] = useState(false);
    const [grade, setGrade] = useState(null);
    const [applyRight, setApplyRight] = useState(null);
    const [outcome, setOutcome] = useState(null);
    const scrollRef = useRef(null);

    const load = useCallback(async (refresh = false) => {
        setError('');
        setLesson(null);
        try {
            const res = await getLesson(projectId, topic, selectedDocuments, refresh);
            setLesson(res.lesson);
        } catch (e) {
            setError(e?.response?.data?.detail || "Couldn't prepare this lesson. Try again in a moment.");
        }
    }, [projectId, topic, selectedDocuments]);

    useEffect(() => { load(); }, [load]);
    useEffect(() => { scrollRef.current?.scrollTo({ top: 0 }); }, [step]);

    const evidence = (item, correct, kind = 'mcq') => recordLearning(projectId, {
        topic, correct, kind, difficulty: item?.difficulty || 'medium', source: 'lesson',
    });

    // Final step: ask the engine what changed and what comes next
    useEffect(() => {
        if (step !== 'done') return;
        let cancelled = false;
        const t = setTimeout(async () => {
            try {
                const plan = await getLearningPlan(projectId, { horizon: 3, documents: selectedDocuments });
                if (cancelled) return;
                const row = (plan.profile || []).find((p) => p.topic === topic);
                const next = (plan.sequence || []).find((s) => s.topic !== topic);
                setOutcome({ row, next });
            } catch { if (!cancelled) setOutcome({}); }
        }, 1800); // let batched answers reach the server first
        return () => { cancelled = true; clearTimeout(t); };
    }, [step, projectId, topic, selectedDocuments]);

    const stepIndex = STEPS.findIndex((s) => s.id === step);
    const applyItems = lesson ? [...lesson.apply, ...(lesson.contrast ? [lesson.contrast] : [])] : [];
    const reviewDays = outcome?.row?.next_review ? Math.max(1, Math.round((new Date(outcome.row.next_review) - Date.now()) / 86400000)) : null;

    return (
        <div className="fixed inset-0 z-[70] flex flex-col bg-[#FDF6F0]" style={{ paddingTop: 'var(--sat, 0px)', paddingBottom: 'var(--sab, 0px)' }}>
            {/* Header with step dots */}
            <div className="border-b border-[#E6D5CC] bg-white/80 px-4 py-3 backdrop-blur">
                <div className="mx-auto flex max-w-2xl items-center gap-3">
                    <div className="min-w-0 flex-1">
                        <div className="text-xs font-semibold text-[#5E5046]">Lesson</div>
                        <div className="truncate font-bold text-[#163628]">{topic}</div>
                    </div>
                    <button onClick={onClose} aria-label="Close lesson" className="rounded-xl p-2 text-[#5E5046] hover:bg-[#FDF6F0]"><X className="h-5 w-5" /></button>
                </div>
                <div className="mx-auto mt-3 flex max-w-2xl items-center gap-1.5">
                    {STEPS.map((s, i) => {
                        const Icon = s.icon;
                        const done = i < stepIndex;
                        const current = i === stepIndex;
                        return (
                            <div key={s.id} className="flex flex-1 flex-col items-center gap-1">
                                <div className={`flex h-7 w-7 items-center justify-center rounded-full ${current ? 'bg-[#1E5C42] text-white' : done ? 'bg-[#E6D5CC] text-[#5E5046]' : 'bg-white text-[#cbb8ab] border border-[#E6D5CC]'}`}>
                                    <Icon className="h-3.5 w-3.5" />
                                </div>
                                <span className={`hidden text-[10px] sm:block ${current ? 'font-bold text-[#163628]' : 'text-[#5E5046]'}`}>{s.label}</span>
                            </div>
                        );
                    })}
                </div>
            </div>

            <div ref={scrollRef} className="flex-1 overflow-y-auto">
                <div className="mx-auto max-w-2xl p-4 md:p-6">
                    {error ? (
                        <Card className="text-center">
                            <p className="text-[#163628]">{error}</p>
                            <div className="mt-3 flex justify-center gap-2">
                                <Primary onClick={() => load(true)}>Try again</Primary>
                                <Secondary onClick={onClose}>Close</Secondary>
                            </div>
                        </Card>
                    ) : !lesson ? (
                        <div className="flex items-center justify-center gap-3 py-20 text-[#5E5046]">
                            <Loader2 className="h-5 w-5 animate-spin text-[#1E5C42]" /> Preparing your lesson…
                        </div>
                    ) : (
                        <AnimatePresence mode="wait">
                            <motion.div key={step} initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} className="space-y-4">
                                {step === 'diagnose' && (
                                    <>
                                        <div>
                                            <h2 className="text-xl font-bold text-[#163628]">First, what do you already know?</h2>
                                            <p className="mt-1 text-sm text-[#5E5046]">Two quick questions. If you nail them, we skip ahead.</p>
                                        </div>
                                        {diagRight === null ? (
                                            <QuestionRun items={lesson.diagnose} onAnswer={(item, ok) => evidence(item, ok)}
                                                onDone={(n) => { if (!lesson.diagnose.length) setStep('model'); else setDiagRight(n); }} doneLabel="See result" />
                                        ) : (
                                            <Card>
                                                {diagRight === lesson.diagnose.length ? (
                                                    <>
                                                        <p className="font-semibold text-[#163628]">You already have the basics.</p>
                                                        <p className="mt-1 text-sm text-[#5E5046]">Skip to applying it, or walk through it anyway.</p>
                                                        <div className="mt-3 flex flex-col gap-2 sm:flex-row">
                                                            <Primary onClick={() => setStep('apply')}>Skip to applying <ArrowRight className="h-4 w-4" /></Primary>
                                                            <Secondary onClick={() => setStep('model')}>Walk me through it</Secondary>
                                                        </div>
                                                    </>
                                                ) : (
                                                    <>
                                                        <p className="font-semibold text-[#163628]">{diagRight ? 'A good start.' : 'No problem — that is what this lesson is for.'}</p>
                                                        <p className="mt-1 text-sm text-[#5E5046]">Let's build the idea properly.</p>
                                                        <Primary className="mt-3" onClick={() => setStep('model')}>Start <ArrowRight className="h-4 w-4" /></Primary>
                                                    </>
                                                )}
                                            </Card>
                                        )}
                                    </>
                                )}

                                {step === 'model' && (
                                    <>
                                        <h2 className="text-xl font-bold text-[#163628]">The idea</h2>
                                        <Card><Label>In a nutshell</Label><p className="leading-relaxed text-[#163628]">{lesson.model.core}</p></Card>
                                        {lesson.model.why && <Card><Label>Why it exists</Label><p className="leading-relaxed text-[#163628]">{lesson.model.why}</p></Card>}
                                        {lesson.model.connects && <Card><Label>How it connects</Label><p className="leading-relaxed text-[#163628]">{lesson.model.connects}</p></Card>}
                                        {lesson.model.example && (
                                            <Card className="border-amber-200 bg-amber-50">
                                                <div className="mb-1.5 flex items-center gap-1 text-xs font-bold uppercase tracking-wide text-amber-800"><Sparkles className="h-3.5 w-3.5" /> For example</div>
                                                <p className="leading-relaxed text-amber-950">{lesson.model.example}</p>
                                            </Card>
                                        )}
                                        <Primary onClick={() => setStep('worked')}>See it worked through <ArrowRight className="h-4 w-4" /></Primary>
                                    </>
                                )}

                                {step === 'worked' && (
                                    <>
                                        <h2 className="text-xl font-bold text-[#163628]">Worked example</h2>
                                        <Card>
                                            <Label>Problem</Label>
                                            <p className="leading-relaxed text-[#163628]">{lesson.worked_example.problem}</p>
                                            <ol className="mt-3 space-y-2">
                                                {lesson.worked_example.steps.slice(0, workedShown).map((s, i) => (
                                                    <motion.li key={i} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="flex gap-3">
                                                        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[#1E5C42] text-xs font-bold text-white">{i + 1}</span>
                                                        <span className="leading-relaxed text-[#163628]">{s}</span>
                                                    </motion.li>
                                                ))}
                                            </ol>
                                            {workedShown < lesson.worked_example.steps.length ? (
                                                <button onClick={() => setWorkedShown((n) => n + 1)} className="mt-3 text-sm font-semibold text-[#163628] hover:underline">Next step →</button>
                                            ) : lesson.worked_example.takeaway && (
                                                <p className="mt-3 rounded-xl bg-[#FDF6F0] p-3 text-sm font-semibold text-[#163628]">{lesson.worked_example.takeaway}</p>
                                            )}
                                        </Card>

                                        {workedShown >= lesson.worked_example.steps.length && lesson.guided.problem && (
                                            <Card>
                                                <Label>Your turn</Label>
                                                <p className="leading-relaxed text-[#163628]">{lesson.guided.problem}</p>
                                                <textarea value={guidedTry} onChange={(e) => setGuidedTry(e.target.value)} rows={3} placeholder="Work it out here (optional)…"
                                                    className="mt-3 w-full rounded-xl border border-[#E6D5CC] p-3 text-sm text-[#163628] focus:border-[#1E5C42] focus:outline-none" />
                                                {hintShown && lesson.guided.hint && <p className="mt-2 rounded-xl bg-amber-50 p-3 text-sm text-amber-950"><b>Hint:</b> {lesson.guided.hint}</p>}
                                                {solutionShown && <p className="mt-2 rounded-xl bg-emerald-50 p-3 text-sm text-emerald-950"><b>Answer:</b> {lesson.guided.solution}</p>}
                                                <div className="mt-3 flex flex-wrap gap-2">
                                                    {!hintShown && !solutionShown && lesson.guided.hint && <Secondary onClick={() => setHintShown(true)}><Lightbulb className="h-4 w-4" /> Hint</Secondary>}
                                                    {!solutionShown && <Secondary onClick={() => setSolutionShown(true)}><Eye className="h-4 w-4" /> Show answer</Secondary>}
                                                </div>
                                                {solutionShown && !selfGraded && (
                                                    <div className="mt-3 flex flex-col gap-2 sm:flex-row">
                                                        <Secondary onClick={() => { setSelfGraded(true); recordLearning(projectId, { topic, correct: true, kind: 'flashcard', hinted: hintShown, source: 'lesson' }); }}>I got it</Secondary>
                                                        <Secondary onClick={() => { setSelfGraded(true); recordLearning(projectId, { topic, correct: false, kind: 'flashcard', source: 'lesson' }); }}>I didn't</Secondary>
                                                    </div>
                                                )}
                                            </Card>
                                        )}
                                        {workedShown >= lesson.worked_example.steps.length && (!lesson.guided.problem || selfGraded) && (
                                            <Primary onClick={() => setStep('recall')}>Now explain it yourself <ArrowRight className="h-4 w-4" /></Primary>
                                        )}
                                    </>
                                )}

                                {step === 'recall' && (
                                    <>
                                        <div>
                                            <h2 className="text-xl font-bold text-[#163628]">From memory</h2>
                                            <p className="mt-1 text-sm text-[#5E5046]">No peeking. Putting it in your own words is what makes it stick.</p>
                                        </div>
                                        <Card>
                                            <p className="font-semibold leading-relaxed text-[#163628]">{lesson.recall.prompt}</p>
                                            <textarea value={recallText} onChange={(e) => setRecallText(e.target.value)} rows={6} disabled={!!grade}
                                                placeholder="Write your explanation…"
                                                className="mt-3 w-full rounded-xl border border-[#E6D5CC] p-3 text-sm text-[#163628] focus:border-[#1E5C42] focus:outline-none disabled:bg-[#FDF6F0]" />
                                            {!grade && (
                                                <div className="mt-3 flex flex-col gap-2 sm:flex-row">
                                                    <Primary disabled={grading || recallText.trim().length < 15} onClick={async () => {
                                                        setGrading(true);
                                                        try { setGrade(await gradeRecall(projectId, topic, lesson.recall.prompt, recallText, lesson.recall.key_points)); }
                                                        catch { setGrade({ score: null, feedback: "Couldn't check that right now — compare it with the key points below.", covered: [], missing: lesson.recall.key_points }); }
                                                        finally { setGrading(false); }
                                                    }}>{grading ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />} Check my explanation</Primary>
                                                    <Secondary onClick={() => setStep('apply')}>Skip</Secondary>
                                                </div>
                                            )}
                                        </Card>
                                        {grade && (
                                            <Card>
                                                {grade.score != null && (
                                                    <div className="mb-3 flex items-center gap-3">
                                                        <div className="text-3xl font-bold text-[#163628]">{Math.round(grade.score * 100)}%</div>
                                                        <div className="h-2 flex-1 overflow-hidden rounded-full bg-[#F1E6DD]">
                                                            <div className="h-full rounded-full bg-[#1E5C42]" style={{ width: `${Math.round(grade.score * 100)}%` }} />
                                                        </div>
                                                    </div>
                                                )}
                                                {grade.feedback && <p className="leading-relaxed text-[#163628]">{grade.feedback}</p>}
                                                {grade.covered?.length > 0 && (
                                                    <ul className="mt-3 space-y-1 text-sm">{grade.covered.map((c) => <li key={c} className="flex gap-2 text-emerald-800"><CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />{c}</li>)}</ul>
                                                )}
                                                {grade.missing?.length > 0 && (
                                                    <ul className="mt-2 space-y-1 text-sm">{grade.missing.map((c) => <li key={c} className="flex gap-2 text-rose-800"><XCircle className="mt-0.5 h-4 w-4 shrink-0" />{c}</li>)}</ul>
                                                )}
                                                {grade.misconception && <p className="mt-3 rounded-xl bg-rose-50 p-3 text-sm text-rose-900"><b>Watch out:</b> {grade.misconception}</p>}
                                                <Primary className="mt-4" onClick={() => setStep('apply')}>Apply it <ArrowRight className="h-4 w-4" /></Primary>
                                            </Card>
                                        )}
                                    </>
                                )}

                                {step === 'apply' && (
                                    <>
                                        <div>
                                            <h2 className="text-xl font-bold text-[#163628]">Use it somewhere new</h2>
                                            <p className="mt-1 text-sm text-[#5E5046]">Unfamiliar situations show whether you really understand it{lesson.contrast ? `, and how it differs from “${lesson.contrast.with}”` : ''}.</p>
                                        </div>
                                        {applyRight === null ? (
                                            <QuestionRun items={applyItems}
                                                badges={applyItems.map((it, i) => (lesson.contrast && i === applyItems.length - 1 ? `Tell them apart: ${topic} vs ${lesson.contrast.with}` : `Scenario ${i + 1} of ${lesson.apply.length}`))}
                                                onAnswer={(item, ok) => evidence({ difficulty: 'hard' }, ok)}
                                                onDone={(n) => { setApplyRight(n); setStep('done'); }} doneLabel="Finish lesson" />
                                        ) : null}
                                    </>
                                )}

                                {step === 'done' && (
                                    <>
                                        <div className="text-center">
                                            <CheckCircle2 className="mx-auto h-12 w-12 text-[#1E5C42]" />
                                            <h2 className="mt-2 text-2xl font-bold text-[#163628]">Lesson done</h2>
                                            {applyRight != null && <p className="mt-1 text-[#5E5046]">{applyRight} of {applyItems.length} new situations handled.</p>}
                                        </div>
                                        <Card>
                                            {!outcome ? (
                                                <div className="flex items-center gap-2 text-sm text-[#5E5046]"><Loader2 className="h-4 w-4 animate-spin text-[#1E5C42]" /> Updating what you know…</div>
                                            ) : (
                                                <div className="space-y-3">
                                                    {outcome.row && (
                                                        <div>
                                                            <div className="flex items-baseline justify-between">
                                                                <span className="font-semibold text-[#163628]">Your mastery of this topic</span>
                                                                <span className="text-lg font-bold text-[#163628]">{Math.round(outcome.row.mastery * 100)}%</span>
                                                            </div>
                                                            <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-[#F1E6DD]"><div className="h-full rounded-full bg-[#1E5C42]" style={{ width: `${Math.round(outcome.row.mastery * 100)}%` }} /></div>
                                                            <p className="mt-1 text-xs text-[#5E5046]">Estimate {outcome.row.confidence}{outcome.row.mastery < 0.85 ? ' — a bit more practice will lock it in.' : '.'}</p>
                                                        </div>
                                                    )}
                                                    {reviewDays && (
                                                        <p className="flex items-center gap-2 text-sm text-[#163628]"><RotateCcw className="h-4 w-4 text-[#5E8C6A]" /> Lumina will bring it back for review in about <b>{reviewDays} day{reviewDays > 1 ? 's' : ''}</b>, just before you'd start forgetting.</p>
                                                    )}
                                                    {outcome.next && (
                                                        <div className="rounded-xl bg-[#FDF6F0] p-3">
                                                            <div className="text-xs font-bold uppercase tracking-wide text-[#1E5C42]">Up next</div>
                                                            <div className="font-semibold text-[#163628]">{outcome.next.topic}</div>
                                                            <div className="text-xs text-[#5E5046]">{outcome.next.reason}</div>
                                                        </div>
                                                    )}
                                                </div>
                                            )}
                                        </Card>
                                        <div className="flex flex-col gap-2 sm:flex-row">
                                            {outcome?.next && onNextTopic && (
                                                <Primary onClick={() => onNextTopic(outcome.next.topic)}>Next lesson <ArrowRight className="h-4 w-4" /></Primary>
                                            )}
                                            <Secondary onClick={onClose}>Back to my path</Secondary>
                                        </div>
                                        {lesson.contrast && <p className="flex items-center justify-center gap-1.5 text-xs text-[#5E5046]"><Scale className="h-3.5 w-3.5" /> Tip: revisit “{lesson.contrast.with}” soon to keep the two apart.</p>}
                                    </>
                                )}
                            </motion.div>
                        </AnimatePresence>
                    )}
                </div>
            </div>
        </div>
    );
};

export default LessonView;
