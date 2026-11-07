/**
 * A list of tools with on/off switches. Used by the platform admin (per level)
 * and by school admins (per class, where only platform-allowed tools appear).
 */
const Switch = ({ on, onChange, label, disabled }) => (
    <button
        type="button"
        role="switch"
        aria-checked={on}
        aria-label={label}
        disabled={disabled}
        onClick={() => onChange(!on)}
        className={`relative h-6 w-11 shrink-0 rounded-full transition-colors disabled:opacity-50 ${on ? 'bg-[#1E5C42]' : 'bg-[#D9CBC1]'}`}
    >
        <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all ${on ? 'left-[22px]' : 'left-0.5'}`} />
    </button>
);

export const SettingRow = ({ title, description, on, onChange, disabled }) => (
    <div className="flex items-center justify-between gap-4 rounded-2xl border border-[#E6D5CC] bg-white px-4 py-3">
        <div>
            <p className="text-sm font-semibold text-[#163628]">{title}</p>
            {description && <p className="text-xs text-[#5E5046]">{description}</p>}
        </div>
        <Switch on={on} onChange={onChange} label={title} disabled={disabled} />
    </div>
);

const ToolToggles = ({ tools, enabled, onChange, disabled = false, columns = 2 }) => (
    <ul className={`grid gap-2 ${columns === 2 ? 'sm:grid-cols-2' : ''}`}>
        {tools.map((t) => (
            <li key={t.key} className="flex items-center justify-between gap-3 rounded-2xl border border-[#E6D5CC] bg-white px-4 py-3">
                <span className="text-sm font-medium text-[#163628]">{t.label}</span>
                <Switch on={enabled.includes(t.key)} disabled={disabled} label={t.label}
                    onChange={(on) => onChange(on ? [...enabled, t.key] : enabled.filter((k) => k !== t.key))} />
            </li>
        ))}
    </ul>
);

export default ToolToggles;
