'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

/** The closing band's second button: Compare plans, except on the pricing page, where it would point at itself. */
export function FinaleLink() {
  const onPricing = usePathname()?.startsWith('/pricing');
  return (
    <Link href={onPricing ? '/how-it-works/' : '/pricing/'} className="btn btn--ghost">
      <span>{onPricing ? 'See how it works' : 'Compare plans'}</span>
    </Link>
  );
}
