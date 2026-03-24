import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const PrivateRoute = () => {
    const { user, loading } = useAuth();
    
    // Wait for auth to initialize before redirecting
    // This prevents race condition where OAuth callback arrives but session isn't ready
    if (loading) {
        return null; // Or a loading spinner
    }
    
    return user ? <Outlet /> : <Navigate to="/login" replace />;
};

export default PrivateRoute;
