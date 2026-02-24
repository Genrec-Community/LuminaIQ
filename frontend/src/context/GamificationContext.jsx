import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { getGamification, awardXP } from '../api';
import { setXPCallback } from '../utils/studyActivity';

const GamificationContext = createContext(null);

export const useGamification = () => {
    const context = useContext(GamificationContext);
    if (!context) {
        throw new Error('useGamification must be used within a GamificationProvider');
    }
    return context;
};

export const GamificationProvider = ({ children }) => {
    const [data, setData] = useState(null);
    const [loaded, setLoaded] = useState(false);
    const [xpEvents, setXpEvents] = useState([]); // For XP toast animations

    // Load gamification data on mount
    useEffect(() => {
        const load = async () => {
            try {
                const result = await getGamification();
                setData(result);
            } catch (err) {
                console.warn('Failed to load gamification data:', err);
            } finally {
                setLoaded(true);
            }
        };
        load();
    }, []);

    // Award XP and trigger animations
    const earnXP = useCallback(async (activityType, meta = {}) => {
        try {
            const result = await awardXP(activityType, meta);

            if (result && !result.error) {
                // Update local state
                setData(prev => prev ? {
                    ...prev,
                    total_xp: result.total_xp,
                    level: result.level,
                    level_title: result.level_title,
                    level_progress: result.level_progress,
                    xp_in_level: result.xp_in_level,
                    xp_needed: result.xp_needed,
                    next_level: result.next_level,
                    stats: result.stats,
                } : prev);

                // Add new badges to local state
                if (result.new_badges && result.new_badges.length > 0) {
                    setData(prev => {
                        if (!prev) return prev;
                        const existingIds = new Set((prev.badges || []).map(b => b.id));
                        const toAdd = result.new_badges.filter(b => !existingIds.has(b.id));
                        return {
                            ...prev,
                            badges: [...(prev.badges || []), ...toAdd.map(b => ({
                                ...b,
                                earned_at: new Date().toISOString(),
                            }))],
                        };
                    });
                }

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
            setData(result);
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
