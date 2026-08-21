import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { getUserSettings, saveUserSettings } from '../api';
import { useAuth } from './AuthContext';

const SettingsContext = createContext();

export const useSettings = () => {
    const context = useContext(SettingsContext);
    if (!context) {
        throw new Error('useSettings must be used within a SettingsProvider');
    }
    return context;
};

const defaultSettings = {
    // Student Profile
    studentName: '',
    learningGoal: '',
    selfLevel: 'intermediate',
    learningStyle: 'balanced',
    subjectsOfInterest: [],
    dailyStudyGoal: 30, // minutes

    // Learning Mode
    bookIsolation: true,
    darkMode: false,
    fontSize: 'md', // 'sm' | 'md' | 'lg' | 'xl'
    pomodoroWork: 25,
    pomodoroBreak: 5,
    pomodoroLongBreak: 15,
    pomodoroAutoStart: false,
    studyReminders: true,
    reminderTime: '09:00',
    soundEnabled: true,
    showStreaks: true,
    compactMode: false,
    tutorStyle: 'balanced',
    quizDifficulty: 'adaptive',
    hasSeenDashboardTutorial: false,
    hasSeenProjectTutorial: false,
};

const freshDefaults = () => ({
    ...defaultSettings,
    subjectsOfInterest: [],
    darkMode: localStorage.getItem('lumina_dark_mode') === '1',
});

export const SettingsProvider = ({ children }) => {
    const { user } = useAuth();
    const [settings, setSettings] = useState(freshDefaults);
    const [loaded, setLoaded] = useState(false);
    const settingsRef = useRef(settings);
    const saveQueueRef = useRef(Promise.resolve());
    const saveGenerationRef = useRef(0);

    // Load settings from API only when user is authenticated
    useEffect(() => {
        let cancelled = false;
        const generation = ++saveGenerationRef.current;
        saveQueueRef.current = Promise.resolve();
        setLoaded(false);

        const initial = freshDefaults();
        settingsRef.current = initial;
        setSettings(initial);

        if (!user) {
            setLoaded(true);
            return () => {
                cancelled = true;
            };
        }
        const load = async () => {
            try {
                const data = await getUserSettings();
                if (!cancelled && generation === saveGenerationRef.current && data?.settings) {
                    const next = { ...freshDefaults(), ...data.settings };
                    settingsRef.current = next;
                    setSettings(next);
                    // Keep localStorage in sync with server value so the
                    // FOUC-prevention script (index.html) always has fresh data
                    localStorage.setItem(
                        'lumina_dark_mode',
                        data.settings.darkMode ? '1' : '0'
                    );
                }
            } catch (err) {
                console.warn('Failed to load settings from API, using defaults', err);
            } finally {
                if (!cancelled && generation === saveGenerationRef.current) {
                    setLoaded(true);
                }
            }
        };
        load();
        return () => {
            cancelled = true;
        };
    }, [user?.id]);

    // Apply dark mode — toggle html.dark for CSS cascade.
    // Also persist to localStorage so index.html blocking script can read it
    // before React mounts and prevent the flash of light mode on reload.
    useEffect(() => {
        if (settings.darkMode) {
            document.documentElement.classList.add('dark');
            localStorage.setItem('lumina_dark_mode', '1');
        } else {
            document.documentElement.classList.remove('dark');
            localStorage.setItem('lumina_dark_mode', '0');
        }
    }, [settings.darkMode]);

    // Apply font size class to html element
    useEffect(() => {
        const el = document.documentElement;
        el.classList.remove('app-font-sm', 'app-font-md', 'app-font-lg', 'app-font-xl');
        const fontSize = ['sm', 'md', 'lg', 'xl'].includes(settings.fontSize)
            ? settings.fontSize
            : 'md';
        el.classList.add(`app-font-${fontSize}`);
    }, [settings.fontSize]);

    // Apply compact mode whenever settings change
    useEffect(() => {
        if (settings.compactMode) {
            document.documentElement.classList.add('compact');
        } else {
            document.documentElement.classList.remove('compact');
        }
    }, [settings.compactMode]);

    const queueSave = useCallback((next) => {
        const generation = saveGenerationRef.current;
        const save = saveQueueRef.current
            .catch(() => undefined)
            .then(() => {
                if (generation !== saveGenerationRef.current) return next;
                return saveUserSettings(next);
            });
        saveQueueRef.current = save;
        return save;
    }, []);

    const updateSettings = useCallback((updates) => {
        const next = { ...settingsRef.current, ...updates };
        settingsRef.current = next;
        setSettings(next);
        const save = queueSave(next);
        save.catch(err => {
            console.warn('Failed to save settings:', err);
        });
        return save;
    }, [queueSave]);

    const updateSetting = useCallback((key, value) => (
        updateSettings({ [key]: value })
    ), [updateSettings]);

    const resetSettings = useCallback(async () => {
        try {
            const next = freshDefaults();
            settingsRef.current = next;
            setSettings(next);
            await queueSave(next);
        } catch (err) {
            console.warn('Failed to reset settings:', err);
        }
    }, [queueSave]);

    return (
        <SettingsContext.Provider value={{ settings, updateSetting, updateSettings, resetSettings, loaded }}>
            {children}
        </SettingsContext.Provider>
    );
};

export default SettingsContext;
