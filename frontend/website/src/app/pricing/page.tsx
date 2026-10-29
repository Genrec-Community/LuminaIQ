import type { Metadata } from 'next';
import { breadcrumbs, ld, pageMeta } from '@/lib/seo';
import { Faq } from '@/components/Faq';
import { Pricing } from '@/components/Pricing';
import { comparison, faqs, plans } from '@/data/site';

export const metadata: Metadata = pageMeta({
  title: 'Pricing: Free, Scholar ₹299 and Topper ₹999 a month',
  description:
    'Start free with 3 books. Scholar is ₹299 a month for 15 books and a smarter AI model. Topper is ₹999 a month for unlimited books and Deep mode. Exam Night Pass: ₹49 for 48 hours.',
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
            Free to start. <em>₹299</em> to keep going.
          </h1>
          <p className="lede rise" style={{ ['--d' as string]: '0.15s' }}>
            Every plan includes chat with citations, quizzes, your learning path and reviews timed to your memory. Upgrade for
            more books, more practice and a smarter AI model. Pay by UPI, card or netbanking.
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
                      <span>{p.monthly === 0 ? '₹0' : `₹${p.monthly} / month`}</span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {comparison.map((r) => (
                  <tr key={r.row}>
                    <th scope="row">{r.row}</th>
                    <td><Cell v={r.free} /></td>
                    <td className="is-popular"><Cell v={r.scholar} /></td>
                    <td><Cell v={r.topper} /></td>
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
