// The Lumina IQ mark, shared with the marketing site: a tiny memory curve that sinks,
// gets lifted by a review, and sinks less each time.
export function Mark({ className = 'h-8 w-8', ink = '#163628', lime = '#D3EE6A' }) {
    return (
        <svg className={`lumina-logomark ${className}`} viewBox="0 0 32 32" aria-hidden="true" focusable="false">
            <rect width="32" height="32" rx="9" fill={ink} />
            <path d="M6 9c2.5 7 4 9 6.5 9.5V9c2.6 6 5 7.6 7.5 7.8V9c2 4.5 4 5.4 6 5.6"
                fill="none" stroke={lime} strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
            <circle cx="26" cy="22.5" r="2.4" fill={lime} />
        </svg>
    );
}

export default function Logo({ className = '', size = 'h-8 w-8', word = true }) {
    return (
        <span className={`lumina-logo ${className}`}>
            <Mark className={size} />
            {word && <span className="lumina-logo__word">Lumina<span>IQ</span></span>}
        </span>
    );
}
