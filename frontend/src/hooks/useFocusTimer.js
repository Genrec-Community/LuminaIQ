import { useEffect } from 'react';
import { bumpDailyProgress } from '../utils/dailyProgress';
import { onActiveTime } from '../utils/activeTime';

const SAVE_EVERY_MS = 15 * 1000;

/**
 * Counts active study time for the daily goal: only while the app is in
 * front, focused, and the learner was active within the idle window
 * (see utils/activeTime). Saved in seconds, a few times a minute.
 */
export default function useFocusTimer(userId) {
    useEffect(() => {
        if (!userId) return;
        let pending = 0;
        const flush = () => {
            const seconds = Math.floor(pending / 1000);
            if (seconds <= 0) return;
            pending -= seconds * 1000;
            bumpDailyProgress(userId, { seconds });
        };
        return onActiveTime({
            add: (ms) => { pending += ms; if (pending >= SAVE_EVERY_MS) flush(); },
            flush,
        });
    }, [userId]);
}
