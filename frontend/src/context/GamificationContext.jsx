import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { getGamification, awardXP } from '../api';
import { setXPCallback } from '../utils/studyActivity';
import { useAuth } from './AuthContext';

/**
 * Progress, XP and badges (AGENTS.md Phase 7).
 *
 * XP is granted only by the server, when it measures learning (mastery up, a mistake fixed,
 * a review done on time, the daily goal, a plan step). This context just syncs: after an
 * activity it asks for XP earned since the last sync and shows a toast for real rewards.
 * `data.style` says how this learner's level likes progress shown (playful / exam / quiet /
 * milestones).
 */
const GamificationContext = createContext(null);

export const useGamification = () => {
    const context = useContext(GamificationContext);
    if (!context) {
        throw new Error('useGamification must be used within a GamificationProvider');
    }
    return context;
};

// Syncing a few seconds apart is plenty: rewards are computed on the server either way
const SYNC_GAP_MS = 3000;

export const GamificationProvider = ({ children }) => {
    const { user } = useAuth();
    const [data, setData] = useState(null);
    const [loaded, setLoaded] = useState(false);
    const [xpEvents, setXpEvents] = useState([]);   // toasts
    const sinceRef = useRef(null);                   // server time of the last sync
    const lastSyncRef = useRef(0);
    const pendingRef = useRef(null);
    const dataRef = useRef(null);
    dataRef.current = data;

    const pushToast = useCallback((toast) => {
        const event = { id: Date.now() + Math.random(), ...toast };
        setXpEvents((prev) => [...prev, event]);
        setTimeout(() => setXpEvents((prev) => prev.filter((e) => e.id !== event.id)), 4000);
    }, []);

    // Apply a server state; toast the XP earned since the previous sync
    const apply = useCallback((result) => {
        if (!result || result.error) return;
        const prev = dataRef.current;
        if (result.server_time) sinceRef.current = result.server_time;
        setData(result);
        const events = result.events || [];
        if (!prev || !events.length) return;
        const earned = events.reduce((n, e) => n + (e.xp || 0), 0);
        const known = new Set((prev.badges || []).map((b) => b.id));
        const newBadges = (result.badges || []).filter((b) => !known.has(b.id));
        pushToast({
            xp_earned: earned,
            label: events.length === 1 ? events[0].label : `${events.length} rewards`,
            kinds: events.map((e) => e.kind),
            leveled_up: result.level > (prev.level || 1),
            new_level: result.level,
            new_level_title: result.level_title,
            new_badges: newBadges,
        });
    }, [pushToast]);

    useEffect(() => {
        if (!user) {
            setData(null);
            setLoaded(true);
            sinceRef.current = null;
            return;
        }
        getGamification()
            .then(apply)
            .catch((err) => console.warn('Failed to load progress:', err))
            .finally(() => setLoaded(true));
    }, [user, apply]);

    const sync = useCallback(async (activityType = 'activity', meta = {}) => {
        if (!user || !sinceRef.current) return null;
        try {
            const result = await awardXP(activityType, meta, sinceRef.current);
            apply(result);
            return result;
        } catch (err) {
            console.warn('Progress sync failed:', err);
            return null;
        }
    }, [user, apply]);

    // Called after any study activity (kept under its old name for existing callers):
    // it never grants XP itself, it just picks up what the server has granted
    const earnXP = useCallback((activityType, meta = {}) => {
        const wait = SYNC_GAP_MS - (Date.now() - lastSyncRef.current);
        if (wait <= 0) {
            lastSyncRef.current = Date.now();
            return sync(activityType, meta);
        }
        if (!pendingRef.current) {
            // Results (e.g. a quiz's mastery change) can land a moment later: sync once more
            pendingRef.current = setTimeout(() => {
                pendingRef.current = null;
                lastSyncRef.current = Date.now();
                sync(activityType, meta);
            }, wait + 500);
        }
        return Promise.resolve(null);
    }, [sync]);

    const earnXPRef = useRef(earnXP);
    earnXPRef.current = earnXP;
    useEffect(() => {
        setXPCallback((activityType, meta) => { earnXPRef.current(activityType, meta); });
        return () => setXPCallback(null);
    }, []);

    // Coming back to the tab: rewards may have been granted by background work
    useEffect(() => {
        const onFocus = () => { if (document.visibilityState === 'visible') earnXPRef.current('focus'); };
        document.addEventListener('visibilitychange', onFocus);
        return () => document.removeEventListener('visibilitychange', onFocus);
    }, []);

    const refresh = useCallback(async () => {
        try {
            apply(await getGamification(sinceRef.current));
        } catch (err) {
            console.warn('Failed to refresh progress:', err);
        }
    }, [apply]);

    const dismissXpEvent = useCallback((eventId) => {
        setXpEvents((prev) => prev.filter((e) => e.id !== eventId));
    }, []);

    return (
        <GamificationContext.Provider value={{
            data,
            loaded,
            style: data?.style || 'quiet',
            earnXP,
            refresh,
            xpEvents,
            dismissXpEvent,
        }}>
            {children}
        </GamificationContext.Provider>
    );
};

export default GamificationContext;
