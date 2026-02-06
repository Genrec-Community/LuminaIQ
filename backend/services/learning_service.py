"""
Learning Service - Adaptive Learning System

Features:
1. PerformanceTracker - Track quiz scores per topic using HashMap
2. WeaknessDetector - Identify weak areas using Sliding Window + Min-Heap
3. SpacedRepetition - SM-2 algorithm with Priority Queue (Min-Heap)

DSA Used:
- HashMap (dict) for O(1) topic lookups
- Sliding Window for recent performance analysis
- Min-Heap (heapq) for top-N weak topics and review scheduling
- SM-2 Algorithm for optimal spaced repetition intervals
"""

import heapq
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
from db.client import supabase_client
from utils.logger import logger
from uuid import uuid4
import math


class PerformanceTracker:
    """
    Track user performance per topic.

    DSA: HashMap for O(1) topic performance lookups

    Stores:
    - correct_count: Number of correct answers
    - wrong_count: Number of wrong answers
    - last_attempt: Timestamp of last attempt
    - history: Recent attempt results (for sliding window)
    """

    def __init__(self):
        self.client = supabase_client

    async def record_performance(
        self, user_id: str, project_id: str, topic: str, correct: int, wrong: int
    ) -> Dict[str, Any]:
        """
        Record quiz performance for a topic.
        Uses UPSERT pattern - insert or update existing record.
        """
        try:
            # Check if record exists
            existing = (
                self.client.table("user_performance")
                .select("*")
                .eq("user_id", user_id)
                .eq("project_id", project_id)
                .eq("topic", topic)
                .execute()
            )

            now = datetime.utcnow().isoformat()

            if existing.data:
                # Update existing record
                record = existing.data[0]
                new_correct = record["correct_count"] + correct
                new_wrong = record["wrong_count"] + wrong

                # Append to history (keep last 20 attempts)
                history = record.get("history") or []
                history.append({"correct": correct, "wrong": wrong, "timestamp": now})
                history = history[-20:]  # Sliding window of last 20

                result = (
                    self.client.table("user_performance")
                    .update(
                        {
                            "correct_count": new_correct,
                            "wrong_count": new_wrong,
                            "last_attempt": now,
                            "history": history,
                        }
                    )
                    .eq("id", record["id"])
                    .execute()
                )

                logger.info(
                    f"Updated performance for topic '{topic}': +{correct} correct, +{wrong} wrong"
                )
                return result.data[0] if result.data else {}
            else:
                # Insert new record
                history = [{"correct": correct, "wrong": wrong, "timestamp": now}]

                result = (
                    self.client.table("user_performance")
                    .insert(
                        {
                            "id": str(uuid4()),
                            "user_id": user_id,
                            "project_id": project_id,
                            "topic": topic,
                            "correct_count": correct,
                            "wrong_count": wrong,
                            "last_attempt": now,
                            "history": history,
                        }
                    )
                    .execute()
                )

                logger.info(f"Created performance record for topic '{topic}'")
                return result.data[0] if result.data else {}

        except Exception as e:
            logger.error(f"Error recording performance: {e}")
            raise

    async def get_performance(
        self, user_id: str, project_id: str, topic: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get performance records for user, optionally filtered by topic."""
        try:
            query = (
                self.client.table("user_performance")
                .select("*")
                .eq("user_id", user_id)
                .eq("project_id", project_id)
            )

            if topic:
                query = query.eq("topic", topic)

            result = query.order("last_attempt", desc=True).execute()
            return result.data or []

        except Exception as e:
            logger.error(f"Error getting performance: {e}")
            return []

    async def get_all_user_performance(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all performance records across all projects for a user."""
        try:
            result = (
                self.client.table("user_performance")
                .select("*")
                .eq("user_id", user_id)
                .order("last_attempt", desc=True)
                .execute()
            )
            return result.data or []
        except Exception as e:
            logger.error(f"Error getting all user performance: {e}")
            return []


class WeaknessDetector:
    """
    Detect weak topics based on performance data.

    DSA Used:
    - Sliding Window: Analyze recent N attempts for trend detection
    - Min-Heap: Get top-K weakest topics efficiently O(n log k)

    Weakness Score Formula:
    - Base: wrong_count / (correct_count + wrong_count)
    - Recent Weight: Give more weight to recent attempts
    - Decay: Topics not attempted recently get slight boost (assumed forgotten)
    """

    def __init__(self):
        self.client = supabase_client

    def calculate_weakness_score(
        self, record: Dict[str, Any], window_size: int = 10
    ) -> float:
        """
        Calculate weakness score for a topic.

        Score = 0.0 (strong) to 1.0 (weak)

        Components:
        1. Overall accuracy (40% weight)
        2. Recent accuracy - sliding window (40% weight)
        3. Time decay - forgotten topics (20% weight)
        """
        correct = record.get("correct_count", 0)
        wrong = record.get("wrong_count", 0)
        total = correct + wrong

        if total == 0:
            return 0.5  # Neutral for untested topics

        # 1. Overall accuracy (inverted - higher wrong = higher weakness)
        overall_weakness = wrong / total

        # 2. Recent accuracy using sliding window
        history = record.get("history") or []
        recent = history[-window_size:] if history else []

        if recent:
            recent_correct = sum(h.get("correct", 0) for h in recent)
            recent_wrong = sum(h.get("wrong", 0) for h in recent)
            recent_total = recent_correct + recent_wrong
            recent_weakness = recent_wrong / recent_total if recent_total > 0 else 0.5
        else:
            recent_weakness = overall_weakness

        # 3. Time decay (topics not practiced recently are likely forgotten)
        last_attempt_str = record.get("last_attempt")
        if last_attempt_str:
            try:
                last_attempt = datetime.fromisoformat(
                    last_attempt_str.replace("Z", "+00:00")
                )
                days_since = (datetime.now(last_attempt.tzinfo) - last_attempt).days
                # Decay factor: increases weakness by up to 0.3 if not practiced in 30 days
                time_decay = min(0.3, days_since / 100)
            except:
                time_decay = 0
        else:
            time_decay = 0.1

        # Weighted combination
        weakness_score = (
            0.4 * overall_weakness + 0.4 * recent_weakness + 0.2 * time_decay
        )

        return min(1.0, weakness_score)

    async def get_weak_topics(
        self, user_id: str, project_id: str, top_k: int = 5, threshold: float = 0.3
    ) -> List[Dict[str, Any]]:
        """
        Get top-K weakest topics using Min-Heap.

        DSA: Min-Heap of size K
        - Push all topics with their weakness scores
        - Keep only top K weakest (highest scores)

        Time Complexity: O(n log k) where n = topics, k = top_k
        """
        try:
            # Get all performance records
            result = (
                self.client.table("user_performance")
                .select("*")
                .eq("user_id", user_id)
                .eq("project_id", project_id)
                .execute()
            )

            records = result.data or []

            if not records:
                return []

            # Use max-heap (negate scores) to get top-K weakest
            # Python's heapq is min-heap, so we negate for max behavior
            heap = []

            for record in records:
                weakness = self.calculate_weakness_score(record)

                # Only include if above threshold
                if weakness >= threshold:
                    # Use negative for max-heap behavior
                    if len(heap) < top_k:
                        heapq.heappush(heap, (weakness, record["topic"], record))
                    else:
                        # Push and pop to maintain size K
                        heapq.heappushpop(heap, (weakness, record["topic"], record))

            # Extract results sorted by weakness (descending)
            weak_topics = []
            while heap:
                score, topic, record = heapq.heappop(heap)
                weak_topics.append(
                    {
                        "topic": topic,
                        "weakness_score": round(score, 3),
                        "correct_count": record.get("correct_count", 0),
                        "wrong_count": record.get("wrong_count", 0),
                        "last_attempt": record.get("last_attempt"),
                        "recommendation": self._get_recommendation(score),
                    }
                )

            # Reverse to get highest weakness first
            weak_topics.reverse()

            return weak_topics

        except Exception as e:
            logger.error(f"Error getting weak topics: {e}")
            return []

    def _get_recommendation(self, weakness_score: float) -> str:
        """Generate recommendation based on weakness score."""
        if weakness_score >= 0.7:
            return "Critical - Review immediately and take practice quizzes"
        elif weakness_score >= 0.5:
            return "Needs improvement - Schedule regular review sessions"
        elif weakness_score >= 0.3:
            return "Fair - Light review recommended"
        else:
            return "Good - Occasional refresh sufficient"


class SpacedRepetition:
    """
    Spaced Repetition using SM-2 (SuperMemo 2) Algorithm.

    SM-2 Algorithm:
    - Easiness Factor (EF): 1.3 to 2.5 (default 2.5)
    - Quality: 0-5 rating (0-2 = fail, 3-5 = pass)
    - Interval: Days until next review

    Formula:
    - If quality < 3: Reset (interval = 1, repetition = 0)
    - If quality >= 3:
      - If repetition = 0: interval = 1
      - If repetition = 1: interval = 6
      - Else: interval = previous_interval * EF
    - EF = EF + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    - EF = max(1.3, EF)

    DSA: Priority Queue (Min-Heap) for due cards
    - Cards due soonest have highest priority
    - O(log n) insert, O(1) peek, O(log n) pop
    """

    def __init__(self):
        self.client = supabase_client
        self.MIN_EF = 1.3
        self.DEFAULT_EF = 2.5

    async def create_review_card(
        self, user_id: str, project_id: str, topic: str, question: str, answer: str
    ) -> Dict[str, Any]:
        """Create a new review card for spaced repetition."""
        try:
            now = datetime.utcnow().isoformat()

            card = {
                "id": str(uuid4()),
                "user_id": user_id,
                "project_id": project_id,
                "topic": topic,
                "question": question,
                "answer": answer,
                "easiness_factor": self.DEFAULT_EF,
                "interval_days": 0,
                "repetition": 0,
                "next_review": now,  # Due immediately
                "created_at": now,
            }

            result = self.client.table("review_cards").insert(card).execute()
            logger.info(f"Created review card for topic '{topic}'")
            return result.data[0] if result.data else {}

        except Exception as e:
            logger.error(f"Error creating review card: {e}")
            raise

    async def create_cards_from_quiz(
        self,
        user_id: str,
        project_id: str,
        topic: str,
        questions: List[Dict[str, Any]],
        wrong_only: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Create review cards from quiz questions.

        Args:
            wrong_only: If True, only create cards for incorrectly answered questions
        """
        try:
            cards = []
            now = datetime.utcnow().isoformat()

            for q in questions:
                # Skip if wrong_only and question was answered correctly
                if wrong_only and q.get("is_correct", False):
                    continue

                # Format answer with explanation
                answer = f"**Correct Answer:** {q.get('correct_answer', 'N/A')}\n\n"
                answer += f"**Explanation:** {q.get('explanation', 'No explanation provided')}"

                card = {
                    "id": str(uuid4()),
                    "user_id": user_id,
                    "project_id": project_id,
                    "topic": topic,
                    "question": q.get("question", ""),
                    "answer": answer,
                    "easiness_factor": self.DEFAULT_EF,
                    "interval_days": 0,
                    "repetition": 0,
                    "next_review": now,
                    "created_at": now,
                }
                cards.append(card)

            if cards:
                result = self.client.table("review_cards").insert(cards).execute()
                logger.info(f"Created {len(cards)} review cards for topic '{topic}'")
                return result.data or []

            return []

        except Exception as e:
            logger.error(f"Error creating cards from quiz: {e}")
            raise

    def calculate_sm2(
        self, quality: int, easiness_factor: float, interval: int, repetition: int
    ) -> Tuple[float, int, int]:
        """
        Calculate next review parameters using SM-2 algorithm.

        Args:
            quality: 0-5 rating (0=complete blackout, 5=perfect recall)
            easiness_factor: Current EF (1.3-2.5)
            interval: Current interval in days
            repetition: Number of successful repetitions

        Returns:
            Tuple of (new_ef, new_interval, new_repetition)
        """
        # Clamp quality to 0-5
        quality = max(0, min(5, quality))

        # Calculate new easiness factor
        new_ef = easiness_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        new_ef = max(self.MIN_EF, new_ef)

        if quality < 3:
            # Failed - reset
            new_interval = 1
            new_repetition = 0
        else:
            # Passed
            if repetition == 0:
                new_interval = 1
            elif repetition == 1:
                new_interval = 6
            else:
                new_interval = round(interval * new_ef)

            new_repetition = repetition + 1

        return (new_ef, new_interval, new_repetition)

    async def record_review(self, card_id: str, quality: int) -> Dict[str, Any]:
        """
        Record a review and calculate next review date.

        Quality scale:
        0 - Complete blackout, no recall
        1 - Incorrect, but recognized answer
        2 - Incorrect, but answer seemed easy to recall
        3 - Correct with serious difficulty
        4 - Correct with some hesitation
        5 - Perfect recall
        """
        try:
            # Get current card
            result = (
                self.client.table("review_cards")
                .select("*")
                .eq("id", card_id)
                .execute()
            )

            if not result.data:
                raise Exception(f"Card {card_id} not found")

            card = result.data[0]

            # Calculate new SM-2 values
            new_ef, new_interval, new_repetition = self.calculate_sm2(
                quality=quality,
                easiness_factor=card.get("easiness_factor", self.DEFAULT_EF),
                interval=card.get("interval_days", 0),
                repetition=card.get("repetition", 0),
            )

            # Calculate next review date
            next_review = datetime.utcnow() + timedelta(days=new_interval)

            # Update card
            updated = (
                self.client.table("review_cards")
                .update(
                    {
                        "easiness_factor": new_ef,
                        "interval_days": new_interval,
                        "repetition": new_repetition,
                        "next_review": next_review.isoformat(),
                        "last_reviewed": datetime.utcnow().isoformat(),
                    }
                )
                .eq("id", card_id)
                .execute()
            )

            logger.info(
                f"Reviewed card {card_id}: quality={quality}, "
                f"next_review in {new_interval} days"
            )

            return {
                "card_id": card_id,
                "quality": quality,
                "new_easiness_factor": round(new_ef, 2),
                "new_interval_days": new_interval,
                "next_review": next_review.isoformat(),
                "repetition": new_repetition,
            }

        except Exception as e:
            logger.error(f"Error recording review: {e}")
            raise

    async def get_due_cards(
        self, user_id: str, project_id: Optional[str] = None, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get cards due for review using Priority Queue concept.

        Cards are ordered by next_review date (earliest first).
        This is effectively a min-heap where priority = next_review timestamp.
        """
        try:
            now = datetime.utcnow().isoformat()

            query = (
                self.client.table("review_cards")
                .select("*")
                .eq("user_id", user_id)
                .lte("next_review", now)
            )  # Due now or overdue

            if project_id:
                query = query.eq("project_id", project_id)

            # Order by next_review (priority queue behavior)
            result = query.order("next_review", desc=False).limit(limit).execute()

            cards = result.data or []

            # Add overdue info
            for card in cards:
                try:
                    next_review = datetime.fromisoformat(
                        card["next_review"].replace("Z", "+00:00")
                    )
                    overdue_days = (datetime.now(next_review.tzinfo) - next_review).days
                    card["overdue_days"] = max(0, overdue_days)
                except:
                    card["overdue_days"] = 0

            return cards

        except Exception as e:
            logger.error(f"Error getting due cards: {e}")
            return []

    async def get_review_stats(
        self, user_id: str, project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get spaced repetition statistics."""
        try:
            now = datetime.utcnow().isoformat()

            # Base query
            base_query = (
                self.client.table("review_cards").select("*").eq("user_id", user_id)
            )

            if project_id:
                base_query = base_query.eq("project_id", project_id)

            result = base_query.execute()
            cards = result.data or []

            if not cards:
                return {
                    "total_cards": 0,
                    "due_today": 0,
                    "overdue": 0,
                    "mastered": 0,
                    "learning": 0,
                    "new": 0,
                }

            due_today = 0
            overdue = 0
            mastered = 0  # repetition >= 5 and EF >= 2.0
            learning = 0  # 0 < repetition < 5
            new = 0  # repetition = 0

            now_dt = datetime.utcnow()

            for card in cards:
                try:
                    next_review = datetime.fromisoformat(
                        card["next_review"].replace("Z", "+00:00")
                    ).replace(tzinfo=None)

                    if next_review.date() == now_dt.date():
                        due_today += 1
                    elif next_review < now_dt:
                        overdue += 1
                except:
                    pass

                rep = card.get("repetition", 0)
                ef = card.get("easiness_factor", 2.5)

                if rep == 0:
                    new += 1
                elif rep >= 5 and ef >= 2.0:
                    mastered += 1
                else:
                    learning += 1

            return {
                "total_cards": len(cards),
                "due_today": due_today,
                "overdue": overdue,
                "mastered": mastered,
                "learning": learning,
                "new": new,
            }

        except Exception as e:
            logger.error(f"Error getting review stats: {e}")
            return {}

    async def delete_card(self, card_id: str) -> bool:
        """Delete a review card."""
        try:
            self.client.table("review_cards").delete().eq("id", card_id).execute()
            return True
        except Exception as e:
            logger.error(f"Error deleting card: {e}")
            return False


class LearningService:
    """
    Main Learning Service combining all adaptive learning features.
    """

    def __init__(self):
        self.performance = PerformanceTracker()
        self.weakness = WeaknessDetector()
        self.spaced_rep = SpacedRepetition()

    async def get_learning_dashboard(
        self, user_id: str, project_id: str
    ) -> Dict[str, Any]:
        """
        Get comprehensive learning dashboard data.

        Returns:
        - Performance summary
        - Weak topics
        - Due review cards
        - Review statistics
        """
        try:
            # Get all data in parallel would be ideal, but sync client
            performance = await self.performance.get_performance(user_id, project_id)
            weak_topics = await self.weakness.get_weak_topics(user_id, project_id)
            due_cards = await self.spaced_rep.get_due_cards(
                user_id, project_id, limit=10
            )
            review_stats = await self.spaced_rep.get_review_stats(user_id, project_id)

            # Calculate overall stats
            total_correct = sum(p.get("correct_count", 0) for p in performance)
            total_wrong = sum(p.get("wrong_count", 0) for p in performance)
            total_attempts = total_correct + total_wrong
            overall_accuracy = (
                (total_correct / total_attempts * 100) if total_attempts > 0 else 0
            )

            return {
                "overall": {
                    "total_topics_studied": len(performance),
                    "total_questions_attempted": total_attempts,
                    "overall_accuracy": round(overall_accuracy, 1),
                    "total_correct": total_correct,
                    "total_wrong": total_wrong,
                },
                "weak_topics": weak_topics[:5],  # Top 5 weakest
                "due_cards": due_cards,
                "review_stats": review_stats,
                "performance_by_topic": performance[:10],  # Recent 10
            }

        except Exception as e:
            logger.error(f"Error getting learning dashboard: {e}")
            return {}


# Singleton instances
performance_tracker = PerformanceTracker()
weakness_detector = WeaknessDetector()
spaced_repetition = SpacedRepetition()
learning_service = LearningService()
