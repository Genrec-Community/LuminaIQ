from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID


# Auth Schemas
class UserSignup(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    full_name: str = Field(..., min_length=1)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class GoogleLoginRequest(BaseModel):
    access_token: str


class UserResponse(BaseModel):
    id: str
    email: str
    created_at: str


# Project Schemas
class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)


class ProjectResponse(BaseModel):
    id: str
    user_id: str
    name: str
    created_at: datetime
    updated_at: datetime


class ProjectList(BaseModel):
    projects: List[ProjectResponse]


# Document Schemas
class DocumentUploadResponse(BaseModel):
    id: str
    project_id: str
    filename: str
    file_type: str
    file_size: int
    upload_status: str
    created_at: Optional[datetime] = None


class DocumentList(BaseModel):
    documents: List[DocumentUploadResponse]


class DocumentStatus(BaseModel):
    id: str
    filename: str
    upload_status: str
    message: Optional[str] = None


# Chat Schemas
class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    project_id: str
    message: str
    selected_documents: Optional[List[str]] = None
    session_history: List[ChatMessage] = []


class SourceInfo(BaseModel):
    doc_id: str
    doc_name: str
    chunk_text: str


class ChatResponse(BaseModel):
    answer: str
    sources: List[SourceInfo]


# Summary Schema (separate from ChatRequest since it doesn't need message)
class SummaryRequest(BaseModel):
    project_id: str
    selected_documents: Optional[List[str]] = None


# MCQ Schemas
class MCQGenerateRequest(BaseModel):
    project_id: str
    topic: Optional[str] = None
    num_questions: int = Field(default=5, ge=1, le=30)
    selected_documents: Optional[List[str]] = None
    difficulty: str = Field(
        default="medium", description="Difficulty level: easy, medium, hard"
    )


class MCQOption(BaseModel):
    option: str
    text: str


class MCQQuestion(BaseModel):
    question: str
    options: List[MCQOption]
    correct_answer: str
    explanation: str


class MCQTestResponse(BaseModel):
    test_id: str
    topic: Optional[str]
    questions: List[MCQQuestion]


class MCQSubmitRequest(BaseModel):
    test_id: str
    answers: Dict[int, str]


class MCQSubmitResponse(BaseModel):
    score: int
    total: int
    percentage: float
    feedback: List[Dict[str, Any]]


# Evaluation Schemas
class EvaluationSubmitRequest(BaseModel):
    project_id: str
    question: str
    user_answer: str


class EvaluationResponse(BaseModel):
    evaluation_id: str
    question: str
    user_answer: str
    score: int
    feedback: str
    suggestions: List[str]
    key_points_covered: List[str]
    key_points_missed: List[str]


class SubjectiveTestGenerateRequest(BaseModel):
    project_id: str
    topic: Optional[str] = None
    num_questions: int = Field(default=3, ge=1, le=30)
    selected_documents: Optional[List[str]] = None
    answer_size: str = Field(
        default="medium", description="Answer size: small, medium, large"
    )


class SubjectiveQuestion(BaseModel):
    id: int
    question: str
    answer: str


class SubjectiveTestResponse(BaseModel):
    test_id: str
    topic: Optional[str]
    questions: List[SubjectiveQuestion]


class SubjectiveTestSubmitRequest(BaseModel):
    test_id: str
    answers: Dict[int, str]


class SubjectiveEvaluationResult(BaseModel):
    question_id: int
    question: str
    user_answer: str
    score: int
    feedback: str
    suggestions: List[str]
    model_answer: Optional[str] = None


class SubjectiveTestResult(BaseModel):
    test_id: str
    total_score: float
    max_score: int
    percentage: float
    evaluations: List[SubjectiveEvaluationResult]


# Notes Schemas
class NoteCreate(BaseModel):
    project_id: str
    content: str


class NoteUpdate(BaseModel):
    content: str


class NoteResponse(BaseModel):
    id: str
    project_id: str
    user_id: str
    content: str
    created_at: datetime
    updated_at: datetime


class NotesGenerateRequest(BaseModel):
    project_id: str
    note_type: str = Field(..., description="Summary, Key Points, Glossary, etc.")
    topic: Optional[str] = None
    selected_documents: Optional[List[str]] = None


class NotesGenerateResponse(BaseModel):
    content: str
