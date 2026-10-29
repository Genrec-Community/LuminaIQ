// All visible content for the Lumina IQ site lives here.
//
// Assumptions (mirrored in the hand-off; replace before launch):
// - appUrl / loginUrl: taken from the app repo (Genrec-Community/LuminaIQ): its own landing
//   page sends every CTA to /dashboard, which asks logged-out visitors to sign in.
// - email: the support address from the Play Store listing.
// - Prices: the app's plans (backend/services/plans.py), yearly saves about 30%.
// - Stats: the figures the current luminaiq.fun site reports, shown as reported.
// - Photos: real product screens from the app (public/shots), with sample study content;
//   swap in student photography later if wanted.
// - The YouTube video is presented as the product walkthrough.
// - Example study content (photosynthesis) is invented to demonstrate the tools.

// Where this marketing site is served. Canonical URLs, the sitemap and the share image all use it.
// Set NEXT_PUBLIC_SITE_URL when the site moves to its own domain (for example https://luminaiq.fun).
const siteUrl = (
  process.env.NEXT_PUBLIC_SITE_URL ||
  (process.env.VERCEL_PROJECT_PRODUCTION_URL ? `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}` : 'https://luminaiq-website.vercel.app')
).replace(/\/$/, '');

export const site = {
  name: 'Lumina IQ',
  url: siteUrl,
  tagline: 'The AI study companion that remembers when you will forget',
  description:
    'Lumina IQ turns your PDFs, textbooks and lecture notes into cited answers, quizzes, notes, flashcards and a spaced repetition schedule. Start free.',
  // Same-origin by default: the site is served in front of the app, so test stays on test
  appUrl: process.env.NEXT_PUBLIC_APP_URL || '/dashboard',
  loginUrl: process.env.NEXT_PUBLIC_LOGIN_URL || '/login',
  email: 'support@luminaiq.fun',
  maker: { name: 'GenrecAI', url: 'https://www.genrecai.com' },
  youtubeId: 'uLXTLmunK0g',
  nav: [
    { href: '/features/', label: 'Features' },
    { href: '/how-it-works/', label: 'How it works' },
    { href: '/pricing/', label: 'Pricing' },
    { href: '/about/', label: 'About' },
  ],
};

export const stats = [
  { value: 12000, suffix: '+', label: 'active learners' },
  { value: 50000, suffix: '+', label: 'documents studied' },
  { value: 4.9, suffix: '/5', label: 'average rating from 2,000+ students', decimals: 1 },
  { value: 30, prefix: '<', suffix: ' s', label: 'from upload to your first quiz' },
];

/** Review days for a topic you keep remembering: each right answer makes the next gap longer. */
export const reviewDays = [1, 6, 15, 38, 95];

// Real product screens (frontend/website/public/shots), captured from the app with sample
// study material. `id` is kept for Unsplash photos; `src` marks a self-hosted product shot.
export type Photo = { id: string; alt: string; src?: string; placeholder?: boolean };
const shot = (file: string, alt: string): Photo => ({ id: file, src: `/shots/${file}`, alt });
export const photos = {
  hero: shot('feed.webp', 'The Lumina IQ phone app: a quick question on where the light reactions happen, answered correctly'),
  college: shot('dashboard.webp', 'The Lumina IQ dashboard: a greeting, today\'s numbers and quests, and the books on the shelf'),
  medlaw: shot('phone-home.webp', 'The phone home screen: a getting-started checklist and today\'s review feed'),
  teachers: shot('learning-path.webp', 'The learning path: the next topic to learn, why it comes next, and the memory curve'),
  self: shot('exam-tonight.webp', 'Exam Tonight: pick how much time you have and get a plan that fits'),
  books: shot('library.webp', 'The phone library: a shelf of books, one per subject'),
  group: shot('memory-curve.webp', 'The memory curve on the dashboard: what you keep with reviews and what you lose without them'),
} satisfies Record<string, Photo>;

export type Stage = 'Understand' | 'Practise' | 'Measure' | 'Revise';

export type Tool = {
  slug: string;
  name: string;
  stage: Stage;
  line: string; // one line for the index
  body: string; // a short paragraph for the features page
  points: string[];
};

export const tools: Tool[] = [
  {
    slug: 'chat',
    name: 'Chat with your documents',
    stage: 'Understand',
    line: 'Ask in your own words. The answer comes from your file, with the page it came from.',
    body: 'Upload a chapter and ask it anything. Lumina IQ answers from your material, not from the open internet, and shows the passage it used so you can check it in seconds.',
    points: ['Answers grounded in your upload', 'Source citations on every answer', 'Follow-up questions keep context'],
  },
  {
    slug: 'quizzes',
    name: 'Quiz generator',
    stage: 'Practise',
    line: 'Multiple choice and written questions, by topic and difficulty, graded for you.',
    body: 'Pick a topic and a difficulty and get questions written from your document. Multiple choice is graded instantly; written answers get feedback on what you missed.',
    points: ['Multiple choice and subjective questions', 'Choose topic and difficulty', 'Automatic grading'],
  },
  {
    slug: 'notes',
    name: 'Four kinds of notes',
    stage: 'Understand',
    line: 'A full summary, key facts, a glossary and an exam cheat sheet from the same chapter.',
    body: 'Different moments need different notes. Read the comprehensive summary the first time, the key facts the night before, the glossary when terms blur, and the cheat sheet on the way in.',
    points: ['Comprehensive summary', 'Key facts', 'Glossary', 'Exam cheat sheet'],
  },
  {
    slug: 'flashcards',
    name: 'Flashcards',
    stage: 'Practise',
    line: 'Question and answer cards made for you. Flip, shuffle, mark what you know.',
    body: 'Cards are written from your document, so they test what your course actually covers. Shuffle the deck, flip a card, and mark it known or not yet. The not-yets come back first.',
    points: ['Generated question and answer pairs', 'Shuffle and 3D flip', 'Known and unknown tracking'],
  },
  {
    slug: 'mind-maps',
    name: 'Visual mind maps',
    stage: 'Understand',
    line: 'See how the concepts connect. Zoom in on a branch, pan across the chapter.',
    body: 'Facts stick better when you can see where they hang. Mind maps lay out a chapter as a map of ideas and the links between them, and you can zoom and pan through it.',
    points: ['Concepts and their relationships', 'Zoom and pan', 'Built from your document'],
  },
  {
    slug: 'learning-paths',
    name: 'Personalized learning paths',
    stage: 'Measure',
    line: 'Topics in prerequisite order, with your weak areas pulled to the front.',
    body: 'Lumina IQ orders topics so each one builds on the last, then uses your quiz results to surface the parts you are weakest on. You always know what to study next.',
    points: ['Prerequisite ordering', 'Weak areas surfaced', 'Progress analytics'],
  },
  {
    slug: 'spaced-repetition',
    name: 'Spaced repetition',
    stage: 'Revise',
    line: 'Each topic comes back just before you would forget it.',
    body: 'Lumina IQ estimates how well you know each topic and how fast it is fading, and brings it back just before it slips: after a day, then about a week, then longer each time you remember. Topics you miss come back sooner.',
    points: ['A memory model for every topic', 'Gaps that grow as you remember', 'Missed topics come back sooner'],
  },
  {
    slug: 'progress',
    name: 'Gamified progress',
    stage: 'Revise',
    line: 'XP, levels, badges and streaks. A reason to open it again tomorrow.',
    body: 'Consistency beats cramming, so Lumina IQ rewards it. Earn XP for reviews and quizzes, level up, collect badges and keep a daily streak alive.',
    points: ['XP and levels', 'Badges', 'Daily streaks'],
  },
];

export const loop: { stage: Stage; title: string; text: string; tools: string[] }[] = [
  {
    stage: 'Understand',
    title: 'Understand it',
    text: 'Ask your document the questions you would ask a tutor, read the summary, and see the chapter as a map before you try to memorize any of it.',
    tools: ['chat', 'notes', 'mind-maps'],
  },
  {
    stage: 'Practise',
    title: 'Practise it',
    text: 'Pulling an answer out of memory is what makes it stay. Quizzes and flashcards make you do the pulling, on your own material.',
    tools: ['quizzes', 'flashcards'],
  },
  {
    stage: 'Measure',
    title: 'Measure it',
    text: 'Every answer is data. Lumina IQ finds the topics you keep missing and moves them to the front of your path.',
    tools: ['learning-paths'],
  },
  {
    stage: 'Revise',
    title: 'Revise it, on time',
    text: 'Reviews arrive on day 1, day 6, day 15 and further apart each time you remember. Short sessions, spread out, instead of one long night.',
    tools: ['spaced-repetition', 'progress'],
  },
];

export const pipeline = [
  {
    title: 'Upload',
    text: 'Drop in a PDF, DOCX or TXT: a textbook chapter, lecture slides exported to PDF, your own notes.',
    why: 'You study your course, not a generic version of the subject.',
  },
  {
    title: 'Extract',
    text: 'The text is pulled out of the file. Scanned pages go through OCR so photographed handouts work too.',
    why: 'Nothing on the page is lost because it was an image.',
  },
  {
    title: 'Chunk and embed',
    text: 'The material is split into short passages, and each passage becomes a vector that captures its meaning.',
    why: 'Meaning, not keywords, decides what is relevant.',
  },
  {
    title: 'Index',
    text: 'The vectors are stored in a vector database, searchable by meaning across your whole library.',
    why: 'A question finds the right page even when it uses different words.',
  },
  {
    title: 'Retrieve and generate',
    text: 'The passages that match go to the model, which writes the answer, quiz, notes or map and cites where each part came from.',
    why: 'Every output can be traced back to your material.',
  },
];

export type Plan = {
  id: 'free' | 'scholar' | 'topper';
  name: string;
  monthly: number;
  annualPerMonth: number; // the yearly price divided by 12
  yearly: number;
  who: string;
  includesLabel: string;
  features: string[];
  cta: string;
  href: string;
  popular?: boolean;
};

// Mirrors the app's plans (backend/services/plans.py, frontend/src/utils/pricing.js).
export const plans: Plan[] = [
  {
    id: 'free',
    name: 'Free',
    monthly: 0,
    annualPerMonth: 0,
    yearly: 0,
    who: 'Try the whole thing, no card needed',
    includesLabel: 'What you get',
    features: ['3 books', '20 chat answers a day', '60 quiz and Power Hour questions a day', '20 notes, flashcards and summaries a day', 'Exam Tonight plans and 30 cram cards a month', 'Learning path, reviews and your AI study buddy'],
    cta: 'Start free',
    href: '/login?signup=1',
  },
  {
    id: 'scholar',
    name: 'Scholar',
    monthly: 299,
    annualPerMonth: 208,
    yearly: 2499,
    who: 'For steady, everyday study',
    includesLabel: 'Everything in Free, plus',
    features: ['A smarter AI model', '15 books', '60 chat answers a day', '300 quiz and Power Hour questions a day', '60 notes, flashcards and summaries a day', 'Unlimited Exam Tonight plans, 300 cram cards a month', '15 Visual Lab simulations a month'],
    cta: 'Get Scholar',
    href: '/plans?plan=scholar',
    popular: true,
  },
  {
    id: 'topper',
    name: 'Topper',
    monthly: 999,
    annualPerMonth: 708,
    yearly: 8499,
    who: 'For aiming at the top rank',
    includesLabel: 'Everything in Scholar, plus',
    features: ['Our best AI model for every answer', 'Unlimited books', 'Deep mode: 200 answers a month from our most capable model', '100 chat answers a day', '1,000 quiz and Power Hour questions a day', 'Cram cards written by the Deep model', '40 Visual Lab simulations a month'],
    cta: 'Get Topper',
    href: '/plans?plan=topper',
  },
];

/** One night of Topper for the exam you did not see coming. */
export const examNightPass = { price: 49, hours: 48, href: '/plans#pass' };
/** Schools and coaching institutes: per seat, per month. */
export const institution = { perSeat: 179, minSeats: 100, href: '/institution' };

export const comparison: { row: string; free: string | boolean; scholar: string | boolean; topper: string | boolean }[] = [
  { row: 'Books', free: '3', scholar: '15', topper: 'Unlimited' },
  { row: 'Chat answers with citations', free: '20 a day', scholar: '60 a day', topper: '100 a day' },
  { row: 'Quiz and Power Hour questions', free: '60 a day', scholar: '300 a day', topper: '1,000 a day' },
  { row: 'Notes, flashcards and summaries', free: '20 a day', scholar: '60 a day', topper: '150 a day' },
  { row: 'Exam Tonight cram cards', free: '30 a month', scholar: '300 a month', topper: '1,000 a month' },
  { row: 'Visual Lab simulations', free: '3 a month', scholar: '15 a month', topper: '40 a month' },
  { row: 'Learning path and reviews', free: true, scholar: true, topper: true },
  { row: 'Mind maps and knowledge graph', free: true, scholar: true, topper: true },
  { row: 'Smarter AI model', free: false, scholar: true, topper: 'Our best' },
  { row: 'Deep mode answers', free: false, scholar: false, topper: '200 a month' },
];

export const faqs = [
  {
    q: 'What can I upload?',
    a: 'PDF, Word and text files, or paste text straight in. Scanned PDFs are run through OCR, so photographed handouts work too. Each file can be up to 50 MB.',
  },
  {
    q: 'Does Lumina IQ make things up?',
    a: 'Answers are generated from the passages it retrieves from your own document, and each answer cites the passage it used. If something looks wrong, the citation takes you straight to the source to check.',
  },
  {
    q: 'How does Lumina IQ decide when I review?',
    a: 'It keeps an estimate of how well you know each topic and how fast you are forgetting it. Each topic comes back just before you are likely to forget it, and every review you get right makes the memory last longer, so the gaps grow. Topics you miss come back sooner.',
  },
  {
    q: 'How is this different from a general chatbot?',
    a: 'A chatbot answers from everything it was trained on. Lumina IQ answers from your material and then keeps going: it turns that material into practice, tracks what you miss, and schedules your reviews.',
  },
  {
    q: 'Can a school or teacher use it with a class?',
    a: 'Yes. The Institution plan is ₹179 per student a month (from 100 seats). Every student gets Scholar-level access, teachers publish books to whole classes, and a class dashboard shows progress and weak topics.',
  },
  {
    q: 'What is the Exam Night Pass?',
    a: 'Exam tomorrow and on the Free plan? ₹49 gives you 48 hours of Topper: Deep answers, unlimited books and Deep cram cards for the night that counts. One payment, nothing renews.',
  },
];

export const audiences = [
  { key: 'college', title: 'College students', text: 'Lecture PDFs, textbooks and slides become summaries, quizzes and revision cards the same evening.' },
  { key: 'medlaw', title: 'Medical and law students', text: 'Dense reading, heavy terminology, a lot to recall. Notes, flashcards and well-timed reviews were made for this.' },
  { key: 'teachers', title: 'Teachers', text: 'Publish your own handouts to a whole class and follow progress and weak topics on the class dashboard.' },
  { key: 'self', title: 'Self-learners', text: 'Technical manuals and online courses, turned into something you can question and practise.' },
] as const;
