/**
 * Device-local daily learning progress: focused minutes, cards completed and
 * questions answered. Powers the daily goal ring and daily quests.
 * Kept in localStorage per user; resets naturally each day.
 */

const todayKey = () => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};

const storageKey = (userId) => `lumina_daily_${userId || 'anon'}`;
const EVENT = 'lumina-daily-progress';

const empty = () => ({ date: todayKey(), minutes: 0, cards: 0, answered: 0, correct: 0, bestCombo: 0 });

export const getDailyProgress = (userId) => {
    try {
        const raw = JSON.parse(localStorage.getItem(storageKey(userId)) || 'null');
        if (raw && raw.date === todayKey()) return { ...empty(), ...raw };
    } catch { /* ignore */ }
    return empty();
};

export const bumpDailyProgress = (userId, delta) => {
    const cur = getDailyProgress(userId);
    const next = { ...cur };
    for (const [k, v] of Object.entries(delta)) {
        if (k === 'bestCombo') next.bestCombo = Math.max(cur.bestCombo, v);
        else next[k] = (cur[k] || 0) + v;
    }
    try { localStorage.setItem(storageKey(userId), JSON.stringify(next)); } catch { /* ignore */ }
    window.dispatchEvent(new CustomEvent(EVENT, { detail: next }));
    return next;
};

export const onDailyProgress = (cb) => {
    const handler = (e) => cb(e.detail);
    window.addEventListener(EVENT, handler);
    return () => window.removeEventListener(EVENT, handler);
};

export const dailyQuests = (p, goalMinutes = 30) => [
    { id: 'minutes', emoji: '⏱️', label: `Study ${goalMinutes} minutes`, value: Math.min(p.minutes, goalMinutes), target: goalMinutes },
    { id: 'cards', emoji: '⚡', label: 'Master 5 Power Hour cards', value: Math.min(p.cards, 5), target: 5 },
    { id: 'answered', emoji: '🎯', label: 'Answer 10 questions', value: Math.min(p.answered, 10), target: 10 },
];

export const LAST_PROJECT_KEY = 'lumina_last_project';
