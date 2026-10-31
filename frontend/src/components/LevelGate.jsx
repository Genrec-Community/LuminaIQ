import { useState } from 'react';
import { useTools } from '../context/ToolsContext';
import LevelPicker from './LevelPicker';

/**
 * One question for anyone who hasn't told us their level yet (e.g. accounts made
 * before levels existed). Answers, tools and difficulty all depend on it.
 */
const LevelGate = () => {
    const { chooseLevel } = useTools();
    const [level, setLevel] = useState('');
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');

    const save = async () => {
        setSaving(true);
        setError('');
        try {
            await chooseLevel(level);
        } catch {
            setError("Couldn't save that. Please try again.");
            setSaving(false);
        }
    };

    return (
        <div className="fixed inset-0 z-[9998] flex items-center justify-center bg-[#182B22]/50 backdrop-blur-md p-3"
            role="dialog" aria-modal="true" aria-labelledby="level-gate-title">
            <div className="w-full max-w-xl max-h-[calc(100dvh-1.5rem)] overflow-y-auto rounded-3xl bg-white p-5 sm:p-6 shadow-2xl">
                <h2 id="level-gate-title" className="text-xl sm:text-2xl font-bold text-[#163628]">What are you studying? 📚</h2>
                <p className="mt-1 mb-5 text-[#5E5046]">
                    So your answers, tools and quizzes are just right for you. You can change it later in Settings.
                </p>
                <LevelPicker value={level} onChange={setLevel} disabled={saving} />
                {error && <p className="mt-3 text-sm text-red-700" role="alert">{error}</p>}
                <button
                    type="button"
                    onClick={save}
                    disabled={!level || saving}
                    className="mt-5 w-full rounded-2xl bg-[#1E5C42] py-3.5 text-lg font-bold text-white transition-colors hover:bg-[#163628] disabled:opacity-50"
                >
                    {saving ? 'Saving…' : 'Continue'}
                </button>
            </div>
        </div>
    );
};

export default LevelGate;
