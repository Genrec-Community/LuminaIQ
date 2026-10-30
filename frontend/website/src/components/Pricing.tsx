'use client';
import { useState } from 'react';
import { examNightPass, plans } from '@/data/site';

const money = (n: number) => `₹${n.toLocaleString('en-IN')}`;

/** Plans with a monthly / yearly switch; the same plans the app sells at /plans. */
export function Pricing({ headingLevel = 'h3' }: { headingLevel?: 'h2' | 'h3' }) {
  const [annual, setAnnual] = useState(false);
  const H = headingLevel;
  return (
    <div className="pricing">
      <div className="billing" role="group" aria-label="Billing period">
        <button type="button" className="billing__opt" aria-pressed={!annual} onClick={() => setAnnual(false)}>
          Monthly billing
        </button>
        <button type="button" className="billing__opt" aria-pressed={annual} onClick={() => setAnnual(true)}>
          Yearly billing <span className="billing__save">save about 30%</span>
        </button>
      </div>

      <ul className="plans">
        {plans.map((p, i) => {
          const price = annual ? p.annualPerMonth : p.monthly;
          return (
            <li key={p.id} className={`plan ${p.popular ? 'plan--popular' : ''}`} data-reveal="settle" data-tilt={String([-2.5, 0, 2.5][i] ?? 0)} data-delay={String(i * 0.1)}>
              {p.popular && <p className="plan__badge">Most popular</p>}
              <div className="plan__top">
                <H className="plan__name">{p.name}</H>
                <p className="plan__who">{p.who}</p>
                <p className="plan__price">
                  <span className="plan__amount" aria-live="polite">{money(price)}</span>
                  <span className="plan__per">
                    {p.monthly === 0 ? 'forever' : annual ? `per month, ${money(p.yearly)} a year` : 'per month'}
                  </span>
                </p>
                <a href={annual && p.monthly ? `${p.href}&cycle=yearly` : p.href} className={`btn ${p.popular ? 'btn--dark' : 'btn--soft'} btn--block`}>
                  <span>{p.cta}</span>
                </a>
              </div>
              <div className="plan__body">
                <p className="plan__inc">{p.includesLabel}</p>
                <ul className="ticks">
                  {p.features.map((f) => (
                    <li key={f}>{f}</li>
                  ))}
                </ul>
              </div>
            </li>
          );
        })}
      </ul>
      <p className="pricing__pass">
        Exam tomorrow? The <a className="link" href={examNightPass.href}>Exam Night Pass</a> gives you {examNightPass.hours} hours of Topper for ₹{examNightPass.price}. One payment, nothing renews.
      </p>
    </div>
  );
}
