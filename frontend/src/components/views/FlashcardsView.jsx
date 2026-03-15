import React, { useState, useEffect, useCallback } from 'react';
import { Layers, Plus, Trash2, Edit2, Save, X, ChevronDown, Loader2, BookOpen, Sparkles, Shuffle, ChevronLeft, ChevronRight, RotateCcw } from 'lucide-react';
import { useToast } from '../../context/ToastContext';
import { getFlashcardSets, createFlashcardSet, deleteFlashcardSet, generateFlashcardsWithAI } from '../../api';

const FlashcardsView = ({ projectId, availableTopics, selectedDocuments }) => {
    const toast = useToast();
    const [flashcardSets, setFlashcardSets] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showCreateModal, setShowCreateModal] = useState(false);
    const [showAIModal, setShowAIModal] = useState(false);
    const [selectedSet, setSelectedSet] = useState(null);
    const [currentCardIndex, setCurrentCardIndex] = useState(0);
    const [isFlipped, setIsFlipped] = useState(false);
    const [aiGenerating, setAiGenerating] = useState(false);
    
    // Study tracking
    const [knownCards, setKnownCards] = useState(new Set());
    const [unknownCards, setUnknownCards] = useState(new Set());
    const [studyCards, setStudyCards] = useState([]); // possibly shuffled order
    
    // Create/Edit form state
    const [formData, setFormData] = useState({
        title: '',
        topic: '',
        cards: [{ front: '', back: '' }]
    });
    
    // AI generation form state
    const [aiFormData, setAiFormData] = useState({
        topic: '',
        customTopic: '',
        numCards: 10
    });

    useEffect(() => {
        fetchFlashcardSets();
    }, [projectId]);

    const fetchFlashcardSets = async () => {
        setLoading(true);
        try {
            const data = await getFlashcardSets(projectId);
            setFlashcardSets(data);
        } catch (error) {
            console.error('Failed to fetch flashcard sets:', error);
            toast.error('Failed to load flashcard sets');
        } finally {
            setLoading(false);
        }
    };

    const handleCreateSet = async () => {
        if (!formData.title.trim()) {
            toast.warning('Please enter a title');
            return;
        }
        
        const validCards = formData.cards.filter(card => card.front.trim() && card.back.trim());
        if (validCards.length === 0) {
            toast.warning('Please add at least one card');
            return;
        }

        try {
            await createFlashcardSet(
                projectId,
                formData.title,
                formData.topic || null,
                null,
                validCards
            );
            toast.success('Flashcard set created!');
            setShowCreateModal(false);
            setFormData({ title: '', topic: '', cards: [{ front: '', back: '' }] });
            fetchFlashcardSets();
        } catch (error) {
            console.error('Failed to create flashcard set:', error);
            toast.error('Failed to create flashcard set');
        }
    };

    const handleAIGenerate = async () => {
        const topic = aiFormData.topic === 'custom' ? aiFormData.customTopic : aiFormData.topic;
        
        if (!topic.trim()) {
            toast.warning('Please select or enter a topic');
            return;
        }
        
        if (selectedDocuments.length === 0) {
            toast.warning('Please select at least one document from the sidebar');
            return;
        }

        setAiGenerating(true);
        try {
            const result = await generateFlashcardsWithAI(
                projectId,
                topic,
                aiFormData.numCards,
                selectedDocuments
            );
            toast.success(`Generated ${result.card_count || result.cards?.length || 0} flashcards!`);
            setShowAIModal(false);
            setAiFormData({ topic: '', customTopic: '', numCards: 10 });
            await fetchFlashcardSets();
            // Auto-open the new set
            if (result) {
                startStudying(result);
            }
        } catch (error) {
            console.error('Failed to generate flashcards:', error);
            toast.error('Failed to generate flashcards');
        } finally {
            setAiGenerating(false);
        }
    };

    const handleDeleteSet = async (setId, e) => {
        if (e) e.stopPropagation();
        try {
            await deleteFlashcardSet(setId);
            toast.success('Flashcard set deleted');
            if (selectedSet?.id === setId) {
                setSelectedSet(null);
            }
            fetchFlashcardSets();
        } catch (error) {
            console.error('Failed to delete flashcard set:', error);
            toast.error('Failed to delete flashcard set');
        }
    };

    const addCard = () => {
        setFormData({
            ...formData,
            cards: [...formData.cards, { front: '', back: '' }]
        });
    };

    const updateCard = (index, field, value) => {
        const newCards = [...formData.cards];
        newCards[index][field] = value;
        setFormData({ ...formData, cards: newCards });
    };

    const removeCard = (index) => {
        if (formData.cards.length > 1) {
            const newCards = formData.cards.filter((_, i) => i !== index);
            setFormData({ ...formData, cards: newCards });
        }
    };

    const startStudying = (set) => {
        if (!set.cards || set.cards.length === 0) {
            toast.warning('This set has no cards');
            return;
        }
        setSelectedSet(set);
        setStudyCards([...set.cards]);
        setCurrentCardIndex(0);
        setIsFlipped(false);
        setKnownCards(new Set());
        setUnknownCards(new Set());
    };

    const shuffleCards = () => {
        const shuffled = [...studyCards].sort(() => Math.random() - 0.5);
        setStudyCards(shuffled);
        setCurrentCardIndex(0);
        setIsFlipped(false);
    };

    const nextCard = () => {
        if (currentCardIndex < studyCards.length - 1) {
            setCurrentCardIndex(currentCardIndex + 1);
            setIsFlipped(false);
        }
    };

    const previousCard = () => {
        if (currentCardIndex > 0) {
            setCurrentCardIndex(currentCardIndex - 1);
            setIsFlipped(false);
        }
    };

    const markKnown = () => {
        const cardId = studyCards[currentCardIndex]?.id;
        if (cardId) {
            setKnownCards(prev => new Set(prev).add(cardId));
            setUnknownCards(prev => { const s = new Set(prev); s.delete(cardId); return s; });
        }
        nextCard();
    };

    const markUnknown = () => {
        const cardId = studyCards[currentCardIndex]?.id;
        if (cardId) {
            setUnknownCards(prev => new Set(prev).add(cardId));
            setKnownCards(prev => { const s = new Set(prev); s.delete(cardId); return s; });
        }
        nextCard();
    };

    const resetStudy = () => {
        setCurrentCardIndex(0);
        setIsFlipped(false);
        setKnownCards(new Set());
        setUnknownCards(new Set());
        setStudyCards([...selectedSet.cards]);
    };

    // Keyboard shortcuts for study mode
    useEffect(() => {
        if (!selectedSet) return;
        const handleKeyDown = (e) => {
            if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); setIsFlipped(f => !f); }
            if (e.key === 'ArrowRight') { e.preventDefault(); nextCard(); }
            if (e.key === 'ArrowLeft') { e.preventDefault(); previousCard(); }
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [selectedSet, currentCardIndex, studyCards]);

    if (loading) {
        return (
            <div className="h-full flex items-center justify-center">
                <Loader2 className="h-8 w-8 text-[#C8A288] animate-spin" />
            </div>
        );
    }

    // Study Mode
    if (selectedSet && studyCards.length > 0) {
        const currentCard = studyCards[currentCardIndex];
        const progress = ((knownCards.size + unknownCards.size) / studyCards.length) * 100;
        const isLastCard = currentCardIndex === studyCards.length - 1;
        const allReviewed = knownCards.size + unknownCards.size === studyCards.length;

        return (
            <div className="h-full flex flex-col">
                {/* Study Header */}
                <div className="flex items-center justify-between px-4 md:px-6 py-3 border-b border-[#E6D5CC]/50 bg-white/50 shrink-0">
                    <div className="min-w-0">
                        <h2 className="text-lg font-bold text-[#4A3B32] truncate">{selectedSet.title}</h2>
                        <p className="text-xs text-[#8a6a5c]">
                            Card {currentCardIndex + 1} of {studyCards.length}
                            {knownCards.size > 0 && <span className="text-green-600 ml-2">Known: {knownCards.size}</span>}
                            {unknownCards.size > 0 && <span className="text-red-500 ml-2">Review: {unknownCards.size}</span>}
                        </p>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                        <button onClick={shuffleCards} className="p-2 text-[#8a6a5c] hover:bg-[#FDF6F0] rounded-lg transition-colors" title="Shuffle">
                            <Shuffle className="h-4 w-4" />
                        </button>
                        <button onClick={resetStudy} className="p-2 text-[#8a6a5c] hover:bg-[#FDF6F0] rounded-lg transition-colors" title="Reset">
                            <RotateCcw className="h-4 w-4" />
                        </button>
                        <button
                            onClick={() => setSelectedSet(null)}
                            className="px-3 py-1.5 text-sm text-[#8a6a5c] hover:bg-[#FDF6F0] rounded-lg transition-colors"
                        >
                            Exit
                        </button>
                    </div>
                </div>

                {/* Progress Bar */}
                <div className="h-1.5 bg-[#E6D5CC]/30">
                    <div
                        className="h-full bg-gradient-to-r from-[#C8A288] to-[#A08072] transition-all duration-300"
                        style={{ width: `${progress}%` }}
                    />
                </div>

                {/* Flashcard */}
                <div className="flex-1 flex items-center justify-center p-4 md:p-8">
                    {allReviewed ? (
                        // Completion summary
                        <div className="text-center max-w-md">
                            <div className="h-20 w-20 bg-gradient-to-br from-[#C8A288] to-[#A08072] rounded-full flex items-center justify-center mx-auto mb-6 shadow-lg">
                                <BookOpen className="h-10 w-10 text-white" />
                            </div>
                            <h3 className="text-2xl font-bold text-[#4A3B32] mb-2">Session Complete!</h3>
                            <div className="flex justify-center gap-6 mb-6">
                                <div className="text-center">
                                    <p className="text-3xl font-bold text-green-600">{knownCards.size}</p>
                                    <p className="text-sm text-[#8a6a5c]">Known</p>
                                </div>
                                <div className="text-center">
                                    <p className="text-3xl font-bold text-red-500">{unknownCards.size}</p>
                                    <p className="text-sm text-[#8a6a5c]">Need Review</p>
                                </div>
                            </div>
                            <div className="flex gap-3 justify-center">
                                <button onClick={resetStudy} className="px-5 py-2.5 bg-[#C8A288] text-white rounded-lg hover:bg-[#B08B72] transition-colors">
                                    Study Again
                                </button>
                                <button onClick={() => setSelectedSet(null)} className="px-5 py-2.5 border border-[#E6D5CC] rounded-lg hover:bg-[#FDF6F0] transition-colors">
                                    Back to Sets
                                </button>
                            </div>
                        </div>
                    ) : (
                        <div
                            onClick={() => setIsFlipped(!isFlipped)}
                            className="relative w-full max-w-2xl h-80 md:h-96 cursor-pointer"
                            style={{ perspective: '1000px' }}
                        >
                            <div
                                className="relative w-full h-full transition-transform duration-500"
                                style={{
                                    transformStyle: 'preserve-3d',
                                    transform: isFlipped ? 'rotateY(180deg)' : 'rotateY(0deg)',
                                }}
                            >
                                {/* Front */}
                                <div
                                    className="absolute inset-0 bg-white rounded-2xl border-2 border-[#C8A288] shadow-xl p-6 md:p-8 flex flex-col items-center justify-center"
                                    style={{ backfaceVisibility: 'hidden' }}
                                >
                                    <p className="text-xs text-[#8a6a5c] mb-4 uppercase tracking-wide font-semibold">Question</p>
                                    <p className="text-lg md:text-xl text-center text-[#4A3B32] leading-relaxed">{currentCard.front}</p>
                                    <p className="text-xs text-[#8a6a5c] mt-6">Click or press Space to flip</p>
                                </div>
                                {/* Back */}
                                <div
                                    className="absolute inset-0 bg-gradient-to-br from-[#C8A288] to-[#A08072] rounded-2xl border-2 border-[#C8A288] shadow-xl p-6 md:p-8 flex flex-col items-center justify-center"
                                    style={{ backfaceVisibility: 'hidden', transform: 'rotateY(180deg)' }}
                                >
                                    <p className="text-xs text-white/70 mb-4 uppercase tracking-wide font-semibold">Answer</p>
                                    <p className="text-lg md:text-xl text-center text-white leading-relaxed">{currentCard.back}</p>
                                    <p className="text-xs text-white/60 mt-6">Click or press Space to flip</p>
                                </div>
                            </div>
                        </div>
                    )}
                </div>

                {/* Navigation & Rating */}
                {!allReviewed && (
                    <div className="p-4 border-t border-[#E6D5CC]/50 bg-white/50 shrink-0">
                        <div className="max-w-2xl mx-auto">
                            {/* Rating buttons (only shown when flipped) */}
                            {isFlipped && (
                                <div className="flex gap-3 mb-3 justify-center">
                                    <button
                                        onClick={markUnknown}
                                        className="px-6 py-2.5 bg-red-50 text-red-600 border border-red-200 rounded-lg hover:bg-red-100 transition-colors text-sm font-medium"
                                    >
                                        Need Review
                                    </button>
                                    <button
                                        onClick={markKnown}
                                        className="px-6 py-2.5 bg-green-50 text-green-600 border border-green-200 rounded-lg hover:bg-green-100 transition-colors text-sm font-medium"
                                    >
                                        Got It!
                                    </button>
                                </div>
                            )}
                            
                            {/* Navigation */}
                            <div className="flex items-center justify-center gap-4">
                                <button
                                    onClick={previousCard}
                                    disabled={currentCardIndex === 0}
                                    className="p-2.5 bg-white border border-[#E6D5CC] rounded-lg hover:bg-[#FDF6F0] disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                                >
                                    <ChevronLeft className="h-5 w-5" />
                                </button>
                                <span className="text-sm text-[#8a6a5c] tabular-nums min-w-[60px] text-center">
                                    {currentCardIndex + 1} / {studyCards.length}
                                </span>
                                <button
                                    onClick={nextCard}
                                    disabled={isLastCard}
                                    className="p-2.5 bg-white border border-[#E6D5CC] rounded-lg hover:bg-[#FDF6F0] disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                                >
                                    <ChevronRight className="h-5 w-5" />
                                </button>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        );
    }

    // List View
    return (
        <div className="h-full overflow-y-auto custom-scrollbar p-4 md:p-8">
            <div className="max-w-6xl mx-auto">
                <div className="flex items-center justify-between mb-8">
                    <div>
                        <h2 className="text-2xl font-bold text-[#4A3B32]">Flashcards</h2>
                        <p className="text-[#8a6a5c]">Create and study flashcard sets</p>
                    </div>
                    <div className="flex gap-2">
                        <button
                            onClick={() => setShowAIModal(true)}
                            className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-[#C8A288] to-[#A08072] text-white rounded-lg hover:opacity-90 transition-opacity shadow-sm"
                        >
                            <Sparkles className="h-4 w-4" />
                            AI Generate
                        </button>
                        <button
                            onClick={() => setShowCreateModal(true)}
                            className="flex items-center gap-2 px-4 py-2 border border-[#E6D5CC] text-[#4A3B32] rounded-lg hover:bg-[#FDF6F0] transition-colors"
                        >
                            <Plus className="h-4 w-4" />
                            Manual
                        </button>
                    </div>
                </div>

                {flashcardSets.length === 0 ? (
                    <div className="text-center py-16">
                        <Layers className="h-16 w-16 text-[#E6D5CC] mx-auto mb-4" />
                        <h3 className="text-xl font-bold text-[#4A3B32] mb-2">No Flashcard Sets Yet</h3>
                        <p className="text-[#8a6a5c] mb-6">Create your first flashcard set to start studying</p>
                        <div className="flex gap-3 justify-center">
                            <button
                                onClick={() => setShowAIModal(true)}
                                className="px-6 py-3 bg-gradient-to-r from-[#C8A288] to-[#A08072] text-white rounded-lg hover:opacity-90 transition-opacity flex items-center gap-2"
                            >
                                <Sparkles className="h-5 w-5" />
                                Generate with AI
                            </button>
                            <button
                                onClick={() => setShowCreateModal(true)}
                                className="px-6 py-3 border border-[#E6D5CC] rounded-lg hover:bg-[#FDF6F0] transition-colors"
                            >
                                Create Manually
                            </button>
                        </div>
                    </div>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                        {flashcardSets.map((set) => (
                            <div
                                key={set.id}
                                onClick={() => startStudying(set)}
                                className="bg-white rounded-xl border border-[#E6D5CC] p-6 hover:shadow-lg transition-all cursor-pointer group"
                            >
                                <div className="flex items-start justify-between mb-3">
                                    <div className="flex-1 min-w-0">
                                        <h3 className="font-bold text-[#4A3B32] mb-1 truncate">{set.title}</h3>
                                        {set.topic && (
                                            <p className="text-sm text-[#8a6a5c] truncate">{set.topic}</p>
                                        )}
                                    </div>
                                    <button
                                        onClick={(e) => handleDeleteSet(set.id, e)}
                                        className="text-red-400 hover:text-red-600 p-1 opacity-0 group-hover:opacity-100 transition-opacity"
                                    >
                                        <Trash2 className="h-4 w-4" />
                                    </button>
                                </div>
                                <div className="flex items-center gap-3 mb-4">
                                    <div className="flex items-center gap-1.5 text-xs text-[#8a6a5c] bg-[#FDF6F0] px-2.5 py-1 rounded-full">
                                        <Layers className="h-3 w-3" />
                                        {set.card_count || set.cards?.length || 0} cards
                                    </div>
                                    {set.description && (
                                        <p className="text-xs text-[#8a6a5c] truncate">{set.description}</p>
                                    )}
                                </div>
                                <button
                                    onClick={(e) => { e.stopPropagation(); startStudying(set); }}
                                    className="w-full py-2 bg-[#C8A288] text-white rounded-lg hover:bg-[#B08B72] transition-colors text-sm font-medium"
                                >
                                    Study
                                </button>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* AI Generate Modal */}
            {showAIModal && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
                    <div className="bg-white rounded-2xl p-6 max-w-md w-full">
                        <div className="flex items-center justify-between mb-6">
                            <div className="flex items-center gap-2">
                                <Sparkles className="h-5 w-5 text-[#C8A288]" />
                                <h3 className="text-xl font-bold text-[#4A3B32]">AI Generate Flashcards</h3>
                            </div>
                            <button onClick={() => setShowAIModal(false)} className="p-2 hover:bg-[#FDF6F0] rounded-lg transition-colors">
                                <X className="h-5 w-5" />
                            </button>
                        </div>

                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-[#4A3B32] mb-2">Topic</label>
                                <select
                                    value={aiFormData.topic}
                                    onChange={(e) => setAiFormData({ ...aiFormData, topic: e.target.value })}
                                    className="w-full px-4 py-2 border border-[#E6D5CC] rounded-lg focus:ring-2 focus:ring-[#C8A288] outline-none"
                                >
                                    <option value="">Select a topic</option>
                                    {availableTopics.map((topic, idx) => (
                                        <option key={idx} value={topic}>{topic}</option>
                                    ))}
                                    <option value="custom">Custom Topic...</option>
                                </select>
                            </div>

                            {aiFormData.topic === 'custom' && (
                                <div>
                                    <label className="block text-sm font-medium text-[#4A3B32] mb-2">Custom Topic</label>
                                    <input
                                        type="text"
                                        value={aiFormData.customTopic}
                                        onChange={(e) => setAiFormData({ ...aiFormData, customTopic: e.target.value })}
                                        placeholder="Enter custom topic"
                                        className="w-full px-4 py-2 border border-[#E6D5CC] rounded-lg focus:ring-2 focus:ring-[#C8A288] outline-none"
                                    />
                                </div>
                            )}

                            <div>
                                <label className="block text-sm font-medium text-[#4A3B32] mb-2">Number of Cards</label>
                                <select
                                    value={aiFormData.numCards}
                                    onChange={(e) => setAiFormData({ ...aiFormData, numCards: parseInt(e.target.value) })}
                                    className="w-full px-4 py-2 border border-[#E6D5CC] rounded-lg focus:ring-2 focus:ring-[#C8A288] outline-none"
                                >
                                    <option value={5}>5 cards</option>
                                    <option value={8}>8 cards</option>
                                    <option value={10}>10 cards</option>
                                    <option value={15}>15 cards</option>
                                    <option value={20}>20 cards</option>
                                </select>
                            </div>

                            {selectedDocuments.length === 0 && (
                                <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
                                    <p className="text-sm text-amber-700">
                                        Please select at least one document from the sidebar
                                    </p>
                                </div>
                            )}
                        </div>

                        <div className="flex gap-3 mt-6">
                            <button
                                onClick={() => setShowAIModal(false)}
                                disabled={aiGenerating}
                                className="flex-1 py-2 border border-[#E6D5CC] rounded-lg hover:bg-[#FDF6F0] transition-colors disabled:opacity-50"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleAIGenerate}
                                disabled={aiGenerating}
                                className="flex-1 py-2 bg-gradient-to-r from-[#C8A288] to-[#A08072] text-white rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center justify-center gap-2"
                            >
                                {aiGenerating ? (
                                    <>
                                        <Loader2 className="h-4 w-4 animate-spin" />
                                        Generating...
                                    </>
                                ) : (
                                    <>
                                        <Sparkles className="h-4 w-4" />
                                        Generate
                                    </>
                                )}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Create Manual Modal */}
            {showCreateModal && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
                    <div className="bg-white rounded-2xl p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto">
                        <div className="flex items-center justify-between mb-6">
                            <h3 className="text-xl font-bold text-[#4A3B32]">Create Flashcard Set</h3>
                            <button
                                onClick={() => setShowCreateModal(false)}
                                className="p-2 hover:bg-[#FDF6F0] rounded-lg transition-colors"
                            >
                                <X className="h-5 w-5" />
                            </button>
                        </div>

                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-[#4A3B32] mb-2">Title</label>
                                <input
                                    type="text"
                                    value={formData.title}
                                    onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                                    placeholder="e.g., Biology Chapter 3"
                                    className="w-full px-4 py-2 border border-[#E6D5CC] rounded-lg focus:ring-2 focus:ring-[#C8A288] outline-none"
                                />
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-[#4A3B32] mb-2">Topic (Optional)</label>
                                <select
                                    value={formData.topic}
                                    onChange={(e) => setFormData({ ...formData, topic: e.target.value })}
                                    className="w-full px-4 py-2 border border-[#E6D5CC] rounded-lg focus:ring-2 focus:ring-[#C8A288] outline-none"
                                >
                                    <option value="">Select a topic</option>
                                    {availableTopics.map((topic, idx) => (
                                        <option key={idx} value={topic}>{topic}</option>
                                    ))}
                                </select>
                            </div>

                            <div>
                                <div className="flex items-center justify-between mb-2">
                                    <label className="block text-sm font-medium text-[#4A3B32]">Cards</label>
                                    <button
                                        onClick={addCard}
                                        className="text-sm text-[#C8A288] hover:text-[#B08B72] font-medium"
                                    >
                                        + Add Card
                                    </button>
                                </div>
                                <div className="space-y-4">
                                    {formData.cards.map((card, index) => (
                                        <div key={index} className="border border-[#E6D5CC] rounded-lg p-4">
                                            <div className="flex items-center justify-between mb-2">
                                                <span className="text-sm font-medium text-[#8a6a5c]">Card {index + 1}</span>
                                                {formData.cards.length > 1 && (
                                                    <button
                                                        onClick={() => removeCard(index)}
                                                        className="text-red-500 hover:text-red-600"
                                                    >
                                                        <Trash2 className="h-4 w-4" />
                                                    </button>
                                                )}
                                            </div>
                                            <input
                                                type="text"
                                                value={card.front}
                                                onChange={(e) => updateCard(index, 'front', e.target.value)}
                                                placeholder="Front (Question)"
                                                className="w-full px-3 py-2 border border-[#E6D5CC] rounded-lg mb-2 focus:ring-2 focus:ring-[#C8A288] outline-none"
                                            />
                                            <textarea
                                                value={card.back}
                                                onChange={(e) => updateCard(index, 'back', e.target.value)}
                                                placeholder="Back (Answer)"
                                                rows={2}
                                                className="w-full px-3 py-2 border border-[#E6D5CC] rounded-lg focus:ring-2 focus:ring-[#C8A288] outline-none resize-none"
                                            />
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>

                        <div className="flex gap-3 mt-6">
                            <button
                                onClick={() => setShowCreateModal(false)}
                                className="flex-1 py-2 border border-[#E6D5CC] rounded-lg hover:bg-[#FDF6F0] transition-colors"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleCreateSet}
                                className="flex-1 py-2 bg-[#C8A288] text-white rounded-lg hover:bg-[#B08B72] transition-colors"
                            >
                                Create Set
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default FlashcardsView;
