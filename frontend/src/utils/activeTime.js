/**
 * Active study time, measured in real seconds.
 *
 * A moment counts only when all of these hold:
 *  - the page is visible (tab in front, Android app in the foreground)
 *  - the window has focus (not behind another app or window)
 *  - the learner did something in the last IDLE_MS (moved the mouse,
 *    scrolled, typed, tapped, answered a question)
 *
 * Time is measured from timestamps, not by counting ticks, and a single step
 * is capped, so a throttled or suspended page never credits the gap.
 */
import { isNativeApp } from './platform';

export const IDLE_MS = 60 * 1000;
const TICK_MS = 1000;
const MAX_STEP_MS = 2500;

// Only events a person causes: a plain 'scroll' also fires when the app scrolls
// itself (a streaming answer), so wheel, touch and keys stand in for it.
const ACTIVITY_EVENTS = ['pointerdown', 'pointermove', 'keydown', 'wheel', 'touchstart', 'touchmove', 'input'];

let lastActivity = Date.now();
let visible = true;
let listening = false;
let timer = null;
let lastTick = 0;
let wasActive = false;
const sinks = new Set();

export const markActive = () => { lastActivity = Date.now(); };

const onVisibility = () => {
    visible = document.visibilityState === 'visible';
    if (visible) markActive();
    else flushAll();
};

const flushAll = () => sinks.forEach((s) => s.flush?.());

const listen = () => {
    if (listening || typeof window === 'undefined') return;
    listening = true;
    visible = document.visibilityState === 'visible';
    const opts = { passive: true, capture: true };
    ACTIVITY_EVENTS.forEach((e) => window.addEventListener(e, markActive, opts));
    document.addEventListener('visibilitychange', onVisibility);
    window.addEventListener('focus', markActive);
    window.addEventListener('blur', flushAll);
    window.addEventListener('pagehide', flushAll);
    if (isNativeApp()) {
        import('@capacitor/app').then(({ App }) => {
            App.addListener('appStateChange', ({ isActive }) => {
                visible = isActive;
                if (isActive) markActive();
                else flushAll();
            });
        }).catch(() => { /* web build without the plugin */ });
    }
};

// hasFocus() stays true while focus is inside one of our own frames (Visual Lab).
// The Android WebView does not always report focus; there the app being in the
// foreground (visible) is the focus signal.
const hasFocus = () => {
    if (isNativeApp()) return true;
    try { return document.hasFocus(); } catch { return true; }
};

/** True when this very moment counts as active study. */
export const isActive = (now = Date.now()) => {
    listen();
    if (!visible || !hasFocus()) return false;
    return now - lastActivity < IDLE_MS;
};

// A step counts only when the learner was active at both of its ends, so the
// first tick after coming back never credits the time spent away.
const tick = () => {
    const now = Date.now();
    const step = Math.min(now - lastTick, MAX_STEP_MS);
    const active = isActive(now);
    if (step > 0 && active && wasActive) sinks.forEach((s) => s.add(step));
    lastTick = now;
    wasActive = active;
};

/**
 * Receive active milliseconds as they accrue. The sink is
 * { add(ms), flush?() }; flush is called when the page hides or loses focus.
 * Returns an unsubscribe function.
 */
export const onActiveTime = (sink) => {
    listen();
    sinks.add(sink);
    if (!timer) {
        lastTick = Date.now();
        wasActive = isActive(lastTick);
        timer = setInterval(tick, TICK_MS);
    }
    return () => {
        sink.flush?.();
        sinks.delete(sink);
        if (!sinks.size && timer) { clearInterval(timer); timer = null; }
    };
};

/** Test hook: reset module state between cases. */
export const __resetActiveTime = () => {
    sinks.clear();
    if (timer) clearInterval(timer);
    timer = null;
    wasActive = false;
    lastActivity = Date.now();
};
