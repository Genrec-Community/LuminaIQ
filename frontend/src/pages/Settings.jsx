import React, { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
    Crown,
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
import PlanUsage from '../components/PlanUsage';
import { useGamification } from '../context/GamificationContext';
import { useAuth } from '../context/AuthContext';
import { AI_CHARACTERS, USER_AVATARS, AI_AVATARS, AGE_GROUPS, getCharacter, displayName } from '../utils/persona';
import { onboardedKey } from '../components/Onboarding';
import { THEMES, FONT_STYLES, ACCENT_PRESETS, resolveThemeId } from '../utils/themes';

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
    const { settings, updateSetting, updateSettings, resetSettings } = useSettings();
    const { data: gamificationData } = useGamification();
    const { user } = useAuth();
    const [searchParams] = useSearchParams();
    const [activeSection, setActiveSection] = useState(searchParams.get('section') || 'profile');

    const isDark = settings?.darkMode ?? false;

    // Shorthand theme tokens used throughout this page
    // Theme-aware (see utils/themes.js); fallbacks are the classic palette
    const bg     = isDark ? 'var(--dm-bg, #1c1814)' : 'var(--th-bg, #FDF6F0)';
    const paper  = isDark ? 'var(--dm-surface, #252018)' : 'var(--th-surface, #FFFFFF)';
    const border  = isDark ? 'var(--dm-border-strong, #3d3028)' : 'var(--th-border, #E6D5CC)';
    const muted   = isDark ? 'var(--dm-text-secondary, #8a7060)' : 'var(--th-muted, #8a6a5c)';
    const heading = isDark ? 'var(--dm-text-primary, #e8e2dc)' : 'var(--th-text, #4A3B32)';
    const inputBg = isDark ? 'var(--dm-surface-elevated, #1e1a16)' : 'var(--th-alt, #FDF6F0)';


    const sections = [
        { id: 'profile', label: 'Profile', icon: User },
        { id: 'companion', label: 'AI Buddy', icon: Sparkles },
        { id: 'study', label: 'Study', icon: Layers },
        { id: 'focus', label: 'Focus', icon: Maximize2 },
        { id: 'ai', label: 'AI & Quiz', icon: Brain },
        { id: 'appearance', label: 'Display', icon: Sun },
        { id: 'notifications', label: 'Alerts', icon: Bell },
        { id: 'plan', label: 'Plan', icon: Crown },
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
                        <span className="text-3xl">{settings.userAvatar || '🦊'}</span>
                    </div>
                    <div className="flex-1 min-w-0">
                        <p className="text-base font-bold truncate">
                            {settings.studentName || 'Set your name below'}{settings.nickname ? ` · "${settings.nickname}"` : ''}
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
                    value={settings.nickname}
                    onChange={(v) => updateSetting('nickname', v)}
                    label="Nickname"
                    description="What your AI buddy calls you"
                    icon={Sparkles}
                    placeholder="e.g. Captain, Doc, Pri..."
                />
                <ChoiceGrid label="Your Avatar" value={settings.userAvatar || '🦊'} options={USER_AVATARS} onPick={(v) => updateSetting('userAvatar', v)} />
                <SelectOption
                    value={settings.ageGroup || ''}
                    onChange={(v) => updateSetting('ageGroup', v)}
                    label="About You"
                    description="Your AI adapts its language to you"
                    icon={User}
                    options={[{ value: '', label: 'Prefer not to say' }, ...Object.entries(AGE_GROUPS).map(([value, g]) => ({ value, label: g.label }))]}
                />
                <TextInput
                    value={settings.examName}
                    onChange={(v) => updateSetting('examName', v)}
                    label="Upcoming Exam"
                    description="Shown in your countdown and used to focus answers"
                    icon={Trophy}
                    placeholder="e.g. Class 12 Boards, NEET, AWS cert"
                />
                <div className="flex items-center justify-between gap-4 p-4 bg-white rounded-2xl border border-[#E6D5CC]/80">
                    <div className="flex items-center gap-3.5">
                        <div className="h-10 w-10 bg-[#FDF6F0] rounded-xl flex items-center justify-center shrink-0">
                            <Clock className="h-5 w-5 text-[#C8A288]" />
                        </div>
                        <div>
                            <p className="font-semibold text-[#4A3B32] text-sm">Exam Date</p>
                            <p className="text-xs text-[#8a6a5c] mt-0.5">We'll count down the days</p>
                        </div>
                    </div>
                    <input
                        type="date"
                        value={settings.examDate || ''}
                        onChange={(e) => updateSetting('examDate', e.target.value)}
                        className="px-3 py-2 bg-[#FDF6F0] border border-[#E6D5CC] rounded-xl text-sm text-[#4A3B32] outline-none focus:ring-2 focus:ring-[#C8A288]"
                    />
                </div>
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

    const ChoiceGrid = ({ label, value, options, onPick }) => (
        <div className="p-4 bg-white rounded-2xl border border-[#E6D5CC]/80">
            <p className="font-semibold text-[#4A3B32] text-sm mb-3">{label}</p>
            <div className="flex flex-wrap gap-2">
                {options.map(o => (
                    <button
                        key={o}
                        onClick={() => onPick(o)}
                        className={`h-10 w-10 text-xl rounded-xl border-2 transition-all active:scale-90 ${value === o ? 'border-[#C8A288] bg-[#C8A288]/10' : 'border-[#E6D5CC] hover:border-[#C8A288]/60'}`}
                    >
                        {o}
                    </button>
                ))}
            </div>
        </div>
    );

    const renderCompanion = () => {
        const character = getCharacter(settings.aiCharacter);
        const aiDisplay = settings.aiName?.trim() || 'Lumi';
        return (
            <div className="space-y-5">
                <SectionHeader icon={Sparkles} title="Your AI Study Buddy" subtitle="Name it, pick a personality, make it yours" />

                <div className="flex items-start gap-4 p-5 rounded-2xl bg-gradient-to-br from-[#C8A288] via-[#B08B72] to-[#8a6a5c] text-white">
                    <div className="h-14 w-14 shrink-0 rounded-2xl bg-white/20 border border-white/30 flex items-center justify-center text-3xl">{settings.aiAvatar || '✨'}</div>
                    <div>
                        <p className="font-bold">{aiDisplay} <span className="text-white/70 font-medium text-xs">· {character.label}</span></p>
                        <p className="text-sm text-white/90 mt-1">{character.greet(displayName(settings, user))}</p>
                    </div>
                </div>

                <div className="space-y-3">
                    <TextInput
                        value={settings.aiName}
                        onChange={(v) => updateSetting('aiName', v.slice(0, 24))}
                        label="Buddy's Name"
                        description="Shown in chat, Power Hour and your dashboard"
                        icon={Pencil}
                        placeholder="Lumi"
                    />
                    <ChoiceGrid label="Buddy's Avatar" value={settings.aiAvatar || '✨'} options={AI_AVATARS} onPick={(v) => updateSetting('aiAvatar', v)} />

                    <div className="p-4 bg-white rounded-2xl border border-[#E6D5CC]/80">
                        <p className="font-semibold text-[#4A3B32] text-sm mb-3">Personality</p>
                        <div className="grid sm:grid-cols-2 gap-2">
                            {Object.entries(AI_CHARACTERS).map(([k, c]) => (
                                <button
                                    key={k}
                                    onClick={() => updateSetting('aiCharacter', k)}
                                    className={`flex items-start gap-3 p-3 rounded-xl border-2 text-left transition-all ${settings.aiCharacter === k ? 'border-[#C8A288] bg-[#C8A288]/10' : 'border-[#E6D5CC] hover:border-[#C8A288]/60'}`}
                                >
                                    <span className="text-2xl">{c.emoji}</span>
                                    <span>
                                        <span className="block text-sm font-semibold text-[#4A3B32]">{c.label}</span>
                                        <span className="block text-xs text-[#8a6a5c]">{c.tagline}</span>
                                    </span>
                                </button>
                            ))}
                        </div>
                    </div>

                    <SelectOption
                        value={settings.aiHumor || 'some'}
                        onChange={(v) => updateSetting('aiHumor', v)}
                        label="Humour"
                        description="How playful should your buddy be?"
                        icon={Sparkles}
                        options={[
                            { value: 'none', label: 'Strictly serious' },
                            { value: 'some', label: 'A little fun' },
                            { value: 'lots', label: 'Lots of jokes & mnemonics' },
                        ]}
                    />
                    <ToggleSwitch
                        enabled={settings.aiEmoji !== false}
                        onChange={(v) => updateSetting('aiEmoji', v)}
                        label="Use Emojis"
                        description="Let your buddy sprinkle emojis in replies"
                        icon={Sparkles}
                    />
                    <button
                        onClick={() => {
                            try { localStorage.removeItem(onboardedKey(user?.id)); } catch { /* ignore */ }
                            updateSetting('onboardingComplete', false);
                            navigate('/dashboard');
                        }}
                        className="w-full p-3 rounded-2xl border-2 border-dashed border-[#E6D5CC] text-sm font-semibold text-[#8a6a5c] hover:border-[#C8A288] hover:text-[#4A3B32] transition-colors"
                    >
                        ✨ Replay the welcome setup
                    </button>
                </div>
            </div>
        );
    };

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

    const activeTheme = resolveThemeId(settings);

    const renderAppearance = () => (
        <div className="space-y-5">
            <SectionHeader icon={Sun} title="Appearance" subtitle="Customize the look and feel" />
            <div className="space-y-3">
                {/* Theme gallery */}
                <div className="p-4 bg-white rounded-2xl border border-[#E6D5CC]/80">
                    <div className="flex items-center justify-between mb-3">
                        <div>
                            <p className="font-semibold text-[#4A3B32] text-sm">Theme</p>
                            <p className="text-xs text-[#8a6a5c] mt-0.5">Pick a vibe — applies instantly everywhere</p>
                        </div>
                        <span className="text-xs font-semibold text-[#C8A288]">{THEMES[activeTheme].name}</span>
                    </div>
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
                        {Object.entries(THEMES).map(([id, t]) => {
                            const active = activeTheme === id;
                            return (
                                <button
                                    key={id}
                                    onClick={() => updateSettings({ theme: id, darkMode: t.mode === 'dark' })}
                                    className={`text-left rounded-xl border-2 overflow-hidden transition-all active:scale-[0.98] ${active ? 'border-[#C8A288] shadow-md shadow-[#C8A288]/20' : 'border-[#E6D5CC] hover:border-[#C8A288]/60'}`}
                                    aria-pressed={active}
                                >
                                    {/* Mini preview */}
                                    <div className="h-16 p-2 flex gap-1.5" style={{ background: t.swatch[0] }}>
                                        <div className="w-5 rounded-md" style={{ background: t.swatch[1] }} />
                                        <div className="flex-1 rounded-md p-1.5 flex flex-col justify-between" style={{ background: t.swatch[1] }}>
                                            <div className="h-1.5 w-3/4 rounded-full" style={{ background: t.swatch[3], opacity: 0.8 }} />
                                            <div className="h-3 w-1/2 rounded-md" style={{ background: t.swatch[2] }} />
                                        </div>
                                    </div>
                                    <div className="px-2.5 py-2">
                                        <p className="text-xs font-bold text-[#4A3B32] flex items-center gap-1">
                                            {t.name} {active && <Check className="h-3.5 w-3.5 text-[#C8A288]" />}
                                        </p>
                                        <p className="text-[10.5px] leading-snug text-[#8a6a5c]">{t.blurb}</p>
                                    </div>
                                </button>
                            );
                        })}
                    </div>
                </div>

                {/* Accent colour */}
                <div className="p-4 bg-white rounded-2xl border border-[#E6D5CC]/80">
                    <div className="flex items-center justify-between mb-3">
                        <div>
                            <p className="font-semibold text-[#4A3B32] text-sm">Accent colour</p>
                            <p className="text-xs text-[#8a6a5c] mt-0.5">Buttons, highlights and progress bars</p>
                        </div>
                        {settings.customAccent && (
                            <button onClick={() => updateSetting('customAccent', '')} className="text-xs font-semibold text-[#8a6a5c] hover:text-[#4A3B32]">
                                Use theme default
                            </button>
                        )}
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                        {ACCENT_PRESETS.map(c => (
                            <button
                                key={c}
                                onClick={() => updateSetting('customAccent', c)}
                                className={`h-8 w-8 rounded-full border-2 transition-transform active:scale-90 ${settings.customAccent?.toLowerCase() === c.toLowerCase() ? 'border-[#4A3B32] scale-110' : 'border-white shadow'}`}
                                style={{ background: c }}
                                title={c}
                                aria-label={`Accent ${c}`}
                            />
                        ))}
                        <label className="h-8 px-3 rounded-full border border-[#E6D5CC] flex items-center gap-2 text-xs font-semibold text-[#4A3B32] cursor-pointer hover:border-[#C8A288]">
                            <input
                                type="color"
                                value={settings.customAccent || '#C8A288'}
                                onChange={(e) => updateSetting('customAccent', e.target.value)}
                                className="h-5 w-5 cursor-pointer rounded border-0 bg-transparent p-0"
                            />
                            Custom
                        </label>
                    </div>
                </div>

                {/* Font style */}
                <div className="p-4 bg-white rounded-2xl border border-[#E6D5CC]/80">
                    <p className="font-semibold text-[#4A3B32] text-sm">Font style</p>
                    <p className="text-xs text-[#8a6a5c] mt-0.5 mb-3">How text looks across the app</p>
                    <div className="grid grid-cols-5 gap-2">
                        {[['auto', { name: 'Theme', stack: 'inherit' }], ...Object.entries(FONT_STYLES)].map(([key, f]) => {
                            const active = (settings.fontStyle || 'auto') === key;
                            return (
                                <button
                                    key={key}
                                    onClick={() => updateSetting('fontStyle', key)}
                                    className={`rounded-xl border-2 py-2 text-center transition-all ${active ? 'border-[#C8A288] bg-[#C8A288]/10' : 'border-[#E6D5CC] hover:border-[#C8A288]/60'}`}
                                >
                                    <span className="block text-lg text-[#4A3B32]" style={{ fontFamily: f.stack }}>Aa</span>
                                    <span className="block text-[10.5px] font-semibold text-[#8a6a5c]">{f.name}</span>
                                </button>
                            );
                        })}
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

                {/* Reset Tutorials */}
                <div className="p-4 rounded-2xl border flex items-center justify-between" style={{ background: paper, borderColor: border }}>
                    <div className="flex items-center gap-3.5">
                        <div className="h-10 w-10 rounded-xl flex items-center justify-center shrink-0" style={{ background: inputBg }}>
                            <Sparkles className="h-5 w-5 text-[#C8A288]" />
                        </div>
                        <div>
                            <p className="font-semibold text-sm" style={{ color: heading }}>App Tutorials</p>
                            <p className="text-xs mt-0.5" style={{ color: muted }}>Reset onboarding tours and show them again</p>
                        </div>
                    </div>
                    <button
                        onClick={() => {
                            if (user?.id) {
                                localStorage.removeItem(`hasSeenDashboardTutorial_${user.id}`);
                                localStorage.removeItem(`hasSeenProjectTutorial_${user.id}`);
                                navigate('/dashboard');
                            }
                        }}
                        className="px-4 py-2 bg-[#FDF6F0] hover:bg-[#E6D5CC] text-[#C8A288] border border-[#E6D5CC] rounded-xl font-semibold text-sm transition-colors shrink-0"
                    >
                        Restart Tour
                    </button>
                </div>
            </div>
        </div>
    );


    const renderPlan = () => (
        <div className="space-y-5">
            <SectionHeader icon={Crown} title="Plan & usage" subtitle="What your plan includes and how much you've used" />
            <PlanUsage />
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
            case 'companion': return renderCompanion();
            case 'study': return renderStudy();
            case 'focus': return renderFocus();
            case 'ai': return renderAI();
            case 'appearance': return renderAppearance();
            case 'notifications': return renderNotifications();
            case 'plan': return renderPlan();
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


