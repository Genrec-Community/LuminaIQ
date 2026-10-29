# LuminaIQ website

Marketing site for [LuminaIQ](https://www.luminaiq.fun), the AI study companion by GenrecAI.
Next.js (App Router) + GSAP + Lenis. Design notes and decisions live in `DESIGN.md`.

## Run

```bash
npm install
npm run dev            # http://localhost:3000
npm run build && npm start
```

## Edit content

Every visible string, price, stat, photo and link is in `src/data/site.ts`. The top of that file
lists what is still a placeholder (annual prices, contact email, stock photos).

## Pages

`/` home · `/features/` · `/how-it-works/` · `/pricing/` · `/about/` · designed 404.

## Structure

- `src/engine/` motion engine (one GSAP clock, Lenis smooth scroll, reveals, page transitions)
- `src/motion/setup.ts` site motion: curtain transition, highlighter strokes, tool previews, counters
- `src/components/MemoryCurve.tsx` the interactive forgetting curve in the hero
- `src/components/Thread.tsx` the scroll-drawn lime line with SM-2 review nodes on the home page
