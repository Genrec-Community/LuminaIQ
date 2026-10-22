import { lazy, Suspense } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { isAppShell } from './utils/platform';
import { AuthProvider } from './context/AuthContext';
import { ToastProvider } from './context/ToastContext';
import { SettingsProvider } from './context/SettingsContext';
import { GamificationProvider } from './context/GamificationContext';
import PrivateRoute from './components/PrivateRoute';
import XPToast from './components/XPToast';
import LimitModal from './components/LimitModal';

// Route-level code splitting: each page loads only when visited
const Login = lazy(() => import('./pages/Login'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const ProjectView = lazy(() => import('./pages/ProjectView'));
const Settings = lazy(() => import('./pages/Settings'));
const BookStore = lazy(() => import('./pages/BookStore'));
const Landing = lazy(() => import('./pages/Landing'));
const Pricing = lazy(() => import('./pages/Pricing'));
const Institution = lazy(() => import('./pages/Institution'));
const JoinClass = lazy(() => import('./pages/JoinClass'));
const Privacy = lazy(() => import('./pages/Legal').then((m) => ({ default: m.Privacy })));
const Terms = lazy(() => import('./pages/Legal').then((m) => ({ default: m.Terms })));
// The phone app has its own interface (bottom tabs, feed, onboarding)
const MobileApp = lazy(() => import('./mobile/MobileApp'));
const APP_SHELL = isAppShell();

const PageLoader = () => (
    <div className="min-h-screen flex items-center justify-center bg-[#FDF6F0]">
        <div className="h-12 w-12 rounded-2xl bg-[#C8A288] animate-pulse shadow-lg shadow-[#C8A288]/30" />
    </div>
);

function App() {
    return (
        <AuthProvider>
            <SettingsProvider>
                <GamificationProvider>
                    <ToastProvider>
                        <Router>
                            <Suspense fallback={<PageLoader />}>
                            {APP_SHELL ? <MobileApp /> : (
                            <Routes>
                                <Route path="/" element={<Landing />} />
                                <Route path="/login" element={<Login />} />
                                <Route path="/pricing" element={<Pricing />} />
                                <Route path="/privacy" element={<Privacy />} />
                                <Route path="/terms" element={<Terms />} />
                                
                                {/* Protected Routes */}
                                <Route element={<PrivateRoute />}>
                                    <Route path="/dashboard" element={<Dashboard />} />
                                    <Route path="/project/:projectId" element={<ProjectView />} />
                                    <Route path="/settings" element={<Settings />} />
                                    <Route path="/bookstore" element={<BookStore />} />
                                    <Route path="/institution" element={<Institution />} />
                                    <Route path="/join/:code" element={<JoinClass />} />
                                </Route>
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
