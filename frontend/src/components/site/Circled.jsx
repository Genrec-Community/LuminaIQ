// The hand-drawn lime highlighter circle from the site's hero, drawn once on entry.
export default function Circled({ children, delay = 0.5 }) {
    return (
        <span className="circled">
            {children}
            <svg viewBox="0 0 300 110" aria-hidden="true" preserveAspectRatio="none">
                <path pathLength={1} style={{ animationDelay: `${delay}s` }}
                    d="M226 14C170 2 70 4 30 26 4 41 6 72 44 88c52 21 168 20 220-2 30-13 34-42 8-60-24-16-90-22-150-14" />
            </svg>
        </span>
    );
}
