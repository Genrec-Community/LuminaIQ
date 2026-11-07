from fastapi import APIRouter, Depends

from api.access import enforce_resource_access
from api.v1.endpoints import (
    auth,
    books,
    chat,
    memory,
    documents,
    mcq,
    evaluation,
    projects,
    notes,
    webhook,
    learning,
    knowledge_graph,
    user_data,
    flashcards,
    mindmaps,
    progress,
    jobs,
    levels,
    study_modes,
    lessons,
    billing,
    institutions,
    platform,
)

api_router = APIRouter()

# Routers that touch a user's projects or documents: ownership is checked for every request.
# auth, billing, webhook, progress, institutions and platform do their own checks.
_GUARD = [Depends(enforce_resource_access)]

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"], dependencies=_GUARD)
api_router.include_router(documents.router, prefix="/documents", tags=["documents"], dependencies=_GUARD)
api_router.include_router(chat.router, prefix="/chat", tags=["chat"], dependencies=_GUARD)
api_router.include_router(mcq.router, prefix="/mcq", tags=["mcq"], dependencies=_GUARD)
api_router.include_router(evaluation.router, prefix="/evaluation", tags=["evaluation"], dependencies=_GUARD)
api_router.include_router(notes.router, prefix="/notes", tags=["notes"], dependencies=_GUARD)
api_router.include_router(webhook.router, prefix="/webhook", tags=["webhook"])
api_router.include_router(learning.router, prefix="/learning", tags=["learning"], dependencies=_GUARD)
# Plans, usage and payments
api_router.include_router(billing.router, prefix="/billing", tags=["billing"])
api_router.include_router(institutions.router, prefix="/institutions", tags=["institutions"])
# Lumina IQ staff: approve / pause / extend schools
api_router.include_router(platform.router, prefix="/platform", tags=["platform"])
# Exam Tonight (crash mode) + Visual Lab
api_router.include_router(study_modes.router, prefix="/learning", tags=["study-modes"], dependencies=_GUARD)
api_router.include_router(lessons.router, prefix="/learning", tags=["lessons"], dependencies=_GUARD)
api_router.include_router(knowledge_graph.router, prefix="/knowledge-graph", tags=["knowledge-graph"], dependencies=_GUARD)
api_router.include_router(user_data.router, prefix="/user-data", tags=["user-data"], dependencies=_GUARD)
api_router.include_router(memory.router, prefix="/memory", tags=["memory"], dependencies=_GUARD)
api_router.include_router(flashcards.router, prefix="/flashcards", tags=["flashcards"], dependencies=_GUARD)
api_router.include_router(mindmaps.router, prefix="/mindmaps", tags=["mindmaps"], dependencies=_GUARD)
api_router.include_router(progress.router, prefix="/progress", tags=["progress"])

# Book Store
api_router.include_router(books.router, prefix="/books", tags=["books"], dependencies=_GUARD)

# Background jobs for heavy AI tasks
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"], dependencies=_GUARD)
api_router.include_router(levels.router, prefix="/levels", tags=["levels"])
