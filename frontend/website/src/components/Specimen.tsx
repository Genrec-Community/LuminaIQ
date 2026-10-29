// Small illustrative cards, one per tool, built from an example chapter on photosynthesis.
// They demonstrate what each tool produces; they are not screenshots of the app.

export function Specimen({ slug }: { slug: string }) {
  switch (slug) {
    case 'chat':
      return (
        <div className="spec spec--chat">
          <p className="spec__q">Why does the Calvin cycle need ATP?</p>
          <p className="spec__a">
            It spends ATP and NADPH from the light reactions to turn carbon dioxide into sugar.
            <span className="cite">Biology, ch. 8, p. 142</span>
          </p>
        </div>
      );
    case 'quizzes':
      return (
        <div className="spec spec--quiz">
          <p className="spec__meta">Question 3 of 10 · Medium</p>
          <p className="spec__q">Which molecule is split in the light reactions?</p>
          <ul>
            <li>Glucose</li>
            <li className="is-right">Water</li>
            <li>Carbon dioxide</li>
          </ul>
        </div>
      );
    case 'notes':
      return (
        <div className="spec spec--notes">
          <p className="spec__tabs">
            <span>Summary</span>
            <span className="is-on">Key facts</span>
            <span>Glossary</span>
            <span>Cheat sheet</span>
          </p>
          <ul>
            <li>Light reactions happen in the thylakoid membranes.</li>
            <li>Water is split; oxygen is released.</li>
            <li>The Calvin cycle runs in the stroma.</li>
          </ul>
        </div>
      );
    case 'flashcards':
      return (
        <div className="spec spec--card">
          <p className="spec__meta">Card 7 of 24</p>
          <p className="spec__q">Where do the light-dependent reactions happen?</p>
          <p className="spec__hint">Flip for the answer</p>
        </div>
      );
    case 'mind-maps':
      return (
        <div className="spec spec--map">
          <svg viewBox="0 0 240 140" aria-hidden="true">
            <g className="map__edges">
              <path d="M120 70 L46 30 M120 70 L50 112 M120 70 L196 34 M120 70 L194 110 M46 30 L20 64" />
            </g>
            <g className="map__nodes">
              <rect x="78" y="58" width="84" height="24" rx="12" className="is-root" />
              <rect x="10" y="20" width="72" height="20" rx="10" />
              <rect x="14" y="102" width="72" height="20" rx="10" />
              <rect x="160" y="24" width="72" height="20" rx="10" />
              <rect x="158" y="100" width="72" height="20" rx="10" />
            </g>
            <g className="map__labels">
              <text x="120" y="74">Photosynthesis</text>
              <text x="46" y="34">Light reactions</text>
              <text x="50" y="116">Calvin cycle</text>
              <text x="196" y="38">Chloroplast</text>
              <text x="194" y="114">Products</text>
            </g>
          </svg>
        </div>
      );
    case 'learning-paths':
      return (
        <div className="spec spec--path">
          <ol>
            <li className="is-done">Cell structure</li>
            <li className="is-done">The chloroplast</li>
            <li className="is-weak">Light reactions <em>weak area</em></li>
            <li>Calvin cycle</li>
            <li>Cellular respiration</li>
          </ol>
        </div>
      );
    case 'spaced-repetition':
      return (
        <div className="spec spec--srs">
          <p className="spec__meta">Next reviews for this card</p>
          <ol>
            {[1, 6, 15, 38, 95].map((d, i) => (
              <li key={d} className={i < 2 ? 'is-done' : i === 2 ? 'is-next' : ''}>
                <b>{d}</b>
                <span>{d === 1 ? 'day' : 'days'}</span>
              </li>
            ))}
          </ol>
          <p className="spec__hint">Remembered it? The gap grows. Missed it? Back to day 1.</p>
        </div>
      );
    case 'progress':
      return (
        <div className="spec spec--xp">
          <p className="spec__row">
            <span>Level 7</span>
            <span>
              <b>12</b> day streak
            </span>
          </p>
          <span className="xp" aria-hidden="true">
            <span style={{ width: '68%' }} />
          </span>
          <p className="spec__meta">340 XP to level 8</p>
          <p className="badges" aria-hidden="true">
            <span>First quiz</span>
            <span>7-day streak</span>
            <span>100 cards</span>
          </p>
        </div>
      );
    default:
      return null;
  }
}
