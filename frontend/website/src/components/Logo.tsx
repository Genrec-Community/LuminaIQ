/** The mark is a tiny memory curve: it sinks, a review lifts it, it sinks less. */
export function Mark({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 32 32" aria-hidden="true" focusable="false">
      <rect width="32" height="32" rx="9" fill="currentColor" />
      <path
        d="M6 9c2.5 7 4 9 6.5 9.5V9c2.6 6 5 7.6 7.5 7.8V9c2 4.5 4 5.4 6 5.6"
        fill="none"
        stroke="var(--c-accent)"
        strokeWidth="2.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="26" cy="22.5" r="2.4" fill="var(--c-accent)" />
    </svg>
  );
}

export function Logo() {
  return (
    <span className="logo">
      <Mark className="logo__mark" />
      <span className="logo__word">
        Lumina <span>IQ</span>
      </span>
    </span>
  );
}
