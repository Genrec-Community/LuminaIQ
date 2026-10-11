// Companion characters, avatars and friendly copy shared across the app.
// The selected character is stored in settings (aiCharacter) and the backend
// turns it into tutoring instructions (see backend/api/v1/endpoints/chat.py).

export const AI_CHARACTERS = {
    buddy: {
        label: 'Cheerful Buddy',
        emoji: '😄',
        tagline: 'Hypes you up, explains like a friend, loves a good pun.',
        cheers: ['Nailed it!', "You're on fire! 🔥", 'Big brain energy!', 'Look at you go!', 'Too easy for you 😎'],
        consoles: ["Close one! Let's lock it in.", 'Mistakes = brain gains 💪', "No stress — now you'll never forget it.", 'Good try! Peek at why below.'],
        greet: (n) => `Hey ${n}! Ready to make your brain a little bit bigger today? 🚀`,
    },
    mentor: {
        label: 'Wise Mentor',
        emoji: '🦉',
        tagline: 'Calm, patient, and always asks the question behind the question.',
        cheers: ['Well reasoned.', 'Exactly right.', 'Your understanding is deepening.', 'Precisely.'],
        consoles: ['A valuable mistake — study the explanation.', "Understanding grows from this. Let's review.", 'Not quite. Notice the subtle difference.'],
        greet: (n) => `Welcome back, ${n}. Small steps every day build mastery.`,
    },
    coach: {
        label: 'Hype Coach',
        emoji: '🏆',
        tagline: 'High energy, goal-focused, treats every quiz like a final.',
        cheers: ["THAT'S A POINT! 🏆", 'Champion move!', 'Keep that streak alive!', 'Unstoppable!'],
        consoles: ['Shake it off, next rep!', "Champions miss too. Learn it, crush it.", 'Reset. Refocus. Go again!'],
        greet: (n) => `Let's GO, ${n}! Today we train like it's exam day. 💪`,
    },
    sage: {
        label: 'Zen Sage',
        emoji: '🍵',
        tagline: 'Gentle and soothing. Perfect when exams feel stressful.',
        cheers: ['Beautiful.', 'Calm mind, clear answer. 🌿', 'Lovely work.', 'Well done, breathe it in.'],
        consoles: ["It's okay. Every leaf falls before it grows back. 🍃", 'Gently noted. You will remember this.', 'No rush. Read why, then move on.'],
        greet: (n) => `Hello ${n}. Take a breath — we'll learn one calm step at a time. 🌿`,
    },
    scientist: {
        label: 'Curious Scientist',
        emoji: '🧪',
        tagline: 'Obsessed with how things work, full of real-world examples.',
        cheers: ['Hypothesis confirmed! ✅', 'Experimentally verified!', 'Fascinating — and correct!', 'Eureka!'],
        consoles: ['Interesting result! Let us analyse the data.', 'Failed experiments teach the most.', 'Unexpected outcome — check the explanation!'],
        greet: (n) => `Greetings, ${n}! What shall we discover today? 🔬`,
    },
    pirate: {
        label: 'Pirate Captain',
        emoji: '🏴‍☠️',
        tagline: 'Arr! Turns studying into a treasure hunt. Great for younger learners.',
        cheers: ['Arr, treasure found! 💰', 'Ye be a fine scholar!', 'Shiver me timbers, correct!', 'Gold for the captain!'],
        consoles: ['Arr, the map was tricky there.', "Even pirates take wrong turns, matey.", 'Back to the map, scallywag!'],
        greet: (n) => `Ahoy, ${n}! Ready to hunt for knowledge treasure? 🗺️`,
    },
};

export const USER_AVATARS = ['🦊', '🐼', '🦁', '🐯', '🐨', '🐸', '🦄', '🐙', '🐧', '🦉', '🐻', '🐶', '🐱', '🐵', '🌟', '🚀', '🎧', '🎨', '⚽', '🧠'];
export const AI_AVATARS = ['✨', '🤖', '🦉', '🧙', '🐉', '👾', '🦊', '🌙', '🔮', '🪐', '🍵', '🏴‍☠️', '🧪', '🏆', '😄', '🐲'];

export const AGE_GROUPS = {
    teen: { label: 'Teen (13–17)', hint: 'School & board exams' },
    young: { label: 'College (18–24)', hint: 'Uni, entrance & competitive exams' },
    adult: { label: 'Professional (25–45)', hint: 'Certifications & upskilling' },
    mature: { label: 'Lifelong learner (45+)', hint: 'Learning for the joy of it' },
};

export const getCharacter = (key) => AI_CHARACTERS[key] || AI_CHARACTERS.buddy;

export const displayName = (settings, user) =>
    settings?.nickname || settings?.studentName || user?.full_name?.split(' ')[0] || 'friend';

export const aiName = (settings) => settings?.aiName?.trim() || 'Lumi';

export const pick = (arr) => arr[Math.floor(Math.random() * arr.length)];

export const timeGreeting = () => {
    const h = new Date().getHours();
    if (h < 5) return 'Burning the midnight oil';
    if (h < 12) return 'Good morning';
    if (h < 17) return 'Good afternoon';
    if (h < 21) return 'Good evening';
    return 'Night owl mode';
};

export const daysUntil = (dateStr) => {
    if (!dateStr) return null;
    const target = new Date(dateStr + 'T00:00:00');
    if (isNaN(target)) return null;
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return Math.round((target - today) / 86400000);
};
