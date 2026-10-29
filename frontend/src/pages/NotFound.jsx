import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, RotateCcw } from 'lucide-react';
import SiteHeader from '../components/site/SiteHeader';
import { useAuth } from '../context/AuthContext';

// The 404 is a flashcard: the question on the front, the way back on the back.
const NotFound = () => {
    const { user } = useAuth();
    const [flipped, setFlipped] = useState(false);
    return (
        <>
        <SiteHeader />
        <main id="main" className="flex min-h-[calc(100dvh-4.5rem)] flex-col items-center justify-center gap-8 bg-[#FDF6F0] px-4 text-[#163628]">
            <h1 className="sr-only">Page not found</h1>
            <button
                type="button"
                onClick={() => setFlipped((f) => !f)}
                aria-pressed={flipped}
                className="group h-64 w-full max-w-md transition-transform duration-500 [perspective:1200px] hover:-translate-y-1 hover:rotate-[-1deg]"
            >
                <span className="relative block h-full w-full transition-transform duration-700 [transform-style:preserve-3d] [transition-timing-function:cubic-bezier(0.16,1,0.3,1)]"
                    style={{ transform: flipped ? 'rotateY(180deg)' : 'none' }}>
                    <span className="absolute inset-0 flex flex-col items-center justify-center rounded-3xl border border-[#E6D5CC] bg-white p-8 shadow-xl shadow-[#163628]/10 [backface-visibility:hidden]">
                        <span className="text-xs font-bold uppercase tracking-widest text-[#5E5046]">Question · 404</span>
                        <span className="mt-3 font-display text-3xl leading-tight">Where did this page <em>go</em>?</span>
                        <span className="mt-6 inline-flex items-center gap-1.5 text-sm text-[#5E5046]"><RotateCcw className="h-4 w-4" /> Tap to flip</span>
                    </span>
                    <span className="absolute inset-0 flex flex-col items-center justify-center rounded-3xl bg-[#163628] p-8 text-[#f4eee2] shadow-xl [backface-visibility:hidden] [transform:rotateY(180deg)]">
                        <span className="text-xs font-bold uppercase tracking-widest text-[#D3EE6A]">Answer</span>
                        <span className="mt-3 font-display text-3xl leading-tight">It was never written. Your books are still here.</span>
                    </span>
                </span>
            </button>
            <div className="flex flex-wrap justify-center gap-3">
                {user ? (
                    <>
                        <Link to="/dashboard" className="btn btn--dark">Go to my books <ArrowRight className="arrow" /></Link>
                        <a href="/" className="btn btn--light">Home</a>
                    </>
                ) : (
                    <>
                        <a href="/" className="btn btn--dark">Back to the home page <ArrowRight className="arrow" /></a>
                        <Link to="/login" className="btn btn--light">Log in</Link>
                    </>
                )}
            </div>
        </main>
        </>
    );
};

export default NotFound;
