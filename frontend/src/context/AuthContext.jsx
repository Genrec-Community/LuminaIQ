import React, { createContext, useContext, useState, useEffect } from 'react';
import { api, login as apiLogin, signup as apiSignup, loginWithGoogle as apiLoginGoogle } from '../api';
import { supabase } from '../supabaseClient';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);
    // Guard against multiple token exchanges
    const tokenExchanged = React.useRef(false);

    useEffect(() => {
        // Initialize auth - wait for Supabase session to be ready
        const initAuth = async () => {
            // First, check for existing app token
            const token = localStorage.getItem('token');
            const storedUser = localStorage.getItem('user');

            if (token && storedUser) {
                setUser(JSON.parse(storedUser));
                api.defaults.headers.common['Authorization'] = `Bearer ${token}`;
            }

            // Wait for Supabase session to initialize (handles OAuth callback)
            const { data: { session } } = await supabase.auth.getSession();
            
            if (session && !tokenExchanged.current) {
                console.log("Supabase session found, exchanging token...");
                const currentToken = localStorage.getItem('token');
                
                // If we don't have our app token yet, exchange the Supabase one
                if (!currentToken) {
                    tokenExchanged.current = true;
                    try {
                        const data = await apiLoginGoogle(session.access_token);
                        if (data.access_token) {
                            localStorage.setItem('token', data.access_token);
                            localStorage.setItem('user', JSON.stringify(data.user));
                            api.defaults.headers.common['Authorization'] = `Bearer ${data.access_token}`;
                            setUser(data.user);
                        }
                    } catch (e) {
                        console.error("Google Token Exchange Failed:", e);
                        tokenExchanged.current = false; // Reset on failure
                    }
                }
            }

            setLoading(false);
        };

        initAuth();

        // Listen for Supabase auth changes (including OAuth callbacks)
        const { data: authListener } = supabase.auth.onAuthStateChange(async (event, session) => {
            console.log("Auth event:", event, session ? "with session" : "no session");
            
            if (event === 'SIGNED_IN' && session && !tokenExchanged.current) {
                // Mark as exchanged immediately to prevent multiple exchanges
                tokenExchanged.current = true;
                
                console.log("Supabase Signed In via OAuth, exchanging token...");
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
                            
                            // Redirect to dashboard after successful token exchange
                            window.location.href = '/dashboard';
                        }
                    } catch (e) {
                        console.error("Google Token Exchange Failed:", e);
                        tokenExchanged.current = false; // Reset on failure to allow retry
                        await supabase.auth.signOut(); // Clear invalid supabase session
                    }
                }
            }
            if (event === 'SIGNED_OUT') {
                localStorage.removeItem('token');
                localStorage.removeItem('user');
                setUser(null);
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
                    redirectTo: `${window.location.origin}/dashboard`
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
