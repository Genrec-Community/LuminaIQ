/**
 * Choose what you're studying: Class 5-10, 11-12, UG/PG, PhD or general.
 * Big, friendly cards so a Class 6 child can pick confidently.
 */
export const LEVEL_OPTIONS = [
    { key: 'school', emoji: '🎒', label: 'Class 5–10', hint: 'School student' },
    { key: 'higher_secondary', emoji: '📐', label: 'Class 11–12', hint: 'Boards, JEE, NEET, CUET' },
    { key: 'ugpg', emoji: '🎓', label: 'UG / PG', hint: 'College or university' },
    { key: 'research', emoji: '🔬', label: 'PhD / Research', hint: 'Research and papers' },
    { key: 'general', emoji: '🌱', label: 'General learner', hint: 'Learning for myself' },
];

const LevelPicker = ({ value, onChange, disabled = false }) => (
    <div role="radiogroup" aria-label="What are you studying?" className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
        {LEVEL_OPTIONS.map((o) => {
            const active = value === o.key;
            return (
                <button
                    key={o.key}
                    type="button"
                    role="radio"
                    aria-checked={active}
                    disabled={disabled}
                    onClick={() => onChange(o.key)}
                    className={`flex items-center gap-3 rounded-2xl border-2 p-3.5 text-left transition-all active:scale-[0.98] disabled:opacity-60 ${active
                        ? 'border-[#1E5C42] bg-[#1E5C42]/10 shadow-md shadow-[#1E5C42]/20'
                        : 'border-[#E6D5CC] bg-white hover:border-[#1E5C42]/60'}`}
                >
                    <span className="text-3xl leading-none" aria-hidden="true">{o.emoji}</span>
                    <span>
                        <span className="block font-bold text-[#163628]">{o.label}</span>
                        <span className="block text-xs text-[#5E5046]">{o.hint}</span>
                    </span>
                </button>
            );
        })}
    </div>
);

export default LevelPicker;
