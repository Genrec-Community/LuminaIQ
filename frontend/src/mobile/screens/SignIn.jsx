import React, { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { Mail, Loader2, ChevronLeft, KeyRound } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { apiErrorText } from '../../api';
import { tap, notify } from '../device';
import logo from '../logo.png';

const GoogleLogo = () => (
    <svg viewBox="0 0 48 48" className="h-5 w-5" aria-hidden="true">
        <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3 0 5.8 1.1 7.9 3l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z" />
        <path fill="#FF3D00" d="m6.3 14.7 6.6 4.8C14.7 15.1 19 12 24 12c3 0 5.8 1.1 7.9 3l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" />
        <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-8l-6.5 5C9.5 39.6 16.2 44 24 44z" />
        <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z" />
    </svg>
);

const field = 'h-14 w-full rounded-2xl px-4 text-[16px] outline-none transition-shadow focus:ring-2';
const fieldStyle = { background: 'var(--m-soft)', color: 'var(--m-text)', '--tw-ring-color': 'var(--m-accent)' };

/**
 * Direct sign-in: one tap with Google, or an emailed 6-digit code (works for
 * new and existing accounts alike, no password to remember). Password sign-in
 * stays available for accounts that use one.
 */
const SignIn = () => {
    const navigate = useNavigate();
    const { user, loginWithGoogle, requestOtp, verifyOtpCode, login, requestPasswordReset } = useAuth();
    const [step, setStep] = useState('choose'); // choose | email | code | password
    const [email, setEmail] = useState('');
    const [code, setCode] = useState('');
    const [password, setPassword] = useState('');
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    const [notice, setNotice] = useState('');
    const [resendIn, setResendIn] = useState(0);
    const codeRef = useRef(null);

    useEffect(() => { if (user) navigate('/app/home', { replace: true }); }, [user, navigate]);
    // Errors from the Google round trip or the token exchange (AuthContext, native.js)
    useEffect(() => {
        const onErr = (e) => { notify('error'); setBusy(false); setError(e.detail || 'Sign-in failed. Please try again.'); };
        window.addEventListener('lumina-auth-error', onErr);
        return () => window.removeEventListener('lumina-auth-error', onErr);
    }, []);
    useEffect(() => {
        if (resendIn <= 0) return undefined;
        const t = setTimeout(() => setResendIn(resendIn - 1), 1000);
        return () => clearTimeout(t);
    }, [resendIn]);

    const fail = (e, fallback) => {
        notify('error');
        setError(apiErrorText(e, fallback));
    };

    const google = async () => {
        tap('medium'); setError(''); setBusy(true);
        try {
            await loginWithGoogle();
            // Native picker: signed in, the effect above opens the app once the account is ready
        } catch (e) {
            if (e?.code === 'cancelled') { setBusy(false); return; }
            fail(e, 'Google sign-in did not start. Try again.');
        }
        // Browser fallback returns through a deep link; don't leave the button stuck
        setTimeout(() => setBusy(false), 12000);
    };

    const sendCode = async (e) => {
        e?.preventDefault();
        if (!/^\S+@\S+\.\S+$/.test(email)) { setError('Enter a valid email address.'); return; }
        tap('medium'); setError(''); setBusy(true);
        try {
            await requestOtp(email.trim());
            setStep('code'); setResendIn(45);
            setTimeout(() => codeRef.current?.focus(), 350);
        } catch (err) { fail(err, 'Could not send the code. Check the address and try again.'); }
        setBusy(false);
    };

    const verify = async (value = code) => {
        if (value.length < 6) return;
        setError(''); setBusy(true);
        try {
            await verifyOtpCode(email.trim(), value);
            notify('success');
            // AuthContext exchanges the session; the effect above opens the app
        } catch (err) { fail(err, 'That code did not work. Check it or send a new one.'); setCode(''); setBusy(false); }
    };

    const passwordLogin = async (e) => {
        e.preventDefault();
        tap('medium'); setError(''); setBusy(true);
        try { await login(email.trim(), password); notify('success'); } catch (err) { fail(err, 'Wrong email or password.'); setBusy(false); }
    };

    const forgotPassword = async () => {
        const id = email.trim();
        setError(''); setNotice('');
        if (!id.includes('@') || id.toLowerCase().endsWith('@luminaiq.fun')) {
            setError(id ? "School IDs can't receive email. Ask your school to reset your password." : 'Enter your email first, then tap Forgot password.');
            return;
        }
        tap(); setBusy(true);
        try {
            await requestPasswordReset(id);
            setNotice(`If ${id} has an account, we've emailed it a link to choose a new password.`);
        } catch (err) { fail(err, "Couldn't send the reset email. Try again in a minute."); }
        setBusy(false);
    };

    const back = () => { tap(); setError(''); setStep(step === 'code' || step === 'password' ? 'email' : 'choose'); };

    return (
        <div className="m-app m-shell relative flex min-h-[100dvh] flex-col overflow-hidden m-safe-top m-safe-bottom">
            <div className="pointer-events-none absolute inset-0" style={{ background: 'radial-gradient(120% 60% at 50% 0%, color-mix(in srgb, var(--m-accent) 30%, transparent) 0%, transparent 65%)' }} />
            <div className="relative flex h-14 items-center px-3">
                {step !== 'choose' && (
                    <button onClick={back} aria-label="Back" className="m-pressable flex h-11 w-11 items-center justify-center rounded-full"><ChevronLeft className="h-7 w-7" /></button>
                )}
            </div>

            <div className="relative flex flex-1 flex-col px-7">
                <AnimatePresence mode="wait">
                    {step === 'choose' && (
                        <motion.div key="choose" className="flex flex-1 flex-col" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -16 }}>
                            <div className="flex flex-1 flex-col justify-center">
                                <motion.img src={logo} alt="" initial={{ scale: 0.8, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ type: 'spring', damping: 12 }}
                                    className="mb-8 h-20 w-20" />
                                <h1 className="text-[34px] font-extrabold leading-[1.08] tracking-tight">Study smarter,<br />starting now.</h1>
                                <p className="mt-3 text-[16px]" style={{ color: 'var(--m-muted)' }}>One step and your books start working for you. No password needed.</p>
                            </div>
                            <div className="space-y-3 pb-6">
                                <button onClick={google} disabled={busy}
                                    className="m-pressable flex h-14 w-full items-center justify-center gap-3 rounded-2xl m-white text-[16px] font-bold text-[#1f1f1f] shadow-md disabled:opacity-70"
                                    style={{ border: '1px solid #e6e1dc' }}>
                                    {busy ? <Loader2 className="h-5 w-5 animate-spin" /> : <GoogleLogo />} Continue with Google
                                </button>
                                <button onClick={() => { tap(); setStep('email'); }}
                                    className="m-pressable flex h-14 w-full items-center justify-center gap-3 rounded-2xl text-[16px] font-bold"
                                    style={{ background: 'var(--m-text)', color: 'var(--m-bg)' }}>
                                    <Mail className="h-5 w-5" /> Continue with email
                                </button>
                                {error && <p className="text-center text-sm font-medium text-red-500">{error}</p>}
                                <p className="pt-2 text-center text-[12px] leading-relaxed" style={{ color: 'var(--m-muted)' }}>
                                    By continuing you agree to our <button type="button" onClick={() => navigate('/terms')} className="underline">Terms</button> and <button type="button" onClick={() => navigate('/privacy')} className="underline">Privacy Policy</button>.
                                </p>
                            </div>
                        </motion.div>
                    )}

                    {step === 'email' && (
                        <motion.form key="email" onSubmit={sendCode} className="flex flex-1 flex-col" initial={{ opacity: 0, x: 30 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -30 }}>
                            <h1 className="text-[30px] font-extrabold tracking-tight">What's your email?</h1>
                            <p className="mt-2 text-[15px]" style={{ color: 'var(--m-muted)' }}>We'll send a 6-digit code. New here? This creates your account.</p>
                            <input type="email" inputMode="email" autoComplete="email" autoFocus value={email} onChange={(e) => setEmail(e.target.value)}
                                placeholder="you@example.com" className={`${field} mt-8`} style={fieldStyle} />
                            {error && <p className="mt-3 text-sm font-medium text-red-500">{error}</p>}
                            <div className="mt-auto space-y-3 pb-6 pt-6">
                                <button type="submit" disabled={busy || !email}
                                    className="m-pressable flex h-14 w-full items-center justify-center gap-2 rounded-2xl text-[16px] font-bold text-white disabled:opacity-50"
                                    style={{ background: 'var(--m-accent)' }}>
                                    {busy ? <Loader2 className="h-5 w-5 animate-spin" /> : 'Send code'}
                                </button>
                                <button type="button" onClick={() => { tap(); setError(''); setStep('password'); }}
                                    className="m-pressable flex h-12 w-full items-center justify-center gap-2 text-[14px] font-semibold" style={{ color: 'var(--m-muted)' }}>
                                    <KeyRound className="h-4 w-4" /> Use a password instead
                                </button>
                            </div>
                        </motion.form>
                    )}

                    {step === 'code' && (
                        <motion.div key="code" className="flex flex-1 flex-col" initial={{ opacity: 0, x: 30 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -30 }}>
                            <h1 className="text-[30px] font-extrabold tracking-tight">Check your inbox</h1>
                            <p className="mt-2 text-[15px]" style={{ color: 'var(--m-muted)' }}>Enter the code sent to <b style={{ color: 'var(--m-text)' }}>{email}</b></p>
                            <label className="relative mt-8 block">
                                <input ref={codeRef} value={code} inputMode="numeric" autoComplete="one-time-code" maxLength={6}
                                    onChange={(e) => {
                                        const v = e.target.value.replace(/\D/g, '').slice(0, 6);
                                        setCode(v);
                                        if (v.length === 6) verify(v);
                                    }}
                                    className="absolute inset-0 opacity-0" aria-label="6-digit code" />
                                <div className="grid grid-cols-6 gap-2">
                                    {Array.from({ length: 6 }).map((_, n) => (
                                        <div key={n} className="flex h-16 items-center justify-center rounded-2xl text-2xl font-extrabold tabular-nums transition-all"
                                            style={{ background: 'var(--m-soft)', boxShadow: n === code.length ? '0 0 0 2px var(--m-accent)' : 'none' }}>
                                            {code[n] || ''}
                                        </div>
                                    ))}
                                </div>
                            </label>
                            {busy && <p className="mt-4 flex items-center gap-2 text-sm" style={{ color: 'var(--m-muted)' }}><Loader2 className="h-4 w-4 animate-spin" /> Signing you in…</p>}
                            {error && <p className="mt-4 text-sm font-medium text-red-500">{error}</p>}
                            <button disabled={resendIn > 0 || busy} onClick={sendCode}
                                className="m-pressable mt-6 self-start text-[14px] font-semibold disabled:opacity-50" style={{ color: 'var(--m-accent-text)' }}>
                                {resendIn > 0 ? `Send a new code in ${resendIn}s` : 'Send a new code'}
                            </button>
                        </motion.div>
                    )}

                    {step === 'password' && (
                        <motion.form key="password" onSubmit={passwordLogin} className="flex flex-1 flex-col" initial={{ opacity: 0, x: 30 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -30 }}>
                            <h1 className="text-[30px] font-extrabold tracking-tight">Welcome back</h1>
                            <input type="text" inputMode="email" autoCapitalize="none" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)}
                                placeholder="Email" className={`${field} mt-8`} style={fieldStyle} />
                            <input type="password" autoComplete="current-password" autoFocus value={password} onChange={(e) => setPassword(e.target.value)}
                                placeholder="Password" className={`${field} mt-3`} style={fieldStyle} />
                            <button type="button" onClick={forgotPassword} disabled={busy}
                                className="mt-3 self-end text-[14px] font-semibold" style={{ color: 'var(--m-accent)' }}>
                                Forgot password?
                            </button>
                            {error && <p className="mt-3 text-sm font-medium text-red-500">{error}</p>}
                            {notice && <p className="mt-3 text-sm font-medium text-green-600">{notice}</p>}
                            <p className="mt-4 text-[13px]" style={{ color: 'var(--m-muted)' }}>From a school or institution? Use the sign-in ID they gave you (like arun-07@luminaiq.fun) as your email. Forgot it? Ask your school to reset it.</p>
                            <div className="mt-auto pb-6 pt-6">
                                <button type="submit" disabled={busy || !email || !password}
                                    className="m-pressable flex h-14 w-full items-center justify-center rounded-2xl text-[16px] font-bold text-white disabled:opacity-50"
                                    style={{ background: 'var(--m-accent)' }}>
                                    {busy ? <Loader2 className="h-5 w-5 animate-spin" /> : 'Sign in'}
                                </button>
                            </div>
                        </motion.form>
                    )}
                </AnimatePresence>
            </div>
        </div>
    );
};

export default SignIn;
