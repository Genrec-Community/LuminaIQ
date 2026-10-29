import type { Metadata } from 'next';
import { breadcrumbs, ld, pageMeta } from '@/lib/seo';
import Link from 'next/link';
import { Faq } from '@/components/Faq';
import { Arrow } from '@/components/Footer';
import { faqs, loop, pipeline, reviewDays, site } from '@/data/site';

export const metadata: Metadata = pageMeta({
  title: 'How it works: from your PDF to cited answers',
  description:
    'What happens after you upload: text extraction and OCR, chunking and embeddings, vector search, cited generation, then a review schedule timed to your memory.',
  path: '/how-it-works/',
});

const howFaqs = faqs.filter((f) => ['What can I upload?', 'Does Lumina IQ make things up?', 'What is spaced repetition, exactly?'].includes(f.q));

export default function HowItWorks() {
  return (
    <>
      <section className="page-hero" aria-labelledby="how-title">
        <div className="wrap page-hero__grid">
          <h1 id="how-title" className="display h-mega rise">
            What happens after you <em>upload.</em>
          </h1>
          <div className="page-hero__aside">
            <p className="lede rise" style={{ ['--d' as string]: '0.15s' }}>
              Five steps turn a file into something you can question. Then a schedule takes over and decides when you
              see each idea again.
            </p>
          </div>
        </div>
      </section>

      {/* PIPELINE: a real sequence, so it is numbered */}
      <section className="pipe" aria-labelledby="pipe-title">
        <div className="wrap">
          <h2 id="pipe-title" className="pipe__title">The pipeline</h2>
          <div className="pipe__track">
            <svg className="pipe__line" viewBox="0 0 1000 40" preserveAspectRatio="none" aria-hidden="true">
              <path pathLength={1} d="M0 20 C 120 4 180 36 250 20 S 380 4 500 20 S 620 36 750 20 S 880 4 1000 20" />
            </svg>
            <ol className="pipe__steps">
              {pipeline.map((p, i) => (
                <li key={p.title} className="step" data-reveal="up" data-delay={String(i * 0.08)}>
                  <span className="step__n" aria-hidden="true">{i + 1}</span>
                  <h3 className="step__title">{p.title}</h3>
                  <p>{p.text}</p>
                  <p className="step__why">{p.why}</p>
                </li>
              ))}
            </ol>
          </div>
          <p className="pipe__note">
            In short: retrieval-augmented generation over your own documents. The model only writes from the passages it
            finds in your upload, which is why every answer can cite its page.
          </p>
        </div>
      </section>

      {/* SCHEDULE */}
      <section className="sched" aria-labelledby="sched-title">
        <div className="wrap sched__grid">
          <div className="sched__copy">
            <h2 id="sched-title" className="display h-xl" data-split="lines">
              Then the <em>schedule</em> takes over.
            </h2>
            <p data-reveal="up">
              Every answer you give is evidence. Lumina IQ keeps an estimate of how well you know each topic and how fast
              you are forgetting it, and brings the topic back just before it slips. Every review you get right makes the
              memory last longer, so the gaps grow.
            </p>
            <p data-reveal="up">A topic you miss comes back sooner. A topic you know drifts out to months.</p>
          </div>
          <div className="sched__days" data-reveal="up">
            <p className="sched__label">A topic you keep remembering, bars drawn to scale</p>
            <ol>
              {reviewDays.map((d, i) => (
                <li key={d} style={{ ['--w' as string]: `${Math.max(3, (d / reviewDays[reviewDays.length - 1]) * 100)}%` }}>
                  <span className="sched__n">Review {i + 1}</span>
                  <span className="sched__bar" aria-hidden="true" />
                  <span className="sched__d">
                    day <b>{d}</b>
                  </span>
                </li>
              ))}
            </ol>
          </div>
        </div>
      </section>

      {/* LOOP recap */}
      <section className="recap" aria-labelledby="recap-title">
        <div className="wrap">
          <h2 id="recap-title" className="display h-l" data-split="lines">
            Around it, the loop
          </h2>
          <ul className="recap__list">
            {loop.map((l) => (
              <li key={l.stage} data-reveal="up">
                <h3>{l.stage}</h3>
                <p>{l.text}</p>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* FAQ */}
      <section className="faq-sec" aria-labelledby="how-faq">
        <div className="wrap faq-sec__grid">
          <h2 id="how-faq" className="display h-l" data-split="lines">
            Questions people ask first
          </h2>
          <Faq items={howFaqs} />
        </div>
      </section>

      <section className="band" aria-labelledby="band-title">
        <div className="wrap band__inner">
          <h2 id="band-title" className="display h-xl" data-split="lines">
            Try it on tonight’s <em>reading.</em>
          </h2>
          <div className="actions">
            <a href={site.appUrl} className="btn btn--dark">
              <span>Start free</span>
              <Arrow />
            </a>
            <Link href="/features/" className="btn btn--light">
              <span>Browse the tools</span>
            </Link>
          </div>
        </div>
      </section>
      <script type="application/ld+json" dangerouslySetInnerHTML={ld(breadcrumbs('How it works', '/how-it-works/'))} />
    </>
  );
}
