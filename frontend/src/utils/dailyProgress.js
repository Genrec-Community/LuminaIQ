/**
 * Device-local daily learning progress: active study time, cards completed and
 * questions answered. Powers the daily goal ring and daily quests.
 * Kept in localStorage per user; resets naturally each day.
 */

import { markActive } from './activeTime';

const todayKey = () => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};

const storageKey = (userId) => `lumina_daily_${userId || 'anon'}`;
const EVENT = 'lumina-daily-progress';

// `seconds` is the measured active time; `minutes` is derived from it for display.
const empty = () => ({ date: todayKey(), seconds: 0, minutes: 0, cards: 0, answered: 0, correct: 0, bestCombo: 0 });

export const getDailyProgress = (userId) => {
    try {
        const raw = JSON.parse(localStorage.getItem(storageKey(userId)) || 'null');
        if (raw && raw.date === todayKey()) {
            const p = { ...empty(), ...raw };
            // Saved before time was kept in seconds
            if (raw.seconds == null) p.seconds = (raw.minutes || 0) * 60;
            p.minutes = Math.floor(p.seconds / 60);
            return p;
        }
    } catch { /* ignore */ }
    return empty();
};

export const bumpDailyProgress = (userId, delta) => {
    if (delta.answered || delta.cards) markActive();
    const cur = getDailyProgress(userId);
    const next = { ...cur };
    for (const [k, v] of Object.entries(delta)) {
        if (k === 'bestCombo') next.bestCombo = Math.max(cur.bestCombo, v);
        else if (k === 'minutes') continue; // time only comes from the active-time clock
        else next[k] = (cur[k] || 0) + v;
    }
    next.minutes = Math.floor(next.seconds / 60);
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
