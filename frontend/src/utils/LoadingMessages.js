// src/utils/LoadingMessages.js

const loadingMessagesList = [
    "Bribing neurons with virtual coffee...",
    "Convincing the AI you read the material...",
    "Cooking your learning path.",
    "Reading the textbook so you don't have to.",
    "Chunking data into bite-sized pieces.",
    "Equipping flashcards for the boss fight...",
    "Recalculating your academic route...",
    "Distilling text into pure knowledge.",
    "Embedding vectors for your brain.",
    "Calculating the optimal study strategy.",
    "Watering concepts so they actually grow.",
    "Mining your PDFs for diamonds.",
    "Locating the chapter you ignored...",
    "Navigating you away from the cliff.",
    "Organizing an academic intervention.",
    "Brewing extreme comprehension potion...",
    "Translating professor-speak into English.",
    "Feeding the knowledge graph.",
    "Compressing reality into vectors.",
    "Downloading brain updates...",
    "Summoning the study ghost.",
    "Polishing the learning gems.",
    "Connecting the dots for you.",
    "Squeezing truth from text.",
    "Building your neural network.",
    "Unscrambling the alphabet soup.",
    "Assembling the puzzle pieces.",
    "Mapping the academic terrain.",
    "Hunting for key concepts.",
    "Aligning your chakras of knowledge.",
    "Defeating procrastination demons.",
    "Upgrading your mental RAM.",
    "Siphoning wisdom from pages.",
    "Constructing your study fortress.",
    "Igniting the spark of genius.",
    "Decoding the matrix of text."
];

export const getRandomLoadingMessage = () => {
    const randomIndex = Math.floor(Math.random() * loadingMessagesList.length);
    return loadingMessagesList[randomIndex];
};

/**
 * Hook or utility for getting a rotating loading message
 */
export const getRotatingLoadingMessage = (currentIndex) => {
    // Cycles through the array incrementally to avoid immediate repeats
    return loadingMessagesList[currentIndex % loadingMessagesList.length];
};
