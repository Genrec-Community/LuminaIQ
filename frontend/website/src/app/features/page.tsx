import type { Metadata } from 'next';
import { breadcrumbs, ld, pageMeta } from '@/lib/seo';
import { FlashcardDemo, NotesDemo, QuizDemo } from '@/components/Demos';
import { Arrow } from '@/components/Footer';
import { Specimen } from '@/components/Specimen';
import { site, tools } from '@/data/site';

export const metadata: Metadata = pageMeta({
  title: 'Study tools: chat, quizzes, notes and flashcards',
  description:
    'Eight study tools from one upload: chat with citations, a quiz generator, four kinds of notes, flashcards, mind maps, learning paths, well-timed reviews and streaks.',
  path: '/features/',
});

const demos: Record<string, React.ReactNode> = {
  quizzes: <QuizDemo />,
  notes: <NotesDemo />,
  flashcards: <FlashcardDemo />,
};

const stages = ['Understand', 'Practise', 'Measure', 'Revise'] as const;

export default function Features() {
  return (
    <>
      <section className="page-hero" aria-labelledby="features-title">
        <div className="wrap page-hero__grid">
          <h1 id="features-title" className="display h-mega rise">
            Eight tools, all made from <em>your</em> material.
          </h1>
          <div className="page-hero__aside">
            <p className="lede rise" style={{ ['--d' as string]: '0.15s' }}>
              Upload a chapter once. Ask it questions, test yourself on it, read it four ways, see it as a map, and get
              it back on the day you are about to forget it.
            </p>
            <nav className="stage-nav" aria-label="Tools by stage" data-reveal="up" data-intro data-delay="0.35">
              {stages.map((s) => (
                <div key={s} className="stage-nav__group">
                  <p className="stage-nav__label">{s}</p>
                  <ul>
                    {tools
                      .filter((t) => t.stage === s)
                      .map((t) => (
                        <li key={t.slug}>
                          <a href={`#${t.slug}`} className="tag" data-no-transition>
                            {t.name}
                          </a>
                        </li>
                      ))}
                  </ul>
                </div>
              ))}
            </nav>
          </div>
        </div>
      </section>

      <div className="wrap">
        {tools.map((t, i) => (
          <section key={t.slug} id={t.slug} className={`feature ${i % 2 ? 'feature--flip' : ''}`} aria-labelledby={`${t.slug}-title`}>
            <div className="feature__copy">
              <p className="feature__stage">{t.stage}</p>
              <h2 id={`${t.slug}-title`} className="display h-l" data-split="lines">
                {t.name}
              </h2>
              <p className="feature__body" data-reveal="up">
                {t.body}
              </p>
              <ul className="ticks" data-reveal="up" data-delay="0.08">
                {t.points.map((p) => (
                  <li key={p}>{p}</li>
                ))}
              </ul>
            </div>
            <div className="feature__demo" data-reveal="settle" data-tilt={i % 2 ? '-2' : '2'} data-delay="0.1">
              <p className="feature__example">{demos[t.slug] ? 'Try it: example chapter' : 'Example output'}</p>
              {demos[t.slug] ?? <Specimen slug={t.slug} />}
            </div>
          </section>
        ))}
      </div>

      <section className="band" aria-labelledby="band-title">
        <div className="wrap band__inner">
          <h2 id="band-title" className="display h-xl" data-split="lines">
            Your next chapter, <em>in thirty seconds.</em>
          </h2>
          <div className="actions">
            <a href={site.appUrl} className="btn btn--dark">
              <span>Start free</span>
              <Arrow />
            </a>
            <a href="/how-it-works/" className="btn btn--light" data-title="How it works">
              <span>See how it works</span>
            </a>
          </div>
        </div>
      </section>
      <script type="application/ld+json" dangerouslySetInnerHTML={ld(breadcrumbs('Features', '/features/'))} />
    </>
  );
}
