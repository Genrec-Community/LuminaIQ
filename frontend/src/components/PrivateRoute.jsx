import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useSettings } from '../context/SettingsContext';
import Onboarding, { onboardedKey } from './Onboarding';

const hasOnboardedLocally = (userId) => {
    try { return localStorage.getItem(onboardedKey(userId)) === '1'; } catch { return false; }
};

const PrivateRoute = () => {
    const { user, loading } = useAuth();
    const { settings, loaded } = useSettings();

    // Wait for auth to initialize before redirecting
    // This prevents race condition where OAuth callback arrives but session isn't ready
    if (loading) {
        return null; // Or a loading spinner
    }

    if (!user) return <Navigate to="/login" replace />;

    const showOnboarding = loaded && !settings.onboardingComplete && !hasOnboardedLocally(user.id);

    return (
        <>
            <Outlet />
            {showOnboarding && <Onboarding />}
        </>
    );
};

export default PrivateRoute;
