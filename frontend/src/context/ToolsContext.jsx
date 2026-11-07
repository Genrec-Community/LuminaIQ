import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { useAuth } from './AuthContext';
import { useSettings } from './SettingsContext';
import { getMyLevel, setMyLevel } from '../api';

/**
 * The learner's level and the tools they may use (set by the platform admin per
 * level and narrowed by their class). The backend enforces this too; here it
 * decides what to show. Until it loads, every tool shows, so nothing flickers away.
 */
const ToolsContext = createContext(null);

const EMPTY = { level: null, level_label: null, locked: false, needs_level: false, tools: null,
    hint_mode: 'student_choice', hints_default: false, outside_book: true };

export const ToolsProvider = ({ children }) => {
    const { user } = useAuth();
    const { updateSettings } = useSettings();
    const [info, setInfo] = useState(EMPTY);
    const [loaded, setLoaded] = useState(false);

    const refresh = useCallback(async () => {
        if (!user) { setInfo(EMPTY); setLoaded(false); return; }
        try {
            setInfo(await getMyLevel());
        } catch {
            setInfo(EMPTY);   // backend unreachable: show everything, the API still enforces
        } finally {
            setLoaded(true);
        }
    }, [user]);

    useEffect(() => { refresh(); }, [refresh]);

    // Lets the whole app adapt to the level (e.g. larger text for Class 5-10)
    useEffect(() => {
        const root = document.documentElement;
        if (info.level) root.dataset.level = info.level;
        else delete root.dataset.level;
    }, [info.level]);

    const chooseLevel = useCallback(async (level) => {
        setInfo(await setMyLevel(level));
        setLoaded(true);
        // Keep the local settings in step, so a later settings save doesn't drop it
        updateSettings({ studyLevel: level });
    }, [updateSettings]);

    const value = useMemo(() => ({
        ...info,
        loaded,
        isSchool: info.level === 'school',
        has: (tool) => !info.tools || info.tools.includes(tool),
        refresh,
        chooseLevel,
    }), [info, loaded, refresh, chooseLevel]);

    return <ToolsContext.Provider value={value}>{children}</ToolsContext.Provider>;
};

export const useTools = () => {
    const ctx = useContext(ToolsContext);
    // Outside the provider (tests, isolated renders): everything allowed
    return ctx || { ...EMPTY, loaded: true, isSchool: false, has: () => true, refresh: async () => {}, chooseLevel: async () => {} };
};
