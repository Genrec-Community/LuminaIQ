// Phone features for the app interface: haptics, status bar, splash screen and
// study reminders. Every call is safe on the web (it does nothing there).
import { isNativeApp } from '../utils/platform';

const native = () => isNativeApp();

/** Light tap feedback: 'light' for taps, 'medium' for actions, 'heavy' for big moments. */
export async function tap(style = 'light') {
    if (!native()) {
        try { navigator.vibrate?.(style === 'heavy' ? 18 : 8); } catch { /* not supported */ }
        return;
    }
    try {
        const { Haptics, ImpactStyle } = await import('@capacitor/haptics');
        await Haptics.impact({ style: { light: ImpactStyle.Light, medium: ImpactStyle.Medium, heavy: ImpactStyle.Heavy }[style] || ImpactStyle.Light });
    } catch { /* plugin unavailable */ }
}

/** Success / warning / error buzz (right or wrong answers). */
export async function notify(type = 'success') {
    if (!native()) {
        try { navigator.vibrate?.(type === 'success' ? [10, 40, 10] : 30); } catch { /* not supported */ }
        return;
    }
    try {
        const { Haptics, NotificationType } = await import('@capacitor/haptics');
        await Haptics.notification({ type: { success: NotificationType.Success, warning: NotificationType.Warning, error: NotificationType.Error }[type] });
    } catch { /* plugin unavailable */ }
}

/** Status bar icons and colour to match the screen (dark = light icons). */
export async function setStatusBar(dark, color) {
    if (!native()) return;
    try {
        const { StatusBar, Style } = await import('@capacitor/status-bar');
        await StatusBar.setStyle({ style: dark ? Style.Dark : Style.Light });
        if (color) await StatusBar.setBackgroundColor({ color });
    } catch { /* plugin unavailable */ }
}

export async function hideSplash() {
    if (!native()) return;
    try {
        const { SplashScreen } = await import('@capacitor/splash-screen');
        await SplashScreen.hide({ fadeOutDuration: 250 });
    } catch { /* plugin unavailable */ }
}

const REMINDER_ID = 4101;
const REMINDER_FLAG = 'lumina_reminder_set';

/** True once a reminder has actually been scheduled on this phone. */
export const reminderScheduled = () => {
    try { return localStorage.getItem(REMINDER_FLAG) === '1'; } catch { return false; }
};
const NUDGES = [
    'Your streak is waiting 🔥 A 2-minute feed keeps it alive.',
    'Swipe through 5 cards from your books. That is all it takes today.',
    'Quick one? Your feed has fresh questions ready.',
    'Future you says thanks. 3 minutes of study?',
];

/**
 * Daily study reminder at "HH:MM" (asks for notification permission the first
 * time). Pass enabled=false to cancel it. Returns false when not allowed.
 */
export async function scheduleStudyReminder(enabled, time = '19:00') {
    if (!native()) return false;
    try {
        const { LocalNotifications } = await import('@capacitor/local-notifications');
        await LocalNotifications.cancel({ notifications: [{ id: REMINDER_ID }] });
        if (!enabled) {
            try { localStorage.removeItem(REMINDER_FLAG); } catch { /* ignore */ }
            return true;
        }
        let perm = await LocalNotifications.checkPermissions();
        if (perm.display !== 'granted') perm = await LocalNotifications.requestPermissions();
        if (perm.display !== 'granted') return false;
        const [hour, minute] = (time || '19:00').split(':').map(Number);
        await LocalNotifications.schedule({
            notifications: [{
                id: REMINDER_ID,
                title: 'LuminaIQ',
                body: NUDGES[Math.floor(Math.random() * NUDGES.length)],
                schedule: { on: { hour, minute }, repeats: true, allowWhileIdle: true },
                extra: { route: '/app/feed' },
            }],
        });
        try { localStorage.setItem(REMINDER_FLAG, '1'); } catch { /* ignore */ }
        return true;
    } catch {
        return false;
    }
}
