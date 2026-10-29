import { lazy, Suspense, useEffect, useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { isAppShell } from './utils/platform';
import { AuthProvider } from './context/AuthContext';
import { ToastProvider } from './context/ToastContext';
import { SettingsProvider } from './context/SettingsContext';
import { GamificationProvider } from './context/GamificationContext';
import PrivateRoute from './components/PrivateRoute';
import XPToast from './components/XPToast';
import LimitModal from './components/LimitModal';
import RouteMeta from './components/RouteMeta';
import Feel from './feel/Feel';
import { Mark } from './components/brand/Logo';

// Route-level code splitting: each page loads only when visited
const Login = lazy(() => import('./pages/Login'));
const ResetPassword = lazy(() => import('./pages/ResetPassword'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const ProjectView = lazy(() => import('./pages/ProjectView'));
const Settings = lazy(() => import('./pages/Settings'));
const BookStore = lazy(() => import('./pages/BookStore'));
const Landing = lazy(() => import('./pages/Landing'));
const Pricing = lazy(() => import('./pages/Pricing'));
const Institution = lazy(() => import('./pages/Institution'));
const Platform = lazy(() => import('./pages/Platform'));
const JoinClass = lazy(() => import('./pages/JoinClass'));
const Privacy = lazy(() => import('./pages/Legal').then((m) => ({ default: m.Privacy })));
const DeleteAccount = lazy(() => import('./pages/Legal').then((m) => ({ default: m.DeleteAccount })));
const Terms = lazy(() => import('./pages/Legal').then((m) => ({ default: m.Terms })));
// The phone app has its own interface (bottom tabs, feed, onboarding)
const MobileApp = lazy(() => import('./mobile/MobileApp'));
const NotFound = lazy(() => import('./pages/NotFound'));
const APP_SHELL = isAppShell();

const PageLoader = () => (
    <div className="min-h-screen flex items-center justify-center bg-[#FDF6F0]">
        <Mark className="h-12 w-12 animate-pulse" />
    </div>
);

// Mounts only once the first page's code has loaded: lifts the first-load screen
const Ready = () => {
    useEffect(() => { window.dispatchEvent(new Event('lumina:ready')); }, []);
    return null;
};

// The marketing site (frontend/website, a static Next.js export) owns "/" and its own
// pages; the app is served for everything else. A client-side jump to "/" reloads so the
// server hands over the site. Without the site (local dev) the old landing is the fallback.
const SiteHome = () => {
    const [fallback, setFallback] = useState(false);
    useEffect(() => {
        const key = 'lumina_site_reload';
        const last = Number(sessionStorage.getItem(key) || 0);
        if (Date.now() - last > 4000) {
            sessionStorage.setItem(key, String(Date.now()));
            window.location.replace('/');
        } else {
            setFallback(true);
        }
    }, []);
    return fallback ? <Landing /> : <PageLoader />;
};


// First keyboard stop: jump past the header to the page's main content
const SkipLink = () => (
    <a href="#main" className="lumina-skip" onClick={(e) => {
        const main = document.querySelector('main');
        if (!main) return;
        e.preventDefault();
        main.setAttribute('tabindex', '-1');
        main.focus();
    }}>Skip to content</a>
);

// Warm the main page chunks once the browser is idle, so moving between pages
// never flashes the loader
const usePrefetchPages = () => {
    useEffect(() => {
        if (APP_SHELL) return undefined;
        const warm = () => {
            import('./pages/Login'); import('./pages/Pricing');
            import('./pages/Dashboard'); import('./pages/ProjectView'); import('./pages/NotFound');
        };
        const idle = window.requestIdleCallback || ((fn) => setTimeout(fn, 1500));
        const id = idle(warm, { timeout: 4000 });
        return () => (window.cancelIdleCallback || clearTimeout)(id);
    }, []);
};

function App() {
    usePrefetchPages();
    return (
        <AuthProvider>
            <SettingsProvider>
                <GamificationProvider>
                    <ToastProvider>
                        <Router>
                            {!APP_SHELL && <RouteMeta />}
                            {!APP_SHELL && <SkipLink />}
                            {!APP_SHELL && <Feel />}
                            <Suspense fallback={<PageLoader />}>
                            <Ready />
                            {APP_SHELL ? <MobileApp /> : (
                            <Routes>
                                <Route path="/" element={<SiteHome />} />
                                <Route path="/login" element={<Login />} />
                                <Route path="/reset-password" element={<ResetPassword />} />
                                <Route path="/plans" element={<Pricing />} />
                                <Route path="/pricing" element={<Navigate to="/plans" replace />} />
                                <Route path="/privacy" element={<Privacy />} />
                                <Route path="/terms" element={<Terms />} />
                                <Route path="/delete-account" element={<DeleteAccount />} />
                                
                                {/* Protected Routes */}
                                <Route element={<PrivateRoute />}>
                                    <Route path="/dashboard" element={<Dashboard />} />
                                    <Route path="/project/:projectId" element={<ProjectView />} />
                                    <Route path="/settings" element={<Settings />} />
                                    <Route path="/bookstore" element={<BookStore />} />
                                    <Route path="/institution" element={<Institution />} />
                                    <Route path="/platform" element={<Platform />} />
                                    <Route path="/join/:code" element={<JoinClass />} />
                                </Route>
                                <Route path="*" element={<NotFound />} />
                            </Routes>
                            )}
                            </Suspense>
                            <LimitModal />
                        </Router>
                        <XPToast />
                    </ToastProvider>
                </GamificationProvider>
            </SettingsProvider>
        </AuthProvider>
    );
}

export default App;
