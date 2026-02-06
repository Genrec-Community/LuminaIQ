import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BookOpen, Loader2, ArrowRight, Mail, Lock, User } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

const Login = () => {
    const navigate = useNavigate();
    const { login, signup, loginWithGoogle } = useAuth();
    const [isLogin, setIsLogin] = useState(true);
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [fullName, setFullName] = useState('');
    const [loading, setLoading] = useState(false);
    const [message, setMessage] = useState(null); // { type: 'success' | 'error', text: '' }

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        setMessage(null);

        try {
            if (isLogin) {
                const success = await login(email, password);
                if (success) navigate('/dashboard');
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
            let errorMsg = err.response?.data?.detail || 'An error occurred. Please try again.';

            if (errorMsg.includes('already registered')) {
                errorMsg = "This email is already registered. Please log in.";
            }

            setMessage({ type: 'error', text: errorMsg });
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-[#FDF6F0] flex items-center justify-center p-4 font-sans text-[#4A3B32]">
            <div className="max-w-md w-full bg-white rounded-3xl shadow-2xl shadow-[#C8A288]/10 overflow-hidden border border-[#E6D5CC]">
                <div className="p-6 sm:p-12">
                    <div className="text-center mb-10">
                        <div className="h-16 w-16 bg-[#C8A288] rounded-2xl flex items-center justify-center text-white mx-auto mb-6 shadow-lg shadow-[#C8A288]/20 transform rotate-3 transition-transform hover:rotate-6">
                            <BookOpen className="h-8 w-8" />
                        </div>
                        <h1 className="text-3xl font-bold mb-2 text-[#4A3B32]">
                            {isLogin ? 'Welcome Back' : 'Join Lumina IQ'}
                        </h1>
                        <p className="text-[#8a6a5c] text-sm">
                            {isLogin ? 'Enter your credentials to access your workspace' : 'Start your intelligent learning journey today'}
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
                            {!isLogin && (
                                <div className="relative group">
                                    <div className="absolute left-4 top-1/2 -translate-y-1/2 pointer-events-none">
                                        <User className="h-5 w-5 text-[#8a6a5c] group-focus-within:text-[#C8A288] transition-colors" />
                                    </div>
                                    <input
                                        type="text"
                                        required
                                        value={fullName}
                                        onChange={(e) => setFullName(e.target.value)}
                                        className="w-full pl-12 pr-4 py-4 bg-white border-2 border-[#E6D5CC] rounded-xl outline-none focus:border-[#C8A288] focus:ring-4 focus:ring-[#C8A288]/10 transition-all text-[#4A3B32] placeholder-[#d2bab0] font-medium"
                                        placeholder="Full Name"
                                    />
                                </div>
                            )}

                            <div className="relative group">
                                <div className="absolute left-4 top-1/2 -translate-y-1/2 pointer-events-none">
                                    <Mail className="h-5 w-5 text-[#8a6a5c] group-focus-within:text-[#C8A288] transition-colors" />
                                </div>
                                <input
                                    type="email"
                                    required
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                    className="w-full pl-12 pr-4 py-4 bg-white border-2 border-[#E6D5CC] rounded-xl outline-none focus:border-[#C8A288] focus:ring-4 focus:ring-[#C8A288]/10 transition-all text-[#4A3B32] placeholder-[#d2bab0] font-medium"
                                    placeholder="name@example.com"
                                />
                            </div>

                            <div className="relative group">
                                <div className="absolute left-4 top-1/2 -translate-y-1/2 pointer-events-none">
                                    <Lock className="h-5 w-5 text-[#8a6a5c] group-focus-within:text-[#C8A288] transition-colors" />
                                </div>
                                <input
                                    type="password"
                                    required
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    className="w-full pl-12 pr-4 py-4 bg-white border-2 border-[#E6D5CC] rounded-xl outline-none focus:border-[#C8A288] focus:ring-4 focus:ring-[#C8A288]/10 transition-all text-[#4A3B32] placeholder-[#d2bab0] font-medium"
                                    placeholder="••••••••"
                                />
                            </div>
                        </div>

                        <button
                            type="submit"
                            disabled={loading}
                            className="w-full py-4 bg-[#C8A288] text-white rounded-xl font-bold text-lg hover:bg-[#B08B72] focus:ring-4 focus:ring-[#C8A288]/30 transition-all disabled:opacity-70 flex items-center justify-center gap-2 shadow-xl shadow-[#C8A288]/20 transform active:scale-[0.98]"
                        >
                            {loading ? (
                                <Loader2 className="h-6 w-6 animate-spin" />
                            ) : (
                                <>
                                    {isLogin ? 'Sign In' : 'Create Account'}
                                    <ArrowRight className="h-5 w-5" />
                                </>
                            )}
                        </button>
                    </form>

                    <div className="relative my-6">
                        <div className="absolute inset-0 flex items-center">
                            <div className="w-full border-t border-[#E6D5CC]"></div>
                        </div>
                        <div className="relative flex justify-center text-sm">
                            <span className="px-2 bg-white text-[#8a6a5c]">Or continue with</span>
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
                        className="w-full py-4 bg-white border-2 border-[#E6D5CC] text-[#4A3B32] rounded-xl font-bold text-lg hover:bg-[#FDF6F0] focus:ring-4 focus:ring-[#C8A288]/10 transition-all flex items-center justify-center gap-3 active:scale-[0.98]"
                    >
                        <img src="https://www.svgrepo.com/show/475656/google-color.svg" className="h-6 w-6" alt="Google" />
                        Google
                    </button>

                    <div className="mt-8 pt-6 border-t border-[#FDF6F0] text-center">
                        <p className="text-[#8a6a5c] text-sm">
                            {isLogin ? "New to Lumina IQ? " : "Already have an account? "}
                            <button
                                onClick={() => {
                                    setIsLogin(!isLogin);
                                    setMessage(null);
                                }}
                                className="text-[#C8A288] font-bold hover:text-[#B08B72] hover:underline transition-colors ml-1"
                            >
                                {isLogin ? 'Create an account' : 'Sign in'}
                            </button>
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default Login;