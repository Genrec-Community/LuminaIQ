from fastapi import APIRouter
from api.v1.endpoints import (
    auth,
    chat,
    documents,
    mcq,
    evaluation,
    projects,
    notes,
    webhook,
    learning,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(mcq.router, prefix="/mcq", tags=["mcq"])
api_router.include_router(evaluation.router, prefix="/evaluation", tags=["evaluation"])
api_router.include_router(notes.router, prefix="/notes", tags=["notes"])
api_router.include_router(webhook.router, prefix="/webhook", tags=["webhook"])
api_router.include_router(learning.router, prefix="/learning", tags=["learning"])
