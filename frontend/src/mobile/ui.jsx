import React, { useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useLocation, useNavigate } from 'react-router-dom';
import { Home, Flame, Plus, Library, User, ChevronLeft } from 'lucide-react';
import { tap } from './device';

const TABS = [
    { to: '/app/home', icon: Home, label: 'Home' },
    { to: '/app/feed', icon: Flame, label: 'Learn' },
    { add: true },
    { to: '/app/library', icon: Library, label: 'Books' },
    { to: '/app/me', icon: User, label: 'You' },
];

/** Bottom tab bar with a raised add button in the middle. */
export const TabBar = ({ onAdd, overlay = false }) => {
    const { pathname } = useLocation();
    const navigate = useNavigate();
    return (
        <nav
            className="fixed inset-x-0 bottom-0 z-40 m-safe-bottom"
            style={{
                background: overlay ? 'linear-gradient(to top, rgba(0,0,0,0.55), rgba(0,0,0,0))' : 'color-mix(in srgb, var(--m-surface) 88%, transparent)',
                backdropFilter: overlay ? 'none' : 'blur(18px) saturate(1.4)',
                WebkitBackdropFilter: overlay ? 'none' : 'blur(18px) saturate(1.4)',
                borderTop: overlay ? 'none' : '1px solid var(--m-border)',
            }}
            aria-label="Main"
        >
            <div className="mx-auto flex h-[var(--m-tabbar-h)] max-w-lg items-center justify-around px-2">
                {TABS.map((t) => {
                    if (t.add) {
                        return (
                            <button
                                key="add"
                                onClick={() => { tap('medium'); onAdd?.(); }}
                                aria-label="Add a book"
                                className="m-pressable -mt-6 flex h-14 w-14 items-center justify-center rounded-2xl text-white shadow-lg"
                                style={{ background: 'linear-gradient(135deg, var(--m-accent), var(--m-accent-deep))', boxShadow: '0 10px 24px -8px color-mix(in srgb, var(--m-accent) 70%, transparent)' }}
                            >
                                <Plus className="h-7 w-7" strokeWidth={2.5} />
                            </button>
                        );
                    }
                    const active = pathname.startsWith(t.to);
                    const Icon = t.icon;
                    const color = overlay ? (active ? '#fff' : 'rgba(255,255,255,0.7)') : (active ? 'var(--m-accent)' : 'var(--m-muted)');
                    return (
                        <button
                            key={t.to}
                            onClick={() => { if (!active) { tap(); navigate(t.to); } }}
                            className="m-pressable relative flex w-16 flex-col items-center gap-0.5 py-1"
                            aria-current={active ? 'page' : undefined}
                            style={{ color }}
                        >
                            <Icon className="h-6 w-6" strokeWidth={active ? 2.4 : 1.9} fill={active && t.label === 'Learn' ? 'currentColor' : 'none'} />
                            <span className={`text-[10.5px] ${active ? 'font-bold' : 'font-medium'}`}>{t.label}</span>
                            {active && !overlay && (
                                <motion.span layoutId="m-tab-dot" className="absolute -top-1 h-1 w-6 rounded-full" style={{ background: 'var(--m-accent)' }} />
                            )}
                        </button>
                    );
                })}
            </div>
        </nav>
    );
};

/** Bottom sheet that slides up; swipe down or tap outside to close. */
export const Sheet = ({ open, onClose, title, children }) => {
    useEffect(() => {
        if (!open) return undefined;
        const onBack = (e) => { e.preventDefault?.(); onClose(); };
        window.addEventListener('lumina-back', onBack);
        return () => window.removeEventListener('lumina-back', onBack);
    }, [open, onClose]);
    return (
        <AnimatePresence>
            {open && (
                <>
                    <motion.div
                        className="fixed inset-0 z-[70] bg-black/45"
                        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                        onClick={onClose}
                    />
                    <motion.div
                        role="dialog"
                        aria-modal="true"
                        aria-label={title}
                        className="fixed inset-x-0 bottom-0 z-[71] max-h-[88dvh] overflow-hidden rounded-t-[28px] m-safe-bottom"
                        style={{ background: 'var(--m-surface)', color: 'var(--m-text)' }}
                        initial={{ y: '100%' }} animate={{ y: 0 }} exit={{ y: '100%' }}
                        transition={{ type: 'spring', damping: 32, stiffness: 380 }}
                        drag="y" dragConstraints={{ top: 0, bottom: 0 }} dragElastic={{ top: 0, bottom: 0.6 }}
                        onDragEnd={(_, info) => { if (info.offset.y > 110 || info.velocity.y > 600) onClose(); }}
                    >
                        <div className="flex justify-center pt-3 pb-1"><span className="h-1.5 w-10 rounded-full" style={{ background: 'var(--m-border)' }} /></div>
                        {title && <h3 className="px-6 pb-2 pt-1 text-lg font-extrabold">{title}</h3>}
                        <div className="m-scroll max-h-[calc(88dvh-60px)] px-4 pb-6">{children}</div>
                    </motion.div>
                </>
            )}
        </AnimatePresence>
    );
};

/** Screen title bar: large title, optional back button and right-side actions. */
export const ScreenHeader = ({ title, subtitle, back, right, large = true }) => {
    const navigate = useNavigate();
    return (
        <header className="m-safe-top sticky top-0 z-30" style={{ background: 'color-mix(in srgb, var(--m-bg) 90%, transparent)', backdropFilter: 'blur(14px)', WebkitBackdropFilter: 'blur(14px)' }}>
            <div className="flex min-h-[56px] items-center gap-2 px-4">
                {back && (
                    <button onClick={() => { tap(); typeof back === 'function' ? back() : navigate(-1); }} aria-label="Back"
                        className="m-pressable -ml-2 flex h-10 w-10 items-center justify-center rounded-full" style={{ color: 'var(--m-text)' }}>
                        <ChevronLeft className="h-7 w-7" />
                    </button>
                )}
                <div className="min-w-0 flex-1">
                    <h1 className={`truncate font-extrabold tracking-tight ${large ? 'text-[26px]' : 'text-lg'}`}>{title}</h1>
                    {subtitle && <p className="truncate text-[13px]" style={{ color: 'var(--m-muted)' }}>{subtitle}</p>}
                </div>
                {right}
            </div>
        </header>
    );
};

export const IconButton = ({ icon: Icon, label, onClick, badge }) => (
    <button onClick={() => { tap(); onClick?.(); }} aria-label={label}
        className="m-pressable relative flex h-10 w-10 items-center justify-center rounded-full"
        style={{ background: 'var(--m-soft)', color: 'var(--m-text)' }}>
        <Icon className="h-5 w-5" />
        {badge ? <span className="absolute -right-0.5 -top-0.5 min-w-[18px] rounded-full px-1 text-center text-[10px] font-bold leading-[18px] text-white" style={{ background: '#e5484d' }}>{badge}</span> : null}
    </button>
);

/** Page transition used by every app screen. */
export const Screen = ({ children, className = '', style }) => (
    <motion.div
        className={`min-h-[100dvh] ${className}`}
        style={style}
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.22, ease: [0.2, 0.8, 0.2, 1] }}
    >
        {children}
    </motion.div>
);

/** Circular progress ring. */
export const Ring = ({ value = 0, size = 64, stroke = 7, color = 'var(--m-accent)', track = 'var(--m-soft)', children }) => {
    const r = (size - stroke) / 2;
    const c = 2 * Math.PI * r;
    const v = Math.max(0, Math.min(1, value));
    return (
        <div className="relative shrink-0" style={{ width: size, height: size }}>
            <svg width={size} height={size} className="-rotate-90">
                <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={track} strokeWidth={stroke} />
                <motion.circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={stroke} strokeLinecap="round"
                    strokeDasharray={c} initial={{ strokeDashoffset: c }} animate={{ strokeDashoffset: c * (1 - v) }} transition={{ duration: 0.9, ease: 'easeOut' }} />
            </svg>
            <div className="absolute inset-0 flex items-center justify-center">{children}</div>
        </div>
    );
};
