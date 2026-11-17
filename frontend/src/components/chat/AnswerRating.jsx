import { useState } from 'react';
import { ThumbsUp, ThumbsDown } from 'lucide-react';
import { sendFeedback } from '../../api';

const KEY = 'lumina_answer_ratings';
const remembered = () => { try { return JSON.parse(localStorage.getItem(KEY) || '{}'); } catch { return {}; } };

/**
 * Was this answer helpful? One tap, changeable. Stored as feedback (answer_rating) so the
 * admin dashboard shows the share of helpful answers. No answer text is sent.
 */
const AnswerRating = ({ targetId, projectId }) => {
    const [rating, setRating] = useState(() => remembered()[targetId] || 0);

    const rate = (value) => {
        const next = rating === value ? 0 : value;
        setRating(next);
        try {
            const all = remembered();
            if (next) all[targetId] = next; else delete all[targetId];
            const keys = Object.keys(all);
            if (keys.length > 300) keys.slice(0, keys.length - 300).forEach((k) => delete all[k]);
            localStorage.setItem(KEY, JSON.stringify(all));
        } catch { /* fine */ }
        if (next) sendFeedback({ kind: 'answer_rating', rating: next, target_type: 'chat_message', target_id: targetId,
                                 context: { project_id: projectId } }).catch(() => {});
    };

    const btn = (value, Icon, label) => (
        <button type="button" onClick={() => rate(value)} aria-label={label} aria-pressed={rating === value}
            className={`inline-flex h-8 w-8 items-center justify-center rounded-full transition-colors ${rating === value
                ? 'bg-[#1E5C42]/10 text-[#1E5C42]' : 'text-[#5E5046]/70 hover:bg-[#F6F1EA] hover:text-[#163628]'}`}>
            <Icon className="h-4 w-4" />
        </button>
    );

    return (
        <span className="ml-1 inline-flex items-center gap-0.5 align-middle" role="group" aria-label="Rate this answer">
            {btn(1, ThumbsUp, 'Helpful answer')}
            {btn(-1, ThumbsDown, 'Not helpful')}
        </span>
    );
};

export default AnswerRating;
