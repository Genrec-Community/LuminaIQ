import React, { useState, useEffect, useCallback } from 'react';
import {
    Layers, RefreshCw, ArrowLeft, ArrowRight,
    RotateCcw, Check, X, Shuffle, Eye, EyeOff
} from 'lucide-react';
import { generateFlashcardsLegacy as generateFlashcards } from '../../api';

const FlashCard = ({ card, index, total, flipped, onFlip }) => {
    return (
        <div
            className="w-full max-w-lg mx-auto cursor-pointer select-none"
            onClick={onFlip}
            style={{ perspective: '1200px' }}
        >
            <div
                className="relative w-full transition-transform duration-500"
                style={{
                    transformStyle: 'preserve-3d',
                    transform: flipped ? 'rotateY(180deg)' : 'rotateY(0deg)',
                    minHeight: '280px',
                }}
            >
                {/* Front */}
                <div
                    className="absolute inset-0 w-full h-full rounded-2xl border-2 border-[#E6D5CC] bg-white shadow-lg p-8 flex flex-col items-center justify-center"
                    style={{ backfaceVisibility: 'hidden' }}
                >
                    <div className="absolute top-4 left-4 text-xs font-bold text-[#C8A288] bg-[#FDF6F0] px-2.5 py-1 rounded-full">
                        {index + 1} / {total}
                    </div>
                    <div className="absolute top-4 right-4">
                        <div className="flex items-center gap-1 text-xs text-[#8a6a5c]">
                            <Eye className="h-3 w-3" />
                            <span>Question</span>
                        </div>
                    </div>
                    <div className="text-center">
                        <p className="text-lg font-bold text-[#4A3B32] leading-relaxed">
                            {card.front}
                        </p>
                    </div>
                    <p className="absolute bottom-4 text-xs text-[#8a6a5c] font-medium">
                        Click to reveal answer
                    </p>
                </div>

                {/* Back */}
                <div
                    className="absolute inset-0 w-full h-full rounded-2xl border-2 border-emerald-200 bg-gradient-to-br from-emerald-50 to-white shadow-lg p-8 flex flex-col items-center justify-center"
                    style={{
                        backfaceVisibility: 'hidden',
                        transform: 'rotateY(180deg)',
                    }}
                >
                    <div className="absolute top-4 left-4 text-xs font-bold text-emerald-600 bg-emerald-100 px-2.5 py-1 rounded-full">
                        {index + 1} / {total}
                    </div>
                    <div className="absolute top-4 right-4">
                        <div className="flex items-center gap-1 text-xs text-emerald-600">
                            <EyeOff className="h-3 w-3" />
                            <span>Answer</span>
                        </div>
                    </div>
                    <div className="text-center">
                        <p className="text-base text-[#4A3B32] leading-relaxed">
                            {card.back}
                        </p>
                    </div>
                    <p className="absolute bottom-4 text-xs text-emerald-600 font-medium">
                        Click to see question
                    </p>
                </div>
            </div>
        </div>
    );
};

const TopicFlashcards = ({ projectId, topic, selectedDocuments = [], onClose }) => {
    const [loading, setLoading] = useState(true);
    const [flashcards, setFlashcards] = useState([]);
    const [error, setError] = useState(null);
    const [currentIndex, setCurrentIndex] = useState(0);
    const [flipped, setFlipped] = useState(false);
    const [known, setKnown] = useState(new Set());
    const [unknown, setUnknown] = useState(new Set());

    const loadFlashcards = useCallback(async () => {
        setLoading(true);
        setError(null);
        setCurrentIndex(0);
        setFlipped(false);
        setKnown(new Set());
        setUnknown(new Set());
        try {
            const data = await generateFlashcards(projectId, topic, 8, selectedDocuments);
            if (data.success && data.flashcards) {
                setFlashcards(data.flashcards);
            } else {
                setError('Failed to generate flashcards');
            }
        } catch (err) {
            console.error('Flashcard generation failed:', err);
            setError(err.response?.data?.detail || 'Failed to generate flashcards. Please try again.');
        } finally {
            setLoading(false);
        }
    }, [projectId, topic, selectedDocuments]);

    useEffect(() => {
        loadFlashcards();
    }, [loadFlashcards]);

    // Keyboard navigation
    useEffect(() => {
        const handleKey = (e) => {
            if (e.key === 'ArrowRight' || e.key === 'd') {
                goNext();
            } else if (e.key === 'ArrowLeft' || e.key === 'a') {
                goPrev();
            } else if (e.key === ' ' || e.key === 'Enter') {
                e.preventDefault();
                setFlipped(f => !f);
            }
        };
        window.addEventListener('keydown', handleKey);
        return () => window.removeEventListener('keydown', handleKey);
    }, [currentIndex, flashcards.length]);

    const goNext = () => {
        if (currentIndex < flashcards.length - 1) {
            setCurrentIndex(i => i + 1);
            setFlipped(false);
        }
    };

    const goPrev = () => {
        if (currentIndex > 0) {
            setCurrentIndex(i => i - 1);
            setFlipped(false);
        }
    };

    const markKnown = () => {
        setKnown(prev => new Set(prev).add(currentIndex));
        setUnknown(prev => {
            const next = new Set(prev);
            next.delete(currentIndex);
            return next;
        });
        goNext();
    };

    const markUnknown = () => {
        setUnknown(prev => new Set(prev).add(currentIndex));
        setKnown(prev => {
            const next = new Set(prev);
            next.delete(currentIndex);
            return next;
        });
        goNext();
    };

    const shuffleCards = () => {
        const shuffled = [...flashcards].sort(() => Math.random() - 0.5);
        setFlashcards(shuffled);
        setCurrentIndex(0);
        setFlipped(false);
        setKnown(new Set());
        setUnknown(new Set());
    };

    const resetCards = () => {
        setCurrentIndex(0);
        setFlipped(false);
        setKnown(new Set());
        setUnknown(new Set());
    };

    const totalReviewed = known.size + unknown.size;
    const progressPercent = flashcards.length > 0 ? Math.round((totalReviewed / flashcards.length) * 100) : 0;

    return (
        <div className="h-full flex flex-col bg-white">
            {/* Header */}
            <div className="px-4 md:px-6 py-4 border-b border-[#E6D5CC] bg-white flex items-center justify-between flex-shrink-0">
                <div className="flex items-center gap-3 min-w-0">
                    <button
                        onClick={onClose}
                        className="p-2 hover:bg-[#FDF6F0] rounded-lg transition-colors text-[#8a6a5c] flex-shrink-0"
                        title="Back to Learning Path"
                    >
                        <ArrowLeft className="h-5 w-5" />
                    </button>
                    <div className="h-10 w-10 bg-gradient-to-br from-amber-500 to-orange-500 rounded-xl flex items-center justify-center text-white flex-shrink-0">
                        <Layers className="h-5 w-5" />
                    </div>
                    <div className="min-w-0">
                        <h3 className="font-bold text-[#4A3B32] text-lg truncate">Flashcards</h3>
                        <p className="text-xs text-[#8a6a5c] truncate">{topic}</p>
                    </div>
                </div>

                <div className="flex items-center gap-1 flex-shrink-0">
                    <button
                        onClick={shuffleCards}
                        disabled={loading || flashcards.length === 0}
                        className="p-2 hover:bg-[#FDF6F0] rounded-lg transition-colors text-[#8a6a5c] disabled:opacity-50"
                        title="Shuffle cards"
                    >
                        <Shuffle className="h-4 w-4" />
                    </button>
                    <button
                        onClick={resetCards}
                        disabled={loading || flashcards.length === 0}
                        className="p-2 hover:bg-[#FDF6F0] rounded-lg transition-colors text-[#8a6a5c] disabled:opacity-50"
                        title="Reset progress"
                    >
                        <RotateCcw className="h-4 w-4" />
                    </button>
                    <div className="w-px h-5 bg-[#E6D5CC] mx-1" />
                    <button
                        onClick={loadFlashcards}
                        disabled={loading}
                        className="p-2 hover:bg-[#FDF6F0] rounded-lg transition-colors text-[#8a6a5c] disabled:opacity-50"
                        title="Generate new cards"
                    >
                        <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                    </button>
                </div>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-auto p-4 md:p-8 bg-[#FDF6F0]/50">
                {loading ? (
                    <div className="flex flex-col items-center justify-center h-full gap-4">
                        <div className="relative">
                            <div className="h-16 w-16 border-4 border-[#E6D5CC] rounded-full" />
                            <div className="absolute inset-0 h-16 w-16 border-4 border-amber-400 rounded-full border-t-transparent animate-spin" />
                            <Layers className="absolute inset-0 m-auto h-6 w-6 text-amber-500" />
                        </div>
                        <div className="text-center">
                            <p className="text-[#4A3B32] font-bold">Generating Flashcards</p>
                            <p className="text-xs text-[#8a6a5c] mt-1">Creating study cards for "{topic}"...</p>
                        </div>
                    </div>
                ) : error ? (
                    <div className="flex flex-col items-center justify-center h-full gap-4">
                        <div className="h-16 w-16 bg-red-100 rounded-full flex items-center justify-center">
                            <X className="h-8 w-8 text-red-500" />
                        </div>
                        <p className="text-[#4A3B32] font-bold">Generation Failed</p>
                        <p className="text-sm text-[#8a6a5c] text-center max-w-md">{error}</p>
                        <button
                            onClick={loadFlashcards}
                            className="px-4 py-2 bg-[#C8A288] text-white rounded-lg font-medium hover:bg-[#B08B72] transition-colors flex items-center gap-2"
                        >
                            <RefreshCw className="h-4 w-4" />
                            Try Again
                        </button>
                    </div>
                ) : flashcards.length > 0 ? (
                    <div className="flex flex-col items-center max-w-lg mx-auto h-full">
                        {/* Progress bar */}
                        <div className="w-full mb-6">
                            <div className="flex items-center justify-between mb-2">
                                <div className="flex items-center gap-3 text-sm">
                                    <span className="flex items-center gap-1 text-green-600 font-bold">
                                        <Check className="h-3.5 w-3.5" />
                                        {known.size}
                                    </span>
                                    <span className="flex items-center gap-1 text-red-500 font-bold">
                                        <X className="h-3.5 w-3.5" />
                                        {unknown.size}
                                    </span>
                                </div>
                                <span className="text-xs font-bold text-[#8a6a5c]">
                                    {totalReviewed}/{flashcards.length} reviewed
                                </span>
                            </div>
                            <div className="h-2 bg-[#E6D5CC] rounded-full overflow-hidden flex">
                                <div
                                    className="h-full bg-green-400 transition-all duration-300"
                                    style={{ width: `${(known.size / flashcards.length) * 100}%` }}
                                />
                                <div
                                    className="h-full bg-red-300 transition-all duration-300"
                                    style={{ width: `${(unknown.size / flashcards.length) * 100}%` }}
                                />
                            </div>
                        </div>

                        {/* Card dots */}
                        <div className="flex gap-1.5 mb-6 flex-wrap justify-center">
                            {flashcards.map((_, idx) => (
                                <button
                                    key={idx}
                                    onClick={() => { setCurrentIndex(idx); setFlipped(false); }}
                                    className={`h-2.5 w-2.5 rounded-full transition-all ${
                                        idx === currentIndex
                                            ? 'bg-[#C8A288] scale-125'
                                            : known.has(idx)
                                                ? 'bg-green-400'
                                                : unknown.has(idx)
                                                    ? 'bg-red-300'
                                                    : 'bg-[#E6D5CC]'
                                    }`}
                                />
                            ))}
                        </div>

                        {/* Flashcard */}
                        <div className="flex-1 w-full flex items-center justify-center min-h-[300px]">
                            <FlashCard
                                card={flashcards[currentIndex]}
                                index={currentIndex}
                                total={flashcards.length}
                                flipped={flipped}
                                onFlip={() => setFlipped(f => !f)}
                            />
                        </div>

                        {/* Navigation */}
                        <div className="w-full mt-6 space-y-3">
                            {/* Know / Don't Know Buttons */}
                            <div className="flex gap-3 justify-center">
                                <button
                                    onClick={markUnknown}
                                    className="flex items-center gap-2 px-5 py-2.5 bg-red-50 border-2 border-red-200 text-red-600 rounded-xl font-bold text-sm hover:bg-red-100 transition-colors"
                                >
                                    <X className="h-4 w-4" />
                                    Still Learning
                                </button>
                                <button
                                    onClick={markKnown}
                                    className="flex items-center gap-2 px-5 py-2.5 bg-green-50 border-2 border-green-200 text-green-600 rounded-xl font-bold text-sm hover:bg-green-100 transition-colors"
                                >
                                    <Check className="h-4 w-4" />
                                    Got It
                                </button>
                            </div>

                            {/* Prev / Next */}
                            <div className="flex items-center justify-between">
                                <button
                                    onClick={goPrev}
                                    disabled={currentIndex === 0}
                                    className="flex items-center gap-2 px-4 py-2 text-[#8a6a5c] hover:bg-[#E6D5CC]/50 rounded-lg transition-colors disabled:opacity-30 font-medium text-sm"
                                >
                                    <ArrowLeft className="h-4 w-4" />
                                    Previous
                                </button>
                                <button
                                    onClick={goNext}
                                    disabled={currentIndex === flashcards.length - 1}
                                    className="flex items-center gap-2 px-4 py-2 text-[#8a6a5c] hover:bg-[#E6D5CC]/50 rounded-lg transition-colors disabled:opacity-30 font-medium text-sm"
                                >
                                    Next
                                    <ArrowRight className="h-4 w-4" />
                                </button>
                            </div>
                        </div>

                        {/* Keyboard hints */}
                        <div className="mt-4 flex gap-4 text-[10px] text-[#8a6a5c] font-medium">
                            <span>Space: Flip</span>
                            <span>Arrow keys: Navigate</span>
                        </div>

                        {/* Completion banner */}
                        {totalReviewed === flashcards.length && flashcards.length > 0 && (
                            <div className="mt-6 w-full bg-gradient-to-r from-amber-500 to-orange-500 text-white rounded-2xl p-6 text-center">
                                <Layers className="h-10 w-10 mx-auto mb-2" />
                                <h4 className="text-lg font-bold mb-1">All Cards Reviewed!</h4>
                                <p className="text-sm opacity-90">
                                    {known.size} known, {unknown.size} to review again
                                </p>
                                {unknown.size > 0 && (
                                    <button
                                        onClick={resetCards}
                                        className="mt-3 px-4 py-2 bg-white/20 rounded-lg text-sm font-bold hover:bg-white/30 transition-colors"
                                    >
                                        Review Again
                                    </button>
                                )}
                            </div>
                        )}
                    </div>
                ) : null}
            </div>
        </div>
    );
};

export default TopicFlashcards;
