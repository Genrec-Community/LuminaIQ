'use client';
// Working demos for the features page. Example content only (a chapter on photosynthesis).
import { useState } from 'react';

const cards = [
  { q: 'Where do the light-dependent reactions happen?', a: 'In the thylakoid membranes of the chloroplast.' },
  { q: 'What gas is released when water is split?', a: 'Oxygen.' },
  { q: 'Which enzyme fixes carbon dioxide in the Calvin cycle?', a: 'RuBisCO.' },
];

export function FlashcardDemo() {
  const [i, setI] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [known, setKnown] = useState<Record<number, boolean>>({});
  const card = cards[i];
  const next = (k?: boolean) => {
    if (k !== undefined) setKnown((m) => ({ ...m, [i]: k }));
    setFlipped(false);
    setI((v) => (v + 1) % cards.length);
  };
  const knownCount = Object.values(known).filter(Boolean).length;
  return (
    <div className="demo demo--flash">
      <button
        type="button"
        className={`flip ${flipped ? 'is-flipped' : ''}`}
        onClick={() => setFlipped((f) => !f)}
        aria-pressed={flipped}
      >
        <span className="flip__inner">
          <span className="flip__face flip__front" aria-hidden={flipped}>
            <span className="flip__meta">Question {i + 1} of {cards.length}</span>
            <span className="flip__text">{card.q}</span>
            <span className="flip__hint">Flip</span>
          </span>
          <span className="flip__face flip__back" aria-hidden={!flipped}>
            <span className="flip__meta">Answer</span>
            <span className="flip__text">{card.a}</span>
          </span>
        </span>
      </button>
      <div className="demo__row">
        <button type="button" className="chip" onClick={() => next(false)}>
          Not yet
        </button>
        <button type="button" className="chip chip--on" onClick={() => next(true)}>
          I knew it
        </button>
        <p className="demo__status" aria-live="polite">
          {knownCount} known
        </p>
      </div>
    </div>
  );
}

const quiz = {
  q: 'Which molecule is split during the light-dependent reactions?',
  options: ['Glucose', 'Water', 'Carbon dioxide', 'ATP'],
  right: 1,
  why: 'Water is split in photosystem II, which releases oxygen and supplies electrons. Source: ch. 8, p. 139.',
};

export function QuizDemo() {
  const [pick, setPick] = useState<number | null>(null);
  return (
    <div className="demo demo--quiz">
      <p className="demo__meta">Question 3 of 10 · Medium · Light reactions</p>
      <p className="demo__q" id="quiz-q">{quiz.q}</p>
      <ul className="options" aria-labelledby="quiz-q">
        {quiz.options.map((o, i) => {
          const state = pick === null ? '' : i === quiz.right ? 'is-right' : i === pick ? 'is-wrong' : 'is-dim';
          return (
            <li key={o}>
              <button type="button" className={`option ${state}`} onClick={() => setPick(i)} disabled={pick !== null} aria-pressed={pick === i}>
                {o}
              </button>
            </li>
          );
        })}
      </ul>
      <p className="demo__feedback" aria-live="polite">
        {pick === null ? 'Choose an answer.' : pick === quiz.right ? `Correct. ${quiz.why}` : `Not quite. ${quiz.why}`}
      </p>
      {pick !== null && (
        <button type="button" className="chip" onClick={() => setPick(null)}>
          Try again
        </button>
      )}
    </div>
  );
}

const notes = {
  Summary:
    'Photosynthesis turns light energy into chemical energy in two stages. In the thylakoid membranes, light splits water, releases oxygen and makes ATP and NADPH. In the stroma, the Calvin cycle spends that ATP and NADPH to fix carbon dioxide into sugar.',
  'Key facts': [
    'Light reactions: thylakoid membranes.',
    'Water is split; oxygen is the by-product.',
    'Calvin cycle: stroma; needs ATP and NADPH.',
    'RuBisCO fixes carbon dioxide.',
  ],
  Glossary: [
    ['Thylakoid', 'membrane sac inside the chloroplast where the light reactions run'],
    ['Stroma', 'fluid around the thylakoids, home of the Calvin cycle'],
    ['RuBisCO', 'the enzyme that fixes carbon dioxide'],
  ],
  'Cheat sheet': ['Light + H₂O → O₂ + ATP + NADPH', 'CO₂ + ATP + NADPH → sugar', 'Where: thylakoid, then stroma'],
} as const;

type NoteKind = keyof typeof notes;

export function NotesDemo() {
  const kinds = Object.keys(notes) as NoteKind[];
  const [kind, setKind] = useState<NoteKind>('Summary');
  const body = notes[kind];
  return (
    <div className="demo demo--notes">
      <div className="tabs" role="tablist" aria-label="Note type">
        {kinds.map((k) => (
          <button key={k} type="button" role="tab" id={`tab-${k}`} aria-selected={k === kind} aria-controls="notes-panel" className="tab" onClick={() => setKind(k)}>
            {k}
          </button>
        ))}
      </div>
      <div className="notes" role="tabpanel" id="notes-panel" aria-labelledby={`tab-${kind}`}>
        {typeof body === 'string' ? (
          <p>{body}</p>
        ) : kind === 'Glossary' ? (
          <dl>
            {(body as readonly (readonly [string, string])[]).map(([t, d]) => (
              <div key={t}>
                <dt>{t}</dt>
                <dd>{d}</dd>
              </div>
            ))}
          </dl>
        ) : (
          <ul>
            {(body as readonly string[]).map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
