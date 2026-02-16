/**
 * Study Activity Tracker
 * 
 * Tracks real user study activity per day via the backend API.
 * Used by AdvancedAnalytics heatmap and trend calculations.
 * 
 * The data shape remains the same:
 *   {
 *     "2026-02-10": { quiz: 2, review: 5, notes: 1, qa: 1, pomodoro: 3, chat: 0, quizScores: [80, 65], total: 12 },
 *     "2026-02-09": { ... }
 *   }
 */

import { recordStudyActivity, getStudyActivity } from '../api';

/**
 * Get today's date as YYYY-MM-DD string
 */
const getToday = () => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};

/**
 * Get date string for N days ago
 */
const getDaysAgo = (n) => {
    const d = new Date();
    d.setDate(d.getDate() - n);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};

/**
 * Get the day-of-week name for a YYYY-MM-DD string
 */
const getDayName = (dateStr) => {
    const d = new Date(dateStr + 'T00:00:00');
    return d.toLocaleDateString('en-US', { weekday: 'short' });
};

// ============================
// Public API
// ============================

/**
 * Record a study activity event (fire-and-forget to backend).
 * @param {string} projectId
 * @param {'quiz'|'review'|'notes'|'qa'|'pomodoro'|'chat'} activityType
 * @param {object} [meta] - Optional metadata, e.g. { score: 80 } for quiz
 */
export const recordActivity = (projectId, activityType, meta = {}) => {
    if (!projectId) return;

    // Fire-and-forget — callers never await this
    recordStudyActivity(projectId, activityType, meta).catch(err =>
        console.warn('Failed to record study activity:', err)
    );
};

/**
 * Fetch activity data from the API.
 * @param {string} projectId
 * @param {number} days
 * @returns {Promise<object>} - Activity keyed by date string
 */
export const fetchActivity = async (projectId, days = 90) => {
    try {
        const data = await getStudyActivity(projectId, days);
        return data.activity || {};
    } catch (err) {
        console.warn('Failed to fetch study activity:', err);
        return {};
    }
};

/**
 * Get the last N days of activity data for the heatmap.
 * Accepts pre-fetched data (from fetchActivity) to avoid repeated API calls.
 * 
 * @param {object} data - Activity data keyed by date string (from fetchActivity)
 * @param {number} days - Number of days to look back (default 7)
 * @returns {Array}
 */
export const getActivityHeatmap = (data, days = 7) => {
    const result = [];

    for (let i = days - 1; i >= 0; i--) {
        const dateStr = getDaysAgo(i);
        const dayData = data[dateStr] || { quiz: 0, review: 0, notes: 0, qa: 0, pomodoro: 0, chat: 0, total: 0 };

        result.push({
            date: dateStr,
            dayName: getDayName(dateStr),
            ...dayData,
            total: dayData.total || 0,
        });
    }

    return result;
};

/**
 * Compute the accuracy trend: average quiz score this period vs previous period.
 * 
 * @param {object} data - Activity data keyed by date string (from fetchActivity)
 * @param {number} periodDays
 * @returns {number|null}
 */
export const getAccuracyTrend = (data, periodDays = 7) => {
    const collectScores = (startDaysAgo, endDaysAgo) => {
        const scores = [];
        for (let i = startDaysAgo; i >= endDaysAgo; i--) {
            const dateStr = getDaysAgo(i);
            const day = data[dateStr];
            if (day && Array.isArray(day.quizScores)) {
                scores.push(...day.quizScores);
            }
        }
        return scores;
    };

    const currentScores = collectScores(periodDays - 1, 0);
    const previousScores = collectScores(periodDays * 2 - 1, periodDays);

    if (currentScores.length === 0 || previousScores.length === 0) {
        return null;
    }

    const currentAvg = currentScores.reduce((s, v) => s + v, 0) / currentScores.length;
    const previousAvg = previousScores.reduce((s, v) => s + v, 0) / previousScores.length;

    return Math.round(currentAvg - previousAvg);
};

/**
 * Get total activity count for a specific day.
 * @param {object} data
 * @param {string} dateStr
 * @returns {number}
 */
export const getDayActivity = (data, dateStr) => {
    return data[dateStr]?.total || 0;
};

/**
 * Get total activity count for the last N days.
 * @param {object} data
 * @param {number} days
 * @returns {number}
 */
export const getTotalActivity = (data, days = 7) => {
    const heatmap = getActivityHeatmap(data, days);
    return heatmap.reduce((sum, day) => sum + day.total, 0);
};

/**
 * Compute the maximum daily activity across all stored data (for scaling heatmap intensity).
 * @param {object} data
 * @returns {number}
 */
export const getMaxDailyActivity = (data) => {
    let max = 0;
    for (const day of Object.values(data)) {
        const total = day.total || 0;
        if (total > max) max = total;
    }
    return Math.max(max, 1);
};
