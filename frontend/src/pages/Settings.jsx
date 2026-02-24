import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
    Settings as SettingsIcon,
    BookOpen,
    Moon,
    Sun,
    Bell,
    Clock,
    Target,
    Shield,
    ChevronLeft,
    Check,
    X,
    Layers,
    Timer,
    Brain,
    Smartphone,
    User,
    GraduationCap,
    Sparkles,
    BookMarked,
    Pencil
} from 'lucide-react';
import { useSettings } from '../context/SettingsContext';
import { useGamification } from '../context/GamificationContext';

const Settings = () => {
    const navigate = useNavigate();
    const { settings, updateSetting, resetSettings } = useSettings();
    const { data: gamificationData } = useGamification();

    const ToggleSwitch = ({ enabled, onChange, label, description, icon: Icon }) => (
        <div className="flex items-center justify-between p-4 bg-white rounded-xl border border-[#E6D5CC] hover:border-[#C8A288] transition-colors">
            <div className="flex items-center gap-4">
                <div className="h-10 w-10 bg-[#FDF6F0] rounded-lg flex items-center justify-center">
                    <Icon className="h-5 w-5 text-[#C8A288]" />
                </div>
                <div>
                    <p className="font-bold text-[#4A3B32]">{label}</p>
                    <p className="text-sm text-[#8a6a5c]">{description}</p>
                </div>
            </div>
            <button
                onClick={() => onChange(!enabled)}
                className={`relative w-14 h-8 rounded-full transition-colors ${
                    enabled ? 'bg-[#C8A288]' : 'bg-gray-300'
                }`}
            >
                <div className={`absolute top-1 w-6 h-6 bg-white rounded-full shadow-md transition-transform ${
                    enabled ? 'translate-x-7' : 'translate-x-1'
                }`}>
                    {enabled ? (
                        <Check className="h-4 w-4 text-[#C8A288] m-1" />
                    ) : (
                        <X className="h-4 w-4 text-gray-400 m-1" />
                    )}
                </div>
            </button>
        </div>
    );

    const SelectOption = ({ value, onChange, label, description, icon: Icon, options }) => (
        <div className="p-4 bg-white rounded-xl border border-[#E6D5CC]">
            <div className="flex items-center gap-4 mb-3">
                <div className="h-10 w-10 bg-[#FDF6F0] rounded-lg flex items-center justify-center">
                    <Icon className="h-5 w-5 text-[#C8A288]" />
                </div>
                <div>
                    <p className="font-bold text-[#4A3B32]">{label}</p>
                    <p className="text-sm text-[#8a6a5c]">{description}</p>
                </div>
            </div>
            <select
                value={value}
                onChange={(e) => onChange(e.target.value)}
                className="w-full px-4 py-2 bg-[#FDF6F0] border border-[#E6D5CC] rounded-lg focus:ring-2 focus:ring-[#C8A288] text-[#4A3B32] font-medium"
            >
                {options.map(opt => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
            </select>
        </div>
    );

    const NumberInput = ({ value, onChange, label, description, icon: Icon, min, max, suffix }) => (
        <div className="p-4 bg-white rounded-xl border border-[#E6D5CC]">
            <div className="flex items-center gap-4 mb-3">
                <div className="h-10 w-10 bg-[#FDF6F0] rounded-lg flex items-center justify-center">
                    <Icon className="h-5 w-5 text-[#C8A288]" />
                </div>
                <div className="flex-1">
                    <p className="font-bold text-[#4A3B32]">{label}</p>
                    <p className="text-sm text-[#8a6a5c]">{description}</p>
                </div>
                <div className="flex items-center gap-2">
                    <button
                        onClick={() => onChange(Math.max(min, value - 5))}
                        className="h-8 w-8 bg-[#FDF6F0] rounded-lg flex items-center justify-center text-[#4A3B32] hover:bg-[#E6D5CC] transition-colors font-bold"
                    >
                        -
                    </button>
                    <span className="w-16 text-center font-bold text-[#4A3B32]">
                        {value} {suffix}
                    </span>
                    <button
                        onClick={() => onChange(Math.min(max, value + 5))}
                        className="h-8 w-8 bg-[#FDF6F0] rounded-lg flex items-center justify-center text-[#4A3B32] hover:bg-[#E6D5CC] transition-colors font-bold"
                    >
                        +
                    </button>
                </div>
            </div>
        </div>
    );

    return (
        <div className="min-h-screen bg-[#FDF6F0]">
            {/* Header */}
            <div className="bg-white border-b border-[#E6D5CC] sticky top-0 z-10">
                <div className="max-w-4xl mx-auto px-4 py-4 flex items-center gap-4">
                    <button
                        onClick={() => navigate(-1)}
                        className="p-2 hover:bg-[#FDF6F0] rounded-xl transition-colors"
                    >
                        <ChevronLeft className="h-6 w-6 text-[#4A3B32]" />
                    </button>
                    <div className="flex items-center gap-3">
                        <div className="h-10 w-10 bg-gradient-to-br from-[#C8A288] to-[#A08072] rounded-xl flex items-center justify-center">
                            <SettingsIcon className="h-5 w-5 text-white" />
                        </div>
                        <h1 className="text-xl font-bold text-[#4A3B32]">Settings</h1>
                    </div>
                </div>
            </div>

            {/* Content */}
            <div className="max-w-4xl mx-auto px-4 py-6 space-y-8">

                {/* Student Profile Section */}
                <section>
                    <h2 className="text-lg font-bold text-[#4A3B32] mb-4 flex items-center gap-2">
                        <User className="h-5 w-5 text-[#C8A288]" />
                        Student Profile
                    </h2>

                    {/* Profile Card with Level */}
                    <div className="bg-gradient-to-br from-[#C8A288] via-[#B08B72] to-[#8a6a5c] rounded-2xl p-5 mb-4 text-white relative overflow-hidden">
                        <div className="absolute top-0 right-0 w-40 h-40 bg-white/5 rounded-full -translate-y-1/2 translate-x-1/2" />
                        <div className="relative z-10 flex items-center gap-4">
                            <div className="h-16 w-16 bg-white/20 backdrop-blur-sm rounded-2xl flex items-center justify-center border border-white/30 shadow-lg shrink-0">
                                {settings.studentName ? (
                                    <span className="text-2xl font-black">{settings.studentName.charAt(0).toUpperCase()}</span>
                                ) : (
                                    <User className="h-7 w-7" />
                                )}
                            </div>
                            <div className="flex-1 min-w-0">
                                <p className="text-lg font-bold truncate">
                                    {settings.studentName || 'Set your name'}
                                </p>
                                <p className="text-white/70 text-sm font-medium">
                                    {gamificationData ? `Level ${gamificationData.level} — ${gamificationData.level_title}` : 'Getting started...'}
                                </p>
                                {settings.learningGoal && (
                                    <p className="text-white/60 text-xs mt-1 truncate">
                                        Goal: {settings.learningGoal}
                                    </p>
                                )}
                            </div>
                            {gamificationData && (
                                <div className="text-right shrink-0 hidden sm:block">
                                    <p className="text-2xl font-black">{gamificationData.total_xp}</p>
                                    <p className="text-white/70 text-xs font-semibold">Total XP</p>
                                </div>
                            )}
                        </div>
                    </div>

                    <div className="space-y-3">
                        {/* Name */}
                        <div className="p-4 bg-white rounded-xl border border-[#E6D5CC]">
                            <div className="flex items-center gap-4 mb-3">
                                <div className="h-10 w-10 bg-[#FDF6F0] rounded-lg flex items-center justify-center">
                                    <Pencil className="h-5 w-5 text-[#C8A288]" />
                                </div>
                                <div>
                                    <p className="font-bold text-[#4A3B32]">Your Name</p>
                                    <p className="text-sm text-[#8a6a5c]">How should we address you?</p>
                                </div>
                            </div>
                            <input
                                type="text"
                                value={settings.studentName || ''}
                                onChange={(e) => updateSetting('studentName', e.target.value)}
                                placeholder="Enter your name..."
                                className="w-full px-4 py-2.5 bg-[#FDF6F0] border border-[#E6D5CC] rounded-lg focus:ring-2 focus:ring-[#C8A288] outline-none text-[#4A3B32] font-medium placeholder-[#8a6a5c]/50"
                            />
                        </div>

                        {/* Learning Goal */}
                        <div className="p-4 bg-white rounded-xl border border-[#E6D5CC]">
                            <div className="flex items-center gap-4 mb-3">
                                <div className="h-10 w-10 bg-[#FDF6F0] rounded-lg flex items-center justify-center">
                                    <Target className="h-5 w-5 text-[#C8A288]" />
                                </div>
                                <div>
                                    <p className="font-bold text-[#4A3B32]">Learning Goal</p>
                                    <p className="text-sm text-[#8a6a5c]">What are you studying for?</p>
                                </div>
                            </div>
                            <input
                                type="text"
                                value={settings.learningGoal || ''}
                                onChange={(e) => updateSetting('learningGoal', e.target.value)}
                                placeholder="e.g., Pass my biology exam, Master JavaScript..."
                                className="w-full px-4 py-2.5 bg-[#FDF6F0] border border-[#E6D5CC] rounded-lg focus:ring-2 focus:ring-[#C8A288] outline-none text-[#4A3B32] font-medium placeholder-[#8a6a5c]/50"
                            />
                        </div>

                        {/* Self-Assessed Level */}
                        <SelectOption
                            value={settings.selfLevel || 'intermediate'}
                            onChange={(v) => updateSetting('selfLevel', v)}
                            label="Your Level"
                            description="How would you rate your current knowledge?"
                            icon={GraduationCap}
                            options={[
                                { value: 'beginner', label: 'Beginner — Just starting out' },
                                { value: 'intermediate', label: 'Intermediate — Know the basics' },
                                { value: 'advanced', label: 'Advanced — Looking to master' },
                            ]}
                        />

                        {/* Learning Style */}
                        <SelectOption
                            value={settings.learningStyle || 'balanced'}
                            onChange={(v) => updateSetting('learningStyle', v)}
                            label="Preferred Learning Style"
                            description="How do you learn best?"
                            icon={Sparkles}
                            options={[
                                { value: 'visual', label: 'Visual — Diagrams & summaries' },
                                { value: 'reading', label: 'Reading — Deep text-based study' },
                                { value: 'practice', label: 'Practice — Quizzes & exercises' },
                                { value: 'balanced', label: 'Balanced — Mix of everything' },
                            ]}
                        />

                        {/* Daily Study Goal */}
                        <NumberInput
                            value={settings.dailyStudyGoal || 30}
                            onChange={(v) => updateSetting('dailyStudyGoal', v)}
                            label="Daily Study Goal"
                            description="How many minutes per day do you want to study?"
                            icon={Clock}
                            min={10}
                            max={180}
                            suffix="min"
                        />

                        {/* Subjects of Interest */}
                        <div className="p-4 bg-white rounded-xl border border-[#E6D5CC]">
                            <div className="flex items-center gap-4 mb-3">
                                <div className="h-10 w-10 bg-[#FDF6F0] rounded-lg flex items-center justify-center">
                                    <BookMarked className="h-5 w-5 text-[#C8A288]" />
                                </div>
                                <div>
                                    <p className="font-bold text-[#4A3B32]">Subjects of Interest</p>
                                    <p className="text-sm text-[#8a6a5c]">Select topics you're interested in</p>
                                </div>
                            </div>
                            <div className="flex flex-wrap gap-2">
                                {['Science', 'Mathematics', 'History', 'Literature', 'Programming', 'Languages', 'Business', 'Arts', 'Psychology', 'Philosophy', 'Engineering', 'Medicine'].map(subject => {
                                    const selected = (settings.subjectsOfInterest || []).includes(subject);
                                    return (
                                        <button
                                            key={subject}
                                            onClick={() => {
                                                const current = settings.subjectsOfInterest || [];
                                                const next = selected
                                                    ? current.filter(s => s !== subject)
                                                    : [...current, subject];
                                                updateSetting('subjectsOfInterest', next);
                                            }}
                                            className={`px-3 py-1.5 rounded-full text-sm font-medium transition-all ${
                                                selected
                                                    ? 'bg-[#C8A288] text-white shadow-sm'
                                                    : 'bg-[#FDF6F0] text-[#8a6a5c] border border-[#E6D5CC] hover:border-[#C8A288] hover:text-[#4A3B32]'
                                            }`}
                                        >
                                            {selected && <Check className="h-3 w-3 inline mr-1 -mt-0.5" />}
                                            {subject}
                                        </button>
                                    );
                                })}
                            </div>
                        </div>
                    </div>
                </section>
                
                {/* Learning Mode Section */}
                <section>
                    <h2 className="text-lg font-bold text-[#4A3B32] mb-4 flex items-center gap-2">
                        <Layers className="h-5 w-5 text-[#C8A288]" />
                        Learning Mode
                    </h2>
                    <div className="space-y-3">
                        <div className={`p-4 rounded-xl border-2 transition-all ${
                            settings.bookIsolation 
                                ? 'bg-[#C8A288]/10 border-[#C8A288]' 
                                : 'bg-white border-[#E6D5CC]'
                        }`}>
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-4">
                                    <div className={`h-12 w-12 rounded-xl flex items-center justify-center ${
                                        settings.bookIsolation ? 'bg-[#C8A288]' : 'bg-[#FDF6F0]'
                                    }`}>
                                        <BookOpen className={`h-6 w-6 ${
                                            settings.bookIsolation ? 'text-white' : 'text-[#C8A288]'
                                        }`} />
                                    </div>
                                    <div>
                                        <p className="font-bold text-[#4A3B32] text-lg">Book-Level Isolation</p>
                                        <p className="text-sm text-[#8a6a5c] max-w-md">
                                            Track progress, analytics, and learning paths separately for each book/document. 
                                            Perfect for studying multiple subjects.
                                        </p>
                                    </div>
                                </div>
                                <button
                                    onClick={() => updateSetting('bookIsolation', !settings.bookIsolation)}
                                    className={`relative w-16 h-9 rounded-full transition-colors ${
                                        settings.bookIsolation ? 'bg-[#C8A288]' : 'bg-gray-300'
                                    }`}
                                >
                                    <div className={`absolute top-1.5 w-6 h-6 bg-white rounded-full shadow-md transition-transform ${
                                        settings.bookIsolation ? 'translate-x-8' : 'translate-x-1.5'
                                    }`} />
                                </button>
                            </div>
                            
                            {settings.bookIsolation && (
                                <div className="mt-4 p-3 bg-white/50 rounded-lg border border-[#C8A288]/30">
                                    <p className="text-xs text-[#8a6a5c] flex items-center gap-2">
                                        <Check className="h-4 w-4 text-green-500" />
                                        Each book has its own learning path, quiz history, and analytics
                                    </p>
                                </div>
                            )}
                        </div>
                    </div>
                </section>

                {/* Pomodoro Settings */}
                <section>
                    <h2 className="text-lg font-bold text-[#4A3B32] mb-4 flex items-center gap-2">
                        <Timer className="h-5 w-5 text-[#C8A288]" />
                        Pomodoro Timer
                    </h2>
                    <div className="space-y-3">
                        <NumberInput
                            value={settings.pomodoroWork}
                            onChange={(v) => updateSetting('pomodoroWork', v)}
                            label="Focus Duration"
                            description="How long each study session lasts"
                            icon={Clock}
                            min={5}
                            max={60}
                            suffix="min"
                        />
                        <NumberInput
                            value={settings.pomodoroBreak}
                            onChange={(v) => updateSetting('pomodoroBreak', v)}
                            label="Short Break"
                            description="Rest time between sessions"
                            icon={Clock}
                            min={1}
                            max={30}
                            suffix="min"
                        />
                        <NumberInput
                            value={settings.pomodoroLongBreak}
                            onChange={(v) => updateSetting('pomodoroLongBreak', v)}
                            label="Long Break"
                            description="Extended rest after 4 sessions"
                            icon={Clock}
                            min={5}
                            max={60}
                            suffix="min"
                        />
                        <ToggleSwitch
                            enabled={settings.pomodoroAutoStart}
                            onChange={(v) => updateSetting('pomodoroAutoStart', v)}
                            label="Auto-Start Next Session"
                            description="Automatically begin next session after break"
                            icon={Timer}
                        />
                    </div>
                </section>

                {/* AI Tutor Settings */}
                <section>
                    <h2 className="text-lg font-bold text-[#4A3B32] mb-4 flex items-center gap-2">
                        <Brain className="h-5 w-5 text-[#C8A288]" />
                        AI Tutor
                    </h2>
                    <div className="space-y-3">
                        <SelectOption
                            value={settings.tutorStyle}
                            onChange={(v) => updateSetting('tutorStyle', v)}
                            label="Teaching Style"
                            description="How the AI explains concepts to you"
                            icon={Brain}
                            options={[
                                { value: 'simple', label: 'Simple - Explain like I\'m 5' },
                                { value: 'balanced', label: 'Balanced - Clear with examples' },
                                { value: 'detailed', label: 'Detailed - In-depth explanations' },
                                { value: 'socratic', label: 'Socratic - Guide with questions' },
                            ]}
                        />
                        <SelectOption
                            value={settings.quizDifficulty}
                            onChange={(v) => updateSetting('quizDifficulty', v)}
                            label="Quiz Difficulty"
                            description="Default difficulty for generated quizzes"
                            icon={Target}
                            options={[
                                { value: 'easy', label: 'Easy - Beginner friendly' },
                                { value: 'medium', label: 'Medium - Standard difficulty' },
                                { value: 'hard', label: 'Hard - Challenging questions' },
                                { value: 'adaptive', label: 'Adaptive - Adjusts to your level' },
                            ]}
                        />
                    </div>
                </section>

                {/* Appearance */}
                <section>
                    <h2 className="text-lg font-bold text-[#4A3B32] mb-4 flex items-center gap-2">
                        <Sun className="h-5 w-5 text-[#C8A288]" />
                        Appearance
                    </h2>
                    <div className="space-y-3">
                        <ToggleSwitch
                            enabled={settings.darkMode}
                            onChange={(v) => updateSetting('darkMode', v)}
                            label="Dark Mode"
                            description="Reduce eye strain in low light"
                            icon={Moon}
                        />
                        <ToggleSwitch
                            enabled={settings.compactMode}
                            onChange={(v) => updateSetting('compactMode', v)}
                            label="Compact Mode"
                            description="Optimized layout for smaller screens"
                            icon={Smartphone}
                        />
                    </div>
                </section>

                {/* Notifications */}
                <section>
                    <h2 className="text-lg font-bold text-[#4A3B32] mb-4 flex items-center gap-2">
                        <Bell className="h-5 w-5 text-[#C8A288]" />
                        Notifications
                    </h2>
                    <div className="space-y-3">
                        <ToggleSwitch
                            enabled={settings.studyReminders}
                            onChange={(v) => updateSetting('studyReminders', v)}
                            label="Study Reminders"
                            description="Get notified when it's time to review"
                            icon={Bell}
                        />
                        <ToggleSwitch
                            enabled={settings.soundEnabled}
                            onChange={(v) => updateSetting('soundEnabled', v)}
                            label="Sound Effects"
                            description="Play sounds for timers and achievements"
                            icon={Bell}
                        />
                        <ToggleSwitch
                            enabled={settings.showStreaks}
                            onChange={(v) => updateSetting('showStreaks', v)}
                            label="Show Streaks"
                            description="Display your daily study streak"
                            icon={Target}
                        />
                    </div>
                </section>

                {/* Reset */}
                <section className="pb-8">
                    <button
                        onClick={() => {
                            if (confirm('Reset all settings to defaults?')) {
                                resetSettings();
                            }
                        }}
                        className="w-full p-4 bg-red-50 text-red-600 rounded-xl border border-red-200 hover:bg-red-100 transition-colors font-medium"
                    >
                        Reset All Settings
                    </button>
                </section>
            </div>
        </div>
    );
};

export default Settings;
