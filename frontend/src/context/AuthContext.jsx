import React, { createContext, useContext, useState, useEffect } from 'react';
import { api, login as apiLogin, signup as apiSignup, exchangeToken as apiExchangeToken } from '../api';
import { supabase } from '../supabaseClient';
import { isNativeApp } from '../utils/platform';
import { nativeGoogleSignIn, initNative } from '../utils/native';

const AuthContext = createContext(null);

// Resolve with `fallback` if a promise takes longer than `ms` (start-up must never hang)
const withTimeout = (promise, ms, fallback) => Promise.race([
    promise,
    new Promise((resolve) => setTimeout(() => resolve(fallback), ms)),
]);

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
                // Check if the JWT is expired before using it
                try {
                    const base64Url = token.split('.')[1];
                    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
                    const jsonPayload = decodeURIComponent(atob(base64).split('').map(function(c) {
                        return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
                    }).join(''));
                    const payload = JSON.parse(jsonPayload);
                    
                    const nowSec = Math.floor(Date.now() / 1000);
                    if (payload.exp && payload.exp < nowSec) {
                        // Token is expired — clear it; Supabase session below will refresh
                        console.log('Stored token expired, clearing...');
                        localStorage.removeItem('token');
                        localStorage.removeItem('user');
                    } else {
                        setUser(JSON.parse(storedUser));
                        api.defaults.headers.common['Authorization'] = `Bearer ${token}`;
                    }
                } catch {
                    // Malformed token — clear it
                    localStorage.removeItem('token');
                    localStorage.removeItem('user');
                }
            }

            // Wait for Supabase session to initialize (handles OAuth callback).
            // Capped: in some Android WebViews the session refresh can hang, which
            // left the app on a blank screen.
            const { data: { session } } = await withTimeout(
                supabase.auth.getSession(), 8000, { data: { session: null } }
            );
            
            if (session && !tokenExchanged.current) {
                console.log("Supabase session found, exchanging token...");
                const currentToken = localStorage.getItem('token');
                
                // If we don't have our app token yet, exchange the Supabase one
                if (!currentToken) {
                    tokenExchanged.current = true;
                    try {
                        const data = await apiExchangeToken(session.access_token);
                        if (data.access_token) {
                            localStorage.setItem('token', data.access_token);
                            localStorage.setItem('user', JSON.stringify(data.user));
                            api.defaults.headers.common['Authorization'] = `Bearer ${data.access_token}`;
                            setUser(data.user);
                        }
                    } catch (e) {
                        console.error("Token Exchange Failed:", e);
                        tokenExchanged.current = false; // Reset on failure
                    }
                }
            }

            setLoading(false);
        };

        initAuth().catch((e) => console.error('Auth start-up failed:', e)).finally(() => setLoading(false));
        initNative(supabase); // Android app: sign-in deep link + back button

        // Listen for Supabase auth changes (including OAuth callbacks)
        const { data: authListener } = supabase.auth.onAuthStateChange((event, session) => {
            // Run outside the callback: awaiting Supabase (signOut, getSession in the
            // 401 handler) inside it deadlocks the auth lock, so sign-in spun forever
            setTimeout(() => handleAuthEvent(event, session), 0);
        });

        const handleAuthEvent = async (event, session) => {
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
                        const data = await apiExchangeToken(session.access_token);

                        if (data.access_token) {
                            localStorage.setItem('token', data.access_token);
                            localStorage.setItem('user', JSON.stringify(data.user));
                            api.defaults.headers.common['Authorization'] = `Bearer ${data.access_token}`;
                            setUser(data.user);
                            
                            // Clean up URL if it has the Supabase hash
                            if (window.location.hash.includes('access_token')) {
                                window.history.replaceState(null, '', window.location.pathname);
                            }
                            
                            // Redirect to dashboard only if we are on login or landing page
                            if (window.location.pathname === '/login' || window.location.pathname === '/') {
                                window.location.href = '/dashboard';
                            }
                        }
                    } catch (e) {
                        console.error("Token Exchange Failed:", e);
                        tokenExchanged.current = false; // Reset on failure to allow retry
                        // Say why on the sign-in screen instead of failing silently
                        const detail = e?.response?.data?.detail;
                        window.dispatchEvent(new CustomEvent('lumina-auth-error', {
                            detail: typeof detail === 'string' ? detail : (e?.response ? 'Sign-in failed on our side. Please try again.' : "Couldn't reach LuminaIQ. Check your connection and try again."),
                        }));
                        await supabase.auth.signOut(); // Clear invalid supabase session
                    }
                }
            }
            if (event === 'SIGNED_OUT') {
                localStorage.removeItem('token');
                localStorage.removeItem('user');
                setUser(null);
            }
        };

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
            if (isNativeApp()) {
                await nativeGoogleSignIn(supabase);
                return;
            }
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

    const requestOtp = async (email) => {
        try {
            const { error } = await supabase.auth.signInWithOtp({ email });
            if (error) throw error;
            return true;
        } catch (error) {
            console.error("OTP Request failed", error);
            throw error;
        }
    };

    const verifyOtpCode = async (email, token) => {
        try {
            const { data, error } = await supabase.auth.verifyOtp({ email, token, type: 'email' });
            if (error) throw error;
            // The authListener will automatically catch the SIGNED_IN event 
            // and perform the token exchange.
            return data;
        } catch (error) {
            console.error("OTP Verification failed", error);
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
        <AuthContext.Provider value={{ user, login, signup, loginWithGoogle, requestOtp, verifyOtpCode, logout, loading }}>

            {loading ? (
                // Not a blank screen while the saved sign-in is checked
                <div style={{ minHeight: '100dvh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#FDF6F0' }}>
                    <div className="h-8 w-8 animate-spin rounded-full border-[3px] border-[#E6D5CC] border-t-[#C8A288]" />
                </div>
            ) : children}
        </AuthContext.Provider >
    );
};

export const useAuth = () => useContext(AuthContext);
