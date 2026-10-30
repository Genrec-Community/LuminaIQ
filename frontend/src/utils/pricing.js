// Marketing copy for the plans (limits mirror backend/services/plans.py).
export const STUDENT_PLANS = [
    {
        key: 'free',
        name: 'Free',
        monthly: 0,
        yearly: 0,
        tagline: 'Try the whole thing',
        features: [
            '3 books',
            '20 chat answers a day',
            '60 quiz & Power Hour questions a day',
            '20 notes, flashcards & summaries a day',
            'Exam Tonight plans + 30 cram cards a month',
            '3 Visual Lab simulations a month',
            'Learning path, themes and your AI buddy',
        ],
    },
    {
        key: 'scholar',
        name: 'Scholar',
        monthly: 299,
        yearly: 2499,
        tagline: 'For steady, everyday study',
        popular: true,
        features: [
            'A smarter AI model than Free',
            '15 books',
            '60 chat answers a day',
            '300 quiz & Power Hour questions a day',
            '60 notes, flashcards & summaries a day',
            'Unlimited Exam Tonight plans, 300 cram cards a month',
            '15 Visual Lab simulations a month',
        ],
    },
    {
        key: 'topper',
        name: 'Topper',
        monthly: 999,
        yearly: 8499,
        tagline: 'For aiming at the top rank',
        features: [
            'Our best AI model for every answer',
            'Unlimited books',
            'Deep mode: 200 answers a month from our most capable model',
            '100 chat answers a day',
            '1,000 quiz & Power Hour questions a day',
            'Cram cards written by the Deep model',
            '40 Visual Lab simulations a month',
        ],
    },
];

export const INSTITUTION_PLAN = {
    key: 'institution',
    name: 'Institution',
    perSeat: 179,
    minSeats: 100,
    tagline: 'For schools and coaching institutes',
    features: [
        'Every student gets Scholar-level access plus 50 Deep answers a month',
        'Teachers publish books to whole classes',
        'Class dashboard: progress, weak topics and activity',
        'Student sign-ins, invite codes and seat management',
    ],
};

export const EXAM_NIGHT_PASS = { price: 49, hours: 48 };

export const yearlySaving = (p) => (p.monthly ? Math.round((1 - p.yearly / (p.monthly * 12)) * 100) : 0);

export const inr = (n) => `₹${Number(n).toLocaleString('en-IN')}`;

// Per-file upload limit; keep in step with MAX_FILE_SIZE on the backend
export const MAX_UPLOAD_MB = 50;
