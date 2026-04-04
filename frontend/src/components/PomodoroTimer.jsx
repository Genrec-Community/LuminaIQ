import React, { useState, useEffect, useCallback, useRef } from 'react';
import { 
    Play, Pause, RotateCcw, Coffee, BookOpen, 
    Volume2, VolumeX, Settings, X, Check,
    Timer, Brain, Target, TrendingUp
} from 'lucide-react';
import { recordActivity } from '../utils/studyActivity';
import { useSettings } from '../context/SettingsContext';
import { getPomodoro, savePomodoro } from '../api';
import { createLogger } from '../utils/logger';

const logger = createLogger('PomodoroTimer');

const PomodoroTimer = ({ 
    projectId = null,
    documentId = null,
    documentName = 'Study Session',
    onSessionComplete,
    compact = false 
}) => {
    const { settings } = useSettings();
    
    // Timer states
    const [mode, setMode] = useState('work'); // 'work', 'break', 'longBreak'
    const [timeLeft, setTimeLeft] = useState((settings.pomodoroWork || 25) * 60);
    const [isRunning, setIsRunning] = useState(false);
    const [sessionsCompleted, setSessionsCompleted] = useState(0);
    const [totalFocusTime, setTotalFocusTime] = useState(0);
    const [showSettings, setShowSettings] = useState(false);
    const [soundEnabled, setSoundEnabled] = useState(settings.soundEnabled !== false);
    
    // Custom durations
    const [workDuration, setWorkDuration] = useState(settings.pomodoroWork || 25);
    const [breakDuration, setBreakDuration] = useState(settings.pomodoroBreak || 5);
    const [longBreakDuration, setLongBreakDuration] = useState(settings.pomodoroLongBreak || 15);
    
    const audioRef = useRef(null);
    const intervalRef = useRef(null);

    // Load session history from API
    useEffect(() => {
        const load = async () => {
            try {
                const data = await getPomodoro(projectId, documentId);
                setSessionsCompleted(data.sessions || 0);
                setTotalFocusTime((data.focusTime || 0) * 60); // API stores minutes, timer uses seconds
            } catch (err) {
                logger.warn('Failed to load pomodoro data', err);
            }
        };
        load();
    }, [documentId, projectId]);

    // Save session history to API
    const saveSession = useCallback(() => {
        savePomodoro(
            sessionsCompleted,
            Math.round(totalFocusTime / 60), // convert seconds to minutes
            projectId,
            documentId
        ).catch(err => logger.warn('Failed to save pomodoro', err));
    }, [documentId, projectId, sessionsCompleted, totalFocusTime]);

    // Timer logic
    useEffect(() => {
        if (isRunning && timeLeft > 0) {
            intervalRef.current = setInterval(() => {
                setTimeLeft(prev => {
                    if (prev <= 1) {
                        handleTimerComplete();
                        return 0;
                    }
                    return prev - 1;
                });
                
                // Track focus time
                if (mode === 'work') {
                    setTotalFocusTime(prev => prev + 1);
                }
            }, 1000);
        }

        return () => {
            if (intervalRef.current) {
                clearInterval(intervalRef.current);
            }
        };
    }, [isRunning, mode]);

    // Save on changes
    useEffect(() => {
        saveSession();
    }, [sessionsCompleted, totalFocusTime, saveSession]);

    const handleTimerComplete = () => {
        setIsRunning(false);
        playSound();
        
        if (mode === 'work') {
            const newSessions = sessionsCompleted + 1;
            setSessionsCompleted(newSessions);
            
            // Track pomodoro activity for heatmap
            if (projectId) {
                recordActivity(projectId, 'pomodoro');
            }
            
            // Notify parent
            if (onSessionComplete) {
                onSessionComplete({
                    documentId,
                    sessionsCompleted: newSessions,
                    focusTime: totalFocusTime,
                });
            }
            
            // Long break every 4 sessions
            if (newSessions % 4 === 0) {
                setMode('longBreak');
                setTimeLeft(longBreakDuration * 60);
            } else {
                setMode('break');
                setTimeLeft(breakDuration * 60);
            }
        } else {
            setMode('work');
            setTimeLeft(workDuration * 60);
            
            // Auto-start if enabled
            if (settings.pomodoroAutoStart) {
                setTimeout(() => setIsRunning(true), 1000);
            }
        }
    };

    const playSound = () => {
        if (soundEnabled) {
            // Use Web Audio API for notification sound
            try {
                const audioContext = new (window.AudioContext || window.webkitAudioContext)();
                const oscillator = audioContext.createOscillator();
                const gainNode = audioContext.createGain();
                
                oscillator.connect(gainNode);
                gainNode.connect(audioContext.destination);
                
                oscillator.frequency.value = mode === 'work' ? 800 : 600;
                oscillator.type = 'sine';
                gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
                gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.5);
                
                oscillator.start(audioContext.currentTime);
                oscillator.stop(audioContext.currentTime + 0.5);
            } catch (e) {
                logger.debug('Audio playback not supported');
            }
        }
    };

    const formatTime = (seconds) => {
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    };

    const formatFocusTime = (seconds) => {
        const hours = Math.floor(seconds / 3600);
        const mins = Math.floor((seconds % 3600) / 60);
        if (hours > 0) {
            return `${hours}h ${mins}m`;
        }
        return `${mins}m`;
    };

    const resetTimer = () => {
        setIsRunning(false);
        setMode('work');
        setTimeLeft(workDuration * 60);
    };

    const switchMode = (newMode) => {
        setIsRunning(false);
        setMode(newMode);
        switch (newMode) {
            case 'work':
                setTimeLeft(workDuration * 60);
                break;
            case 'break':
                setTimeLeft(breakDuration * 60);
                break;
            case 'longBreak':
                setTimeLeft(longBreakDuration * 60);
                break;
        }
    };

    const progress = () => {
        const total = mode === 'work' 
            ? workDuration * 60 
            : mode === 'break' 
                ? breakDuration * 60 
                : longBreakDuration * 60;
        return ((total - timeLeft) / total) * 100;
    };

    const modeColors = {
        work: { bg: 'from-[#C8A288] to-[#A08072]', text: 'text-white', ring: 'ring-[#C8A288]' },
        break: { bg: 'from-green-500 to-emerald-600', text: 'text-white', ring: 'ring-green-500' },
        longBreak: { bg: 'from-blue-500 to-indigo-600', text: 'text-white', ring: 'ring-blue-500' },
    };

    if (compact) {
        return (
            <div className="flex items-center gap-3 p-3 bg-white rounded-xl border border-[#E6D5CC]">
                <div className={`h-10 w-10 rounded-lg bg-gradient-to-br ${modeColors[mode].bg} flex items-center justify-center`}>
                    {mode === 'work' ? <Brain className="h-5 w-5 text-white" /> : <Coffee className="h-5 w-5 text-white" />}
                </div>
                <div className="flex-1">
                    <p className="text-lg font-bold text-[#4A3B32] font-mono">{formatTime(timeLeft)}</p>
                    <p className="text-xs text-[#8a6a5c]">{mode === 'work' ? 'Focus' : 'Break'}</p>
                </div>
                <button
                    onClick={() => setIsRunning(!isRunning)}
                    className={`h-10 w-10 rounded-lg bg-gradient-to-br ${modeColors[mode].bg} flex items-center justify-center text-white`}
                >
                    {isRunning ? <Pause className="h-5 w-5" /> : <Play className="h-5 w-5 ml-0.5" />}
                </button>
            </div>
        );
    }

    return (
        <div className="bg-white rounded-2xl border border-[#E6D5CC] overflow-hidden">
            {/* Header */}
            <div className={`p-4 bg-gradient-to-r ${modeColors[mode].bg} ${modeColors[mode].text}`}>
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <Timer className="h-6 w-6" />
                        <div>
                            <h3 className="font-bold">Pomodoro Timer</h3>
                            <p className="text-sm opacity-90 truncate max-w-[200px]">{documentName}</p>
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                        <button
                            onClick={() => setSoundEnabled(!soundEnabled)}
                            className="p-2 hover:bg-white/20 rounded-lg transition-colors"
                        >
                            {soundEnabled ? <Volume2 className="h-5 w-5" /> : <VolumeX className="h-5 w-5" />}
                        </button>
                        <button
                            onClick={() => setShowSettings(!showSettings)}
                            className="p-2 hover:bg-white/20 rounded-lg transition-colors"
                        >
                            <Settings className="h-5 w-5" />
                        </button>
                    </div>
                </div>
            </div>

            {/* Mode Selector */}
            <div className="flex p-2 gap-2 bg-[#FDF6F0]">
                {[
                    { id: 'work', label: 'Focus', icon: Brain },
                    { id: 'break', label: 'Break', icon: Coffee },
                    { id: 'longBreak', label: 'Long Break', icon: Coffee },
                ].map(({ id, label, icon: Icon }) => (
                    <button
                        key={id}
                        onClick={() => switchMode(id)}
                        className={`flex-1 py-2 px-3 rounded-lg font-medium text-sm transition-all flex items-center justify-center gap-2 ${
                            mode === id 
                                ? `bg-gradient-to-r ${modeColors[id].bg} text-white shadow-md` 
                                : 'text-[#8a6a5c] hover:bg-white'
                        }`}
                    >
                        <Icon className="h-4 w-4" />
                        <span className="hidden sm:inline">{label}</span>
                    </button>
                ))}
            </div>

            {/* Timer Display */}
            <div className="p-8 flex flex-col items-center">
                {/* Circular Progress */}
                <div className="relative w-48 h-48 mb-6">
                    <svg className="w-full h-full transform -rotate-90">
                        <circle
                            cx="96"
                            cy="96"
                            r="88"
                            fill="none"
                            stroke="#E6D5CC"
                            strokeWidth="8"
                        />
                        <circle
                            cx="96"
                            cy="96"
                            r="88"
                            fill="none"
                            stroke={mode === 'work' ? '#C8A288' : mode === 'break' ? '#22c55e' : '#3b82f6'}
                            strokeWidth="8"
                            strokeLinecap="round"
                            strokeDasharray={2 * Math.PI * 88}
                            strokeDashoffset={2 * Math.PI * 88 * (1 - progress() / 100)}
                            className="transition-all duration-1000"
                        />
                    </svg>
                    <div className="absolute inset-0 flex flex-col items-center justify-center">
                        <span className="text-5xl font-bold text-[#4A3B32] font-mono">
                            {formatTime(timeLeft)}
                        </span>
                        <span className="text-sm text-[#8a6a5c] mt-1 capitalize">
                            {mode === 'work' ? 'Focus Time' : mode === 'break' ? 'Short Break' : 'Long Break'}
                        </span>
                    </div>
                </div>

                {/* Controls */}
                <div className="flex items-center gap-4">
                    <button
                        onClick={resetTimer}
                        className="p-3 bg-[#FDF6F0] hover:bg-[#E6D5CC] rounded-xl text-[#8a6a5c] transition-colors"
                    >
                        <RotateCcw className="h-6 w-6" />
                    </button>
                    <button
                        onClick={() => setIsRunning(!isRunning)}
                        className={`px-8 py-4 bg-gradient-to-r ${modeColors[mode].bg} text-white rounded-xl font-bold text-lg flex items-center gap-3 shadow-lg hover:shadow-xl transition-all transform hover:scale-105`}
                    >
                        {isRunning ? (
                            <>
                                <Pause className="h-6 w-6" />
                                Pause
                            </>
                        ) : (
                            <>
                                <Play className="h-6 w-6" />
                                Start
                            </>
                        )}
                    </button>
                    <button
                        onClick={() => switchMode(mode === 'work' ? 'break' : 'work')}
                        className="p-3 bg-[#FDF6F0] hover:bg-[#E6D5CC] rounded-xl text-[#8a6a5c] transition-colors"
                    >
                        {mode === 'work' ? <Coffee className="h-6 w-6" /> : <Brain className="h-6 w-6" />}
                    </button>
                </div>
            </div>

            {/* Stats */}
            <div className="grid grid-cols-3 gap-4 p-4 bg-[#FDF6F0] border-t border-[#E6D5CC]">
                <div className="text-center">
                    <div className="flex items-center justify-center gap-1 text-[#C8A288] mb-1">
                        <Target className="h-4 w-4" />
                    </div>
                    <p className="text-2xl font-bold text-[#4A3B32]">{sessionsCompleted}</p>
                    <p className="text-xs text-[#8a6a5c]">Sessions</p>
                </div>
                <div className="text-center">
                    <div className="flex items-center justify-center gap-1 text-[#C8A288] mb-1">
                        <Timer className="h-4 w-4" />
                    </div>
                    <p className="text-2xl font-bold text-[#4A3B32]">{formatFocusTime(totalFocusTime)}</p>
                    <p className="text-xs text-[#8a6a5c]">Focus Time</p>
                </div>
                <div className="text-center">
                    <div className="flex items-center justify-center gap-1 text-[#C8A288] mb-1">
                        <TrendingUp className="h-4 w-4" />
                    </div>
                    <p className="text-2xl font-bold text-[#4A3B32]">{Math.round(totalFocusTime / 60 / (sessionsCompleted || 1))}m</p>
                    <p className="text-xs text-[#8a6a5c]">Avg Session</p>
                </div>
            </div>

            {/* Settings Panel */}
            {showSettings && (
                <div className="p-4 border-t border-[#E6D5CC] bg-white">
                    <div className="flex items-center justify-between mb-4">
                        <h4 className="font-bold text-[#4A3B32]">Timer Settings</h4>
                        <button
                            onClick={() => setShowSettings(false)}
                            className="p-1 hover:bg-[#FDF6F0] rounded-lg"
                        >
                            <X className="h-5 w-5 text-[#8a6a5c]" />
                        </button>
                    </div>
                    <div className="space-y-3">
                        {[
                            { label: 'Focus Duration', value: workDuration, setter: setWorkDuration },
                            { label: 'Short Break', value: breakDuration, setter: setBreakDuration },
                            { label: 'Long Break', value: longBreakDuration, setter: setLongBreakDuration },
                        ].map(({ label, value, setter }) => (
                            <div key={label} className="flex items-center justify-between">
                                <span className="text-sm text-[#4A3B32]">{label}</span>
                                <div className="flex items-center gap-2">
                                    <button
                                        onClick={() => setter(Math.max(1, value - 5))}
                                        className="h-8 w-8 bg-[#FDF6F0] rounded-lg flex items-center justify-center text-[#4A3B32] hover:bg-[#E6D5CC] font-bold"
                                    >
                                        -
                                    </button>
                                    <span className="w-12 text-center font-bold text-[#4A3B32]">{value}m</span>
                                    <button
                                        onClick={() => setter(Math.min(60, value + 5))}
                                        className="h-8 w-8 bg-[#FDF6F0] rounded-lg flex items-center justify-center text-[#4A3B32] hover:bg-[#E6D5CC] font-bold"
                                    >
                                        +
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                    <button
                        onClick={() => {
                            resetTimer();
                            setShowSettings(false);
                        }}
                        className="w-full mt-4 py-2 bg-[#C8A288] text-white rounded-lg font-medium hover:bg-[#B08B72] transition-colors flex items-center justify-center gap-2"
                    >
                        <Check className="h-4 w-4" />
                        Apply & Reset Timer
                    </button>
                </div>
            )}
        </div>
    );
};

export default PomodoroTimer;
