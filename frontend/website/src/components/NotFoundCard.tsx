import { FlipCard } from './FlipCard';

export function NotFoundCard() {
  return (
    <FlipCard
      className="lost__card"
      meta="Card 404"
      question="Where did this page go?"
      answer="Not here. Everything else is one link away."
    />
  );
}
