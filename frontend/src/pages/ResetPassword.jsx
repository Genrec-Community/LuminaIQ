import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { BookOpen, Loader2, ArrowRight, Lock } from 'lucide-react';
import { supabase } from '../supabaseClient';
import { useAuth } from '../context/AuthContext';

const PASSWORD_RULE = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[\W_]).{8,}$/;

const inputClass = 'w-full pl-12 pr-4 py-4 bg-white border-2 border-[#E6D5CC] rounded-xl outline-none focus:border-[#1E5C42] focus:ring-4 focus:ring-[#1E5C42]/10 transition-all text-[#163628] placeholder-[#d2bab0] font-medium';

/**
 * Landing page for the "reset your password" email. Supabase signs the person in
 * from the link (the session is read from the URL), then they choose a new password.
 */
const ResetPassword = () => {
    const navigate = useNavigate();
    const { login, setNewPassword } = useAuth();
    const [status, setStatus] = useState('checking'); // checking | ready | invalid | done
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [confirm, setConfirm] = useState('');
    const [loading, setLoading] = useState(false);
    const [message, setMessage] = useState(null);

    useEffect(() => {
        let cancelled = false;
        // Supabase puts the reason in the URL when the link is expired or already used
        const params = new URLSearchParams(window.location.hash.replace(/^#/, '') || window.location.search);
        const linkError = params.get('error_description');

        const check = async () => {
            const { data: { session } } = await supabase.auth.getSession();
            if (cancelled) return;
            if (session?.user) {
                setEmail(session.user.email || '');
                setStatus('ready');
                if (window.location.hash) window.history.replaceState(null, '', window.location.pathname);
            } else {
                setStatus('invalid');
                if (linkError) setMessage({ type: 'error', text: linkError.replace(/\+/g, ' ') });
            }
        };
        check();
        // The session can arrive a moment after the page opens
        const { data: sub } = supabase.auth.onAuthStateChange((event, session) => {
            if (session?.user && (event === 'PASSWORD_RECOVERY' || event === 'SIGNED_IN')) {
                setEmail(session.user.email || '');
                setStatus('ready');
                setMessage(null);
            }
        });
        return () => { cancelled = true; sub.subscription.unsubscribe(); };
    }, []);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setMessage(null);
        if (!PASSWORD_RULE.test(password)) {
            setMessage({ type: 'error', text: 'Password must be at least 8 characters and include uppercase, lowercase, numbers, and symbols.' });
            return;
        }
        if (password !== confirm) {
            setMessage({ type: 'error', text: "The two passwords don't match." });
            return;
        }
        setLoading(true);
        try {
            await setNewPassword(password);
        } catch (err) {
            setLoading(false);
            setMessage({ type: 'error', text: err?.message || "Couldn't update your password. Please try again." });
            return;
        }
        // Sign in to Lumina IQ with the new password
        try {
            if (email && await login(email, password)) {
                navigate('/dashboard', { replace: true });
                return;
            }
        } catch { /* fall through to the "sign in" link */ }
        setLoading(false);
        setStatus('done');
    };

    return (
        <div className="min-h-screen bg-[#FDF6F0] flex items-center justify-center p-4 font-sans text-[#163628]">
            <div className="max-w-md w-full bg-white rounded-3xl shadow-2xl shadow-[#1E5C42]/10 overflow-hidden border border-[#E6D5CC]">
                <div className="p-6 sm:p-12">
                    <div className="text-center mb-8">
                        <div className="h-16 w-16 bg-[#1E5C42] rounded-2xl flex items-center justify-center text-white mx-auto mb-6 shadow-lg shadow-[#1E5C42]/20 transform rotate-3">
                            <BookOpen className="h-8 w-8" />
                        </div>
                        <h1 className="text-3xl font-bold mb-2">
                            {status === 'done' ? 'Password updated' : status === 'invalid' ? 'Link expired' : 'Choose a new password'}
                        </h1>
                        <p className="text-[#5E5046] text-sm">
                            {status === 'done' && 'You can now sign in with your new password.'}
                            {status === 'invalid' && 'This reset link is invalid or has already been used. Request a new one from the sign-in page.'}
                            {status === 'ready' && (email ? `For ${email}` : 'Pick something you will remember')}
                            {status === 'checking' && 'Checking your reset link...'}
                        </p>
                    </div>

                    {message && (
                        <div className={`mb-6 p-4 text-sm rounded-xl border ${message.type === 'success' ? 'bg-green-50 text-green-700 border-green-200' : 'bg-red-50 text-red-700 border-red-200'}`}>
                            {message.text}
                        </div>
                    )}

                    {status === 'checking' && (
                        <div className="flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-[#1E5C42]" /></div>
                    )}

                    {status === 'ready' && (
                        <form onSubmit={handleSubmit} className="space-y-4">
                            <div className="relative group">
                                <Lock className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-[#5E5046] pointer-events-none" />
                                <input type="password" autoComplete="new-password" required autoFocus value={password}
                                    onChange={(e) => setPassword(e.target.value)} className={inputClass}
                                    placeholder="New password" disabled={loading} />
                            </div>
                            <div className="relative group">
                                <Lock className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-[#5E5046] pointer-events-none" />
                                <input type="password" autoComplete="new-password" required value={confirm}
                                    onChange={(e) => setConfirm(e.target.value)} className={inputClass}
                                    placeholder="Confirm new password" disabled={loading} />
                            </div>
                            <p className="text-xs text-[#5E5046]">At least 8 characters, with uppercase, lowercase, a number and a symbol.</p>
                            <button type="submit" disabled={loading}
                                className="w-full py-4 bg-[#1E5C42] text-white rounded-xl font-bold text-lg hover:bg-[#163628] transition-all disabled:opacity-70 flex items-center justify-center gap-2 shadow-xl shadow-[#1E5C42]/20">
                                {loading ? <Loader2 className="h-6 w-6 animate-spin" /> : <>Save password <ArrowRight className="h-5 w-5" /></>}
                            </button>
                        </form>
                    )}

                    {(status === 'invalid' || status === 'done') && (
                        <Link to="/login"
                            className="w-full py-4 bg-[#1E5C42] text-white rounded-xl font-bold text-lg hover:bg-[#163628] transition-all flex items-center justify-center gap-2">
                            Go to sign in <ArrowRight className="h-5 w-5" />
                        </Link>
                    )}
                </div>
            </div>
        </div>
    );
};

export default ResetPassword;
