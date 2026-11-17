import { useEffect, useState } from 'react';
import { X } from 'lucide-react';
import { sendFeedback } from '../api';

const SEEN_KEY = 'lumina_nps_first_seen';
const ASKED_KEY = 'lumina_nps_asked_at';
const DAY = 86400000;

/**
 * "How likely are you to recommend Lumina IQ?" (0–10), asked once a learner has used the
 * app for a week, then at most every four months. Answering or closing both count as asked.
 */
const NpsPrompt = () => {
    const [show, setShow] = useState(false);
    const [score, setScore] = useState(null);
    const [comment, setComment] = useState('');
    const [done, setDone] = useState(false);

    useEffect(() => {
        try {
            const now = Date.now();
            const first = Number(localStorage.getItem(SEEN_KEY) || 0);
            if (!first) { localStorage.setItem(SEEN_KEY, String(now)); return; }
            const asked = Number(localStorage.getItem(ASKED_KEY) || 0);
            if (now - first > 7 * DAY && now - asked > 120 * DAY) setShow(true);
        } catch { /* storage blocked: don't ask */ }
    }, []);

    const markAsked = () => { try { localStorage.setItem(ASKED_KEY, String(Date.now())); } catch { /* fine */ } };
    const close = () => { markAsked(); setShow(false); };
    const submit = () => {
        markAsked();
        sendFeedback({ kind: 'nps', rating: score, comment: comment.trim() || null }).catch(() => {});
        setDone(true);
        setTimeout(() => setShow(false), 1800);
    };

    if (!show) return null;
    return (
        <div className="fixed bottom-4 left-1/2 z-[70] w-[calc(100%-2rem)] max-w-md -translate-x-1/2 rounded-2xl border border-[#E6D5CC] bg-white p-4 shadow-xl"
            role="dialog" aria-labelledby="nps-title">
            <button type="button" onClick={close} aria-label="Close" className="absolute right-2 top-2 rounded-full p-1.5 text-[#5E5046] hover:bg-[#F6F1EA]">
                <X className="h-4 w-4" />
            </button>
            {done ? <p className="py-2 text-center font-semibold text-[#163628]">Thank you! 💚</p> : (
                <>
                    <p id="nps-title" className="pr-6 font-semibold text-[#163628]">How likely are you to recommend Lumina IQ to a friend?</p>
                    <div className="mt-3 grid grid-cols-11 gap-1">
                        {Array.from({ length: 11 }, (_, i) => (
                            <button key={i} type="button" onClick={() => setScore(i)} aria-pressed={score === i}
                                className={`h-9 rounded-lg text-sm font-semibold tabular-nums ${score === i ? 'bg-[#1E5C42] text-white' : 'bg-[#F6F1EA] text-[#163628] hover:bg-[#EADFD3]'}`}>
                                {i}
                            </button>
                        ))}
                    </div>
                    <div className="mt-1 flex justify-between text-[11px] text-[#5E5046]"><span>Not likely</span><span>Very likely</span></div>
                    {score !== null && (
                        <>
                            <textarea value={comment} onChange={(e) => setComment(e.target.value)} rows={2} maxLength={1000}
                                placeholder="What's the main reason? (optional)"
                                className="mt-3 w-full rounded-xl border border-[#D8CFC4] px-3 py-2 text-base text-[#163628] focus:border-[#1E5C42] focus:outline-none" />
                            <button type="button" onClick={submit} className="mt-2 w-full rounded-xl bg-[#1E5C42] py-2.5 font-bold text-white hover:bg-[#163628]">
                                Send
                            </button>
                        </>
                    )}
                </>
            )}
        </div>
    );
};

export default NpsPrompt;
