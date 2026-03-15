"""
User Data Service — CRUD for all user-facing data previously in localStorage.

Tables managed:
  1. user_settings
  2. bookmarks
  3. study_activity
  4. exam_schedules
  5. learning_progress
  6. pomodoro_sessions
  7. recent_searches
  8. study_streaks
"""

from typing import List, Dict, Any, Optional
from datetime import date, datetime, timedelta
from db.client import get_supabase_client
from utils.logger import logger
from uuid import uuid4


class UserDataService:
    def __init__(self):
        self.client = get_supabase_client()

    # ===================== 1. User Settings =====================

    async def get_settings(self, user_id: str) -> Dict[str, Any]:
        """Get user settings, returning defaults if none exist."""
        try:
            result = (
                self.client.table("user_settings")
                .select("settings, updated_at")
                .eq("user_id", user_id)
                .execute()
            )
            if result.data:
                return result.data[0]["settings"]
            return self._default_settings()
        except Exception as e:
            logger.error(f"Error getting settings: {e}")
            return self._default_settings()

    async def save_settings(self, user_id: str, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Upsert user settings."""
        try:
            result = self.client.table("user_settings").upsert(
                {
                    "user_id": user_id,
                    "settings": settings,
                    "updated_at": datetime.utcnow().isoformat(),
                },
                on_conflict="user_id",
            ).execute()
            return result.data[0]["settings"] if result.data else settings
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            return settings

    def _default_settings(self) -> Dict[str, Any]:
        return {
            "bookIsolation": False,
            "darkMode": False,
            "pomodoroWork": 25,
            "pomodoroBreak": 5,
            "pomodoroLongBreak": 15,
            "pomodoroAutoStart": False,
            "studyReminders": False,
            "reminderTime": "09:00",
            "soundEnabled": True,
            "showStreaks": True,
            "compactMode": False,
            "tutorStyle": "balanced",
            "quizDifficulty": "medium",
        }

    # ===================== 2. Bookmarks =====================

    async def get_bookmarks(self, user_id: str, project_id: str) -> List[Dict[str, Any]]:
        try:
            result = (
                self.client.table("bookmarks")
                .select("*")
                .eq("user_id", user_id)
                .eq("project_id", project_id)
                .order("created_at", desc=True)
                .execute()
            )
            return result.data or []
        except Exception as e:
            logger.error(f"Error getting bookmarks: {e}")
            return []

    async def add_bookmark(
        self, user_id: str, project_id: str, title: str,
        note: str = "", document_id: str = None, bookmark_type: str = "general",
        highlight_text: str = None, color: str = None
    ) -> Dict[str, Any]:
        try:
            record = {
                "id": str(uuid4()),
                "user_id": user_id,
                "project_id": project_id,
                "title": title,
                "note": note,
                "document_id": document_id,
                "type": bookmark_type,
            }
            if highlight_text is not None:
                record["highlight_text"] = highlight_text
            if color is not None:
                record["color"] = color
            result = self.client.table("bookmarks").insert(record).execute()
            return result.data[0] if result.data else record
        except Exception as e:
            logger.error(f"Error adding bookmark: {e}")
            return {}

    async def update_bookmark(self, user_id: str, bookmark_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        try:
            allowed = {"title", "note", "type", "highlight_text", "color"}
            filtered = {k: v for k, v in updates.items() if k in allowed}
            result = (
                self.client.table("bookmarks")
                .update(filtered)
                .eq("id", bookmark_id)
                .eq("user_id", user_id)
                .execute()
            )
            return result.data[0] if result.data else {}
        except Exception as e:
            logger.error(f"Error updating bookmark: {e}")
            return {}

    async def delete_bookmark(self, user_id: str, bookmark_id: str) -> bool:
        try:
            self.client.table("bookmarks").delete().eq("id", bookmark_id).eq("user_id", user_id).execute()
            return True
        except Exception as e:
            logger.error(f"Error deleting bookmark: {e}")
            return False

    # ===================== 3. Study Activity =====================

    async def get_study_activity(
        self, user_id: str, project_id: str, days: int = 90
    ) -> Dict[str, Any]:
        """Return activity keyed by date string (same shape as old localStorage)."""
        try:
            result = (
                self.client.table("study_activity")
                .select("*")
                .eq("user_id", user_id)
                .eq("project_id", project_id)
                .order("activity_date", desc=True)
                .limit(days)
                .execute()
            )
            activity = {}
            for row in result.data or []:
                date_str = row["activity_date"]
                activity[date_str] = {
                    "quiz": row["quiz"],
                    "review": row["review"],
                    "notes": row["notes"],
                    "qa": row["qa"],
                    "pomodoro": row["pomodoro"],
                    "chat": row["chat"],
                    "quizScores": row.get("quiz_scores", []),
                    "total": row["total"],
                }
            return activity
        except Exception as e:
            logger.error(f"Error getting study activity: {e}")
            return {}

    async def record_study_activity(
        self, user_id: str, project_id: str,
        activity_type: str, meta: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Increment a single activity counter for today, upsert."""
        try:
            today = date.today().isoformat()
            meta = meta or {}

            # Get existing row for today
            existing = (
                self.client.table("study_activity")
                .select("*")
                .eq("user_id", user_id)
                .eq("project_id", project_id)
                .eq("activity_date", today)
                .execute()
            )

            if existing.data:
                row = existing.data[0]
                # Increment the counter
                if activity_type in ("quiz", "review", "notes", "qa", "pomodoro", "chat", "exam", "path", "knowledge_graph"):
                    row[activity_type] = (row.get(activity_type) or 0) + 1

                # Append quiz score
                quiz_scores = row.get("quiz_scores") or []
                if activity_type == "quiz" and "score" in meta:
                    quiz_scores.append(meta["score"])

                total = sum(row.get(k, 0) for k in ("quiz", "review", "notes", "qa", "pomodoro", "chat", "exam", "path", "knowledge_graph"))

                update = {
                    activity_type: row[activity_type],
                    "quiz_scores": quiz_scores,
                    "total": total,
                }

                result = (
                    self.client.table("study_activity")
                    .update(update)
                    .eq("id", row["id"])
                    .execute()
                )
                return result.data[0] if result.data else {}
            else:
                # Create new row
                new_row = {
                    "id": str(uuid4()),
                    "user_id": user_id,
                    "project_id": project_id,
                    "activity_date": today,
                    "quiz": 0, "review": 0, "notes": 0,
                    "qa": 0, "pomodoro": 0, "chat": 0,
                    "exam": 0, "path": 0, "knowledge_graph": 0,
                    "quiz_scores": [],
                    "total": 0,
                }
                if activity_type in new_row:
                    new_row[activity_type] = 1
                if activity_type == "quiz" and "score" in meta:
                    new_row["quiz_scores"] = [meta["score"]]
                new_row["total"] = 1

                result = self.client.table("study_activity").insert(new_row).execute()
                return result.data[0] if result.data else {}

        except Exception as e:
            logger.error(f"Error recording study activity: {e}")
            return {}

    # ===================== 4. Exam Schedules =====================

    async def get_exams(self, user_id: str, project_id: str) -> List[Dict[str, Any]]:
        try:
            result = (
                self.client.table("exam_schedules")
                .select("*")
                .eq("user_id", user_id)
                .eq("project_id", project_id)
                .order("exam_date", desc=False)
                .execute()
            )
            return result.data or []
        except Exception as e:
            logger.error(f"Error getting exams: {e}")
            return []

    async def save_exam(
        self, user_id: str, project_id: str,
        name: str, exam_date: str, topics: List[str] = None,
        difficulty: str = "medium"
    ) -> Dict[str, Any]:
        try:
            record = {
                "id": str(uuid4()),
                "user_id": user_id,
                "project_id": project_id,
                "name": name,
                "exam_date": exam_date,
                "topics": topics or [],
                "difficulty": difficulty,
            }
            result = self.client.table("exam_schedules").insert(record).execute()
            return result.data[0] if result.data else record
        except Exception as e:
            logger.error(f"Error saving exam: {e}")
            return {}

    async def delete_exam(self, user_id: str, exam_id: str) -> bool:
        try:
            self.client.table("exam_schedules").delete().eq("id", exam_id).eq("user_id", user_id).execute()
            return True
        except Exception as e:
            logger.error(f"Error deleting exam: {e}")
            return False

    # ===================== 5. Learning Progress =====================

    async def get_learning_progress(self, user_id: str, project_id: str) -> List[str]:
        """Return list of completed topic strings."""
        try:
            result = (
                self.client.table("learning_progress")
                .select("completed_topics")
                .eq("user_id", user_id)
                .eq("project_id", project_id)
                .execute()
            )
            if result.data:
                return result.data[0].get("completed_topics") or []
            return []
        except Exception as e:
            logger.error(f"Error getting learning progress: {e}")
            return []

    async def save_learning_progress(
        self, user_id: str, project_id: str, completed_topics: List[str]
    ) -> List[str]:
        try:
            result = self.client.table("learning_progress").upsert(
                {
                    "user_id": user_id,
                    "project_id": project_id,
                    "completed_topics": completed_topics,
                    "updated_at": datetime.utcnow().isoformat(),
                },
                on_conflict="user_id,project_id",
            ).execute()
            if result.data:
                return result.data[0].get("completed_topics", [])
            return completed_topics
        except Exception as e:
            logger.error(f"Error saving learning progress: {e}")
            return completed_topics

    # ===================== 6. Pomodoro Sessions =====================

    async def get_pomodoro(
        self, user_id: str, project_id: str = None, document_id: str = None
    ) -> Dict[str, Any]:
        """Get today's pomodoro data for a document or global."""
        try:
            today = date.today().isoformat()
            query = (
                self.client.table("pomodoro_sessions")
                .select("*")
                .eq("user_id", user_id)
                .eq("session_date", today)
            )
            if document_id:
                query = query.eq("document_id", document_id)
            else:
                query = query.is_("document_id", "null")

            if project_id:
                query = query.eq("project_id", project_id)

            result = query.execute()
            if result.data:
                row = result.data[0]
                return {
                    "sessions": row["sessions"],
                    "focusTime": row["focus_time_minutes"],
                    "date": row["session_date"],
                }
            return {"sessions": 0, "focusTime": 0, "date": today}
        except Exception as e:
            logger.error(f"Error getting pomodoro: {e}")
            return {"sessions": 0, "focusTime": 0, "date": date.today().isoformat()}

    async def save_pomodoro(
        self, user_id: str, sessions: int, focus_time_minutes: int,
        project_id: str = None, document_id: str = None
    ) -> Dict[str, Any]:
        try:
            today = date.today().isoformat()

            # Check existing
            query = (
                self.client.table("pomodoro_sessions")
                .select("id")
                .eq("user_id", user_id)
                .eq("session_date", today)
            )
            if document_id:
                query = query.eq("document_id", document_id)
            else:
                query = query.is_("document_id", "null")

            existing = query.execute()

            if existing.data:
                result = (
                    self.client.table("pomodoro_sessions")
                    .update({
                        "sessions": sessions,
                        "focus_time_minutes": focus_time_minutes,
                        "updated_at": datetime.utcnow().isoformat(),
                    })
                    .eq("id", existing.data[0]["id"])
                    .execute()
                )
            else:
                result = self.client.table("pomodoro_sessions").insert({
                    "id": str(uuid4()),
                    "user_id": user_id,
                    "project_id": project_id,
                    "document_id": document_id,
                    "session_date": today,
                    "sessions": sessions,
                    "focus_time_minutes": focus_time_minutes,
                }).execute()

            return result.data[0] if result.data else {}
        except Exception as e:
            logger.error(f"Error saving pomodoro: {e}")
            return {}

    # ===================== 7. Recent Searches =====================

    async def get_recent_searches(self, user_id: str, project_id: str, limit: int = 5) -> List[str]:
        try:
            result = (
                self.client.table("recent_searches")
                .select("query")
                .eq("user_id", user_id)
                .eq("project_id", project_id)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            return [row["query"] for row in (result.data or [])]
        except Exception as e:
            logger.error(f"Error getting recent searches: {e}")
            return []

    async def save_recent_search(self, user_id: str, project_id: str, query: str) -> bool:
        try:
            # Delete existing duplicate
            self.client.table("recent_searches").delete().eq(
                "user_id", user_id
            ).eq("project_id", project_id).eq("query", query).execute()

            # Insert new
            self.client.table("recent_searches").insert({
                "id": str(uuid4()),
                "user_id": user_id,
                "project_id": project_id,
                "query": query,
            }).execute()

            # Prune to 5 most recent
            all_searches = (
                self.client.table("recent_searches")
                .select("id")
                .eq("user_id", user_id)
                .eq("project_id", project_id)
                .order("created_at", desc=True)
                .execute()
            )
            if all_searches.data and len(all_searches.data) > 5:
                ids_to_delete = [r["id"] for r in all_searches.data[5:]]
                for old_id in ids_to_delete:
                    self.client.table("recent_searches").delete().eq("id", old_id).execute()

            return True
        except Exception as e:
            logger.error(f"Error saving recent search: {e}")
            return False

    async def clear_recent_searches(self, user_id: str, project_id: str) -> bool:
        try:
            self.client.table("recent_searches").delete().eq(
                "user_id", user_id
            ).eq("project_id", project_id).execute()
            return True
        except Exception as e:
            logger.error(f"Error clearing recent searches: {e}")
            return False

    # ===================== 8. Study Streaks =====================

    async def get_streak(self, user_id: str, project_id: str) -> Dict[str, Any]:
        try:
            result = (
                self.client.table("study_streaks")
                .select("*")
                .eq("user_id", user_id)
                .eq("project_id", project_id)
                .execute()
            )
            if result.data:
                row = result.data[0]
                return {
                    "current": row["current_streak"],
                    "longest": row["longest_streak"],
                    "lastStudyDate": row.get("last_study_date"),
                }
            return {"current": 0, "longest": 0, "lastStudyDate": None}
        except Exception as e:
            logger.error(f"Error getting streak: {e}")
            return {"current": 0, "longest": 0, "lastStudyDate": None}

    async def update_streak(self, user_id: str, project_id: str) -> Dict[str, Any]:
        """Call this whenever the user studies. Auto-updates streak logic."""
        try:
            today = date.today().isoformat()
            existing = (
                self.client.table("study_streaks")
                .select("*")
                .eq("user_id", user_id)
                .eq("project_id", project_id)
                .execute()
            )

            if existing.data:
                row = existing.data[0]
                last_date = row.get("last_study_date")
                current = row.get("current_streak", 0)
                longest = row.get("longest_streak", 0)

                if last_date == today:
                    # Already studied today
                    return {"current": current, "longest": longest, "lastStudyDate": today}

                yesterday = (date.today() - timedelta(days=1)).isoformat()
                if last_date == yesterday:
                    current += 1
                else:
                    current = 1

                longest = max(longest, current)

                self.client.table("study_streaks").update({
                    "current_streak": current,
                    "longest_streak": longest,
                    "last_study_date": today,
                    "updated_at": datetime.utcnow().isoformat(),
                }).eq("id", row["id"]).execute()

                return {"current": current, "longest": longest, "lastStudyDate": today}
            else:
                self.client.table("study_streaks").insert({
                    "id": str(uuid4()),
                    "user_id": user_id,
                    "project_id": project_id,
                    "current_streak": 1,
                    "longest_streak": 1,
                    "last_study_date": today,
                }).execute()
                return {"current": 1, "longest": 1, "lastStudyDate": today}

        except Exception as e:
            logger.error(f"Error updating streak: {e}")
            return {"current": 0, "longest": 0, "lastStudyDate": None}


# Singleton
user_data = UserDataService()
