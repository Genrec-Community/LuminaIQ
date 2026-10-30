import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { getUserSettings, saveUserSettings } from '../api';
import { useAuth } from './AuthContext';
import { buildThemeState, applyThemeState } from '../utils/themes';

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
    nickname: '',
    userAvatar: '🦊',
    ageGroup: '',
    examName: '',
    examDate: '', // YYYY-MM-DD

    // AI Companion
    aiName: 'Lumi',
    aiAvatar: '✨',
    aiCharacter: 'buddy', // key of AI_CHARACTERS in utils/persona.js
    aiHumor: 'some', // 'none' | 'some' | 'lots'
    aiEmoji: true,
    onboardingComplete: false,

    // Learning Mode
    bookIsolation: true,
    darkMode: false,
    theme: 'latte',      // key of THEMES in utils/themes.js
    customAccent: '',    // '#rrggbb' overrides the theme accent
    fontStyle: 'auto',   // 'auto' (theme default) | key of FONT_STYLES
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
};

export const SettingsProvider = ({ children }) => {
    const { user } = useAuth();
    const [settings, setSettings] = useState(defaultSettings);
    const [loaded, setLoaded] = useState(false);

    // Load settings from API only when user is authenticated
    useEffect(() => {
        if (!user) {
            setLoaded(true);
            return;
        }
        // Mark as not loaded until this user's settings arrive, so UI that
        // depends on them (e.g. onboarding) doesn't act on defaults.
        setLoaded(false);
        const load = async () => {
            try {
                const data = await getUserSettings();
                if (data?.settings) {
                    setSettings(prev => ({ ...prev, ...data.settings }));
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
                setLoaded(true);
            }
        };
        load();
    }, [user]);

    // Apply theme (palette, dark mode, accent, font) to <html>. Also caches
    // the result so index.html can apply it before React mounts (no flash).
    useEffect(() => {
        applyThemeState(buildThemeState(settings));
    }, [settings.theme, settings.darkMode, settings.customAccent, settings.fontStyle]);

    // Apply font size class to html element
    useEffect(() => {
        const el = document.documentElement;
        el.classList.remove('app-font-sm', 'app-font-md', 'app-font-lg', 'app-font-xl');
        if (settings.fontSize && settings.fontSize !== 'md') {
            el.classList.add(`app-font-${settings.fontSize}`);
        }
    }, [settings.fontSize]);

    // Apply compact mode whenever settings change
    useEffect(() => {
        if (settings.compactMode) {
            document.documentElement.classList.add('compact');
        } else {
            document.documentElement.classList.remove('compact');
        }
    }, [settings.compactMode]);

    const updateSetting = useCallback((key, value) => {
        setSettings(prev => {
            const next = { ...prev, [key]: value };
            // The quick dark-mode switch toggles between the two classic themes
            if (key === 'darkMode') next.theme = value ? 'espresso' : 'latte';
            // Fire-and-forget save to API
            saveUserSettings(next).catch(err =>
                console.warn('Failed to save settings:', err)
            );
            return next;
        });
    }, []);

    // Update several settings at once with a single save
    const updateSettings = useCallback((partial) => {
        setSettings(prev => {
            const next = { ...prev, ...partial };
            saveUserSettings(next).catch(err =>
                console.warn('Failed to save settings:', err)
            );
            return next;
        });
    }, []);

    const resetSettings = useCallback(async () => {
        try {
            await saveUserSettings(defaultSettings);
        } catch {
            // ignore
        }
        setSettings(defaultSettings);
    }, []);

    return (
        <SettingsContext.Provider value={{ settings, updateSetting, updateSettings, resetSettings, loaded }}>
            {children}
        </SettingsContext.Provider>
    );
};

export default SettingsContext;
