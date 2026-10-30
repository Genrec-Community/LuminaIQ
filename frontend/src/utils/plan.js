// Plan limit signalling shared by the API layer and the UI.
export const LIMIT_EVENT = 'lumina:limit';
export const PLAN_EVENT = 'lumina:plan-changed';

export const isLimitDetail = (detail) => detail && typeof detail === 'object' && detail.code === 'limit_reached';

export const isLimitError = (err) => err?.response?.status === 402 && isLimitDetail(err.response?.data?.detail);

/** Ask the app to show the "limit reached" prompt. */
export const emitLimit = (detail) => window.dispatchEvent(new CustomEvent(LIMIT_EVENT, { detail }));

/** Tell plan-aware UI to reload (after a purchase, a pass, joining an institution...). */
export const emitPlanChanged = () => window.dispatchEvent(new CustomEvent(PLAN_EVENT));

// Limits reset on the plan's day boundary (India time), whatever the device timezone is
const PLAN_TZ = 'Asia/Kolkata';
const dayKey = (d) => d.toLocaleDateString('en-CA', { timeZone: PLAN_TZ });

export const formatReset = (iso) => {
    if (!iso) return '';
    const d = new Date(iso);
    const tomorrow = new Date(Date.now() + 86400000);
    if (dayKey(d) === dayKey(tomorrow)) return 'Resets at midnight';
    return `Resets ${d.toLocaleDateString([], { day: 'numeric', month: 'short', timeZone: PLAN_TZ })}`;
};
