import { useEffect } from 'react';
import { bumpDailyProgress } from '../utils/dailyProgress';

const IDLE_MS = 90 * 1000;

/**
 * Counts focused study minutes: a minute counts only while the tab is visible
 * and the learner interacted within the last 90 seconds.
 */
export default function useFocusTimer(userId) {
    useEffect(() => {
        if (!userId) return;
        let lastInteraction = Date.now();
        const mark = () => { lastInteraction = Date.now(); };
        const events = ['pointerdown', 'keydown', 'wheel', 'touchstart'];
        events.forEach((e) => window.addEventListener(e, mark, { passive: true }));

        const interval = setInterval(() => {
            if (document.visibilityState === 'visible' && Date.now() - lastInteraction < IDLE_MS) {
                bumpDailyProgress(userId, { minutes: 1 });
            }
        }, 60 * 1000);

        return () => {
            clearInterval(interval);
            events.forEach((e) => window.removeEventListener(e, mark));
        };
    }, [userId]);
}
