import type { Metadata } from 'next';
import { breadcrumbs, ld, pageMeta } from '@/lib/seo';
import Link from 'next/link';
import { Arrow } from '@/components/Footer';
import { FlipCard } from '@/components/FlipCard';
import { Photo } from '@/components/Photo';
import { photos, site } from '@/data/site';

export const metadata: Metadata = pageMeta({
  title: 'About: why Lumina IQ exists',
  description:
    'Lumina IQ is built by GenrecAI on one idea: students should spend their time practising and revising, not preparing notes and cards by hand.',
  path: '/about/',
});

const principles = [
  {
    title: 'Your material, not the internet',
    text: 'Exams test your course. Lumina IQ answers and writes questions from the documents you upload, not from whatever a model happens to know.',
  },
  {
    title: 'Every answer shows its source',
    text: 'A citation on every answer means you can check anything in a few seconds, and you learn where in the chapter it lives.',
  },
  {
    title: 'Retrieval beats rereading',
    text: 'Recalling an answer strengthens memory far more than reading it again. So the product keeps asking you things.',
  },
  {
    title: 'The right review on the right day',
    text: 'Forgetting is predictable. Lumina IQ schedules each topic just before it slips, so short sessions add up to long-term memory.',
  },
];

export default function About() {
  return (
    <>
      <section className="page-hero" aria-labelledby="about-title">
        <div className="wrap page-hero__grid page-hero__grid--card">
          <h1 id="about-title" className="display h-mega rise">
            Studying should be <em>practice,</em> not preparation.
          </h1>
          <div className="page-hero__aside">
            <p className="lede rise" style={{ ['--d' as string]: '0.15s' }}>
              Highlighting, summarizing, copying definitions onto cards. Students spend hours getting ready to study.
              Lumina IQ exists to hand those hours back.
            </p>
          </div>
          <FlipCard
            className="page-hero__card rise"
            meta="Card 1 · How memory works"
            question="What makes a fact stick: reading it again, or recalling it?"
            answer="Recalling it. Each time you pull an answer out of memory, it lasts longer. That is the whole product."
          />
        </div>
      </section>

      <section className="about-pair" aria-labelledby="story-title">
        <div className="wrap about-pair__grid">
          <div className="about-pair__media" data-reveal="clip">
            <div className="wall__media">
              <div data-parallax="0.06">
                <Photo photo={photos.books} ratio="4 / 5" sizes="(min-width: 1024px) 40vw, 100vw" />
              </div>
            </div>
          </div>
          <div className="about-pair__copy">
            <h2 id="story-title" className="display h-l" data-split="lines">
              One upload, the whole study loop
            </h2>
            <p data-reveal="up">
              Most AI tools stop at a summary. That is the easy part. The hard part of studying is coming back to the
              material often enough, at the right moments, to still know it on exam day.
            </p>
            <p data-reveal="up">
              So Lumina IQ connects the steps: understand the chapter, practise it, measure what is not landing, and revise
              on a schedule. Each step uses the same document, so nothing gets lost between tools.
            </p>
            <p data-reveal="up">
              Lumina IQ is built by{' '}
              <a className="link" href={site.maker.url} rel="noopener" target="_blank">
                {site.maker.name}
              </a>
              . Under the hood: semantic search over a vector database, and assessments generated from your own pages.
            </p>
          </div>
        </div>
      </section>

      <section className="principles" aria-labelledby="principles-title">
        <div className="wrap">
          <h2 id="principles-title" className="display h-xl" data-split="lines">
            What we <em>hold to</em>
          </h2>
          <ul className="principles__list">
            {principles.map((p) => (
              <li key={p.title} data-reveal="up">
                <h3 className="display h-m">{p.title}</h3>
                <p>{p.text}</p>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="about-pair about-pair--flip" aria-labelledby="contact-title">
        <div className="wrap about-pair__grid">
          <div className="about-pair__copy">
            <h2 id="contact-title" className="display h-l" data-split="lines">
              Teaching a class? Running a study group?
            </h2>
            <p data-reveal="up">
              The Institution plan gives every student Scholar-level access for ₹179 a month, lets teachers publish books to
              whole classes, and shows a class dashboard of progress and weak topics.
            </p>
            <div className="actions" data-reveal="up">
              <a href={`mailto:${site.email}`} className="btn btn--dark">
                <span>Email the team</span>
                <Arrow />
              </a>
              <Link href="/pricing/" className="btn btn--light">
                <span>See plans</span>
              </Link>
            </div>
          </div>
          <div className="about-pair__media" data-reveal="clip">
            <div className="wall__media">
              <div data-parallax="0.06">
                <Photo photo={photos.group} ratio="4 / 3" sizes="(min-width: 1024px) 40vw, 100vw" />
              </div>
            </div>
          </div>
        </div>
      </section>
      <script type="application/ld+json" dangerouslySetInnerHTML={ld(breadcrumbs('About', '/about/'))} />
    </>
  );
}
