import React, { useEffect, useState } from 'react';
import {
    Moon, Zap, Target, MessageSquare, FlaskConical, Network, HelpCircle, CheckSquare,
    FileText, Layers, Brain, ChevronDown, Pin, PinOff, Eye, EyeOff, SlidersHorizontal, Check, RotateCcw,
} from 'lucide-react';

/*
 * Project sidebar navigation: grouped sections, one consistent row style, and
 * a Customize mode (pin favourites to the top, hide tools you don't use,
 * compact or comfortable spacing, collapsible sections). Preferences are
 * remembered per browser.
 */

const PREFS_KEY = 'lumina_nav_prefs';
const DEFAULT_PREFS = { pinned: [], hidden: [], density: 'comfortable', closed: [] };

const groupsFor = (aiLabel) => [
    {
        key: 'learn', label: 'Learn', items: [
            { id: 'cram', icon: Moon, label: 'Exam Tonight' },
            { id: 'power', icon: Zap, label: 'Power Hour' },
            { id: 'path', icon: Target, label: 'Learning Path' },
        ],
    },
    {
        key: 'explore', label: 'Explore', items: [
            { id: 'chat', icon: MessageSquare, label: `Chat with ${aiLabel}` },
            { id: 'lab', icon: FlaskConical, label: 'Visual Lab' },
            { id: 'knowledge', icon: Network, label: 'Knowledge Graph' },
        ],
    },
    {
        key: 'practice', label: 'Practice', tourId: 'tour-nav-general', items: [
            { id: 'qa', icon: HelpCircle, label: 'Q&A' },
            { id: 'quiz', icon: CheckSquare, label: 'Answer Quiz' },
            { id: 'notes', icon: FileText, label: 'Notes' },
            { id: 'flashcards', icon: Layers, label: 'Flashcards' },
            { id: 'mindmap', icon: Brain, label: 'Mindmap' },
        ],
    },
];

const loadPrefs = () => {
    try { return { ...DEFAULT_PREFS, ...JSON.parse(localStorage.getItem(PREFS_KEY) || '{}') }; } catch { return DEFAULT_PREFS; }
};

const SidebarNav = ({ activeTab, onSelect, collapsed, isDark, aiLabel }) => {
    const [prefs, setPrefs] = useState(loadPrefs);
    const [editing, setEditing] = useState(false);

    useEffect(() => {
        try { localStorage.setItem(PREFS_KEY, JSON.stringify(prefs)); } catch { /* storage unavailable */ }
    }, [prefs]);

    const toggleIn = (field, value) => setPrefs(p => ({
        ...p, [field]: p[field].includes(value) ? p[field].filter(v => v !== value) : [...p[field], value],
    }));

    const groups = groupsFor(aiLabel);
    const all = groups.flatMap(g => g.items);
    const pinned = prefs.pinned.map(id => all.find(i => i.id === id)).filter(Boolean);
    const visible = (item) => editing || !prefs.hidden.includes(item.id);
    const compact = prefs.density === 'compact';

    // Theme tokens
    const c = isDark ? {
        label: 'text-[#8a6a4c]', text: 'text-[#c4a882]', hover: 'hover:bg-[#2e2318]/80 hover:text-[#e8c898]',
        active: 'bg-gradient-to-r from-[#C8A288] to-[#a8824a] text-white shadow-md shadow-[#C8A288]/25',
        rule: 'border-[#3a2a18]', chip: 'bg-[#2e2318] text-[#c4a882]', chipOn: 'bg-[#C8A288] text-white',
        icon: 'text-[#8a6a4c] hover:text-[#e8c898] hover:bg-[#2e2318]',
    } : {
        label: 'text-[#a99080]', text: 'text-[#5a4a42]', hover: 'hover:bg-[#E6D5CC]/60 hover:text-[#4A3B32]',
        active: 'bg-[#C8A288] text-white shadow-md shadow-[#C8A288]/20',
        rule: 'border-[#E6D5CC]/70', chip: 'bg-white/70 text-[#8a6a5c]', chipOn: 'bg-[#C8A288] text-white',
        icon: 'text-[#b8a094] hover:text-[#4A3B32] hover:bg-[#E6D5CC]/60',
    };

    const Row = ({ item }) => {
        const Icon = item.icon;
        const isActive = activeTab === item.id;
        const isHidden = prefs.hidden.includes(item.id);
        const isPinned = prefs.pinned.includes(item.id);
        return (
            <div className={`group/row relative flex items-center ${isHidden ? 'opacity-45' : ''}`}>
                <button
                    id={`tour-nav-${item.id}`}
                    onClick={() => onSelect(item.id)}
                    title={collapsed ? item.label : undefined}
                    aria-current={isActive ? 'page' : undefined}
                    className={`flex flex-1 min-w-0 items-center rounded-xl transition-colors duration-150 ${collapsed
                        ? `justify-center ${compact ? 'h-10' : 'h-11'}`
                        : `gap-3 ${compact ? 'h-9 px-3 text-[13px]' : 'h-11 px-3.5 text-[15px]'}`
                    } ${isActive ? `${c.active} font-semibold` : `${c.text} ${c.hover} font-medium`}`}
                >
                    <Icon className={`${compact ? 'h-[18px] w-[18px]' : 'h-5 w-5'} shrink-0`} strokeWidth={isActive ? 2.25 : 1.9} />
                    {!collapsed && <span className="truncate">{item.label}</span>}
                </button>
                {editing && !collapsed && (
                    <div className="ml-1 flex shrink-0 items-center">
                        <button
                            onClick={() => toggleIn('pinned', item.id)}
                            className={`rounded-lg p-1.5 transition-colors ${isPinned ? 'text-[#C8A288]' : c.icon}`}
                            title={isPinned ? 'Unpin' : 'Pin to top'}
                            aria-label={isPinned ? `Unpin ${item.label}` : `Pin ${item.label}`}
                        >
                            {isPinned ? <PinOff className="h-4 w-4" /> : <Pin className="h-4 w-4" />}
                        </button>
                        <button
                            onClick={() => toggleIn('hidden', item.id)}
                            className={`rounded-lg p-1.5 transition-colors ${c.icon}`}
                            title={isHidden ? 'Show' : 'Hide'}
                            aria-label={isHidden ? `Show ${item.label}` : `Hide ${item.label}`}
                        >
                            {isHidden ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                        </button>
                    </div>
                )}
            </div>
        );
    };

    const Section = ({ id, label, items, tourId, collapsible = true }) => {
        const shown = items.filter(visible);
        if (!shown.length) return null;
        const closed = collapsible && prefs.closed.includes(id) && !editing;
        if (collapsed) {
            return (
                <div id={tourId} className={`space-y-1 border-t pt-2 first:border-t-0 first:pt-0 ${c.rule}`}>
                    {shown.map(item => <Row key={item.id} item={item} />)}
                </div>
            );
        }
        return (
            <div id={tourId}>
                <button
                    onClick={() => collapsible && toggleIn('closed', id)}
                    className={`mb-1 flex w-full items-center justify-between rounded-md px-3.5 py-1 text-[11px] font-semibold uppercase tracking-[0.08em] ${c.label} ${collapsible ? 'cursor-pointer hover:opacity-80' : 'cursor-default'}`}
                    aria-expanded={!closed}
                >
                    {label}
                    {collapsible && <ChevronDown className={`h-3.5 w-3.5 transition-transform duration-200 ${closed ? '-rotate-90' : ''}`} />}
                </button>
                {!closed && <div className={compact ? 'space-y-0.5' : 'space-y-1'}>{shown.map(item => <Row key={item.id} item={item} />)}</div>}
            </div>
        );
    };

    return (
        <div className="flex min-h-0 flex-1 flex-col">
            <nav className={`custom-scrollbar min-h-0 flex-1 overflow-y-auto ${collapsed ? 'space-y-2' : compact ? 'space-y-3' : 'space-y-5'}`} aria-label="Study tools">
                {pinned.length > 0 && (
                    <Section id="pinned" label="Pinned" items={pinned} collapsible={false} />
                )}
                {groups.map(g => (
                    <Section key={g.key} id={g.key} label={g.label} tourId={g.tourId}
                        items={g.items.filter(i => !prefs.pinned.includes(i.id))} />
                ))}
            </nav>

            {!collapsed && (
                <div className={`mt-3 shrink-0 border-t pt-3 ${c.rule}`}>
                    {editing ? (
                        <div className="space-y-2.5">
                            <div className="flex items-center justify-between px-1">
                                <span className={`text-[11px] font-semibold uppercase tracking-[0.08em] ${c.label}`}>Spacing</span>
                                <div className={`flex rounded-lg p-0.5 ${c.chip}`}>
                                    {['comfortable', 'compact'].map(d => (
                                        <button key={d} onClick={() => setPrefs(p => ({ ...p, density: d }))}
                                            className={`rounded-md px-2.5 py-1 text-[11px] font-semibold capitalize transition-colors ${prefs.density === d ? c.chipOn : ''}`}>
                                            {d}
                                        </button>
                                    ))}
                                </div>
                            </div>
                            <div className="flex items-center gap-2">
                                <button onClick={() => setPrefs(DEFAULT_PREFS)}
                                    className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-semibold ${c.icon}`}>
                                    <RotateCcw className="h-3.5 w-3.5" /> Reset
                                </button>
                                <button onClick={() => setEditing(false)}
                                    className="ml-auto flex items-center gap-1.5 rounded-lg bg-[#C8A288] px-3 py-1.5 text-xs font-semibold text-white hover:bg-[#B08B72]">
                                    <Check className="h-3.5 w-3.5" /> Done
                                </button>
                            </div>
                        </div>
                    ) : (
                        <button onClick={() => setEditing(true)}
                            className={`flex w-full items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${c.icon}`}>
                            <SlidersHorizontal className="h-3.5 w-3.5" /> Customize sidebar
                        </button>
                    )}
                </div>
            )}
        </div>
    );
};

export default SidebarNav;
