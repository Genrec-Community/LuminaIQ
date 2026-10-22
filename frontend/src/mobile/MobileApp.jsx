import React, { lazy, Suspense, useEffect, useState } from 'react';
import { Routes, Route, Navigate, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useSettings } from '../context/SettingsContext';
import Onboarding, { onboardedKey } from '../components/Onboarding';
import { isNativeApp } from '../utils/platform';
import { TabBar } from './ui';
import AddSheet from './AddSheet';
import { hideSplash, setStatusBar, scheduleStudyReminder, reminderScheduled } from './device';
import Welcome, { WELCOMED_KEY } from './screens/Welcome';
import SignIn from './screens/SignIn';
import Home from './screens/Home';
import Feed from './screens/Feed';
import Library from './screens/Library';
import Me from './screens/Me';
import Book from './screens/Book';
import './mobile.css';

// Full study tools and secondary pages are shared with the website
const ProjectView = lazy(() => import('../pages/ProjectView'));
const Settings = lazy(() => import('../pages/Settings'));
const BookStore = lazy(() => import('../pages/BookStore'));
const JoinClass = lazy(() => import('../pages/JoinClass'));
const Institution = lazy(() => import('../pages/Institution'));
const Privacy = lazy(() => import('../pages/Legal').then((m) => ({ default: m.Privacy })));
const Terms = lazy(() => import('../pages/Legal').then((m) => ({ default: m.Terms })));

const Loader = () => (
    <div className="m-app flex min-h-[100dvh] items-center justify-center">
        <div className="h-12 w-12 animate-pulse rounded-2xl" style={{ background: 'var(--m-accent)' }} />
    </div>
);

const welcomed = () => { try { return localStorage.getItem(WELCOMED_KEY) === '1'; } catch { return false; } };

/** Signed-in area; first time in, the student sets up their profile and study buddy. */
const Guard = () => {
    const { user } = useAuth();
    const { settings, loaded } = useSettings();
    const location = useLocation();
    if (!user) return <Navigate to="/signin" replace state={{ from: location.pathname }} />;
    let onboarded = settings.onboardingComplete;
    try { onboarded = onboarded || localStorage.getItem(onboardedKey(user.id)) === '1'; } catch { /* ignore */ }
    return (
        <>
            <Outlet />
            {loaded && !onboarded && <Onboarding fullScreen />}
        </>
    );
};

/** The four main tabs share the tab bar and the "+" sheet. */
const Tabs = () => {
    const { pathname } = useLocation();
    const [adding, setAdding] = useState(false);
    useEffect(() => {
        const open = () => setAdding(true);
        window.addEventListener('lumina-add', open);
        return () => window.removeEventListener('lumina-add', open);
    }, []);
    return (
        <div className="m-app">
            <Outlet />
            <TabBar onAdd={() => setAdding(true)} overlay={pathname.startsWith('/app/feed')} />
            <AddSheet open={adding} onClose={() => setAdding(false)} />
        </div>
    );
};

const Public = ({ children }) => {
    const { user } = useAuth();
    return user ? <Navigate to="/app/home" replace /> : children;
};

const Wrap = ({ children }) => <div className="m-app">{children}</div>;

const MobileApp = () => {
    const { user } = useAuth();
    const { settings } = useSettings();
    const navigate = useNavigate();

    useEffect(() => { hideSplash(); }, []);
    useEffect(() => { setStatusBar(!!settings.darkMode, settings.darkMode ? '#1c1814' : '#FDF6F0'); }, [settings.darkMode]);

    // Keep the daily reminder scheduled (it only asks permission when turned on in "You")
    useEffect(() => {
        if (user && settings.studyReminders && reminderScheduled()) {
            scheduleStudyReminder(true, settings.reminderTime || '19:00');
        }
    }, [user, settings.studyReminders, settings.reminderTime]);

    // Navigation requests from outside React (the Android back button)
    useEffect(() => {
        const go = (e) => navigate(e.detail, { replace: true });
        window.addEventListener('lumina-navigate', go);
        return () => window.removeEventListener('lumina-navigate', go);
    }, [navigate]);

    // Tapping a reminder opens the feed
    useEffect(() => {
        if (!isNativeApp()) return undefined;
        let handle;
        import('@capacitor/local-notifications').then(({ LocalNotifications }) => {
            LocalNotifications.addListener('localNotificationActionPerformed', (e) => {
                const route = e?.notification?.extra?.route;
                if (route) navigate(route);
            }).then((h) => { handle = h; });
        }).catch(() => {});
        return () => { handle?.remove?.(); };
    }, [navigate]);

    return (
        <Suspense fallback={<Loader />}>
            <Routes>
                <Route path="/" element={<Navigate to={user ? '/app/home' : welcomed() ? '/signin' : '/welcome'} replace />} />
                <Route path="/welcome" element={<Public><Welcome /></Public>} />
                <Route path="/signin" element={<Public><SignIn /></Public>} />
                <Route path="/login" element={<Navigate to="/signin" replace />} />
                <Route path="/dashboard" element={<Navigate to="/app/home" replace />} />
                <Route path="/pricing" element={<Navigate to="/app/me" replace />} />
                <Route path="/privacy" element={<Privacy />} />
                <Route path="/terms" element={<Terms />} />

                <Route element={<Guard />}>
                    <Route element={<Tabs />}>
                        <Route path="/app/home" element={<Home />} />
                        <Route path="/app/feed" element={<Feed />} />
                        <Route path="/app/library" element={<Library />} />
                        <Route path="/app/me" element={<Me />} />
                    </Route>
                    <Route path="/app/book/:bookId" element={<Wrap><Book /></Wrap>} />
                    <Route path="/project/:projectId" element={<ProjectView />} />
                    <Route path="/settings" element={<Settings />} />
                    <Route path="/bookstore" element={<BookStore />} />
                    <Route path="/institution" element={<Institution />} />
                    <Route path="/join/:code" element={<JoinClass />} />
                </Route>
                <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
        </Suspense>
    );
};

export default MobileApp;
