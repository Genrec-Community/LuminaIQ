import type { Metadata } from 'next';
import { breadcrumbs, ld, pageMeta } from '@/lib/seo';
import { Faq } from '@/components/Faq';
import { Pricing } from '@/components/Pricing';
import { comparison, faqs, plans } from '@/data/site';

export const metadata: Metadata = pageMeta({
  title: 'Pricing: Free, Pro $9 a month, Team $29 a month',
  description:
    'Start free with 3 documents and unlimited chat and quizzes. Pro is $9 a month for unlimited documents and spaced repetition. Team is $29 a month for up to 10 members.',
  path: '/pricing/',
});

const faqLd = {
  '@context': 'https://schema.org',
  '@type': 'FAQPage',
  mainEntity: faqs.map((f) => ({ '@type': 'Question', name: f.q, acceptedAnswer: { '@type': 'Answer', text: f.a } })),
};

function Cell({ v }: { v: string | boolean }) {
  if (v === true) return <span className="yes">Included</span>;
  if (v === false) return <span className="no">Not included</span>;
  return <>{v}</>;
}

export default function PricingPage() {
  return (
    <>
      <section className="page-hero page-hero--center" aria-labelledby="pricing-title">
        <div className="wrap">
          <h1 id="pricing-title" className="display h-mega rise">
            Free to start. <em>Nine dollars</em> to keep going.
          </h1>
          <p className="lede rise" style={{ ['--d' as string]: '0.15s' }}>
            Every plan includes document chat with citations and unlimited quizzes. Upgrade for unlimited documents and a
            review schedule with no end date.
          </p>
        </div>
      </section>

      <section className="wrap price-page" aria-label="Plans">
        <Pricing headingLevel="h2" />
      </section>

      <section className="compare" aria-labelledby="compare-title">
        <div className="wrap">
          <h2 id="compare-title" className="display h-l" data-split="lines">
            Every feature, plan by plan
          </h2>
          <div className="compare__scroll" tabIndex={0} role="region" aria-labelledby="compare-title">
            <table className="compare__table">
              <thead>
                <tr>
                  <th scope="col">
                    <span className="sr-only">Feature</span>
                  </th>
                  {plans.map((p) => (
                    <th key={p.id} scope="col" className={p.popular ? 'is-popular' : undefined}>
                      {p.name}
                      <span>{p.monthly === 0 ? '$0' : `$${p.monthly} / month`}</span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {comparison.map((r) => (
                  <tr key={r.row}>
                    <th scope="row">{r.row}</th>
                    <td><Cell v={r.free} /></td>
                    <td className="is-popular"><Cell v={r.pro} /></td>
                    <td><Cell v={r.team} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section className="faq-sec" aria-labelledby="faq-title">
        <div className="wrap faq-sec__grid">
          <h2 id="faq-title" className="display h-l" data-split="lines">
            Before you pick a plan
          </h2>
          <Faq items={faqs} />
        </div>
      </section>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(faqLd).replace(/</g, '\\u003c') }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={ld(breadcrumbs('Pricing', '/pricing/'))} />
    </>
  );
}
