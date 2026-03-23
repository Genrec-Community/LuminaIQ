/**
 * projectCache.js
 * Thin localStorage cache for the projects list.
 * Allows the Dashboard to show stale data instantly while a fresh fetch runs,
 * and to display something useful when the backend is offline/cold-starting.
 */

const CACHE_KEY = 'lumina_projects_cache';
const CACHE_TS_KEY = 'lumina_projects_cache_ts';
const DEFAULT_MAX_AGE_MS = 2 * 60 * 1000; // 2 minutes

export const getCachedProjects = () => {
    try {
        const raw = localStorage.getItem(CACHE_KEY);
        return raw ? JSON.parse(raw) : null;
    } catch {
        return null;
    }
};

export const setCachedProjects = (projects) => {
    try {
        localStorage.setItem(CACHE_KEY, JSON.stringify(projects));
        localStorage.setItem(CACHE_TS_KEY, String(Date.now()));
    } catch {
        // Storage quota exceeded — silently skip
    }
};

export const clearProjectsCache = () => {
    localStorage.removeItem(CACHE_KEY);
    localStorage.removeItem(CACHE_TS_KEY);
};

export const isCacheStale = (maxAgeMs = DEFAULT_MAX_AGE_MS) => {
    const ts = localStorage.getItem(CACHE_TS_KEY);
    if (!ts) return true;
    return Date.now() - Number(ts) > maxAgeMs;
};
