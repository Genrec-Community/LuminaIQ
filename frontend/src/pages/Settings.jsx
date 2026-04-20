import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    Settings as SettingsIcon,
    BookOpen,
    Moon,
    Sun,
    Bell,
    Clock,
    Target,
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
    Pencil,
    Maximize2,
    Keyboard,
    Volume2,
    Flame,
    Eye,
    Zap,
    Trophy,
    Type
} from 'lucide-react';
import { useSettings } from '../context/SettingsContext';
import { useGamification } from '../context/GamificationContext';

/**
 * TextInput — MUST be defined at module level (outside Settings component).
 * If defined inside, React creates a new component type on every parent render,
 * which unmounts+remounts the input and destroys focus mid-typing.
 */
const TextInput = ({ value, onChange, label, description, icon: Icon, placeholder }) => {
    const [localValue, setLocalValue] = React.useState(value || '');
    const timerRef = React.useRef(null);
    const isFocused = React.useRef(false);
    const pendingValue = React.useRef(value || '');

    // Only sync from parent when NOT actively typing
    React.useEffect(() => {
        if (!isFocused.current) {
            setLocalValue(value || '');
            pendingValue.current = value || '';
        }
    }, [value]);

    // Cleanup timer on unmount
    React.useEffect(() => () => clearTimeout(timerRef.current), []);

    const handleChange = (e) => {
        const v = e.target.value;
        setLocalValue(v);
        pendingValue.current = v;
        clearTimeout(timerRef.current);
        timerRef.current = setTimeout(() => onChange(pendingValue.current), 1200);
    };

    const handleFocus = () => { isFocused.current = true; };

    const handleBlur = () => {
        isFocused.current = false;
        clearTimeout(timerRef.current);
        if (pendingValue.current !== (value || '')) {
            onChange(pendingValue.current);
        }
    };

    return (
        <div className="p-4 bg-white rounded-2xl border border-[#E6D5CC]/80">
            <div className="flex items-center gap-3.5 mb-3">
                <div className="h-10 w-10 bg-[#FDF6F0] rounded-xl flex items-center justify-center shrink-0">
                    <Icon className="h-5 w-5 text-[#C8A288]" />
                </div>
                <div className="min-w-0">
                    <p className="font-semibold text-[#4A3B32] text-sm">{label}</p>
                    <p className="text-xs text-[#8a6a5c] mt-0.5">{description}</p>
                </div>
            </div>
            <input
                type="text"
                value={localValue}
                onChange={handleChange}
                onFocus={handleFocus}
                onBlur={handleBlur}
                placeholder={placeholder}
                autoComplete="off"
                spellCheck={false}
                className="w-full px-4 py-2.5 bg-[#FDF6F0] border border-[#E6D5CC] rounded-xl focus:ring-2 focus:ring-[#C8A288] focus:border-transparent outline-none text-[#4A3B32] font-medium text-sm placeholder-[#8a6a5c]/40 transition-shadow"
            />
        </div>
    );
};

const Settings = () => {
    const navigate = useNavigate();
    const { settings, updateSetting, resetSettings } = useSettings();
    const { data: gamificationData } = useGamification();
    const [activeSection, setActiveSection] = useState('profile');

    const isDark = settings?.darkMode ?? false;

    // Shorthand theme tokens used throughout this page
    const bg     = isDark ? '#1c1814' : '#FDF6F0';
    const paper  = isDark ? '#252018' : '#FFFFFF';
    const border  = isDark ? '#3d3028' : '#E6D5CC';
    const muted   = isDark ? '#8a7060' : '#8a6a5c';
    const heading = isDark ? '#e8e2dc' : '#4A3B32';
    const inputBg = isDark ? '#1e1a16' : '#FDF6F0';


    const sections = [
        { id: 'profile', label: 'Profile', icon: User },
        { id: 'study', label: 'Study', icon: Layers },
        { id: 'focus', label: 'Focus', icon: Maximize2 },
        { id: 'ai', label: 'AI & Quiz', icon: Brain },
        { id: 'appearance', label: 'Display', icon: Sun },
        { id: 'notifications', label: 'Alerts', icon: Bell },
    ];

    // --- Reusable Components ---

    const ToggleSwitch = ({ enabled, onChange, label, description, icon: Icon, comingSoon = false }) => (
        <div className={`flex items-center justify-between p-4 rounded-2xl border hover:border-[#C8A288]/50 transition-all group ${comingSoon ? 'opacity-70' : ''}`}
            style={{ background: paper, borderColor: border }}>
            <div className="flex items-center gap-3.5 min-w-0">
                <div className="h-10 w-10 rounded-xl flex items-center justify-center shrink-0 group-hover:bg-[#C8A288]/10 transition-colors"
                    style={{ background: inputBg }}>
                    <Icon className="h-5 w-5 text-[#C8A288]" />
                </div>
                <div className="min-w-0">
                    <div className="flex items-center gap-2">
                        <p className="font-semibold text-sm" style={{ color: heading }}>{label}</p>
                        {comingSoon && (
                            <span className="px-1.5 py-0.5 bg-amber-100 text-amber-700 text-[9px] font-bold rounded-full uppercase tracking-wider">Soon</span>
                        )}
                    </div>
                    <p className="text-xs mt-0.5 leading-relaxed" style={{ color: muted }}>{description}</p>
                </div>
            </div>
            <button
                onClick={() => !comingSoon && onChange(!enabled)}
                disabled={comingSoon}
                className={`relative w-12 h-7 rounded-full transition-all shrink-0 ml-3 ${
                    comingSoon ? 'bg-gray-200 cursor-not-allowed' :
                    enabled ? 'bg-[#C8A288] shadow-inner' : 'bg-[#E6D5CC]'
                }`}
            >
                <div className={`absolute top-0.5 w-6 h-6 bg-white rounded-full shadow-md transition-transform ${
                    enabled && !comingSoon ? 'translate-x-[22px]' : 'translate-x-0.5'
                }`}>
                    {enabled && !comingSoon && <Check className="h-3.5 w-3.5 text-[#C8A288] m-[5px]" />}
                </div>
            </button>
        </div>
    );


    const SelectOption = ({ value, onChange, label, description, icon: Icon, options }) => (
        <div className="p-4 rounded-2xl border" style={{ background: paper, borderColor: border }}>
            <div className="flex items-center gap-3.5 mb-3">
                <div className="h-10 w-10 rounded-xl flex items-center justify-center shrink-0" style={{ background: inputBg }}>
                    <Icon className="h-5 w-5 text-[#C8A288]" />
                </div>
                <div>
                    <p className="font-semibold text-sm" style={{ color: heading }}>{label}</p>
                    <p className="text-xs mt-0.5" style={{ color: muted }}>{description}</p>
                </div>
            </div>
            <select
                value={value}
                onChange={(e) => onChange(e.target.value)}
                className="w-full px-4 py-2.5 rounded-xl focus:ring-2 focus:ring-[#C8A288] focus:border-transparent outline-none font-medium text-sm cursor-pointer border"
                style={{ background: inputBg, color: heading, borderColor: border }}
            >
                {options.map(opt => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
            </select>
        </div>
    );


    const NumberInput = ({ value, onChange, label, description, icon: Icon, min, max, suffix }) => (
        <div className="p-4 rounded-2xl border" style={{ background: paper, borderColor: border }}>
            <div className="flex items-center gap-3.5">
                <div className="h-10 w-10 rounded-xl flex items-center justify-center shrink-0" style={{ background: inputBg }}>
                    <Icon className="h-5 w-5 text-[#C8A288]" />
                </div>
                <div className="flex-1 min-w-0">
                    <p className="font-semibold text-sm" style={{ color: heading }}>{label}</p>
                    <p className="text-xs mt-0.5" style={{ color: muted }}>{description}</p>
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                    <button
                        onClick={() => onChange(Math.max(min, value - 5))}
                        className="h-8 w-8 rounded-lg flex items-center justify-center hover:bg-[#E6D5CC] transition-colors font-bold text-lg"
                        style={{ background: inputBg, color: heading }}
                    >-</button>
                    <span className="w-14 text-center font-bold text-sm tabular-nums" style={{ color: heading }}>
                        {value}{suffix}
                    </span>
                    <button
                        onClick={() => onChange(Math.min(max, value + 5))}
                        className="h-8 w-8 rounded-lg flex items-center justify-center hover:bg-[#E6D5CC] transition-colors font-bold text-lg"
                        style={{ background: inputBg, color: heading }}
                    >+</button>
                </div>
            </div>
        </div>
    );


    // TextInput is defined at module level — see above the Settings component

    const SectionHeader = ({ icon: Icon, title, subtitle }) => (
        <div className="flex items-center gap-3 mb-5">
            <div className="h-9 w-9 bg-gradient-to-br from-[#C8A288] to-[#A08072] rounded-xl flex items-center justify-center shadow-sm">
                <Icon className="h-4.5 w-4.5 text-white" />
            </div>
            <div>
                <h2 className="text-base font-bold" style={{ color: heading }}>{title}</h2>
                {subtitle && <p className="text-xs mt-0.5" style={{ color: muted }}>{subtitle}</p>}
            </div>
        </div>
    );


    // --- Section Renderers ---

    const renderProfile = () => (
        <div className="space-y-5">
            <SectionHeader icon={User} title="Student Profile" subtitle="Personalize your learning experience" />

            {/* Profile Card */}
            <div className="bg-gradient-to-br from-[#C8A288] via-[#B08B72] to-[#8a6a5c] rounded-2xl p-5 text-white relative overflow-hidden">
                <div className="absolute top-0 right-0 w-32 h-32 bg-white/5 rounded-full -translate-y-1/2 translate-x-1/2" />
                <div className="absolute bottom-0 left-0 w-24 h-24 bg-white/5 rounded-full translate-y-1/2 -translate-x-1/2" />
                <div className="relative z-10 flex items-center gap-4">
                    <div className="h-14 w-14 bg-white/20 backdrop-blur-sm rounded-2xl flex items-center justify-center border border-white/30 shadow-lg shrink-0">
                        {settings.studentName ? (
                            <span className="text-xl font-black">{settings.studentName.charAt(0).toUpperCase()}</span>
                        ) : (
                            <User className="h-6 w-6" />
                        )}
                    </div>
                    <div className="flex-1 min-w-0">
                        <p className="text-base font-bold truncate">
                            {settings.studentName || 'Set your name below'}
                        </p>
                        <p className="text-white/70 text-xs font-medium mt-0.5">
                            {gamificationData ? `Level ${gamificationData.level} — ${gamificationData.level_title}` : 'Getting started...'}
                        </p>
                    </div>
                    {gamificationData && (
                        <div className="text-right shrink-0 hidden sm:block">
                            <div className="flex items-center gap-1 justify-end">
                                <Zap className="h-4 w-4 text-amber-300" />
                                <p className="text-xl font-black">{gamificationData.total_xp}</p>
                            </div>
                            <p className="text-white/60 text-[10px] font-semibold uppercase tracking-wider">XP Earned</p>
                        </div>
                    )}
                </div>
            </div>

            <div className="space-y-3">
                <TextInput
                    value={settings.studentName}
                    onChange={(v) => updateSetting('studentName', v)}
                    label="Your Name"
                    description="How should we address you?"
                    icon={Pencil}
                    placeholder="Enter your name..."
                />
                <TextInput
                    value={settings.learningGoal}
                    onChange={(v) => updateSetting('learningGoal', v)}
                    label="Learning Goal"
                    description="What are you studying for?"
                    icon={Target}
                    placeholder="e.g., Pass my biology exam, Master JavaScript..."
                />
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
                <NumberInput
                    value={settings.dailyStudyGoal || 30}
                    onChange={(v) => updateSetting('dailyStudyGoal', v)}
                    label="Daily Study Goal"
                    description="Minutes per day target"
                    icon={Clock}
                    min={10}
                    max={180}
                    suffix="m"
                />

                {/* Subjects of Interest */}
                <div className="p-4 bg-white rounded-2xl border border-[#E6D5CC]/80">
                    <div className="flex items-center gap-3.5 mb-3">
                        <div className="h-10 w-10 bg-[#FDF6F0] rounded-xl flex items-center justify-center shrink-0">
                            <BookMarked className="h-5 w-5 text-[#C8A288]" />
                        </div>
                        <div>
                            <p className="font-semibold text-[#4A3B32] text-sm">Subjects of Interest</p>
                            <p className="text-xs text-[#8a6a5c] mt-0.5">Select topics you're interested in</p>
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
                                    className={`px-3 py-1.5 rounded-full text-xs font-medium transition-all ${
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
        </div>
    );

    const renderStudy = () => (
        <div className="space-y-5">
            <SectionHeader icon={Layers} title="Study Settings" subtitle="Configure how you learn" />

            {/* Book Isolation - Featured Card */}
            <div className={`p-5 rounded-2xl border-2 transition-all ${
                settings.bookIsolation 
                    ? 'bg-[#C8A288]/5 border-[#C8A288]/60' 
                    : 'bg-white border-[#E6D5CC]'
            }`}>
                <div className="flex items-center justify-between gap-4">
                    <div className="flex items-center gap-3.5">
                        <div className={`h-11 w-11 rounded-xl flex items-center justify-center shrink-0 ${
                            settings.bookIsolation ? 'bg-[#C8A288]' : 'bg-[#FDF6F0]'
                        }`}>
                            <BookOpen className={`h-5 w-5 ${
                                settings.bookIsolation ? 'text-white' : 'text-[#C8A288]'
                            }`} />
                        </div>
                        <div>
                            <p className="font-bold text-[#4A3B32]">Book-Level Isolation</p>
                            <p className="text-xs text-[#8a6a5c] mt-0.5 max-w-sm leading-relaxed">
                                Track progress, analytics, and paths separately per document
                            </p>
                        </div>
                    </div>
                    <button
                        onClick={() => updateSetting('bookIsolation', !settings.bookIsolation)}
                        className={`relative w-12 h-7 rounded-full transition-all shrink-0 ${
                            settings.bookIsolation ? 'bg-[#C8A288]' : 'bg-[#E6D5CC]'
                        }`}
                    >
                        <div className={`absolute top-0.5 w-6 h-6 bg-white rounded-full shadow-md transition-transform ${
                            settings.bookIsolation ? 'translate-x-[22px]' : 'translate-x-0.5'
                        }`}>
                            {settings.bookIsolation && <Check className="h-3.5 w-3.5 text-[#C8A288] m-[5px]" />}
                        </div>
                    </button>
                </div>
            </div>

            {/* Pomodoro Settings */}
            <div className="pt-2">
                <div className="flex items-center gap-2 mb-3">
                    <Timer className="h-4 w-4 text-[#C8A288]" />
                    <p className="text-sm font-bold text-[#4A3B32]">Pomodoro Timer</p>
                </div>
                <div className="space-y-3">
                    <NumberInput
                        value={settings.pomodoroWork}
                        onChange={(v) => updateSetting('pomodoroWork', v)}
                        label="Focus Duration"
                        description="Length of each study session"
                        icon={Clock}
                        min={5}
                        max={60}
                        suffix="m"
                    />
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <NumberInput
                            value={settings.pomodoroBreak}
                            onChange={(v) => updateSetting('pomodoroBreak', v)}
                            label="Short Break"
                            description="Rest between sessions"
                            icon={Clock}
                            min={1}
                            max={30}
                            suffix="m"
                        />
                        <NumberInput
                            value={settings.pomodoroLongBreak}
                            onChange={(v) => updateSetting('pomodoroLongBreak', v)}
                            label="Long Break"
                            description="After 4 sessions"
                            icon={Clock}
                            min={5}
                            max={60}
                            suffix="m"
                        />
                    </div>
                    <ToggleSwitch
                        enabled={settings.pomodoroAutoStart}
                        onChange={(v) => updateSetting('pomodoroAutoStart', v)}
                        label="Auto-Start Next Session"
                        description="Automatically begin next session after break"
                        icon={Timer}
                    />
                </div>
            </div>
        </div>
    );

    const renderFocus = () => (
        <div className="space-y-5">
            <SectionHeader icon={Maximize2} title="Focus & Zen Mode" subtitle="Distraction-free study environment" />

            {/* Zen Mode Feature Card */}
            <div className="bg-gradient-to-br from-emerald-50 to-teal-50 rounded-2xl p-5 border border-emerald-200/60 relative overflow-hidden">
                <div className="absolute top-0 right-0 w-28 h-28 bg-emerald-100/40 rounded-full -translate-y-1/2 translate-x-1/2" />
                <div className="relative z-10">
                    <div className="flex items-center gap-3 mb-3">
                        <div className="h-11 w-11 bg-emerald-500/10 backdrop-blur-sm rounded-xl flex items-center justify-center border border-emerald-500/20">
                            <Maximize2 className="h-5 w-5 text-emerald-600" />
                        </div>
                        <div>
                            <p className="font-bold text-emerald-900">Zen Mode</p>
                            <p className="text-xs text-emerald-700/70 mt-0.5">Full-screen, distraction-free study</p>
                        </div>
                    </div>
                    <div className="bg-white/60 rounded-xl p-4 space-y-3 backdrop-blur-sm">
                        <div className="flex items-start gap-3">
                            <div className="h-7 w-7 bg-emerald-100 rounded-lg flex items-center justify-center shrink-0 mt-0.5">
                                <Eye className="h-3.5 w-3.5 text-emerald-600" />
                            </div>
                            <div>
                                <p className="text-sm font-semibold text-[#4A3B32]">Hides all sidebars</p>
                                <p className="text-xs text-[#8a6a5c] mt-0.5">Navigation, documents panel, and header are hidden to maximize reading area</p>
                            </div>
                        </div>
                        <div className="flex items-start gap-3">
                            <div className="h-7 w-7 bg-emerald-100 rounded-lg flex items-center justify-center shrink-0 mt-0.5">
                                <Keyboard className="h-3.5 w-3.5 text-emerald-600" />
                            </div>
                            <div>
                                <p className="text-sm font-semibold text-[#4A3B32]">Keyboard shortcuts</p>
                                <div className="flex flex-wrap gap-2 mt-1.5">
                                    <div className="flex items-center gap-1">
                                        <kbd className="px-2 py-0.5 bg-[#FDF6F0] border border-[#E6D5CC] rounded text-[10px] font-mono font-bold text-[#4A3B32]">Ctrl</kbd>
                                        <span className="text-[10px] text-[#8a6a5c]">+</span>
                                        <kbd className="px-2 py-0.5 bg-[#FDF6F0] border border-[#E6D5CC] rounded text-[10px] font-mono font-bold text-[#4A3B32]">Shift</kbd>
                                        <span className="text-[10px] text-[#8a6a5c]">+</span>
                                        <kbd className="px-2 py-0.5 bg-[#FDF6F0] border border-[#E6D5CC] rounded text-[10px] font-mono font-bold text-[#4A3B32]">Z</kbd>
                                        <span className="text-xs text-[#8a6a5c] ml-1">Toggle</span>
                                    </div>
                                    <div className="flex items-center gap-1">
                                        <kbd className="px-2 py-0.5 bg-[#FDF6F0] border border-[#E6D5CC] rounded text-[10px] font-mono font-bold text-[#4A3B32]">Esc</kbd>
                                        <span className="text-xs text-[#8a6a5c] ml-1">Exit</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div className="flex items-start gap-3">
                            <div className="h-7 w-7 bg-emerald-100 rounded-lg flex items-center justify-center shrink-0 mt-0.5">
                                <Maximize2 className="h-3.5 w-3.5 text-emerald-600" />
                            </div>
                            <div>
                                <p className="text-sm font-semibold text-[#4A3B32]">Quick access</p>
                                <p className="text-xs text-[#8a6a5c] mt-0.5">Click the expand icon in the header toolbar to enter focus mode instantly</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Other Shortcuts */}
            <div className="p-4 bg-white rounded-2xl border border-[#E6D5CC]/80">
                <div className="flex items-center gap-3.5 mb-3">
                    <div className="h-10 w-10 bg-[#FDF6F0] rounded-xl flex items-center justify-center shrink-0">
                        <Keyboard className="h-5 w-5 text-[#C8A288]" />
                    </div>
                    <div>
                        <p className="font-semibold text-[#4A3B32] text-sm">All Keyboard Shortcuts</p>
                        <p className="text-xs text-[#8a6a5c] mt-0.5">Quick access to features</p>
                    </div>
                </div>
                <div className="space-y-2">
                    {[
                        { keys: ['Ctrl', 'K'], desc: 'Global search' },
                        { keys: ['Ctrl', 'Shift', 'Z'], desc: 'Toggle focus mode' },
                        { keys: ['Esc'], desc: 'Close modals / exit focus mode' },
                    ].map((shortcut, i) => (
                        <div key={i} className="flex items-center justify-between py-2 px-3 bg-[#FDF6F0]/60 rounded-lg">
                            <div className="flex items-center gap-1">
                                {shortcut.keys.map((key, j) => (
                                    <span key={j} className="flex items-center gap-1">
                                        {j > 0 && <span className="text-[10px] text-[#8a6a5c]">+</span>}
                                        <kbd className="px-2 py-0.5 bg-white border border-[#E6D5CC] rounded text-[11px] font-mono font-bold text-[#4A3B32] shadow-sm">{key}</kbd>
                                    </span>
                                ))}
                            </div>
                            <span className="text-xs text-[#8a6a5c] font-medium">{shortcut.desc}</span>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );

    const renderAI = () => (
        <div className="space-y-5">
            <SectionHeader icon={Brain} title="AI & Quiz Settings" subtitle="Customize your AI learning assistant" />
            <div className="space-y-3">
                <SelectOption
                    value={settings.tutorStyle}
                    onChange={(v) => updateSetting('tutorStyle', v)}
                    label="Teaching Style"
                    description="How the AI explains concepts to you"
                    icon={Brain}
                    options={[
                        { value: 'simple', label: "Simple — Explain like I'm 5" },
                        { value: 'balanced', label: 'Balanced — Clear with examples' },
                        { value: 'detailed', label: 'Detailed — In-depth explanations' },
                        { value: 'socratic', label: 'Socratic — Guide with questions' },
                    ]}
                />
                <SelectOption
                    value={settings.quizDifficulty}
                    onChange={(v) => updateSetting('quizDifficulty', v)}
                    label="Quiz Difficulty"
                    description="Default difficulty for generated quizzes"
                    icon={Target}
                    options={[
                        { value: 'easy', label: 'Easy — Beginner friendly' },
                        { value: 'medium', label: 'Medium — Standard difficulty' },
                        { value: 'hard', label: 'Hard — Challenging questions' },
                        { value: 'adaptive', label: 'Adaptive — Adjusts to your performance' },
                    ]}
                />
                {settings.quizDifficulty === 'adaptive' && (
                    <div className="p-3 bg-purple-50 rounded-xl border border-purple-200/60">
                        <div className="flex items-start gap-2">
                            <Zap className="h-4 w-4 text-purple-500 mt-0.5 shrink-0" />
                            <p className="text-xs text-purple-700 leading-relaxed">
                                <span className="font-semibold">Adaptive mode</span> analyzes your quiz scores and automatically adjusts difficulty. You can always override it per-quiz.
                            </p>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );

    const renderAppearance = () => (
        <div className="space-y-5">
            <SectionHeader icon={Sun} title="Appearance" subtitle="Customize the look and feel" />
            <div className="space-y-3">
                {/* Dark Mode — fully functional */}
                <div className={`p-5 rounded-2xl border-2 transition-all ${
                    settings.darkMode
                        ? 'bg-[#2a2927] border-[#C8A288]/60'
                        : 'bg-white border-[#E6D5CC]'
                }`}>
                    <div className="flex items-center justify-between gap-4">
                        <div className="flex items-center gap-3.5">
                            <div className={`h-11 w-11 rounded-xl flex items-center justify-center shrink-0 ${
                                settings.darkMode ? 'bg-[#4A3B32]' : 'bg-[#FDF6F0]'
                            }`}>
                                {settings.darkMode
                                    ? <Moon className="h-5 w-5 text-[#C8A288]" />
                                    : <Sun className="h-5 w-5 text-[#C8A288]" />}
                            </div>
                            <div>
                                <p className="font-bold text-[#4A3B32]">
                                    {settings.darkMode ? 'Dark Mode — On' : 'Dark Mode — Off'}
                                </p>
                                <p className="text-xs text-[#8a6a5c] mt-0.5">
                                    {settings.darkMode ? 'Warm near-black theme, easy on the eyes' : 'Switch to a rich dark theme'}
                                </p>
                            </div>
                        </div>
                        <button
                            onClick={() => updateSetting('darkMode', !settings.darkMode)}
                            className={`relative w-12 h-7 rounded-full transition-all shrink-0 ${
                                settings.darkMode ? 'bg-[#C8A288]' : 'bg-[#E6D5CC]'
                            }`}
                        >
                            <div className={`absolute top-0.5 w-6 h-6 bg-white rounded-full shadow-md transition-transform ${
                                settings.darkMode ? 'translate-x-[22px]' : 'translate-x-0.5'
                            }`}>
                                {settings.darkMode && <Check className="h-3.5 w-3.5 text-[#C8A288] m-[5px]" />}
                            </div>
                        </button>
                    </div>
                </div>

                {/* Font Size */}
                <SelectOption
                    value={settings.fontSize || 'md'}
                    onChange={(v) => updateSetting('fontSize', v)}
                    label="Font Size"
                    description="Adjust the overall text size across the app"
                    icon={Type}
                    options={[
                        { value: 'sm', label: 'Small — Compact text' },
                        { value: 'md', label: 'Medium — Default' },
                        { value: 'lg', label: 'Large — Easier to read' },
                        { value: 'xl', label: 'Extra Large — Maximum readability' },
                    ]}
                />

                {/* Compact Mode */}
                <ToggleSwitch
                    enabled={settings.compactMode}
                    onChange={(v) => updateSetting('compactMode', v)}
                    label="Compact Mode"
                    description="Denser layout with reduced spacing"
                    icon={Smartphone}
                />
            </div>
        </div>
    );


    const renderNotifications = () => (
        <div className="space-y-5">
            <SectionHeader icon={Bell} title="Notifications & Alerts" subtitle="Control what you see and hear" />
            <div className="space-y-3">
                <ToggleSwitch
                    enabled={settings.studyReminders}
                    onChange={(v) => updateSetting('studyReminders', v)}
                    label="Study Reminders"
                    description="Browser notifications for study sessions"
                    icon={Bell}
                    comingSoon
                />
                <ToggleSwitch
                    enabled={settings.soundEnabled}
                    onChange={(v) => updateSetting('soundEnabled', v)}
                    label="Sound Effects"
                    description="Play sounds for timers and achievements"
                    icon={Volume2}
                    comingSoon
                />
                <ToggleSwitch
                    enabled={settings.showStreaks}
                    onChange={(v) => updateSetting('showStreaks', v)}
                    label="Show Streaks"
                    description="Display your daily study streak"
                    icon={Flame}
                    comingSoon
                />
            </div>

            {/* Coming soon info */}
            <div className="p-4 rounded-2xl border" style={{ background: isDark ? '#2a1e10' : '#fffbf2', borderColor: isDark ? '#5a3a20' : '#fde68a' }}>
                <div className="flex items-start gap-3">
                    <div className="h-8 w-8 rounded-lg flex items-center justify-center shrink-0 mt-0.5" style={{ background: isDark ? '#3a2810' : '#fef3c7' }}>
                        <Sparkles className="h-4 w-4 text-amber-500" />
                    </div>
                    <div>
                        <p className="font-semibold text-sm" style={{ color: isDark ? '#d4a060' : '#78350f' }}>Features in Development</p>
                        <p className="text-xs mt-0.5 leading-relaxed" style={{ color: isDark ? '#a07840' : '#92400e' }}>
                            Study reminders, sound effects, and streaks are being built. Settings marked with "Soon" will be enabled in a future update.
                        </p>
                    </div>
                </div>
            </div>

        </div>
    );

    const renderSection = () => {
        switch (activeSection) {
            case 'profile': return renderProfile();
            case 'study': return renderStudy();
            case 'focus': return renderFocus();
            case 'ai': return renderAI();
            case 'appearance': return renderAppearance();
            case 'notifications': return renderNotifications();
            default: return renderProfile();
        }
    };

    return (
        <div className="min-h-screen font-sans transition-colors duration-300" style={{ background: bg, color: heading }}>
            {/* Header */}
            <div className="backdrop-blur-md border-b sticky top-0 z-10 transition-colors duration-300"
                style={{ background: isDark ? 'rgba(28,24,20,0.95)' : 'rgba(255,255,255,0.80)', borderColor: border }}>
                <div className="max-w-5xl mx-auto px-4 py-3 flex items-center gap-3">
                    <button
                        onClick={() => navigate(-1)}
                        className="p-2 rounded-xl transition-colors shrink-0"
                        style={{ background: 'transparent' }}
                        onMouseEnter={e => e.currentTarget.style.background = inputBg}
                        onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                    >
                        <ChevronLeft className="h-5 w-5" style={{ color: heading }} />
                    </button>
                    <div className="flex items-center gap-2.5">
                        <div className="h-9 w-9 bg-gradient-to-br from-[#C8A288] to-[#A08072] rounded-xl flex items-center justify-center shadow-sm">
                            <SettingsIcon className="h-4.5 w-4.5 text-white" />
                        </div>
                        <h1 className="text-lg font-bold" style={{ color: heading }}>Settings</h1>
                    </div>
                </div>
            </div>

            {/* Content */}
            <div className="max-w-5xl mx-auto px-4 py-6">
                <div className="flex gap-6">
                    {/* Side Navigation */}
                    <nav className="hidden md:block w-48 shrink-0 sticky top-20 self-start">
                        <div className="space-y-1">
                            {sections.map(sec => {
                                const Icon = sec.icon;
                                const isActive = activeSection === sec.id;
                                return (
                                    <button
                                        key={sec.id}
                                        onClick={() => setActiveSection(sec.id)}
                                        className="w-full flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl text-sm font-medium transition-all"
                                        style={isActive
                                            ? { background: '#C8A288', color: '#fff' }
                                            : { color: muted, background: 'transparent' }
                                        }
                                        onMouseEnter={e => { if (!isActive) e.currentTarget.style.background = isDark ? '#2e2620' : 'rgba(230,213,204,0.4)'; }}
                                        onMouseLeave={e => { if (!isActive) e.currentTarget.style.background = 'transparent'; }}
                                    >
                                        <Icon className="h-4 w-4 shrink-0" />
                                        {sec.label}
                                    </button>
                                );
                            })}
                        </div>

                        {/* Reset button */}
                        <div className="mt-6 pt-4 border-t" style={{ borderColor: border }}>
                            <button
                                onClick={() => {
                                    if (confirm('Reset all settings to defaults?')) {
                                        resetSettings();
                                    }
                                }}
                                className="w-full px-3.5 py-2.5 text-xs font-medium text-red-500 hover:bg-red-50 rounded-xl transition-colors text-left"
                            >
                                Reset All Settings
                            </button>
                        </div>
                    </nav>

                    {/* Mobile Tab Bar */}
                    <div className="md:hidden fixed bottom-0 left-0 right-0 backdrop-blur-md border-t z-20 px-2 py-1.5 flex justify-around"
                        style={{ background: isDark ? 'rgba(28,24,20,0.97)' : 'rgba(255,255,255,0.95)', borderColor: border }}>
                        {sections.map(sec => {
                            const Icon = sec.icon;
                            const isActive = activeSection === sec.id;
                            return (
                                <button
                                    key={sec.id}
                                    onClick={() => setActiveSection(sec.id)}
                                    className="flex flex-col items-center gap-0.5 px-2 py-1.5 rounded-lg text-[10px] font-medium transition-colors"
                                    style={{ color: isActive ? '#C8A288' : muted }}
                                >
                                    <Icon className="h-4.5 w-4.5" />
                                    <span>{sec.label}</span>
                                </button>
                            );
                        })}
                    </div>

                    {/* Main Content */}
                    <div className="flex-1 min-w-0 mb-20 md:mb-0">
                        {renderSection()}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default Settings;


