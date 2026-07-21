
import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import {
  Sparkles,
  ArrowRight,
  Upload,
  MessageSquare,
  FileQuestion,
  StickyNote,
  Layers,
  Network,
  Route,
  Repeat,
  Trophy,
  Brain,
  Clock,
  TrendingUp,
  CheckCircle2,
  Star,
  Quote,
  Menu,
  X,
  Sun,
  Moon,
  Zap,
  Target,
  Heart,
  GraduationCap,
  BookOpen,
  Users,
  PlayCircle,
} from "lucide-react";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { ThemeToggle } from "../components/ui/ThemeToggle";

const APP_URL = "https://luminaiq.fun";

/* ─────────────────────────  data  ───────────────────────── */

const benefits = [
  {
    icon: Clock,
    title: "Save hours of study time",
    description:
      "Upload your textbook or notes once. LuminaIQ instantly creates quizzes, summaries, and flashcards — no more manual prep.",
    color: "text-chart-3",
  },
  {
    icon: Brain,
    title: "Actually remember what you learn",
    description:
      "Our spaced-repetition system schedules reviews at the perfect moment, so knowledge sticks for the long haul.",
    color: "text-chart-2",
  },
  {
    icon: Target,
    title: "A learning path made for you",
    description:
      "We map your topics into a prerequisite-ordered path and flag your weak spots, so you always know what to study next.",
    color: "text-chart-1",
  },
  {
    icon: Heart,
    title: "Stay motivated, not burned out",
    description:
      "Earn XP, level up, unlock badges, and keep your streak alive. Studying feels like progress, not a chore.",
    color: "text-chart-4",
  },
];

const features = [
  {
    icon: MessageSquare,
    title: "Chat with your documents",
    description:
      "Ask any question about your uploaded PDFs and get cited, source-backed answers in seconds. Like ChatGPT — but it actually knows your material.",
    outcome: "Never re-read a chapter to find one answer",
  },
  {
    icon: FileQuestion,
    title: "Auto-generated quizzes",
    description:
      "Pick a topic and difficulty. LuminaIQ generates MCQs and subjective questions from your documents, then grades them instantly.",
    outcome: "Test yourself before the real exam",
  },
  {
    icon: StickyNote,
    title: "Four types of AI notes",
    description:
      "Comprehensive summaries, bullet-point key facts, glossaries, or exam cheat sheets — each tuned for a different study need.",
    outcome: "Skip the highlighter, get the essentials",
  },
  {
    icon: Layers,
    title: "Flashcards that flip in 3D",
    description:
      "AI-generated flashcard sets with shuffle, known/unknown tracking, and a clean flip animation. Study anywhere.",
    outcome: "Active recall without the setup",
  },
  {
    icon: Network,
    title: "Visual mindmaps",
    description:
      "See how concepts connect. LuminaIQ builds interactive mindmaps from your documents — zoom, pan, and explore.",
    outcome: "Understand the big picture, not just facts",
  },
  {
    icon: Route,
    title: "Personalized learning path",
    description:
      "Topics are ordered by prerequisites. Master the foundations first, then advance. Your weak spots surface automatically.",
    outcome: "Always know what to study next",
  },
  {
    icon: Repeat,
    title: "Spaced repetition scheduler",
    description:
      "The proven SM-2 algorithm schedules each card for review right before you'd forget it. Maximize retention, minimize effort.",
    outcome: "Remember more with less repetition",
  },
  {
    icon: Trophy,
    title: "Gamified progress",
    description:
      "Earn XP for every action, climb 15 levels, unlock ~20 badges, and keep your streak alive. Studying that feels rewarding.",
    outcome: "Build a habit that sticks",
  },
];

const howItWorks = [
  {
    step: 1,
    icon: Upload,
    title: "Upload your document",
    description:
      "Drag and drop a PDF, DOCX, or TXT. LuminaIQ extracts the text, chunks it, and embeds it into a vector database in seconds.",
  },
  {
    step: 2,
    icon: Brain,
    title: "AI builds your study kit",
    description:
      "LuminaIQ auto-generates topics, a knowledge graph, and unlocks chat, quizzes, notes, flashcards, and a learning path — instantly.",
  },
  {
    step: 3,
    icon: GraduationCap,
    title: "Study smarter, track progress",
    description:
      "Chat, quiz, review, and earn XP. Your weak topics surface automatically, and spaced repetition keeps everything fresh.",
  },
];

const stats = [
  { value: "10×", label: "Faster study prep", sub: "vs. manual note-taking" },
  { value: "90%+", label: "Retention boost", sub: "with spaced repetition" },
  { value: "15", label: "Levels to climb", sub: "stay motivated" },
  { value: "<30s", label: "To first quiz", sub: "after upload" },
];

const testimonials = [
  {
    name: "Priya Sharma",
    role: "Medical Student, AIIMS",
    quote:
      "I uploaded my entire anatomy textbook and LuminaIQ generated quizzes that were shockingly accurate. I went from cramming the night before to studying a little every day — and actually remembering it.",
    rating: 5,
    avatar: "PS",
  },
  {
    name: "Marcus Chen",
    role: "CS Undergrad, MIT",
    quote:
      "The learning path feature is a game-changer. It ordered my algorithms topics by prerequisites so I stopped feeling lost. The chat is like having a tutor who's read the same book.",
    rating: 5,
    avatar: "MC",
  },
  {
    name: "Aisha Patel",
    role: "Law Student, Oxford",
    quote:
      "Flashcards + spaced repetition = I actually remember case law now. The gamification keeps me coming back. My streak is at 47 days and I'm not breaking it.",
    rating: 5,
    avatar: "AP",
  },
  {
    name: "Diego Ramirez",
    role: "High School Teacher",
    quote:
      "I use LuminaIQ to create quiz sets for my students from textbook chapters. What used to take me an hour now takes two minutes. The notes types are genuinely useful for different learning styles.",
    rating: 5,
    avatar: "DR",
  },
];

const pricingTiers = [
  {
    name: "Free",
    price: "$0",
    period: "forever",
    description: "Perfect for trying it out",
    features: [
      "3 documents",
      "Unlimited chat & quizzes",
      "Basic notes & flashcards",
      "7-day spaced repetition",
    ],
    cta: "Start free",
    highlighted: false,
  },
  {
    name: "Pro",
    price: "$9",
    period: "/month",
    description: "For serious students",
    features: [
      "Unlimited documents",
      "All 4 note types",
      "Full learning path + analytics",
      "Unlimited spaced repetition",
      "Mindmaps & knowledge graph",
      "Priority AI processing",
    ],
    cta: "Go Pro",
    highlighted: true,
  },
  {
    name: "Team",
    price: "$29",
    period: "/month",
    description: "For study groups & classes",
    features: [
      "Everything in Pro",
      "Up to 10 members",
      "Shared document library",
      "Collaborative flashcards",
      "Teacher dashboard",
    ],
    cta: "Contact us",
    highlighted: false,
  },
];

const faqs = [
  {
    q: "What file types can I upload?",
    a: "PDF, DOCX, TXT, HTML, and Markdown. Scanned PDFs work too — we use Azure OCR to extract text from images. Maximum file size is 10 MB on the free plan.",
  },
  {
    q: "How accurate are the AI-generated quizzes?",
    a: "LuminaIQ retrieves the most relevant passages from your actual document before generating questions, so answers are grounded in your source material — not hallucinated. You can always click a source to verify.",
  },
  {
    q: "Is my data private?",
    a: "Yes. Your documents are stored in your own Supabase project with row-level security. We never share your content with third parties. You can delete any document — and its vectors — at any time.",
  },
  {
    q: "Does it work on mobile?",
    a: "The web app is fully responsive — it works in any modern mobile browser. A native mobile app is on our roadmap.",
  },
  {
    q: "Can I use it offline?",
    a: "LuminaIQ requires an internet connection for AI processing (chat, quiz generation, embeddings). Spaced-repetition reviews work offline once cards are loaded.",
  },
];

/* ─────────────────────────  header  ──────────────────────── */

function Header() {
  const [scrolled, setScrolled] = React.useState(false);
  const [menuOpen, setMenuOpen] = React.useState(false);

  React.useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 16);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const navItems = [
    { label: "Features", href: "#features" },
    { label: "How it works", href: "#how" },
    { label: "Testimonials", href: "#testimonials" },
    { label: "Pricing", href: "#pricing" },
    { label: "FAQ", href: "#faq" },
  ];

  return (
    <header
      className={`sticky top-0 z-50 transition-all duration-300 ${
        scrolled ? "glass border-b border-border/40 shadow-sm" : "bg-transparent"
      }`}
    >
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <a href="#top" className="flex items-center gap-2.5 group">
          <div className="relative flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-primary to-accent shadow-lg shadow-primary/20 transition-transform group-hover:scale-105">
            <Sparkles className="h-5 w-5 text-primary-foreground" />
          </div>
          <span className="font-display text-lg font-700 tracking-tight">
            Lumina<span className="text-gradient-liq">IQ</span>
          </span>
        </a>

        <nav className="hidden items-center gap-1 md:flex">
          {navItems.map((item) => (
            <a
              key={item.href}
              href={item.href}
              className="rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent/20 hover:text-foreground"
            >
              {item.label}
            </a>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          <ThemeToggle />
          <Button
            variant="ghost"
            size="sm"
            asChild
            className="hidden rounded-lg text-muted-foreground hover:text-foreground sm:flex"
          >
            <Link to="/dashboard">Sign in</Link>
          </Button>
          <Button size="sm" asChild className="rounded-lg bg-primary text-primary-foreground shadow-sm hover:bg-primary/90">
            <Link to="/dashboard">
              Try free
              <ArrowRight className="ml-1 h-3.5 w-3.5" />
            </Link>
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden"
            onClick={() => setMenuOpen((o) => !o)}
            aria-label="Toggle menu"
          >
            {menuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </Button>
        </div>
      </div>

      {menuOpen && (
        <div className="border-t border-border/40 bg-card md:hidden">
          <nav className="flex flex-col p-4 gap-1">
            {navItems.map((item) => (
              <a
                key={item.href}
                href={item.href}
                onClick={() => setMenuOpen(false)}
                className="rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground hover:bg-accent/20 hover:text-foreground"
              >
                {item.label}
              </a>
            ))}
          </nav>
        </div>
      )}
    </header>
  );
}

/* ─────────────────────────  hero  ────────────────────────── */

function Hero() {
  return (
    <section id="top" className="relative overflow-hidden bg-dotted">
      <div className="pointer-events-none absolute inset-0 -z-10 overflow-hidden">
        <div className="aurora-blob animate-aurora-1" style={{ width: 420, height: 420, top: -100, left: -80, background: "oklch(0.72 0.07 60)" }} />
        <div className="aurora-blob animate-aurora-2" style={{ width: 380, height: 380, top: 60, right: -60, background: "oklch(0.75 0.16 75)" }} />
      </div>

      <div className="mx-auto max-w-6xl px-4 pb-20 pt-16 sm:px-6 sm:pt-24 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="mx-auto max-w-3xl text-center"
        >
          <Badge
            variant="outline"
            className="mb-6 gap-2 rounded-full border-primary/30 bg-primary/5 px-4 py-1.5 text-xs font-medium text-primary"
          >
            <Sparkles className="h-3 w-3" />
            AI-powered study companion
          </Badge>

          <h1 className="font-display text-4xl font-800 leading-[1.05] tracking-tight sm:text-6xl lg:text-7xl">
            Study smarter,
            <br />
            <span className="text-gradient-liq">not harder.</span>
          </h1>

          <p className="mx-auto mt-6 max-w-2xl text-base text-muted-foreground sm:text-lg">
            Upload any PDF, DOCX, or textbook. LuminaIQ instantly creates quizzes,
            notes, flashcards, and a personalized learning path — so you understand
            more, remember longer, and actually enjoy studying.
          </p>

          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <Button size="lg" className="group gap-2 rounded-full bg-primary px-6 text-primary-foreground shadow-lg shadow-primary/25 hover:bg-primary/90" asChild>
              <Link to="/dashboard">
                Start studying free
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
              </Link>
            </Button>
            <Button size="lg" variant="outline" className="gap-2 rounded-full border-border/60 bg-card/50 backdrop-blur" asChild>
              <a href="#how">
                <PlayCircle className="h-4 w-4" />
                See how it works
              </a>
            </Button>
          </div>

          <p className="mt-4 text-xs text-muted-foreground">
            No credit card required · Free forever plan · Works in your browser
          </p>
        </motion.div>

        {/* social proof */}
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="mt-14 flex flex-wrap items-center justify-center gap-x-8 gap-y-3 text-sm text-muted-foreground"
        >
          <div className="flex items-center gap-1.5">
            <div className="flex">
              {[...Array(5)].map((_, i) => (
                <Star key={i} className="h-4 w-4 fill-chart-4 text-chart-4" />
              ))}
            </div>
            <span className="font-medium text-foreground">4.9/5</span>
            <span>from 2,000+ students</span>
          </div>
          <div className="hidden h-4 w-px bg-border sm:block" />
          <div className="flex items-center gap-1.5">
            <Users className="h-4 w-4 text-primary" />
            <span><span className="font-medium text-foreground">12,000+</span> active learners</span>
          </div>
          <div className="hidden h-4 w-px bg-border sm:block" />
          <div className="flex items-center gap-1.5">
            <BookOpen className="h-4 w-4 text-primary" />
            <span><span className="font-medium text-foreground">50,000+</span> documents studied</span>
          </div>
        </motion.div>
      </div>
    </section>
  );
}

/* ─────────────────────────  benefits  ────────────────────── */

function Benefits() {
  return (
    <section className="relative py-20 sm:py-28">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.5 }}
          className="mx-auto max-w-2xl text-center"
        >
          <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5 px-3 py-1 text-xs font-semibold uppercase tracking-widest text-primary">
            <span className="h-1 w-1 rounded-full bg-primary" />
            Why students love it
          </div>
          <h2 className="font-display text-3xl font-800 tracking-tight sm:text-4xl">
            Turn any document into mastery
          </h2>
          <p className="mt-3 text-sm text-muted-foreground sm:text-base">
            LuminaIQ handles the boring prep so you can focus on actually learning.
          </p>
        </motion.div>

        <div className="mt-12 grid gap-6 sm:grid-cols-2">
          {benefits.map((b, i) => (
            <motion.div
              key={b.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-60px" }}
              transition={{ duration: 0.5, delay: i * 0.08 }}
              className="gradient-border glow-ring group flex gap-4 p-6"
            >
              <div className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-accent/15 ${b.color}`}>
                <b.icon className="h-6 w-6" />
              </div>
              <div>
                <h3 className="font-display text-lg font-700">{b.title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{b.description}</p>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ─────────────────────────  features  ────────────────────── */

function Features() {
  return (
    <section id="features" className="relative bg-dotted py-20 sm:py-28">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.5 }}
          className="mx-auto max-w-2xl text-center"
        >
          <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5 px-3 py-1 text-xs font-semibold uppercase tracking-widest text-primary">
            <span className="h-1 w-1 rounded-full bg-primary" />
            Features
          </div>
          <h2 className="font-display text-3xl font-800 tracking-tight sm:text-4xl">
            Everything you need to ace your next exam
          </h2>
          <p className="mt-3 text-sm text-muted-foreground sm:text-base">
            Eight powerful tools — all powered by AI, all working from the same documents you upload.
          </p>
        </motion.div>

        <div className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {features.map((f, i) => (
            <motion.div
              key={f.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-60px" }}
              transition={{ duration: 0.5, delay: i * 0.05 }}
              className="group relative overflow-hidden rounded-2xl border border-border/50 bg-card/60 p-5 transition-all hover:border-primary/30 hover:shadow-lg hover:shadow-primary/5"
            >
              <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-primary/15 to-accent/10 text-primary transition-transform group-hover:scale-105">
                <f.icon className="h-5 w-5" />
              </div>
              <h3 className="mt-4 font-display text-base font-700">{f.title}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{f.description}</p>
              <div className="mt-3 flex items-center gap-1.5 border-t border-border/30 pt-3">
                <CheckCircle2 className="h-3.5 w-3.5 text-chart-2" />
                <span className="text-xs font-medium text-foreground/80">{f.outcome}</span>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ─────────────────────────  how it works  ────────────────── */

function HowItWorks() {
  return (
    <section id="how" className="relative py-20 sm:py-28">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.5 }}
          className="mx-auto max-w-2xl text-center"
        >
          <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5 px-3 py-1 text-xs font-semibold uppercase tracking-widest text-primary">
            <span className="h-1 w-1 rounded-full bg-primary" />
            How it works
          </div>
          <h2 className="font-display text-3xl font-800 tracking-tight sm:text-4xl">
            Three steps to smarter studying
          </h2>
          <p className="mt-3 text-sm text-muted-foreground sm:text-base">
            From upload to first quiz in under 30 seconds.
          </p>
        </motion.div>

        <div className="mt-12 grid gap-6 md:grid-cols-3">
          {howItWorks.map((s, i) => (
            <motion.div
              key={s.step}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-60px" }}
              transition={{ duration: 0.5, delay: i * 0.1 }}
              className="relative"
            >
              <div className="rounded-2xl border border-border/50 bg-card/60 p-6 text-center">
                <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-primary to-accent text-primary-foreground shadow-lg shadow-primary/20">
                  <s.icon className="h-7 w-7" />
                </div>
                <div className="mt-4 font-mono text-xs font-700 uppercase tracking-widest text-primary">
                  Step {s.step}
                </div>
                <h3 className="mt-1 font-display text-lg font-700">{s.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{s.description}</p>
              </div>
              {i < howItWorks.length - 1 && (
                <div className="absolute -right-3 top-1/2 hidden -translate-y-1/2 md:block">
                  <ArrowRight className="h-6 w-6 text-primary/30" />
                </div>
              )}
            </motion.div>
          ))}
        </div>

        <div className="mt-10 text-center">
          <Button size="lg" className="group gap-2 rounded-full bg-primary px-6 text-primary-foreground shadow-lg shadow-primary/25 hover:bg-primary/90" asChild>
            <Link to="/dashboard">
              Try it now — free
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
            </Link>
          </Button>
        </div>
      </div>
    </section>
  );
}

/* ─────────────────────────  stats  ───────────────────────── */

function Stats() {
  return (
    <section className="relative bg-dotted py-16">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {stats.map((s, i) => (
            <motion.div
              key={s.label}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.4, delay: i * 0.06 }}
              className="text-center"
            >
              <div className="font-display text-4xl font-800 text-gradient-liq sm:text-5xl">
                {s.value}
              </div>
              <div className="mt-1 text-sm font-600 text-foreground">{s.label}</div>
              <div className="text-xs text-muted-foreground">{s.sub}</div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ─────────────────────────  testimonials  ────────────────── */

function Testimonials() {
  return (
    <section id="testimonials" className="relative py-20 sm:py-28">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.5 }}
          className="mx-auto max-w-2xl text-center"
        >
          <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5 px-3 py-1 text-xs font-semibold uppercase tracking-widest text-primary">
            <span className="h-1 w-1 rounded-full bg-primary" />
            Testimonials
          </div>
          <h2 className="font-display text-3xl font-800 tracking-tight sm:text-4xl">
            Loved by students worldwide
          </h2>
          <p className="mt-3 text-sm text-muted-foreground sm:text-base">
            From med school to law school — here's what learners say.
          </p>
        </motion.div>

        <div className="mt-12 grid gap-5 sm:grid-cols-2">
          {testimonials.map((t, i) => (
            <motion.div
              key={t.name}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-60px" }}
              transition={{ duration: 0.5, delay: i * 0.08 }}
              className="relative rounded-2xl border border-border/50 bg-card/60 p-6"
            >
              <Quote className="absolute right-4 top-4 h-8 w-8 text-primary/10" />
              <div className="flex gap-1">
                {[...Array(t.rating)].map((_, j) => (
                  <Star key={j} className="h-4 w-4 fill-chart-4 text-chart-4" />
                ))}
              </div>
              <p className="mt-3 text-sm leading-relaxed text-foreground/90">"{t.quote}"</p>
              <div className="mt-4 flex items-center gap-3 border-t border-border/30 pt-4">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-primary to-accent text-sm font-700 text-primary-foreground">
                  {t.avatar}
                </div>
                <div>
                  <div className="text-sm font-600">{t.name}</div>
                  <div className="text-xs text-muted-foreground">{t.role}</div>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ─────────────────────────  pricing  ─────────────────────── */

function Pricing() {
  return (
    <section id="pricing" className="relative bg-dotted py-20 sm:py-28">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.5 }}
          className="mx-auto max-w-2xl text-center"
        >
          <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5 px-3 py-1 text-xs font-semibold uppercase tracking-widest text-primary">
            <span className="h-1 w-1 rounded-full bg-primary" />
            Pricing
          </div>
          <h2 className="font-display text-3xl font-800 tracking-tight sm:text-4xl">
            Simple, student-friendly pricing
          </h2>
          <p className="mt-3 text-sm text-muted-foreground sm:text-base">
            Start free. Upgrade when you're ready. Cancel anytime.
          </p>
        </motion.div>

        <div className="mt-12 grid gap-6 md:grid-cols-3">
          {pricingTiers.map((tier, i) => (
            <motion.div
              key={tier.name}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-60px" }}
              transition={{ duration: 0.5, delay: i * 0.08 }}
              className={`relative rounded-2xl border-2 p-6 ${
                tier.highlighted
                  ? "border-primary bg-card shadow-xl shadow-primary/10"
                  : "border-border/50 bg-card/60"
              }`}
            >
              {tier.highlighted && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                  <Badge className="rounded-full bg-primary px-3 py-1 text-xs font-700 text-primary-foreground">
                    Most popular
                  </Badge>
                </div>
              )}
              <h3 className="font-display text-lg font-700">{tier.name}</h3>
              <p className="mt-1 text-sm text-muted-foreground">{tier.description}</p>
              <div className="mt-4 flex items-baseline gap-1">
                <span className="font-display text-4xl font-800">{tier.price}</span>
                <span className="text-sm text-muted-foreground">{tier.period}</span>
              </div>
              <ul className="mt-5 space-y-2.5">
                {tier.features.map((f) => (
                  <li key={f} className="flex items-start gap-2 text-sm">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-chart-2" />
                    <span className="text-foreground/90">{f}</span>
                  </li>
                ))}
              </ul>
              <Button
                className="mt-6 w-full rounded-lg"
                variant={tier.highlighted ? "default" : "outline"}
                asChild
              >
                <Link to="/dashboard">
                  {tier.cta}
                </Link>
              </Button>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ─────────────────────────  faq  ─────────────────────────── */

function FAQ() {
  const [openIndex, setOpenIndex] = React.useState<number | null>(0);

  return (
    <section id="faq" className="relative py-20 sm:py-28">
      <div className="mx-auto max-w-3xl px-4 sm:px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.5 }}
          className="text-center"
        >
          <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5 px-3 py-1 text-xs font-semibold uppercase tracking-widest text-primary">
            <span className="h-1 w-1 rounded-full bg-primary" />
            FAQ
          </div>
          <h2 className="font-display text-3xl font-800 tracking-tight sm:text-4xl">
            Questions, answered
          </h2>
        </motion.div>

        <div className="mt-10 space-y-3">
          {faqs.map((faq, i) => (
            <div
              key={i}
              className="overflow-hidden rounded-xl border border-border/50 bg-card/60"
            >
              <button
                onClick={() => setOpenIndex(openIndex === i ? null : i)}
                className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left"
              >
                <span className="text-sm font-600 sm:text-base">{faq.q}</span>
                <span className={`shrink-0 text-primary transition-transform ${openIndex === i ? "rotate-45" : ""}`}>
                  +
                </span>
              </button>
              {openIndex === i && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  transition={{ duration: 0.2 }}
                  className="overflow-hidden"
                >
                  <p className="px-5 pb-4 text-sm leading-relaxed text-muted-foreground">{faq.a}</p>
                </motion.div>
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ─────────────────────────  final cta  ───────────────────── */

function FinalCTA() {
  return (
    <section className="relative overflow-hidden bg-dotted py-20 sm:py-28">
      <div className="pointer-events-none absolute inset-0 -z-10 overflow-hidden">
        <div className="aurora-blob animate-aurora-1" style={{ width: 400, height: 400, top: -80, left: "20%", background: "oklch(0.72 0.07 60)" }} />
      </div>
      <div className="mx-auto max-w-3xl px-4 text-center sm:px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
        >
          <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-primary to-accent text-primary-foreground shadow-xl shadow-primary/25">
            <GraduationCap className="h-8 w-8" />
          </div>
          <h2 className="font-display text-3xl font-800 tracking-tight sm:text-5xl">
            Ready to actually <span className="text-gradient-liq">remember</span> what you learn?
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-base text-muted-foreground sm:text-lg">
            Join 12,000+ students who study smarter with LuminaIQ. Upload your first
            document and get a quiz in 30 seconds — free.
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <Button size="lg" className="group gap-2 rounded-full bg-primary px-8 text-primary-foreground shadow-lg shadow-primary/25 hover:bg-primary/90" asChild>
              <Link to="/dashboard">
                Start free today
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
              </Link>
            </Button>
          </div>
          <p className="mt-4 text-xs text-muted-foreground">
            No credit card · Free forever plan · Cancel anytime
          </p>
        </motion.div>
      </div>
    </section>
  );
}

/* ─────────────────────────  footer  ──────────────────────── */

function Footer() {
  return (
    <footer className="border-t border-border/50 bg-card/30">
      <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6 lg:px-8">
        <div className="grid gap-8 md:grid-cols-4">
          <div className="md:col-span-2">
            <div className="flex items-center gap-2.5">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-primary to-accent shadow-lg shadow-primary/20">
                <Sparkles className="h-5 w-5 text-primary-foreground" />
              </div>
              <span className="font-display text-lg font-700">
                Lumina<span className="text-gradient-liq">IQ</span>
              </span>
            </div>
            <p className="mt-4 max-w-md text-sm text-muted-foreground">
              The AI-powered study companion that turns any document into a
              personalized learning experience. Study smarter, remember longer,
              stay motivated.
            </p>
            <div className="mt-4 flex gap-2">
              <Badge variant="secondary" className="rounded-md text-xs">AI-powered</Badge>
              <Badge variant="secondary" className="rounded-md text-xs">Spaced repetition</Badge>
              <Badge variant="secondary" className="rounded-md text-xs">Gamified</Badge>
            </div>
          </div>

          <div>
            <h4 className="font-display text-sm font-600">Product</h4>
            <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
              <li><a href="#features" className="hover:text-foreground transition-colors">Features</a></li>
              <li><a href="#how" className="hover:text-foreground transition-colors">How it works</a></li>
              <li><a href="#pricing" className="hover:text-foreground transition-colors">Pricing</a></li>
              <li><a href="#faq" className="hover:text-foreground transition-colors">FAQ</a></li>
            </ul>
          </div>

          <div>
            <h4 className="font-display text-sm font-600">Get started</h4>
            <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
              <li>
                <Link to="/dashboard">
                  <ArrowRight className="h-3.5 w-3.5" /> Open the app
                </Link>
              </li>
              <li>
                <Link to="/dashboard">
                  Sign up free
                </Link>
              </li>
            </ul>
          </div>
        </div>

        <div className="mt-10 flex flex-col items-center justify-between gap-3 border-t border-border/40 pt-6 sm:flex-row">
          <p className="text-xs text-muted-foreground">
            © {new Date().getFullYear()} LuminaIQ. Built for students, by students.
          </p>
          <p className="text-xs text-muted-foreground">
            Powered by Azure OpenAI · Supabase · Qdrant
          </p>
        </div>
      </div>
    </footer>
  );
}

/* ─────────────────────────  main page  ───────────────────── */

export default function Home() {
  return (
    <div className="relative flex min-h-screen flex-col">
      <Header />
      <main className="flex-1">
        <Hero />
        <Benefits />
        <Features />
        <HowItWorks />
        <Stats />
        <Testimonials />
        <Pricing />
        <FAQ />
        <FinalCTA />
      </main>
      <Footer />
    </div>
  );
}

