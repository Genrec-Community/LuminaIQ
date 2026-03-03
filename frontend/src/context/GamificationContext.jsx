import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { getGamification, awardXP } from '../api';
import { setXPCallback } from '../utils/studyActivity';
import { useAuth } from './AuthContext';

const GamificationContext = createContext(null);

export const useGamification = () => {
    const context = useContext(GamificationContext);
    if (!context) {
        throw new Error('useGamification must be used within a GamificationProvider');
    }
    return context;
};

// Per-activity cooldowns (ms) to prevent XP spam
const ACTIVITY_COOLDOWNS = {
    chat: 15000,           // 15s between chat XP awards
    review: 3000,          // 3s between review awards
    knowledge_graph: 10000, // 10s between graph explore awards
    path: 8000,            // 8s between path awards
};

export const GamificationProvider = ({ children }) => {
    const { user } = useAuth();
    const [data, setData] = useState(null);
    const [loaded, setLoaded] = useState(false);
    const [xpEvents, setXpEvents] = useState([]); // For XP toast animations

    // Cooldown tracker: { activityType: lastAwardTimestamp }
    const cooldownsRef = useRef({});

    // Load gamification data only when user is authenticated
    useEffect(() => {
        if (!user) {
            setData(null);
            setLoaded(true);
            return;
        }
        const load = async () => {
            try {
                const result = await getGamification();
                if (result) setData(result);
            } catch (err) {
                console.warn('Failed to load gamification data:', err);
            } finally {
                setLoaded(true);
            }
        };
        load();
    }, [user]);

    // Award XP and trigger animations
    const earnXP = useCallback(async (activityType, meta = {}) => {
        // Cooldown check — skip if we awarded this activity type too recently
        const cooldownMs = ACTIVITY_COOLDOWNS[activityType];
        if (cooldownMs) {
            const lastAward = cooldownsRef.current[activityType] || 0;
            if (Date.now() - lastAward < cooldownMs) {
                return null; // Silently skip — too soon
            }
        }

        try {
            const result = await awardXP(activityType, meta);

            if (result && !result.error) {
                // Record this award time for cooldown
                cooldownsRef.current[activityType] = Date.now();

                // Update local state with the new values from server
                setData(prev => {
                    if (!prev) return prev;

                    // Merge new badges
                    let updatedBadges = prev.badges || [];
                    if (result.new_badges && result.new_badges.length > 0) {
                        const existingIds = new Set(updatedBadges.map(b => b.id));
                        const toAdd = result.new_badges
                            .filter(b => !existingIds.has(b.id))
                            .map(b => ({ ...b, earned_at: new Date().toISOString() }));
                        updatedBadges = [...updatedBadges, ...toAdd];
                    }

                    return {
                        ...prev,
                        total_xp: result.total_xp,
                        level: result.level,
                        level_title: result.level_title,
                        level_progress: result.level_progress,
                        xp_in_level: result.xp_in_level,
                        xp_needed: result.xp_needed,
                        next_level: result.next_level,
                        stats: result.stats,
                        badges: updatedBadges,
                    };
                });

                // Create XP event for toast animation
                const event = {
                    id: Date.now() + Math.random(),
                    xp_earned: result.xp_earned,
                    activity: activityType,
                    leveled_up: result.leveled_up,
                    old_level: result.old_level,
                    new_level: result.level,
                    new_level_title: result.level_title,
                    new_badges: result.new_badges || [],
                };

                setXpEvents(prev => [...prev, event]);

                // Auto-remove after animation duration
                setTimeout(() => {
                    setXpEvents(prev => prev.filter(e => e.id !== event.id));
                }, 4000);

                return result;
            } else if (result && result.error) {
                console.warn('XP award failed on server:', result.error);
            }
        } catch (err) {
            console.warn('Failed to award XP:', err);
        }
        return null;
    }, []);

    // Register the XP callback bridge so studyActivity.recordActivity
    // automatically awards XP without modifying every component
    const earnXPRef = useRef(earnXP);
    earnXPRef.current = earnXP;

    useEffect(() => {
        setXPCallback((activityType, meta) => {
            earnXPRef.current(activityType, meta);
        });
        return () => setXPCallback(null);
    }, []);

    // Refresh gamification data
    const refresh = useCallback(async () => {
        try {
            const result = await getGamification();
            if (result) setData(result);
        } catch (err) {
            console.warn('Failed to refresh gamification:', err);
        }
    }, []);

    // Dismiss an XP event
    const dismissXpEvent = useCallback((eventId) => {
        setXpEvents(prev => prev.filter(e => e.id !== eventId));
    }, []);

    return (
        <GamificationContext.Provider value={{
            data,
            loaded,
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
