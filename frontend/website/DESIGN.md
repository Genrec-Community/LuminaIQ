# LuminaIQ website: design notes

## Phase 0: Brief

- **Subject:** LuminaIQ (luminaiq.fun), an AI study companion by GenrecAI. Students upload their own
  PDFs, textbooks and lecture notes and get document chat with citations, quizzes, four kinds of
  notes, flashcards, mind maps, learning paths, SM-2 spaced repetition and gamified progress.
- **Audience:** college students first, then medical and law students, teachers and self-learners.
- **Job of the site:** get a student to upload a first document (start free), and make Pro and Team
  pricing obvious. Secondary: explain how it works well enough to be trusted.
- **Assets:** owner's research notes (features, pricing, stats, pipeline), a YouTube walkthrough
  (`uLXTLmunK0g`), four reference shots (warm paper ground, editorial serif with italic accent,
  forest green ink, lime highlighter circle, a sweeping lime line, floating white cards, a clean
  three-plan pricing table with a monthly/annual toggle, a grid-paper header panel).
- **Constraints:** multi-page, SEO, stock imagery, mobile, clean motion. luminaiq.fun was not
  reachable from the build sandbox, so copy comes from the owner's notes.
- **Assumptions (all mirrored in `src/data/site.ts` and the hand-off):**
  - CTAs go to the live app: www.luminaiq.fun/dashboard (sign in on /login), as the app's own landing does.
  - Annual prices are not published: they are placeholders (two months free).
  - Stats (12,000+ learners, 50,000+ documents, 4.9/5 from 2,000+ students, under 30 s to a first
    quiz) are the figures the current site reports; shown as reported.
  - The YouTube video is presented as the product walkthrough.
  - Photos are Unsplash (free license), hotlinked, treated in a forest duotone so a mixed set reads
    as one series. They are illustrative and flagged for replacement with real product shots.
  - No customer logos and no testimonials: none were provided, so none are invented.

## Phase 1: Concept

| | A. Highlighter (name) | B. The memory curve (material) | C. The flashcard (formal) |
|---|---|---|---|
| Idea | *Lumina* is light: the site is a textbook page being highlighted as you read | Scrolling is time passing: what you learn starts to fade, and every LuminaIQ tool is a review that lifts it back up | Every section is a card: question on the front, answer on the back |
| Anchor | students highlight textbooks | the product schedules reviews with SM-2, on a forgetting curve | the product's 3D flip flashcards |
| Signature | a highlighter stroke runs through the page and marks key words | an interactive forgetting curve in the hero: point at any day and read recall with and without reviews; the same lime line threads the page with review nodes at SM-2 intervals | sections flip in 3D on scroll |
| Screenshot | a headline mid-stroke | the hero chart: a grey curve sinking, a lime saw-tooth staying high | a half-flipped card |
| O / F / Fe / P | 3 / 4 / 5 / 4 | 4 / 5 / 4 / 2 | 3 / 4 / 3 / 3 |

**Pick B.** It depends on the one mechanism that makes LuminaIQ more than a PDF summarizer
(spaced repetition), so it cannot be moved to another brand, and it explains the product while it
decorates. Steal from A: the lime highlighter mark is the hover language and the hand-drawn circle
in the headline. Steal from C for the 404: a flashcard you flip to find the answer.

### Concept card

```
Idea:        You forget most of what you read within days. LuminaIQ schedules the review that brings it back.
Metaphor:    the Ebbinghaus forgetting curve, reset by SM-2 reviews (day 1, 6, 15, 38, 95)
Signature:   hero memory curve: grey "read once" curve decays, the lime "with LuminaIQ" curve jumps at
             every review; pointer or scroll scrubs the day and the readout updates. The lime line
             continues down the home page as a scroll-drawn thread with review nodes at each section.
Emotion:     calm relief: "so that's why I keep forgetting, and here is the fix"
Motion verb: mark and settle (strokes draw fast like a highlighter, cards settle like paper set down)
Screenshot:  the hero: headline with a lime circle around "remember", the curve beneath it, a
             duotone photo of a student with white study cards floating over it
```

## Phase 2: System

### Palette (from the owner's references: exam paper, forest ink, highlighter lime)
| Role | Hex | Use |
|---|---|---|
| ground | `#FDF6F0` | the app's own beige (owner: "the entire software is beige") |
| ground-2 | `#F2E6DB` | panels, soft buttons |
| card | `#FFFFFF` | floating study cards, pricing cards (the app's paper) |
| ink | `#163628` | all text, dark buttons, footer field |
| muted | `#5E5046` | secondary text, warm brown-grey from the app (7:1 on ground) |
| line | `rgb(74 59 50 / 0.15)` | hairlines, grid paper |
| accent | `#D3EE6A` | highlighter: strokes, fills behind ink, never text on paper |
| curtain | `#163628` | page transition, with a lime leading band |

Cream + serif is on the AI-default list; it stays because the owner's references ask for it. What
moves it off the default: forest ink instead of black, lime highlighter instead of terracotta,
and the curve as the visual system.

### Type
- **Display:** Newsreader (Google, variable opsz + wght, italic). Weight 300 at display sizes,
  opsz 72, tracking -0.03em, leading 0.98. Italic carries the one emotional word per headline.
- **Text / UI:** Atkinson Hyperlegible Next (Google, variable). 400 / 500 / 600. Chosen over a plain
  grotesk because its capital I has serifs: in Host Grotesk the brand name read as "LuminalQ".
- Scale: mega clamp(3.1rem → 7.4rem), xl clamp(2.4rem → 5rem), l, m, body 17 to 18 px.

### Grid & rhythm
12 columns, gutter clamp(1rem → 2.5rem), max content width 1440. Strong lines at col 1, col 5 and
col 9. Section moods: hero (full), stats (tight), loop (airy, sticky), tools (index), video
(full-bleed), audiences (gallery wall), pricing (normal), finale (field color).

### Shape
Surfaces (cards, media) 1.25rem radius. Controls fully round. Nothing else.

### Motion language
- Ease: engine `expo.out` for entrances, `expo.inOut` for the curtain, `power3.out` for hovers.
- Mark: SVG strokes draw with stroke-dashoffset, 0.9 to 1.4 s. Highlight bands scale X from the left.
- Settle: cards enter from y 24 px + 1.5 deg rotation to rest.
- Hover treatments (one per role):
  - CTAs: a lime highlighter swipe floods the pill from the left; dark pill text turns ink.
  - Nav links: a lime band draws under the label; the current page keeps it.
  - Tool rows: the lime band sweeps behind the title and a preview card follows the pointer.
  - Inline links: underline at rest that rises into a lime band.
  - Arrows nudge 4 px.
- Idle: the hero "today" marker keeps walking the curve (one loop every ~14 s) and the study cards
  drift a few px with the pointer. Paused off screen, still under reduced motion.
- Page transition: forest curtain rises with a lime band on its leading edge, like a highlighter
  pass; it lifts off the new page the same way.
- No loader: a product page earns craft, not theatre.

### Composition plan (home)
```
HERO       [nav ......................................... Log in][Start free]
           Read it once.  ( remember )  it                       <- display, left on col 1
           for the exam.                 sub copy on col 9
           [Start free] [Watch the demo]
           ┌ memory curve chart: grey decay vs lime saw-tooth, day scrubber ┐
           └ duotone photo with 3 floating white cards on the right (desktop) ┘
STATS      12,000+ | 50,000+ | 4.9/5 | <30 s   (data / facts family, tabular)
LOOP       sticky narrative: left sticky "the loop" card cycling Understand/Practise/Measure/Revise,
           right four chapters; the lime thread runs down the left margin with review nodes
TOOLS      index list of the 8 tools, cursor preview card on desktop, inline on phone
VIDEO      full-bleed forest field with the YouTube facade (poster, play pill)
AUDIENCES  gallery wall: 4 duotone photos of different sizes, captions under
PRICING    three plan summary, link to /pricing
FINALE     footer as finale: giant "Start remembering." with the curve, links
```
Inner pages: `/features` (8 tools in alternating asymmetric pairs with live demos: flip card,
quiz, notes switcher), `/how-it-works` (pipeline figure: upload to generate, then the SM-2
schedule explained), `/pricing` (toggle, cards, comparison table, FAQ), `/about` (statement,
principles, GenrecAI), designed 404.

### Explainer figure
The pipeline on `/how-it-works` would earn an isometric anatomy figure. The `anatomy` skill is
not installed, so it is built as a flat, scroll-drawn diagram in the site's own line language.

### Genericness test
- A generic model would center a hero over a gradient blob with three equal feature cards. Changed:
  the hero is a chart with an argument; the tools are an index list; features alternate pairs.
- A generic model would add a logo wall ("You're in good company"). Removed: no real logos.
- A generic model would put a mono eyebrow over every heading. Changed: labels only where they
  carry data (review day numbers on the thread).

### Idle motion decision
`idleMotion` should be true on the home page (curve marker). Inner pages are still at rest by
design; their hovers and demos carry the life.
