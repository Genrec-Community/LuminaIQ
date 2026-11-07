"""
Learner levels and the tools each one gets by default.

Tool keys are the app's tab ids. The platform admin can change any default
(level_tool_policies); institution admins narrow them per class.
"""

from typing import Dict, List

LEVELS: Dict[str, Dict[str, str]] = {
    "school": {"label": "Class 5–10", "short": "School"},
    "higher_secondary": {"label": "Class 11–12", "short": "Higher secondary"},
    "ugpg": {"label": "UG / PG", "short": "College"},
    "research": {"label": "PhD / Research", "short": "Research"},
    "general": {"label": "General learner", "short": "General"},
}

TOOLS: Dict[str, str] = {
    "chat": "Ask (chat with the tutor)",
    "deep": "Deep answers",
    "image": "Photo questions",
    "qa": "Q&A practice (written answers)",
    "quiz": "Quiz",
    "flashcards": "Flashcards",
    "notes": "Notes",
    "mindmap": "Mind map",
    "knowledge": "Knowledge graph",
    "path": "Learning path",
    "cram": "Exam Tonight",
    "power": "Power Hour",
    "lab": "Visual Lab",
    "analytics": "Analytics",
    "pomodoro": "Focus timer",
    "bookstore": "Book store",
    "companion": "AI companion persona",
    "leaderboard": "Class leaderboard",
}

_ALL = list(TOOLS)
_ADVANCED = {"deep", "knowledge", "analytics", "bookstore"}

DEFAULT_TOOLS: Dict[str, List[str]] = {
    "school": [t for t in _ALL if t not in _ADVANCED],
    "higher_secondary": list(_ALL),
    "ugpg": [t for t in _ALL if t != "leaderboard"],
    "research": [t for t in _ALL if t != "leaderboard"],
    "general": [t for t in _ALL if t != "leaderboard"],
}

# Until someone picks a level, they see the general toolset
FALLBACK_LEVEL = "general"

HINT_MODES = ("always_on", "always_off", "student_choice")
