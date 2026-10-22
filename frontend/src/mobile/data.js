import { useCallback, useEffect, useState } from 'react';
import { getProjects } from '../api';
import { getCachedProjects, setCachedProjects } from '../utils/projectCache';

/** The student's books (projects), shown from cache at once and refreshed in the background. */
export const useBooks = () => {
    const [books, setBooks] = useState(() => getCachedProjects() || []);
    const [loading, setLoading] = useState(!(getCachedProjects() || []).length);
    const [error, setError] = useState(false);

    const refresh = useCallback(async () => {
        setError(false);
        try {
            const data = await getProjects();
            setBooks(data || []);
            setCachedProjects(data || []);
        } catch {
            setError(true);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { refresh(); }, [refresh]);
    return { books, loading, error, refresh, setBooks };
};

// A warm, stable colour per book so covers are recognisable at a glance
const COVERS = [
    ['#C8A288', '#8f6a52'], ['#e07a5f', '#a3452f'], ['#7c6fd6', '#4b3fa3'], ['#2f9e7a', '#1c6b52'],
    ['#3b8fd6', '#245f96'], ['#e46a91', '#a83a60'], ['#d9a441', '#9c7117'], ['#5c7c8a', '#36505c'],
];
export const coverFor = (id = '') => {
    let h = 0;
    for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) >>> 0;
    return COVERS[h % COVERS.length];
};

const EMOJI = [
    [/bio|cell|gene|life|plant/i, '🧬'], [/chem/i, '🧪'], [/phys|quantum|mechanic/i, '⚛️'], [/math|calc|algebra|geometry|stat/i, '📐'],
    [/hist|war|empire/i, '🏛️'], [/econ|financ|market|money|business/i, '📈'], [/law|legal|power/i, '⚖️'], [/code|program|computer|software|python|java/i, '💻'],
    [/med|anatom|health|nurs/i, '🩺'], [/psych|mind|brain/i, '🧠'], [/geo|earth|climate/i, '🌍'], [/art|design|music/i, '🎨'],
    [/value|ethic|philos/i, '🕊️'], [/lang|english|grammar|literat|novel|poem/i, '✍️'],
];
export const emojiFor = (name = '') => (EMOJI.find(([re]) => re.test(name)) || [null, '📘'])[1];

export const timeAgo = (iso) => {
    if (!iso) return '';
    const s = Math.max(1, (Date.now() - new Date(iso).getTime()) / 1000);
    if (s < 3600) return `${Math.round(s / 60)}m ago`;
    if (s < 86400) return `${Math.round(s / 3600)}h ago`;
    if (s < 86400 * 30) return `${Math.round(s / 86400)}d ago`;
    return new Date(iso).toLocaleDateString();
};
