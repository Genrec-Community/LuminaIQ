import React, { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import SiteHeader from '../components/site/SiteHeader';
import Circled from '../components/site/Circled';
import MemoryCurve from '../components/MemoryCurve';
import { AFTER_LOGIN_KEY } from '../utils/afterLogin';
import { Loader2, ArrowRight, Mail, Lock, User, School, ChevronDown } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { apiErrorText, SCHOOL_PAUSED_KEY } from '../api';

const Login = () => {
    const navigate = useNavigate();
    // Where to go after signing in (e.g. back to /pricing). Kept in session
    // storage too, so Google sign-in (which lands on /dashboard) can follow it.
    const [searchParams] = useSearchParams();
    const next = (searchParams.get('next') || '').startsWith('/') ? searchParams.get('next') : '';
    React.useEffect(() => {
        if (next) sessionStorage.setItem(AFTER_LOGIN_KEY, next);
    }, [next]);
    const { login, signup, loginWithGoogle, requestOtp, verifyOtpCode, requestPasswordReset } = useAuth();
    const [isLogin, setIsLogin] = useState(() => searchParams.get('signup') !== '1');
    const [isOtpMode, setIsOtpMode] = useState(false);
    const [isForgot, setIsForgot] = useState(false); // "Forgot password?" form
    const [showSchoolHelp, setShowSchoolHelp] = useState(false);
    const [otpSent, setOtpSent] = useState(false);
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [otpCode, setOtpCode] = useState('');
    const [fullName, setFullName] = useState('');
    const [loading, setLoading] = useState(false);
    const [message, setMessage] = useState(null); // { type: 'success' | 'error', text: '' }

    // A school-created student who was signed out because their school is paused
    React.useEffect(() => {
        try {
            const why = sessionStorage.getItem(SCHOOL_PAUSED_KEY);
            if (why !== null) {
                sessionStorage.removeItem(SCHOOL_PAUSED_KEY);
                setMessage({ type: 'error', text: why || "Your school's Lumina IQ access is paused." });
            }
        } catch { /* ignore */ }
    }, []);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        setMessage(null);

        try {
            if (isForgot) {
                const id = email.trim();
                // School sign-in IDs have no mailbox behind them, so a reset email can't reach anyone
                if (!id.includes('@') || id.toLowerCase().endsWith('@luminaiq.fun')) {
                    setMessage({
                        type: 'error',
                        text: "That looks like a school sign-in ID. These can't receive email, so please ask your school to reset your password.",
                    });
                    return;
                }
                await requestPasswordReset(id);
                setMessage({
                    type: 'success',
                    text: `If ${id} has a Lumina IQ account, we've sent it a link to choose a new password. Check your inbox (and spam).`,
                });
            } else if (isOtpMode) {
                if (!otpSent) {
                    await requestOtp(email);
                    setOtpSent(true);
                    setMessage({
                        type: 'success',
                        text: 'OTP sent! Please check your email for the 6-digit code.'
                    });
                } else {
                    await verifyOtpCode(email, otpCode);
                    // The auth listener will exchange the token and redirect,
                    // but we can also do navigate here if we want to be safe, 
                    // though AuthContext handles it. We'll just wait.
                    setMessage({ type: 'success', text: 'Verified! Redirecting...' });
                }
            } else if (isLogin) {
                const success = await login(email, password);
                if (success) {
                    sessionStorage.removeItem(AFTER_LOGIN_KEY);
                    navigate(next || '/dashboard');
                }
            } else {
                // Password Validation
                const pwdRegex = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[\W_]).{8,}$/;
                if (!pwdRegex.test(password)) {
                    setMessage({
                        type: 'error',
                        text: "Password must be at least 8 characters and include uppercase, lowercase, numbers, and symbols."
                    });
                    setLoading(false);
                    return;
                }

                await signup(email, password, fullName);

                // Signup successful - Redirect to login with confirmation message
                // We do NOT auto-login because email confirmation might be required
                setIsLogin(true);
                setPassword('');
                setMessage({
                    type: 'success',
                    text: 'Account created! If email confirmation is enabled, please check your inbox before logging in.'
                });
            }
        } catch (err) {
            console.error("Auth error:", err);
            // Extract meaningful message
            let errorMsg = apiErrorText(err, 'An error occurred. Please try again.');
            const status = err.response?.status;

            if (errorMsg.includes('already registered')) {
                errorMsg = "This email is already registered. Please log in.";
            } else if (status === 503 || errorMsg.includes('timed out') || errorMsg.includes('timeout') || err.code === 'ECONNABORTED') {
                errorMsg = "Connection to authentication service timed out. Please check your internet connection and try again.";
            } else if (err.name === 'AuthApiError' || err.name === 'AuthUnknownError' || (err.__isAuthError && err.status)) {
                // Supabase answered with an error (OTP / password login): show what it said
                errorMsg = err.status === 429
                    ? "Too many attempts. Please wait a minute and try again."
                    : /sending .*email/i.test(err.message)
                        ? "We couldn't send the email right now. Please try again shortly or use another sign-in option."
                        : err.message;
            } else if (!err.response && (err.code === 'ERR_NETWORK' || err.name === 'AuthRetryableFetchError' || err instanceof TypeError)) {
                // Network error (no response at all)
                errorMsg = "Unable to reach the server. Please check your connection and try again.";
            } else if (!err.response && err.message) {
                errorMsg = err.message;
            }

            setMessage({ type: 'error', text: errorMsg });
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-[#FDF6F0] font-sans text-[#163628]">
        <SiteHeader cta={false} />
        <main id="main" className="site-wrap grid gap-8 pb-16 pt-6 lg:grid-cols-12 lg:items-start lg:gap-10 lg:pt-12">
            {/* The site's argument, on the left: you forget, reviews bring it back */}
            <section className="hidden lg:col-span-6 lg:block lg:sticky lg:top-28" aria-label="Why Lumina IQ">
                <p data-reveal="up" className="display h-xl">
                    Read it once.<br />
                    <Circled><em>Remember</em></Circled> it<br />
                    for the exam.
                </p>
                <div data-reveal="settle" data-delay="0.2" className="mt-10"><MemoryCurve height={210} compact /></div>
            </section>

            <div data-reveal="settle" className="w-full lg:col-span-5 lg:col-start-8 bg-white rounded-[1.5rem] overflow-hidden border border-[#163628]/10 shadow-[0_24px_60px_-34px_rgba(22,54,40,0.45)]">
                <div className="p-6 sm:p-10">
                    <div className="mb-8">
                        <h1 className="display h-l mb-3 mark-em">
                            {isForgot ? <>Choose a new <em>password</em></> : isOtpMode ? <>Sign in with a <em>code</em></> : isLogin ? <>Welcome <em>back</em>.</> : <>Start <em>remembering</em>.</>}
                        </h1>
                        <p className="text-[#5E5046]">
                            {isForgot ? "Enter your email and we'll send you a link to choose a new password" : isOtpMode ? 'We will send a one-time code to your email' : isLogin ? 'Pick up right where your learning path left off' : 'Turn any book into the shortest path to exam-ready'}
                        </p>
                    </div>

                    <form onSubmit={handleSubmit} className="space-y-6">
                        {message && (
                            <div className={`p-4 text-sm rounded-xl border flex items-start gap-3 ${message.type === 'success'
                                ? 'bg-green-50 text-green-700 border-green-200'
                                : 'bg-red-50 text-red-700 border-red-200'
                                }`}>
                                <div className={`mt-0.5 h-2 w-2 shrink-0 rounded-full ${message.type === 'success' ? 'bg-green-500' : 'bg-red-500'
                                    }`} />
                                <span className="flex-1 leading-relaxed">{message.text}</span>
                            </div>
                        )}

                        <div className="space-y-4">
                            {!isLogin && !isOtpMode && (
                                <div className="relative group">
                                    <div className="absolute left-4 top-1/2 -translate-y-1/2 pointer-events-none">
                                        <User className="h-5 w-5 text-[#5E5046] group-focus-within:text-[#1E5C42] transition-colors" />
                                    </div>
                                    <input
                                        aria-label="Full name"
                                        type="text"
                                        required
                                        value={fullName}
                                        onChange={(e) => setFullName(e.target.value)}
                                        className="w-full pl-12 pr-4 py-4 bg-[#FDF6F0] border border-[#163628]/15 rounded-full outline-none focus:border-[#163628] focus:bg-white focus:ring-4 focus:ring-[#D3EE6A]/70 transition-all text-[#163628] placeholder-[#5E5046]/60 font-medium"
                                        placeholder="Full Name"
                                        disabled={loading}
                                    />
                                </div>
                            )}

                            <div className="relative group">
                                <div className="absolute left-4 top-1/2 -translate-y-1/2 pointer-events-none">
                                    <Mail className="h-5 w-5 text-[#5E5046] group-focus-within:text-[#1E5C42] transition-colors" />
                                </div>
                                <input
                                    aria-label="Email"
                                    type={isLogin && !isOtpMode && !isForgot ? 'text' : 'email'}
                                    autoCapitalize="none"
                                    autoComplete="username"
                                    required
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                    className="w-full pl-12 pr-4 py-4 bg-[#FDF6F0] border border-[#163628]/15 rounded-full outline-none focus:border-[#163628] focus:bg-white focus:ring-4 focus:ring-[#D3EE6A]/70 transition-all text-[#163628] placeholder-[#5E5046]/60 font-medium"
                                    placeholder={isLogin && !isOtpMode && !isForgot ? 'Email' : 'name@example.com'}
                                    disabled={loading || (isOtpMode && otpSent)}
                                />
                            </div>

                            {!isOtpMode && !isForgot && (
                                <div className="relative group">
                                    <div className="absolute left-4 top-1/2 -translate-y-1/2 pointer-events-none">
                                        <Lock className="h-5 w-5 text-[#5E5046] group-focus-within:text-[#1E5C42] transition-colors" />
                                    </div>
                                    <input
                                        aria-label="Password"
                                        type="password"
                                        required
                                        value={password}
                                        onChange={(e) => setPassword(e.target.value)}
                                        className="w-full pl-12 pr-4 py-4 bg-[#FDF6F0] border border-[#163628]/15 rounded-full outline-none focus:border-[#163628] focus:bg-white focus:ring-4 focus:ring-[#D3EE6A]/70 transition-all text-[#163628] placeholder-[#5E5046]/60 font-medium"
                                        placeholder="••••••••"
                                        disabled={loading}
                                    />
                                </div>
                            )}

                            {isLogin && !isOtpMode && !isForgot && (
                                <div className="flex justify-end">
                                    <button
                                        type="button"
                                        onClick={() => { setIsForgot(true); setMessage(null); }}
                                        className="lumina-link inline-flex min-h-[32px] items-center text-sm font-semibold"
                                    >
                                        Forgot password?
                                    </button>
                                </div>
                            )}

                            {isOtpMode && otpSent && (
                                <div className="relative group">
                                    <div className="absolute left-4 top-1/2 -translate-y-1/2 pointer-events-none">
                                        <Lock className="h-5 w-5 text-[#5E5046] group-focus-within:text-[#1E5C42] transition-colors" />
                                    </div>
                                    <input
                                        aria-label="Six-digit code"
                                        type="text"
                                        required
                                        value={otpCode}
                                        onChange={(e) => setOtpCode(e.target.value)}
                                        className="w-full pl-12 pr-4 py-4 bg-[#FDF6F0] border border-[#163628]/15 rounded-full outline-none focus:border-[#163628] focus:bg-white focus:ring-4 focus:ring-[#D3EE6A]/70 transition-all text-[#163628] placeholder-[#5E5046]/60 font-medium tracking-widest text-center"
                                        placeholder="123456"
                                        maxLength={6}
                                        disabled={loading}
                                    />
                                </div>
                            )}
                        </div>

                        <button
                            type="submit"
                            disabled={loading}
                            className="btn btn--dark btn--block min-h-[3.4rem] text-lg"
                        >
                            {loading ? (
                                <Loader2 className="h-6 w-6 animate-spin" />
                            ) : (
                                <>
                                    {isForgot ? 'Send reset link' : isOtpMode ? (otpSent ? 'Verify OTP' : 'Send Code') : isLogin ? 'Sign In' : 'Create Account'}
                                    <ArrowRight className="h-5 w-5" />
                                </>
                            )}
                        </button>
                    </form>

                    {isForgot ? (
                        <div className="mt-6 text-center">
                            <button
                                type="button"
                                onClick={() => { setIsForgot(false); setMessage(null); }}
                                className="text-sm font-bold text-[#1E5C42] hover:text-[#163628] hover:underline"
                            >
                                Back to sign in
                            </button>
                        </div>
                    ) : (<>
                    <div className="relative my-6">
                        <div className="absolute inset-0 flex items-center">
                            <div className="w-full border-t border-[#E6D5CC]"></div>
                        </div>
                        <div className="relative flex justify-center text-sm">
                            <span className="px-2 bg-white text-[#5E5046]">Or continue with</span>
                        </div>
                    </div>

                    <button
                        type="button"
                        onClick={async () => {
                            try {
                                setLoading(true);
                                await loginWithGoogle();
                            } catch (e) {
                                setMessage({ type: 'error', text: 'Google Sign In failed' });
                                setLoading(false);
                            }
                        }}
                        disabled={loading}
                        className="btn btn--light btn--block min-h-[3.4rem] gap-3 text-lg"
                    >
                        <svg className="h-6 w-6" viewBox="0 0 48 48" aria-hidden="true"><path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z"/><path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/><path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z"/><path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C36.9 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z"/></svg>
                        Google
                    </button>

                    <button
                        type="button"
                        onClick={() => {
                            setIsOtpMode(!isOtpMode);
                            setOtpSent(false);
                            setMessage(null);
                        }}
                        disabled={loading}
                        className="btn btn--soft btn--block mt-3 min-h-[3.4rem] gap-3 text-lg"
                    >
                        <Mail className="h-5 w-5 text-[#5E5046]" />
                        {isOtpMode ? 'Use Password Instead' : 'Login with Email Code'}
                    </button>

                    <div className="mt-8 pt-6 border-t border-[#FDF6F0] text-center">
                        {!isOtpMode && (
                            <p className="text-[#5E5046] text-sm">
                                {isLogin ? "New to Lumina IQ? " : "Already have an account? "}
                                <button
                                    onClick={() => {
                                        setIsLogin(!isLogin);
                                        setMessage(null);
                                    }}
                                    className="lumina-link ml-1 inline-flex min-h-[32px] items-center font-bold"
                                >
                                    {isLogin ? 'Create an account' : 'Sign in'}
                                </button>
                            </p>
                        )}
                    </div>

                    {isLogin && !isOtpMode && (
                        <div className="mt-4 rounded-xl border border-[#E6D5CC] bg-[#FDF6F0]/60">
                            <button
                                type="button"
                                onClick={() => setShowSchoolHelp(!showSchoolHelp)}
                                aria-expanded={showSchoolHelp}
                                className="w-full flex items-center justify-between gap-3 px-4 py-3 text-sm font-semibold text-[#163628] rounded-[inherit] transition-colors hover:bg-[#D3EE6A]/45"
                            >
                                <span className="flex items-center gap-2">
                                    <School className="h-4 w-4 text-[#5E5046]" />
                                    Signing in through your school or institution?
                                </span>
                                <ChevronDown className={`h-4 w-4 text-[#5E5046] transition-transform ${showSchoolHelp ? 'rotate-180' : ''}`} />
                            </button>
                            {showSchoolHelp && (
                                <p className="px-4 pb-4 text-xs text-[#5E5046] leading-relaxed text-left">
                                    Type the sign-in ID your school gave you, like <span className="font-mono">arun-07@luminaiq.fun</span>, in the email box above, with the password they gave you. School IDs can't receive email, so if you forget that password, ask your school to reset it.
                                </p>
                            )}
                        </div>
                    )}
                    </>)}
                </div>
            </div>
        </main>
        </div>
    );
};

export default Login;