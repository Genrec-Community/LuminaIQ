import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
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
        const load = async () => {
            try {
                const data = await getUserSettings();
                if (data?.settings) {
                    setSettings(prev => ({ ...prev, ...data.settings }));
                }
            } catch (err) {
                console.warn('Failed to load settings from API, using defaults', err);
            } finally {
                setLoaded(true);
            }
        };
        load();
    }, [user]);

    // Apply dark mode whenever settings change
    useEffect(() => {
        if (settings.darkMode) {
            document.documentElement.classList.add('dark');
        } else {
            document.documentElement.classList.remove('dark');
        }
    }, [settings.darkMode]);

    const updateSetting = useCallback((key, value) => {
        setSettings(prev => {
            const next = { ...prev, [key]: value };
            // Fire-and-forget save to API
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
        <SettingsContext.Provider value={{ settings, updateSetting, resetSettings, loaded }}>
            {children}
        </SettingsContext.Provider>
    );
};

export default SettingsContext;
