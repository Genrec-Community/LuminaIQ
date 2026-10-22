import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    Moon, Target, Bell, Sparkles, Settings as SettingsIcon, Shield, FileText, LogOut, Trash2, ChevronRight, Mail, Loader2, Check, Award,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useSettings } from '../../context/SettingsContext';
import { useGamification } from '../../context/GamificationContext';
import { useToast } from '../../context/ToastContext';
import { deleteAccount } from '../../api';
import { displayName } from '../../utils/persona';
import { Screen, ScreenHeader, Sheet } from '../ui';
import { tap, notify, scheduleStudyReminder, reminderScheduled } from '../device';

const GOALS = [{ m: 10, label: 'Casual', e: '🌱' }, { m: 20, label: 'Regular', e: '📘' }, { m: 30, label: 'Serious', e: '🔥' }, { m: 60, label: 'Beast mode', e: '🚀' }];
const TIMES = ['07:00', '09:00', '13:00', '17:00', '19:00', '21:00', '22:30'];
const fmtTime = (t) => {
    const [h, m] = t.split(':').map(Number);
    return `${((h + 11) % 12) + 1}:${String(m).padStart(2, '0')} ${h < 12 ? 'AM' : 'PM'}`;
};

const Toggle = ({ on }) => (
    <span className="relative h-7 w-12 shrink-0 rounded-full transition-colors" style={{ background: on ? 'var(--m-accent)' : 'var(--m-border)' }}>
        <span className="absolute top-0.5 h-6 w-6 rounded-full m-white shadow transition-all" style={{ left: on ? 22 : 2 }} />
    </span>
);

const Row = ({ icon: Icon, color, label, value, onClick, right, danger }) => (
    <button onClick={() => { tap(); onClick?.(); }} className="m-pressable flex w-full items-center gap-3 px-4 py-3.5 text-left">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-white" style={{ background: color }}><Icon className="h-[18px] w-[18px]" /></span>
        <span className={`flex-1 text-[15px] font-semibold ${danger ? 'text-red-500' : ''}`}>{label}</span>
        {value && <span className="text-[14px]" style={{ color: 'var(--m-muted)' }}>{value}</span>}
        {right ?? <ChevronRight className="h-5 w-5" style={{ color: 'var(--m-muted)' }} />}
    </button>
);

const Group = ({ title, children }) => (
    <section>
        {title && <h2 className="mb-2 px-2 text-[12px] font-bold uppercase tracking-[0.1em]" style={{ color: 'var(--m-muted)' }}>{title}</h2>}
        <div className="m-card m-group overflow-hidden">{children}</div>
    </section>
);

const openUrl = async (url) => {
    try {
        const { Browser } = await import('@capacitor/browser');
        await Browser.open({ url });
    } catch {
        window.open(url, '_blank', 'noopener');
    }
};

/** Profile, progress and app settings. */
const Me = () => {
    const navigate = useNavigate();
    const { user, logout } = useAuth();
    const { settings, updateSetting, updateSettings } = useSettings();
    const { data: g } = useGamification();
    const toast = useToast();
    const [sheet, setSheet] = useState(null); // goal | reminder | delete | signout
    const [confirmText, setConfirmText] = useState('');
    const [busy, setBusy] = useState(false);

    // The setting defaults to on, but a reminder exists only once scheduled on this phone
    const [remOn, setRemOn] = useState(() => !!settings.studyReminders && reminderScheduled());
    const streak = g?.streak_days ?? g?.stats?.streak_days ?? 0;
    const badges = g?.badges || [];
    const levelPct = Math.round(g?.level_progress ?? 0); // 0-100 from the server

    const setReminder = async (enabled, time = settings.reminderTime || '19:00') => {
        const ok = await scheduleStudyReminder(enabled, time);
        if (enabled && ok === false) {
            toast.error('Turn on notifications for LuminaIQ in your phone settings to get reminders.');
            updateSettings({ studyReminders: false });
            return;
        }
        updateSettings({ studyReminders: enabled, reminderTime: time });
        setRemOn(enabled && ok !== false);
        if (enabled) notify('success');
    };

    const removeAccount = async () => {
        setBusy(true);
        try {
            await deleteAccount();
            notify('success');
            try { localStorage.clear(); } catch { /* ignore */ }
            await logout();
            navigate('/welcome', { replace: true });
        } catch (e) {
            toast.error(e?.response?.data?.detail || 'Could not delete the account. Try again or email support.');
            setBusy(false);
        }
    };

    return (
        <Screen className="m-tab-space">
            <ScreenHeader title="You" />
            <div className="space-y-6 px-4">
                {/* Profile card */}
                <div className="m-card overflow-hidden">
                    <div className="flex items-center gap-4 p-5">
                        <div className="flex h-16 w-16 items-center justify-center rounded-full text-4xl shadow-md" style={{ background: 'linear-gradient(135deg, var(--m-accent), var(--m-accent-deep))' }}>
                            {settings.userAvatar || '🦊'}
                        </div>
                        <div className="min-w-0 flex-1">
                            <p className="truncate text-[20px] font-extrabold">{displayName(settings, user)}</p>
                            <p className="truncate text-[13px]" style={{ color: 'var(--m-muted)' }}>{user?.email}</p>
                            <p className="mt-1 text-[13px] font-bold" style={{ color: 'var(--m-accent)' }}>Level {g?.level || 1} · {g?.level_title || 'Curious Reader'}</p>
                        </div>
                    </div>
                    <div className="px-5 pb-4">
                        <div className="h-2 overflow-hidden rounded-full" style={{ background: 'var(--m-soft)' }}>
                            <div className="h-full rounded-full" style={{ width: `${Math.min(100, Math.max(3, levelPct))}%`, background: 'linear-gradient(90deg, var(--m-accent), var(--m-accent-deep))' }} />
                        </div>
                        {g?.next_level && <p className="mt-1.5 text-[12px]" style={{ color: 'var(--m-muted)' }}>{g.xp_in_level ?? 0} / {g.xp_needed ?? '—'} XP to level {g.next_level?.level || (g.level || 1) + 1}</p>}
                    </div>
                    <div className="grid grid-cols-3 border-t text-center" style={{ borderColor: 'var(--m-border)' }}>
                        {[
                            { v: streak, l: 'Day streak', e: '🔥' },
                            { v: (g?.total_xp || 0).toLocaleString(), l: 'Total XP', e: '⚡' },
                            { v: badges.length, l: 'Badges', e: '🏅' },
                        ].map((s) => (
                            <div key={s.l} className="py-3.5">
                                <p className="text-[18px] font-extrabold">{s.e} {s.v}</p>
                                <p className="text-[11.5px] font-semibold" style={{ color: 'var(--m-muted)' }}>{s.l}</p>
                            </div>
                        ))}
                    </div>
                </div>

                {badges.length > 0 && (
                    <div className="m-hscroll -mx-4 gap-2 px-4">
                        {badges.map((b) => (
                            <div key={b.id || b.title} className="flex w-28 shrink-0 flex-col items-center rounded-2xl p-3 text-center" style={{ background: 'var(--m-soft)' }}>
                                <Award className="h-7 w-7" style={{ color: 'var(--m-accent)' }} />
                                <p className="mt-1 line-clamp-2 text-[12px] font-bold">{b.title || b.name || b.id}</p>
                            </div>
                        ))}
                    </div>
                )}

                <Group title="Study">
                    <Row icon={Target} color="#2f9e7a" label="Daily goal" value={`${settings.dailyStudyGoal || 30} min`} onClick={() => setSheet('goal')} />
                    <Row icon={Bell} color="#f59e0b" label="Daily reminder" value={remOn ? fmtTime(settings.reminderTime || '19:00') : 'Off'} onClick={() => setSheet('reminder')} />
                    <Row icon={Moon} color="#4b3fa3" label="Dark mode" onClick={() => updateSetting('darkMode', !settings.darkMode)} right={<Toggle on={!!settings.darkMode} />} />
                </Group>

                <Group title="Personalise">
                    <Row icon={Sparkles} color="#e46a91" label="Profile & study buddy" onClick={() => navigate('/settings')} />
                    <Row icon={SettingsIcon} color="#64748b" label="All settings" onClick={() => navigate('/settings')} />
                </Group>

                <Group title="About">
                    <Row icon={Mail} color="#3b8fd6" label="Help & feedback" onClick={() => openUrl('mailto:support@luminaiq.fun?subject=LuminaIQ%20app')} />
                    <Row icon={Shield} color="#14b8a6" label="Privacy policy" onClick={() => navigate('/privacy')} />
                    <Row icon={FileText} color="#a16207" label="Terms of use" onClick={() => navigate('/terms')} />
                </Group>

                <Group>
                    <Row icon={LogOut} color="#8a6a5c" label="Sign out" onClick={() => setSheet('signout')} right={null} />
                    <Row icon={Trash2} color="#ef4444" label="Delete account" danger onClick={() => { setConfirmText(''); setSheet('delete'); }} right={null} />
                </Group>
                <p className="pb-2 text-center text-[12px]" style={{ color: 'var(--m-muted)' }}>LuminaIQ · made for curious minds</p>
            </div>

            <Sheet open={sheet === 'goal'} onClose={() => setSheet(null)} title="Daily goal">
                <div className="grid grid-cols-2 gap-3">
                    {GOALS.map((o) => {
                        const on = (settings.dailyStudyGoal || 30) === o.m;
                        return (
                            <button key={o.m} onClick={() => { tap(); updateSetting('dailyStudyGoal', o.m); setSheet(null); }}
                                className="m-pressable rounded-2xl p-4 text-left" style={{ background: on ? 'color-mix(in srgb, var(--m-accent) 18%, transparent)' : 'var(--m-soft)', boxShadow: on ? '0 0 0 2px var(--m-accent)' : 'none' }}>
                                <span className="text-3xl">{o.e}</span>
                                <p className="mt-2 text-[16px] font-extrabold">{o.m} min</p>
                                <p className="text-[13px]" style={{ color: 'var(--m-muted)' }}>{o.label}</p>
                            </button>
                        );
                    })}
                </div>
            </Sheet>

            <Sheet open={sheet === 'reminder'} onClose={() => setSheet(null)} title="Daily reminder">
                <p className="px-2 pb-3 text-[14px]" style={{ color: 'var(--m-muted)' }}>A gentle nudge once a day keeps your streak alive.</p>
                <div className="grid grid-cols-3 gap-2">
                    {TIMES.map((t) => {
                        const on = remOn && (settings.reminderTime || '19:00') === t;
                        return (
                            <button key={t} onClick={() => { tap(); setReminder(true, t); setSheet(null); }}
                                className="m-pressable flex h-12 items-center justify-center gap-1 rounded-2xl text-[14px] font-bold"
                                style={{ background: on ? 'var(--m-accent)' : 'var(--m-soft)', color: on ? 'var(--m-on-accent)' : 'var(--m-text)' }}>
                                {on && <Check className="h-4 w-4" />}{fmtTime(t)}
                            </button>
                        );
                    })}
                </div>
                {remOn && (
                    <button onClick={() => { tap(); setReminder(false); setSheet(null); }} className="m-pressable mt-4 h-12 w-full rounded-2xl text-[15px] font-bold" style={{ background: 'var(--m-soft)' }}>
                        Turn reminders off
                    </button>
                )}
            </Sheet>

            <Sheet open={sheet === 'signout'} onClose={() => setSheet(null)} title="Sign out?">
                <p className="px-2 text-[14px]" style={{ color: 'var(--m-muted)' }}>Your books and progress stay safe in your account.</p>
                <div className="mt-5 grid grid-cols-2 gap-3">
                    <button onClick={() => setSheet(null)} className="m-pressable h-12 rounded-2xl text-[15px] font-bold" style={{ background: 'var(--m-soft)' }}>Cancel</button>
                    <button onClick={async () => { tap('medium'); await logout(); navigate('/signin', { replace: true }); }}
                        className="m-pressable h-12 rounded-2xl text-[15px] font-bold text-white" style={{ background: 'var(--m-accent)' }}>Sign out</button>
                </div>
            </Sheet>

            <Sheet open={sheet === 'delete'} onClose={() => !busy && setSheet(null)} title="Delete your account?">
                <p className="px-2 text-[14px] leading-relaxed" style={{ color: 'var(--m-muted)' }}>
                    This permanently deletes your account, every book you uploaded, and all your notes, cards, quizzes and progress. It can't be undone.
                </p>
                <p className="mt-4 px-2 text-[13px] font-semibold">Type DELETE to confirm</p>
                <input value={confirmText} onChange={(e) => setConfirmText(e.target.value)} autoCapitalize="characters"
                    className="mt-2 h-12 w-full rounded-2xl px-4 text-[15px] font-bold tracking-widest outline-none" style={{ background: 'var(--m-soft)', color: 'var(--m-text)' }} />
                <button disabled={confirmText.trim().toUpperCase() !== 'DELETE' || busy} onClick={removeAccount}
                    className="m-pressable mt-4 flex h-12 w-full items-center justify-center gap-2 rounded-2xl bg-red-500 text-[15px] font-bold text-white disabled:opacity-40">
                    {busy ? <Loader2 className="h-5 w-5 animate-spin" /> : <Trash2 className="h-5 w-5" />} Delete forever
                </button>
            </Sheet>
        </Screen>
    );
};

export default Me;
