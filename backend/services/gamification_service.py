"""
Gamification Service — XP, Levels, and Badges system for LuminaIQ.

Required Supabase table:

CREATE TABLE user_gamification (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL UNIQUE,
    total_xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    badges JSONB DEFAULT '[]'::jsonb,
    stats JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_user_gamification_user_id ON user_gamification(user_id);
"""

from typing import Dict, Any, List
from datetime import datetime
from db.client import supabase_client
from utils.logger import logger
from uuid import uuid4
import time


# ======================== Level Definitions ========================
# Progression curve: early levels come fast to hook students,
# later levels require sustained effort.

LEVELS = [
    {"level": 1, "title": "Curious Reader", "xp_required": 0},
    {"level": 2, "title": "Page Turner", "xp_required": 100},
    {"level": 3, "title": "Knowledge Seeker", "xp_required": 250},
    {"level": 4, "title": "Study Warrior", "xp_required": 500},
    {"level": 5, "title": "Quick Learner", "xp_required": 850},
    {"level": 6, "title": "Bookworm", "xp_required": 1300},
    {"level": 7, "title": "Topic Explorer", "xp_required": 1900},
    {"level": 8, "title": "Brain Builder", "xp_required": 2700},
    {"level": 9, "title": "Quiz Champion", "xp_required": 3700},
    {"level": 10, "title": "Knowledge Knight", "xp_required": 5000},
    {"level": 11, "title": "Study Sage", "xp_required": 6800},
    {"level": 12, "title": "Wisdom Keeper", "xp_required": 9000},
    {"level": 13, "title": "Mind Master", "xp_required": 12000},
    {"level": 14, "title": "Grand Scholar", "xp_required": 16000},
    {"level": 15, "title": "Lumina Legend", "xp_required": 21000},
]

# ======================== XP Reward Amounts ========================
# Balanced so a student doing ~30 min of focused study earns ~100-150 XP.
# A typical day of active studying (1-2 hours) should yield ~300-500 XP.
# This means:
#   Level 2 after first session (~20 min)
#   Level 5 after ~3-4 days of regular use
#   Level 10 after ~2-3 weeks of consistent study
#   Level 15 after ~2 months of dedicated use

XP_REWARDS = {
    "chat": 3,              # Very frequent — small reward per message
    "review": 8,            # Per flashcard review session
    "knowledge_graph": 10,  # Exploring knowledge graph
    "notes": 15,            # Generating study notes
    "qa": 15,               # Q&A study session
    "path": 20,             # Learning path activity
    "pomodoro": 25,         # Completing a pomodoro session
    "quiz": 30,             # Base quiz XP (bonuses added for scores)
    "exam": 35,             # Exam prep practice
}

XP_BONUS_PERFECT_QUIZ = 50   # 100% score bonus
XP_BONUS_HIGH_SCORE = 15     # 90%+ score bonus

# ======================== Badge Definitions ========================

BADGE_DEFINITIONS = [
    # Milestone Badges
    {"id": "first_quiz", "title": "First Steps", "description": "Complete your first quiz", "icon": "rocket", "category": "milestone"},
    {"id": "quizzes_10", "title": "Quiz Enthusiast", "description": "Complete 10 quizzes", "icon": "check-circle", "category": "milestone"},
    {"id": "quizzes_50", "title": "Quiz Master", "description": "Complete 50 quizzes", "icon": "award", "category": "milestone"},
    {"id": "questions_100", "title": "Century", "description": "Answer 100 questions", "icon": "target", "category": "milestone"},
    {"id": "questions_500", "title": "Question Conqueror", "description": "Answer 500 questions", "icon": "target", "category": "milestone"},
    {"id": "path_complete", "title": "Path Finder", "description": "Complete a learning path topic", "icon": "map", "category": "milestone"},
    {"id": "paths_10", "title": "Trailblazer", "description": "Complete 10 learning path topics", "icon": "map", "category": "milestone"},

    # Achievement Badges
    {"id": "perfect_score", "title": "Perfectionist", "description": "Score 100% on a quiz", "icon": "star", "category": "achievement"},
    {"id": "quiz_ace_5", "title": "Quiz Ace", "description": "Score 90%+ on 5 quizzes", "icon": "trophy", "category": "achievement"},
    {"id": "quiz_ace_20", "title": "Genius", "description": "Score 90%+ on 20 quizzes", "icon": "trophy", "category": "achievement"},

    # Habit Badges
    {"id": "focus_10", "title": "Focus Master", "description": "Complete 10 Pomodoro sessions", "icon": "timer", "category": "habit"},
    {"id": "focus_50", "title": "Deep Focus", "description": "Complete 50 Pomodoro sessions", "icon": "brain", "category": "habit"},
    {"id": "notes_10", "title": "Note Taker", "description": "Generate 10 sets of notes", "icon": "file-text", "category": "habit"},
    {"id": "notes_50", "title": "Scribe", "description": "Generate 50 sets of notes", "icon": "book-open", "category": "habit"},
    {"id": "reviews_50", "title": "Review Pro", "description": "Review 50 flashcards", "icon": "repeat", "category": "habit"},
    {"id": "reviews_200", "title": "Memory Master", "description": "Review 200 flashcards", "icon": "brain", "category": "habit"},
    {"id": "chats_50", "title": "Curious Mind", "description": "Send 50 chat messages", "icon": "message-square", "category": "habit"},

    # Level Badges
    {"id": "level_5", "title": "Rising Star", "description": "Reach Level 5", "icon": "trending-up", "category": "level"},
    {"id": "level_10", "title": "Elite Learner", "description": "Reach Level 10", "icon": "shield", "category": "level"},
    {"id": "level_15", "title": "Lumina Legend", "description": "Reach max level", "icon": "crown", "category": "level"},

    # XP Badges
    {"id": "xp_1000", "title": "XP Hunter", "description": "Earn 1,000 total XP", "icon": "zap", "category": "xp"},
    {"id": "xp_5000", "title": "XP Warrior", "description": "Earn 5,000 total XP", "icon": "zap", "category": "xp"},
    {"id": "xp_10000", "title": "XP Legend", "description": "Earn 10,000 total XP", "icon": "zap", "category": "xp"},
]

DEFAULT_STATS = {
    "quizzes_completed": 0,
    "perfect_scores": 0,
    "high_scores": 0,
    "questions_answered": 0,
    "reviews_completed": 0,
    "notes_generated": 0,
    "pomodoros_completed": 0,
    "paths_completed": 0,
    "chats_sent": 0,
    "exams_taken": 0,
    "graphs_explored": 0,
    "qa_completed": 0,
}


class GamificationService:
    def __init__(self):
        self.client = supabase_client

    # -------------------- Level Calculation --------------------

    def _calculate_level(self, total_xp: int) -> Dict[str, Any]:
        """Determine current level based on total XP."""
        current_level = LEVELS[0]
        next_level = LEVELS[1] if len(LEVELS) > 1 else None

        for i, lvl in enumerate(LEVELS):
            if total_xp >= lvl["xp_required"]:
                current_level = lvl
                next_level = LEVELS[i + 1] if i + 1 < len(LEVELS) else None
            else:
                break

        if next_level:
            xp_in_level = total_xp - current_level["xp_required"]
            xp_needed = next_level["xp_required"] - current_level["xp_required"]
            progress = round((xp_in_level / xp_needed) * 100, 1) if xp_needed > 0 else 100
        else:
            xp_in_level = 0
            xp_needed = 0
            progress = 100

        return {
            "level": current_level["level"],
            "title": current_level["title"],
            "xp_in_level": xp_in_level,
            "xp_needed": xp_needed,
            "progress": progress,
            "next_level": next_level,
        }

    # -------------------- Badge Checking --------------------

    def _check_new_badges(
        self, stats: Dict, total_xp: int, level: int, existing_badge_ids: List[str]
    ) -> List[Dict]:
        """Check which new badges should be awarded based on current stats."""
        new_badges = []
        existing_set = set(existing_badge_ids)

        badge_conditions = {
            "first_quiz": stats.get("quizzes_completed", 0) >= 1,
            "quizzes_10": stats.get("quizzes_completed", 0) >= 10,
            "quizzes_50": stats.get("quizzes_completed", 0) >= 50,
            "perfect_score": stats.get("perfect_scores", 0) >= 1,
            "quiz_ace_5": stats.get("high_scores", 0) >= 5,
            "quiz_ace_20": stats.get("high_scores", 0) >= 20,
            "questions_100": stats.get("questions_answered", 0) >= 100,
            "questions_500": stats.get("questions_answered", 0) >= 500,
            "focus_10": stats.get("pomodoros_completed", 0) >= 10,
            "focus_50": stats.get("pomodoros_completed", 0) >= 50,
            "notes_10": stats.get("notes_generated", 0) >= 10,
            "notes_50": stats.get("notes_generated", 0) >= 50,
            "path_complete": stats.get("paths_completed", 0) >= 1,
            "paths_10": stats.get("paths_completed", 0) >= 10,
            "reviews_50": stats.get("reviews_completed", 0) >= 50,
            "reviews_200": stats.get("reviews_completed", 0) >= 200,
            "chats_50": stats.get("chats_sent", 0) >= 50,
            "level_5": level >= 5,
            "level_10": level >= 10,
            "level_15": level >= 15,
            "xp_1000": total_xp >= 1000,
            "xp_5000": total_xp >= 5000,
            "xp_10000": total_xp >= 10000,
        }

        for badge_def in BADGE_DEFINITIONS:
            bid = badge_def["id"]
            if bid not in existing_set and badge_conditions.get(bid, False):
                new_badges.append(badge_def)

        return new_badges

    # -------------------- Public API --------------------

    async def get_gamification(self, user_id: str) -> Dict[str, Any]:
        """Get the current gamification state for a user."""
        # Retry up to 2 times on timeout/connection errors
        last_error = None
        for attempt in range(3):
            try:
                result = (
                    self.client.table("user_gamification")
                    .select("*")
                    .eq("user_id", user_id)
                    .execute()
                )

                if result.data:
                    row = result.data[0]
                    total_xp = row.get("total_xp", 0)
                    level_info = self._calculate_level(total_xp)

                    return {
                        "total_xp": total_xp,
                        "level": level_info["level"],
                        "level_title": level_info["title"],
                        "xp_in_level": level_info["xp_in_level"],
                        "xp_needed": level_info["xp_needed"],
                        "level_progress": level_info["progress"],
                        "next_level": level_info["next_level"],
                        "badges": row.get("badges", []),
                        "stats": row.get("stats", {}),
                        "all_levels": LEVELS,
                        "all_badges": BADGE_DEFINITIONS,
                    }
                else:
                    # Create initial record
                    record = {
                        "id": str(uuid4()),
                        "user_id": user_id,
                        "total_xp": 0,
                        "level": 1,
                        "badges": [],
                        "stats": DEFAULT_STATS.copy(),
                    }
                    self.client.table("user_gamification").insert(record).execute()

                    level_info = self._calculate_level(0)
                    return {
                        "total_xp": 0,
                        "level": 1,
                        "level_title": "Curious Reader",
                        "xp_in_level": 0,
                        "xp_needed": level_info["xp_needed"],
                        "level_progress": 0,
                        "next_level": level_info["next_level"],
                        "badges": [],
                        "stats": DEFAULT_STATS.copy(),
                        "all_levels": LEVELS,
                        "all_badges": BADGE_DEFINITIONS,
                    }
            except Exception as e:
                last_error = e
                if attempt < 2:
                    wait = 1.5 * (attempt + 1)
                    logger.warning(f"Gamification query attempt {attempt+1} failed ({e}), retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    logger.error(f"Error getting gamification after 3 attempts: {e}")

        return self._default_response()

    async def award_xp(
        self, user_id: str, activity_type: str, meta: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Award XP for an activity and check for new badges / level-ups."""
        try:
            meta = meta or {}

            # Calculate XP amount
            base_xp = XP_REWARDS.get(activity_type, 3)
            bonus_xp = 0

            if activity_type == "quiz":
                score = meta.get("score", 0)
                num_q = meta.get("num_questions", 0)

                # Scale base XP by number of questions (more questions = more effort)
                if num_q > 0:
                    question_bonus = min(num_q, 20) * 2  # 2 XP per question, cap at 20
                    bonus_xp += question_bonus

                # Score-based bonus (0-100 score -> 0-20 bonus)
                bonus_xp += int(score * 0.2)

                # Achievement bonuses
                if score == 100:
                    bonus_xp += XP_BONUS_PERFECT_QUIZ
                elif score >= 90:
                    bonus_xp += XP_BONUS_HIGH_SCORE

            total_earned = base_xp + bonus_xp

            # Get current state
            result = (
                self.client.table("user_gamification")
                .select("*")
                .eq("user_id", user_id)
                .execute()
            )

            if not result.data:
                await self.get_gamification(user_id)
                result = (
                    self.client.table("user_gamification")
                    .select("*")
                    .eq("user_id", user_id)
                    .execute()
                )

            row = result.data[0]
            old_xp = row.get("total_xp", 0)
            old_level = self._calculate_level(old_xp)["level"]
            stats = row.get("stats") or DEFAULT_STATS.copy()
            existing_badge_ids = [b["id"] for b in (row.get("badges") or [])]

            # Update stats counters
            stat_mapping = {
                "quiz": "quizzes_completed",
                "review": "reviews_completed",
                "notes": "notes_generated",
                "qa": "qa_completed",
                "chat": "chats_sent",
                "pomodoro": "pomodoros_completed",
                "path": "paths_completed",
                "exam": "exams_taken",
                "knowledge_graph": "graphs_explored",
            }

            stat_key = stat_mapping.get(activity_type)
            if stat_key:
                stats[stat_key] = stats.get(stat_key, 0) + 1

            # Quiz-specific stat updates
            if activity_type == "quiz":
                num_q = meta.get("num_questions", 0)
                stats["questions_answered"] = stats.get("questions_answered", 0) + num_q
                score = meta.get("score", 0)
                if score == 100:
                    stats["perfect_scores"] = stats.get("perfect_scores", 0) + 1
                if score >= 90:
                    stats["high_scores"] = stats.get("high_scores", 0) + 1

            # New XP and level
            new_xp = old_xp + total_earned
            new_level_info = self._calculate_level(new_xp)
            new_level = new_level_info["level"]
            leveled_up = new_level > old_level

            # Check for new badges
            new_badges = self._check_new_badges(stats, new_xp, new_level, existing_badge_ids)

            # Merge new badges
            all_badges = (row.get("badges") or []) + [
                {**b, "earned_at": datetime.utcnow().isoformat()}
                for b in new_badges
            ]

            # Persist
            update = {
                "total_xp": new_xp,
                "level": new_level,
                "badges": all_badges,
                "stats": stats,
                "updated_at": datetime.utcnow().isoformat(),
            }
            self.client.table("user_gamification").update(update).eq(
                "id", row["id"]
            ).execute()

            return {
                "xp_earned": total_earned,
                "total_xp": new_xp,
                "level": new_level,
                "level_title": new_level_info["title"],
                "level_progress": new_level_info["progress"],
                "xp_in_level": new_level_info["xp_in_level"],
                "xp_needed": new_level_info["xp_needed"],
                "next_level": new_level_info["next_level"],
                "leveled_up": leveled_up,
                "old_level": old_level,
                "new_badges": new_badges,
                "stats": stats,
            }

        except Exception as e:
            logger.error(f"Error awarding XP: {e}")
            # Return error flag but do NOT set fake totals — the frontend
            # checks for .error and ignores the response.
            return {
                "xp_earned": 0,
                "leveled_up": False,
                "new_badges": [],
                "error": str(e),
            }

    def _default_response(self) -> Dict[str, Any]:
        level_info = self._calculate_level(0)
        return {
            "total_xp": 0,
            "level": 1,
            "level_title": "Curious Reader",
            "xp_in_level": 0,
            "xp_needed": level_info["xp_needed"],
            "level_progress": 0,
            "next_level": level_info["next_level"],
            "badges": [],
            "stats": DEFAULT_STATS.copy(),
            "all_levels": LEVELS,
            "all_badges": BADGE_DEFINITIONS,
        }


# Singleton
gamification = GamificationService()
