'use client';
import { useState } from 'react';

export function NotFoundCard() {
  const [flipped, setFlipped] = useState(false);
  return (
    <div className="demo demo--flash lost__card">
      <button
        type="button"
        className={`flip ${flipped ? 'is-flipped' : ''}`}
        onClick={() => setFlipped((f) => !f)}
        aria-pressed={flipped}
      >
        <span className="flip__inner">
          <span className="flip__face flip__front" aria-hidden={flipped}>
            <span className="flip__meta">Card 404</span>
            <span className="flip__text">Where did this page go?</span>
            <span className="flip__hint">Flip</span>
          </span>
          <span className="flip__face flip__back" aria-hidden={!flipped}>
            <span className="flip__meta">Answer</span>
            <span className="flip__text">Not here. Everything else is one link away.</span>
          </span>
        </span>
      </button>
    </div>
  );
}
