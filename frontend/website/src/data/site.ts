// All visible content for the LuminaIQ site lives here.
//
// Assumptions (mirrored in the hand-off; replace before launch):
// - appUrl / loginUrl: taken from the app repo (Genrec-Community/LuminaIQ): its own landing
//   page sends every CTA to /dashboard, which asks logged-out visitors to sign in.
// - email: contact address was not provided.                                     placeholder
// - Annual prices: not published; set to "two months free".                      placeholder
// - Stats: the figures the current luminaiq.fun site reports, shown as reported.
// - Photos: Unsplash (free license), hotlinked and duotoned. Illustrative only;
//   replace with real product and student photography.                            placeholder
// - The YouTube video is presented as the product walkthrough.
// - Example study content (photosynthesis) is invented to demonstrate the tools.

// Where this marketing site is served. Canonical URLs, the sitemap and the share image all use it.
// Set NEXT_PUBLIC_SITE_URL when the site moves to its own domain (for example https://luminaiq.fun).
const siteUrl = (
  process.env.NEXT_PUBLIC_SITE_URL ||
  (process.env.VERCEL_PROJECT_PRODUCTION_URL ? `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}` : 'https://luminaiq-website.vercel.app')
).replace(/\/$/, '');

export const site = {
  name: 'LuminaIQ',
  url: siteUrl,
  tagline: 'The AI study companion that remembers when you will forget',
  description:
    'LuminaIQ turns your PDFs, textbooks and lecture notes into cited answers, quizzes, notes, flashcards and a spaced repetition schedule. Start free.',
  // Same-origin by default: the site is served in front of the app, so test stays on test
  appUrl: process.env.NEXT_PUBLIC_APP_URL || '/dashboard',
  loginUrl: process.env.NEXT_PUBLIC_LOGIN_URL || '/login',
  email: 'hello@luminaiq.fun', // placeholder
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

/** SM-2 intervals with the default ease factor of 2.5: 1, 6, then the previous interval × 2.5. */
export const reviewDays = [1, 6, 15, 38, 95];

export type Photo = { id: string; alt: string; placeholder?: boolean };
const u = (id: string) => id;
export const photos = {
  hero: { id: u('photo-1513258496099-48168024aec0'), alt: 'A student studying at a desk with an open laptop and notes', placeholder: true },
  college: { id: u('photo-1522202176988-66273c2fd55f'), alt: 'College students studying together around a laptop', placeholder: true },
  medlaw: { id: u('photo-1481627834876-b7833e8f5570'), alt: 'Rows of books on library shelves', placeholder: true },
  teachers: { id: u('photo-1524178232363-1fb2b075b655'), alt: 'A lecture hall with students listening to a teacher', placeholder: true },
  self: { id: u('photo-1434030216411-0b793f4b4173'), alt: 'Someone writing study notes by hand next to a laptop', placeholder: true },
  books: { id: u('photo-1497633762265-9d179a990aa6'), alt: 'A stack of textbooks on a table', placeholder: true },
  group: { id: u('photo-1523240795612-9a054b0db644'), alt: 'A small study group working through material together', placeholder: true },
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
    body: 'Upload a chapter and ask it anything. LuminaIQ answers from your material, not from the open internet, and shows the passage it used so you can check it in seconds.',
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
    body: 'LuminaIQ orders topics so each one builds on the last, then uses your quiz results to surface the parts you are weakest on. You always know what to study next.',
    points: ['Prerequisite ordering', 'Weak areas surfaced', 'Progress analytics'],
  },
  {
    slug: 'spaced-repetition',
    name: 'Spaced repetition',
    stage: 'Revise',
    line: 'SM-2 scheduling brings each card back just before you would forget it.',
    body: 'Every review is graded, and the SM-2 algorithm uses that grade to set the next interval: one day, then six, then longer each time you remember. Cards you miss start again.',
    points: ['SM-2 algorithm', 'Intervals that grow as you remember', 'Missed cards reset to day one'],
  },
  {
    slug: 'progress',
    name: 'Gamified progress',
    stage: 'Revise',
    line: 'XP, levels, badges and streaks. A reason to open it again tomorrow.',
    body: 'Consistency beats cramming, so LuminaIQ rewards it. Earn XP for reviews and quizzes, level up, collect badges and keep a daily streak alive.',
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
    text: 'Every answer is data. LuminaIQ finds the topics you keep missing and moves them to the front of your path.',
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
  id: 'free' | 'pro' | 'team';
  name: string;
  monthly: number;
  annualPerMonth: number; // placeholder for pro and team
  who: string;
  includesLabel: string;
  features: string[];
  cta: string;
  popular?: boolean;
};

export const plans: Plan[] = [
  {
    id: 'free',
    name: 'Free',
    monthly: 0,
    annualPerMonth: 0,
    who: 'For trying it on your next chapter',
    includesLabel: 'What you get',
    features: ['Up to 3 documents', 'Unlimited chat and quizzes', 'Basic notes and flashcards', '7-day spaced repetition window'],
    cta: 'Start free',
  },
  {
    id: 'pro',
    name: 'Pro',
    monthly: 9,
    annualPerMonth: 7.5, // placeholder
    who: 'For students who study every week',
    includesLabel: 'Everything in Free, plus',
    features: ['Unlimited documents', 'All four note types', 'Full learning path and analytics', 'Unlimited spaced repetition', 'Mind maps and knowledge graph', 'Priority AI processing'],
    cta: 'Go Pro',
    popular: true,
  },
  {
    id: 'team',
    name: 'Team',
    monthly: 29,
    annualPerMonth: 24, // placeholder
    who: 'For study groups and classes',
    includesLabel: 'Everything in Pro, plus',
    features: ['Up to 10 members', 'Shared document library', 'Collaborative flashcards', 'Teacher dashboard'],
    cta: 'Start a team',
  },
];

export const comparison: { row: string; free: string | boolean; pro: string | boolean; team: string | boolean }[] = [
  { row: 'Documents', free: 'Up to 3', pro: 'Unlimited', team: 'Unlimited' },
  { row: 'Chat with citations', free: 'Unlimited', pro: 'Unlimited', team: 'Unlimited' },
  { row: 'Quizzes', free: 'Unlimited', pro: 'Unlimited', team: 'Unlimited' },
  { row: 'Notes', free: 'Basic', pro: 'All four types', team: 'All four types' },
  { row: 'Flashcards', free: 'Basic', pro: true, team: 'Collaborative' },
  { row: 'Spaced repetition', free: '7-day window', pro: 'Unlimited', team: 'Unlimited' },
  { row: 'Learning path and analytics', free: false, pro: true, team: true },
  { row: 'Mind maps and knowledge graph', free: false, pro: true, team: true },
  { row: 'Priority AI processing', free: false, pro: true, team: true },
  { row: 'Members', free: '1', pro: '1', team: 'Up to 10' },
  { row: 'Shared document library', free: false, pro: false, team: true },
  { row: 'Teacher dashboard', free: false, pro: false, team: true },
];

export const faqs = [
  {
    q: 'What can I upload?',
    a: 'PDF, DOCX and TXT files. Scanned PDFs are run through OCR, so photographed handouts work too. On the Free plan each file can be up to 10 MB.',
  },
  {
    q: 'Does LuminaIQ make things up?',
    a: 'Answers are generated from the passages it retrieves from your own document, and each answer cites the passage it used. If something looks wrong, the citation takes you straight to the source to check.',
  },
  {
    q: 'What is spaced repetition, exactly?',
    a: 'A schedule for reviewing. LuminaIQ uses SM-2: after you grade a review, the next one comes after 1 day, then 6, then the previous gap multiplied by an ease factor that rises when you remember and falls when you do not. A missed card starts again at day one.',
  },
  {
    q: 'How is this different from a general chatbot?',
    a: 'A chatbot answers from everything it was trained on. LuminaIQ answers from your material and then keeps going: it turns that material into practice, tracks what you miss, and schedules your reviews.',
  },
  {
    q: 'Can a teacher use it with a class?',
    a: 'Yes. The Team plan covers up to 10 members with a shared document library, collaborative flashcards and a teacher dashboard.',
  },
  {
    q: 'What happens on the Free plan after 7 days?',
    a: 'The Free plan schedules reviews within a 7-day window. Pro removes the window, so cards keep coming back on day 15, day 38 and beyond.',
  },
];

export const audiences = [
  { key: 'college', title: 'College students', text: 'Lecture PDFs, textbooks and slides become summaries, quizzes and revision cards the same evening.' },
  { key: 'medlaw', title: 'Medical and law students', text: 'Dense reading, heavy terminology, a lot to recall. The glossary and spaced repetition were made for this.' },
  { key: 'teachers', title: 'Teachers', text: 'Generate practice questions from your own handouts and follow a class through the Team dashboard.' },
  { key: 'self', title: 'Self-learners', text: 'Technical manuals and online courses, turned into something you can question and practise.' },
] as const;
