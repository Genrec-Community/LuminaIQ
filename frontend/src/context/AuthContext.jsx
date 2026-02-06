import React, { createContext, useContext, useState, useEffect } from 'react';
import { api, login as apiLogin, signup as apiSignup, loginWithGoogle as apiLoginGoogle } from '../api';
import { supabase } from '../supabaseClient';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        // init check
        const initAuth = async () => {
            const token = localStorage.getItem('token');
            const storedUser = localStorage.getItem('user');

            if (token && storedUser) {
                setUser(JSON.parse(storedUser));
                api.defaults.headers.common['Authorization'] = `Bearer ${token}`;
            }

            // Waiting for OAuth callback?
            if (window.location.hash && window.location.hash.includes('access_token')) {
                console.log("OAuth Redirect detected, waiting for session...");
                // Safety timeout
                setTimeout(() => setLoading(false), 5000);
                return;
            }

            setLoading(false);
        };
        initAuth();

        // Listen for Supabase OAuth Redirects
        const { data: authListener } = supabase.auth.onAuthStateChange(async (event, session) => {
            if (event === 'SIGNED_IN' && session) {
                console.log("Supabase Signed In via OAuth");
                const currentToken = localStorage.getItem('token');

                // If we don't have our app token yet, exchange the Supabase one
                if (!currentToken) {
                    try {
                        // Exchange Supabase Access Token for App JWT
                        const data = await apiLoginGoogle(session.access_token);

                        if (data.access_token) {
                            localStorage.setItem('token', data.access_token);
                            localStorage.setItem('user', JSON.stringify(data.user));
                            api.defaults.headers.common['Authorization'] = `Bearer ${data.access_token}`;
                            setUser(data.user);
                        }
                    } catch (e) {
                        console.error("Google Token Exchange Failed:", e);
                        await supabase.auth.signOut(); // Clear invalid supabase session
                    }
                }
            }
            if (event === 'SIGNED_OUT') {
                // handled by logout function usually
            }
        });

        return () => {
            authListener.subscription.unsubscribe();
        };
    }, []);

    const login = async (email, password) => {
        try {
            const data = await apiLogin(email, password);
            if (data.access_token) {
                localStorage.setItem('token', data.access_token);
                localStorage.setItem('user', JSON.stringify(data.user));
                api.defaults.headers.common['Authorization'] = `Bearer ${data.access_token}`;
                setUser(data.user);
                return true;
            }
            return false;
        } catch (error) {
            console.error("Login failed", error);
            throw error;
        }
    };

    const signup = async (email, password, fullName) => {
        try {
            await apiSignup(email, password, fullName);
            return true;
        } catch (error) {
            console.error("Signup failed", error);
            throw error;
        }
    };

    const loginWithGoogle = async () => {
        try {
            const { error } = await supabase.auth.signInWithOAuth({
                provider: 'google',
                options: {
                    redirectTo: window.location.origin
                }
            });
            if (error) throw error;
        } catch (error) {
            console.error("Google login init failed", error);
            throw error;
        }
    };

    const logout = async () => {
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        delete api.defaults.headers.common['Authorization'];
        setUser(null);
        await supabase.auth.signOut();
    };

    return (
        <AuthContext.Provider value={{ user, login, signup, loginWithGoogle, logout, loading }}>

            {!loading && children}
        </AuthContext.Provider >
    );
};

export const useAuth = () => useContext(AuthContext);
