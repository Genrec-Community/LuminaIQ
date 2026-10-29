'use client';
import { useState } from 'react';

type Props = { meta: string; question: string; answer: string; answerMeta?: string; className?: string };

/** A flashcard that flips on click or Enter: the product's own object, used as a page's hero piece. */
export function FlipCard({ meta, question, answer, answerMeta = 'Answer', className }: Props) {
  const [flipped, setFlipped] = useState(false);
  return (
    <div className={`demo demo--flash ${className ?? ''}`}>
      <button
        type="button"
        className={`flip ${flipped ? 'is-flipped' : ''}`}
        onClick={() => setFlipped((f) => !f)}
        aria-pressed={flipped}
      >
        <span className="flip__inner">
          <span className="flip__face flip__front" aria-hidden={flipped}>
            <span className="flip__meta">{meta}</span>
            <span className="flip__text">{question}</span>
            <span className="flip__hint">Flip</span>
          </span>
          <span className="flip__face flip__back" aria-hidden={!flipped}>
            <span className="flip__meta">{answerMeta}</span>
            <span className="flip__text">{answer}</span>
          </span>
        </span>
      </button>
    </div>
  );
}
