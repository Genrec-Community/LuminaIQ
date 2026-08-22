/**
 * projectCache.js
 * Thin localStorage cache for the projects list.
 * Allows the Dashboard to show stale data instantly while a fresh fetch runs,
 * and to display something useful when the backend is offline/cold-starting.
 */

const DEFAULT_MAX_AGE_MS = 2 * 60 * 1000; // 2 minutes
const cacheKey = (userId) => `lumina_projects_cache_${userId}`;
const cacheTimestampKey = (userId) => `lumina_projects_cache_ts_${userId}`;

export const getCachedProjects = (userId) => {
    if (!userId) return null;
    try {
        const raw = localStorage.getItem(cacheKey(userId));
        return raw ? JSON.parse(raw) : null;
    } catch {
        return null;
    }
};

export const setCachedProjects = (userId, projects) => {
    if (!userId) return;
    try {
        localStorage.setItem(cacheKey(userId), JSON.stringify(projects));
        localStorage.setItem(cacheTimestampKey(userId), String(Date.now()));
    } catch {
        // Storage quota exceeded — silently skip
    }
};

export const clearProjectsCache = (userId) => {
    if (!userId) return;
    localStorage.removeItem(cacheKey(userId));
    localStorage.removeItem(cacheTimestampKey(userId));
};

export const isCacheStale = (userId, maxAgeMs = DEFAULT_MAX_AGE_MS) => {
    if (!userId) return true;
    const ts = localStorage.getItem(cacheTimestampKey(userId));
    if (!ts) return true;
    return Date.now() - Number(ts) > maxAgeMs;
};
