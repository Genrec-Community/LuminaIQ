/**
 * Where the student left off, saved on the server so they resume on any device
 * (last book, the view open in each book, an unfinished quiz).
 * Writes are batched: several changes within ~1s become one request.
 */
import { getAppState, patchAppState } from '../api';
import { LAST_PROJECT_KEY } from './dailyProgress';

let pending = {};
let timer = null;

const flush = async () => {
    const changes = pending;
    pending = {};
    timer = null;
    if (!Object.keys(changes).length) return;
    try { await patchAppState(changes); } catch { /* offline or signed out: the local copy still works */ }
};

/** Merge keys into the saved state (null removes a key). */
export const saveResume = (changes) => {
    pending = { ...pending, ...changes };
    if (timer) clearTimeout(timer);
    timer = setTimeout(flush, 1000);
};

if (typeof document !== 'undefined') {
    document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'hidden') flush(); });
}

/** The saved state; also makes the server's last book this device's "continue" book. */
export const loadResume = async () => {
    try {
        const state = await getAppState();
        if (state.lastProject) {
            try { localStorage.setItem(LAST_PROJECT_KEY, state.lastProject); } catch { /* ignore */ }
        }
        return state;
    } catch {
        return {};
    }
};
