import type { Metadata } from 'next';
import { pageMeta } from '@/lib/seo';
import Link from 'next/link';
import { Arrow } from '@/components/Footer';
import { MemoryCurve } from '@/components/MemoryCurve';
import { Photo } from '@/components/Photo';
import { Pricing } from '@/components/Pricing';
import { Specimen } from '@/components/Specimen';
import { Node, Thread } from '@/components/Thread';
import { Video } from '@/components/Video';
import { audiences, loop, photos, site, stats, tools } from '@/data/site';

export const metadata: Metadata = pageMeta({
  title: 'Lumina IQ: AI study companion for quizzes, notes and flashcards',
  description:
    'Upload a textbook or lecture PDF and get cited answers, quizzes, four kinds of notes, flashcards and reviews timed to your memory. Lumina IQ is free to start.',
  path: '/',
  absolute: true,
});

const toolName = Object.fromEntries(tools.map((t) => [t.slug, t.name]));
const stageIndex = { Understand: 0, Practise: 1, Measure: 2, Revise: 3 } as const;

export default function Home() {
  return (
    <>
      {/* HERO: the claim, then the curve that proves it */}
      <section className="hero" aria-labelledby="hero-title">
        <div className="wrap">
          <div className="hero__head">
            <h1 id="hero-title" className="display hero__title">
              <span className="hline rise">Read it once.</span>
              <span className="hline rise" style={{ ['--d' as string]: '0.08s' }}>
                <span className="circled">
                  <em>Remember</em>
                  <svg viewBox="0 0 300 110" aria-hidden="true" preserveAspectRatio="none">
                    <path
                      data-draw
                      data-draw-intro
                      data-delay="0.65"
                      data-duration="1.1"
                      pathLength={1}
                      d="M226 14C170 2 70 4 30 26 4 41 6 72 44 88c52 21 168 20 220-2 30-13 34-42 8-60-24-16-90-22-150-14"
                    />
                  </svg>
                </span>{' '}
                it
              </span>
              <span className="hline rise" style={{ ['--d' as string]: '0.16s' }}>for the exam.</span>
            </h1>
            <div className="hero__aside">
              <p className="lede rise" style={{ ['--d' as string]: '0.3s' }}>
                Lumina IQ turns your textbooks, lecture PDFs and notes into cited answers, quizzes and flashcards. Then it
                schedules the reviews that keep it all in your head.
              </p>
              <div className="actions rise" style={{ ['--d' as string]: '0.4s' }}>
                <a href={site.appUrl} className="btn btn--dark">
                  <span>Start free</span>
                  <Arrow />
                </a>
                <a href="#walkthrough" className="btn btn--light" data-no-transition>
                  <span>Watch the walkthrough</span>
                </a>
              </div>
            </div>
          </div>

          <div className="hero__stage">
            <div className="hero__chart" data-reveal="up" data-intro data-delay="0.35">
              <MemoryCurve />
            </div>
            <div className="hero__media">
              <div data-reveal="clip" data-intro data-delay="0.45">
                <Photo photo={photos.hero} eager ratio="4 / 5" sizes="(min-width: 1024px) 34vw, 100vw" />
              </div>
              <div className="floater floater--a" data-float="0.8">
                <div className="floater__in" data-reveal="settle" data-tilt="-4" data-intro data-delay="0.9">
                <p className="floater__k">Photosynthesis · 24 cards</p>
                <p className="floater__v">Next review in 6 days</p>
                <span className="floater__dots" aria-hidden="true">
                  <i className="on" />
                  <i className="on" />
                  <i />
                  <i />
                  <i />
                </span>
                </div>
              </div>
              <div className="floater floater--b" data-float="1.2">
                <div className="floater__in" data-reveal="settle" data-tilt="3" data-intro data-delay="1.05">
                <p className="floater__k">Quiz · Light reactions</p>
                <p className="floater__v">
                  <b>8</b>/10 correct
                </p>
                <span className="xp" aria-hidden="true">
                  <span style={{ width: '80%' }} />
                </span>
                </div>
              </div>
              <div className="floater floater--c" data-float="1">
                <div className="floater__in" data-reveal="settle" data-tilt="-2" data-intro data-delay="1.2">
                <p className="floater__k">Answer from your file</p>
                <p className="floater__v">Biology, ch. 8, p. 142</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <Thread>
        {/* STATS: real numbers, small and exact */}
        <section className="stats" aria-label="Lumina IQ in numbers">
          <div className="wrap">
            <ul className="stats__list">
              {stats.map((s) => (
                <li key={s.label}>
                  <p className="stats__value">
                    {s.prefix && <span className="stats__affix">{s.prefix}</span>}
                    <span data-count={s.value} data-decimals={s.decimals ?? 0}>
                      {s.value.toLocaleString('en-US', { minimumFractionDigits: s.decimals ?? 0 })}
                    </span>
                    <span className="stats__affix">{s.suffix}</span>
                  </p>
                  <p className="stats__label">{s.label}</p>
                </li>
              ))}
            </ul>
            <p className="stats__note">Figures reported by Lumina IQ.</p>
          </div>
        </section>

        {/* LOOP: sticky dial + four chapters */}
        <section className="loop" aria-labelledby="loop-title">
          <div className="wrap loop__grid">
            <div className="loop__intro">
              <Node day={1} />
              <h2 id="loop-title" className="display h-xl" data-split="lines">
                Rereading feels like studying. <em>It isn’t.</em>
              </h2>
              <p className="lede" data-reveal="up">
                Most of an evening with a textbook goes on preparation: finding what matters, writing notes, making cards.
                Lumina IQ does the preparation in seconds and spends your time on the four things that make it stick.
              </p>
            </div>
            <div className="loop__stage" data-loop-stage data-state="0" aria-hidden="true">
              <svg viewBox="0 0 200 200" className="dial">
                <circle cx="100" cy="100" r="78" className="dial__track" />
                {[0, 1, 2, 3].map((i) => (
                  <path
                    key={i}
                    className="dial__arc"
                    data-arc={i}
                    d={arc(100, 100, 78, i * 90 + 6, i * 90 + 84)}
                  />
                ))}
              </svg>
              <ol className="dial__labels">
                {loop.map((l, i) => (
                  <li key={l.stage} data-i={i}>
                    {l.stage}
                  </li>
                ))}
              </ol>
              <p className="dial__center">
                <span>The</span> loop
              </p>
            </div>
            <ol className="loop__chapters">
              {loop.map((l, i) => (
                <li key={l.stage} className={`chapter ${i === 0 ? 'is-active' : ''}`} data-loop-chapter>
                  <p className="chapter__stage">{l.stage}</p>
                  <h3 className="display h-l">{l.title}</h3>
                  <p>{l.text}</p>
                  <p className="chapter__tools">
                    {l.tools.map((slug) => (
                      <Link key={slug} href={`/features/#${slug}`} className="tag" data-title="Features">
                        {toolName[slug]}
                      </Link>
                    ))}
                  </p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* TOOLS: index list with a following preview */}
        <section className="tools" aria-labelledby="tools-title">
          <div className="wrap">
            <div className="tools__head">
              <Node day={6} />
              <h2 id="tools-title" className="display h-xl" data-split="lines">
                Eight tools. <em>One upload.</em>
              </h2>
              <p className="lede" data-reveal="up">
                Everything below is generated from the same document, so your quiz, your cards and your notes all agree.
              </p>
            </div>
            <ul className="index" data-index>
              {tools.map((t) => (
                <li key={t.slug} data-reveal="up">
                  <Link href={`/features/#${t.slug}`} data-preview={t.slug} data-title={t.name} className="index__row">
                    <span className="index__name">
                      <span className="index__band" aria-hidden="true" />
                      {t.name}
                    </span>
                    <span className="index__line">{t.line}</span>
                    <span className="index__stage" data-stage={stageIndex[t.stage]}>
                      {t.stage}
                    </span>
                    <Arrow />
                    {/* Phones: the example card desktop shows on hover, built into the swipe deck */}
                    <div className="index__peek" aria-hidden="true">
                      <Specimen slug={t.slug} />
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          </div>
          <div className="preview" data-preview-box aria-hidden="true">
            {tools.map((t) => (
              <div key={t.slug} className="preview__card" data-preview-card={t.slug}>
                <Specimen slug={t.slug} />
              </div>
            ))}
          </div>
        </section>

        {/* VIDEO: full-bleed field */}
        <section className="watch" id="walkthrough" aria-labelledby="watch-title">
          <div className="wrap watch__grid">
            <div className="watch__copy">
              <h2 id="watch-title" className="display h-xl" data-split="lines">
                Watch it <em>work.</em>
              </h2>
              <p>A guided tour of Lumina IQ, from your first upload to your first review.</p>
              <a className="link link--on-dark" href={`https://www.youtube.com/watch?v=${site.youtubeId}`} rel="noopener" target="_blank">
                Open on YouTube
              </a>
            </div>
            <div className="watch__frame" data-reveal="up">
              <Video id={site.youtubeId} title="Lumina IQ walkthrough" />
            </div>
          </div>
        </section>

        {/* AUDIENCES: gallery wall */}
        <section className="people" aria-labelledby="people-title">
          <div className="wrap">
            <div className="people__head">
              <Node day={15} />
              <h2 id="people-title" className="display h-xl" data-split="lines">
                For anyone with a <em>reading list.</em>
              </h2>
            </div>
            <ul className="wall">
              {audiences.map((a, i) => (
                <li key={a.key} className={`wall__item wall__item--${i + 1}`}>
                  <div data-reveal="clip">
                    <div className="wall__media">
                      <div data-parallax="0.06">
                        <Photo photo={photos[a.key]} ratio={i % 3 === 0 ? '4 / 3' : '4 / 5'} sizes="(min-width: 1024px) 45vw, 100vw" />
                      </div>
                    </div>
                  </div>
                  <h3 className="wall__title">{a.title}</h3>
                  <p className="wall__text">{a.text}</p>
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* PRICING */}
        <section className="price-sec" aria-labelledby="price-title">
          <div className="wrap">
            <div className="price-sec__head">
              <Node day={38} />
              <h2 id="price-title" className="display h-xl" data-split="lines">
                Start free. Upgrade <em>when it sticks.</em>
              </h2>
            </div>
            <Pricing />
            <p className="price-sec__more">
              <Link href="/pricing/" className="link">
                Compare every feature by plan
              </Link>
            </p>
          </div>
        </section>
      </Thread>
    </>
  );
}

/** SVG arc path between two angles (degrees, 0 = top, clockwise). */
function arc(cx: number, cy: number, r: number, a0: number, a1: number) {
  const p = (a: number) => {
    const rad = ((a - 90) * Math.PI) / 180;
    return `${(cx + r * Math.cos(rad)).toFixed(2)} ${(cy + r * Math.sin(rad)).toFixed(2)}`;
  };
  return `M${p(a0)} A${r} ${r} 0 0 1 ${p(a1)}`;
}
